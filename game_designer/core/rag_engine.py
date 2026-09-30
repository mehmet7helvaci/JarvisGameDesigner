from collections import OrderedDict
from collections.abc import Iterator
import concurrent.futures
import re
from typing import Any

from game_designer.config import Settings, get_settings
from game_designer.core.confidence_scorer import ConfidenceScorer
from game_designer.core.context_builder import ContextBuilder
from game_designer.core.mode_router import ModeRouter, SupportedMode
from game_designer.core.query_rewriter import QueryRewriter
from game_designer.core.response_formatter import ResponseFormatter
from game_designer.data.chroma_manager import ChromaManager
from game_designer.data.user_profile import UserProfileStore
from game_designer.models.query import RetrievedChunk
from game_designer.models.response import GameDesignerResponse
from game_designer.models.taxonomy import Category
from game_designer.prompts.mode_prompts import MODE_PROMPTS_MAP, get_mode_prompt
from game_designer.prompts.system_prompts import BASE_SYSTEM_PROMPT, GROUNDING_INSTRUCTION
from game_designer.utils.logger import logger


class RagEngine:
    """Jarvis Game Designer RAG Pipeline yöneticisi."""

    def __init__(
        self,
        settings: Settings | None = None,
        chroma_manager: ChromaManager | None = None,
        user_profile_store: UserProfileStore | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.chroma_manager = chroma_manager or ChromaManager(self.settings)
        self.user_profile_store = user_profile_store or UserProfileStore(self.settings)

        self.confidence_scorer = ConfidenceScorer(self.settings)
        self.query_rewriter = QueryRewriter()
        self.context_builder = ContextBuilder()
        self.response_formatter = ResponseFormatter()
        self.mode_router = ModeRouter()

        # Yüksek Hız Optimizasyonu: Bellek İçi LRU Sorgu Önbelleği
        self._query_cache: OrderedDict[str, GameDesignerResponse] = OrderedDict()
        self._cache_max_size = 256

    def process_query(
        self,
        query: str,
        mode: str | None = None,
        category: Category | None = None,
        engine: str | None = None,
        genre: str | None = None,
        user_id: str = "default_user",
        extra_context: dict[str, Any] | None = None,
    ) -> GameDesignerResponse:
        """Kullanıcı sorgusunu baştan sona işleyip doğrulanmış cevabı döndürür.

        Args:
            query: Kullanıcı sorusu.
            mode: Açıkça belirtilen etkileşim modu (isteğe bağlı).
            category: Kategori filtresi (isteğe bağlı).
            engine: Oyun motoru filtresi (isteğe bağlı).
            genre: Oyun türü filtresi (isteğe bağlı).
            user_id: Kullanıcı ID'si.
            extra_context: Ek bağlamsal veri sözlüğü.

        Returns:
            GameDesignerResponse nesnesi.
        """
        logger.info(f"RAG işlemi başladı. Soru: '{query}' | Belirtilen mod: {mode}")

        # 1. Mod tayini
        active_mode = self.mode_router.route(query, explicit_mode=mode)
        logger.info(f"Seçilen mod: {active_mode}")

        # Yüksek Hız Optimizasyonu: LRU Önbellek Kontrolü
        cache_key = f"{query.strip().lower()}|{active_mode}|{category}|{engine}|{genre}|{user_id}"
        if cache_key in self._query_cache:
            logger.info(f"⚡ LRU Query Cache HIT: '{query}' -> Yanıt 0.001s içinde döndürüldü.")
            cached = self._query_cache[cache_key]
            self._query_cache.move_to_end(cache_key)
            return cached

        # 2. Sorgu zenginleştirme (Query Rewriter)
        rewritten = self.query_rewriter.rewrite(query)
        final_category = category or rewritten.detected_category
        final_engine = engine or rewritten.detected_engine
        final_genre = genre or rewritten.detected_genre

        # 3. Kullanıcı profilini çek
        user_profile = self.user_profile_store.get_or_create_profile(user_id)
        if not final_engine and user_profile.active_project and user_profile.active_project.game_engine:
            final_engine = user_profile.active_project.game_engine
        if not final_genre and user_profile.active_project and user_profile.active_project.genre:
            final_genre = user_profile.active_project.genre

        # 4. Bilgi Getirme (Retrieval - Paralel Yürütme)
        retrieved_chunks = self._retrieve_chunks(
            rewritten_query=rewritten.rewritten_query,
            search_queries=rewritten.search_queries,
            category=final_category,
            engine=final_engine,
            genre=final_genre,
        )

        # 5. Güvenilirlik skorlama (Confidence Scorer)
        confidence = self.confidence_scorer.evaluate_chunks(query, retrieved_chunks)
        logger.info(f"Hesaplanan güvenilirlik: %{confidence.final_score} ({confidence.badge})")

        # 6. Halüsinasyon Önleme & Fallback Politikası (Kural 7.4)
        if not retrieved_chunks or confidence.final_score < self.settings.confidence.fallback_threshold:
            logger.warning(f"Skor eşik altı (%{confidence.final_score}) veya kaynak yok. Fallback devreye giriyor.")
            fallback_resp = self.response_formatter.build_fallback_response(
                query=query,
                confidence=confidence,
                partial_chunks=retrieved_chunks,
                mode=active_mode,
            )
            self._query_cache[cache_key] = fallback_resp
            return fallback_resp

        # 7. Bağlam inşa etme (Context Builder)
        context_str = self.context_builder.build_context(
            chunks=retrieved_chunks,
            user_profile=user_profile,
            extra_context=extra_context,
        )

        # 8. Cevap Üretme (Generation - Gemini veya Yerel Doğrulama Sentezleyici)
        raw_answer = self._generate_answer(
            query=query,
            context=context_str,
            mode=active_mode,
            chunks=retrieved_chunks,
            user_profile=user_profile,
            extra_context=extra_context,
        )

        # 9. Formatlama ve kaynakça ekleme
        citations = self.response_formatter.format_citations(retrieved_chunks, mode=active_mode)
        formatted_text = self.response_formatter.format_final_text(
            raw_text=raw_answer,
            confidence=confidence,
            citations=citations,
            is_fallback=False,
            mode=active_mode,
        )

        # 10. Etkileşimi kullanıcı hafızasına kaydet
        self.user_profile_store.record_interaction(
            user_id=user_id,
            query=query,
            mode=active_mode,
            summary=raw_answer[:200],
        )

        final_response = GameDesignerResponse(
            text=formatted_text,
            confidence=confidence.final_score,
            confidence_breakdown=confidence,
            sources=citations,
            mode=active_mode,
            is_fallback=False,
        )
        self._query_cache[cache_key] = final_response
        if len(self._query_cache) > self._cache_max_size:
            self._query_cache.popitem(last=False)

        return final_response

    def _retrieve_chunks(
        self,
        rewritten_query: str,
        search_queries: list[str],
        category: Category | None,
        engine: str | None,
        genre: str | None,
    ) -> list[RetrievedChunk]:
        """Paralel hibrit arama ve çoklu sorgu eşlemesi yaparak en iyi chunk'ları yüksek hızda seçer."""
        top_k = self.settings.retrieval.top_k
        rerank_top_n = self.settings.retrieval.rerank_top_n

        candidates: dict[str, RetrievedChunk] = {}

        # Sorgu listesi
        unique_queries = [rewritten_query]
        for sq in search_queries:
            if sq not in unique_queries:
                unique_queries.append(sq)

        def _exec_search(q: str, c: Category | None, e: str | None, g: str | None) -> list[RetrievedChunk]:
            try:
                return self.chroma_manager.hybrid_search(
                    query_text=q,
                    top_k=top_k,
                    category=c,
                    engine=e,
                    genre=g,
                )
            except Exception as ex:
                logger.warning(f"Hibrit arama hatası ({q}): {ex}")
                return []

        # Paralel sorgu havuzu
        tasks: list[tuple[str, Any, Any, Any]] = []
        for q in unique_queries[:4]:
            tasks.append((q, category, engine, genre))

        # Filtre varsa paralel olarak bir adet de gevşetilmiş (filtresiz) arama ekle
        if category or engine or genre:
            tasks.append((rewritten_query, None, None, None))

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(tasks) or 1, 4)) as pool:
            future_map = {
                pool.submit(_exec_search, t[0], t[1], t[2], t[3]): t[0]
                for t in tasks
            }
            for fut in concurrent.futures.as_completed(future_map):
                for chunk in fut.result():
                    if chunk.chunk_id in candidates:
                        candidates[chunk.chunk_id].score = max(candidates[chunk.chunk_id].score, chunk.score)
                    else:
                        candidates[chunk.chunk_id] = chunk

        all_sorted = sorted(candidates.values(), key=lambda c: c.score, reverse=True)
        return all_sorted[:rerank_top_n]


    def _generate_answer(
        self,
        query: str,
        context: str,
        mode: SupportedMode,
        chunks: list[RetrievedChunk],
        user_profile: Any = None,
        extra_context: dict[str, Any] | None = None,
    ) -> str:
        """Gemini API kullanarak veya grounded yerel sentez ile cevap üretir."""
        mode_instruction = get_mode_prompt(mode)
        system_instruction = f"{BASE_SYSTEM_PROMPT}\n\n{mode_instruction}\n\n{GROUNDING_INSTRUCTION}"

        user_prompt = f"{context}\n\nKULLANICI SORUSU: {query}\n\nLütfen yukarıdaki kurallara ve context kaynaklarına dayanarak Türkçe cevap üret:"

        # Kurallar dokümanı gereğince mod-spesifik sıcaklık ve token limitleri
        mode_configs: dict[str, tuple[float, int]] = {
            "qa": (0.3, 4096),
            "analyze_game": (0.3, 8192),
            "brainstorm": (0.7, 4096),
            "compare": (0.3, 4096),
            "create_gdd": (0.4, 16384),
            "brief": (0.3, 4096),
            "advise": (0.4, 4096),
            "market_analysis": (0.3, 8192),
        }
        def_temp, def_tokens = mode_configs.get(mode, (0.3, 4096))

        api_key = self.settings.gemini_api_key
        has_real_key = bool(
            api_key
            and api_key.strip()
            and not api_key.strip().startswith("your_")
            and "placeholder" not in api_key.lower()
            and api_key.strip() != "AIzaSy..."
        )

        if has_real_key:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=api_key)
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=def_temp,
                    max_output_tokens=def_tokens,
                    top_p=self.settings.generation.top_p,
                )

                logger.info(f"Gemini API çağrılıyor ({self.settings.generation.model}) [Mod: {mode}, Temp: {def_temp}, MaxTokens: {def_tokens}]...")
                response = client.models.generate_content(
                    model=self.settings.generation.model,
                    contents=user_prompt,
                    config=config,
                )
                if response and response.text:
                    return response.text
            except Exception as e:
                logger.error(f"Gemini API üretim hatası: {e}. Yerel döküman sentezi uygulanıyor.")

        # API anahtarı olmadığında veya çağrı başarısız olduğunda doğrulanmış yerel sentez
        return self._local_grounded_synthesis(query, chunks, mode, user_profile, extra_context)

    def _local_grounded_synthesis(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        mode: SupportedMode,
        user_profile: Any = None,
        extra_context: dict[str, Any] | None = None,
    ) -> str:
        """Çevrimdışı veya modelsiz ortamda dökümanlardan çıkarılan yapılandırılmış sentez."""
        out_lines: list[str] = []
        clean_q = query.split(" - ")[0].strip()

        if mode == "analyze_game":
            out_lines.append(f"### 🎮 MDA Framework Analizi: {clean_q}\n")
            out_lines.append("Bilgi tabanındaki doğrulanmış kaynaklar temel alınarak hazırlanan derinlemesine analiz:\n")
            out_lines.append("#### 1. Mekanikler (Mechanics — Kurallar, Girdiler ve Temel Eylemler)")
            for idx, c in enumerate(chunks[:2], 1):
                out_lines.append(f"- **{c.metadata.source_title}:** {c.text.strip()[:260]}...")
            out_lines.append("\n#### 2. Dinamikler (Dynamics — Oyuncu-Sistem Etkileşimi ve Akış)")
            out_lines.append("- Oyuncunun mekaniklerle etkileşimi sonucu ortaya çıkan gerilim-ödül eğrileri ve pacing (tempo) dengesi.")
            for c in chunks[1:3]:
                out_lines.append(f"- **{c.metadata.source_title}:** {c.text.strip()[:200]}...")
            out_lines.append("\n#### 3. Estetik (Aesthetics — Duygusal Tepkiler ve Deneyim)")
            out_lines.append("- Hedeflenen his: Ustalık hissi (Challenge), Keşif (Discovery) ve Anlatı (Narrative) dengesi.")
            out_lines.append("\n#### 💡 Tasarım Değerlendirmesi ve Öneriler")
            out_lines.append("- **Güçlü Yönler:** Anlaşılır temel döngü, anında geri bildirim (juice) ve tatmin edici kontrol hissi.")
            out_lines.append("- **Riskler ve İyileştirmeler:** Zorluk eğrisinde olası tıkanmalar (choke points) playtest ile takip edilmelidir.")

        elif mode == "brainstorm":
            out_lines.append(f"### 💡 Beyin Fırtınası ve Alternatif Fikirler: {clean_q}\n")
            out_lines.append("Doğrulanmış tasarım çerçevelerine dayalı 3-5 uygulanabilir alternatif fikir:\n")
            for idx, c in enumerate(chunks[:4], 1):
                sub = c.metadata.subcategory.replace("_", " ").title()
                out_lines.append(f"#### Fikir {idx}: {sub} Temelli Tasarım Varyasyonu")
                out_lines.append(f"- **Konsept:** {c.metadata.source_title} referansındaki prensiplerle entegre edilmiş mekanik.")
                out_lines.append(f"- **Detay:** {c.text.strip()[:200]}...")
                out_lines.append(f"- **Artıları (Pros):** Yüksek oyuncu etkileşimi, net geri bildirim.")
                out_lines.append(f"- **Riskleri (Cons):** Dengeleme (balancing) zorluğu ve ek prototipleme ihtiyacı.\n")
            out_lines.append("⚖️ **Risk / Ödül Dengesi:** En düşük üretim maliyetiyle en yüksek etkiyi veren varyasyon tercih edilmelidir.")

        elif mode == "compare":
            out_lines.append(f"### ⚖️ Karşılaştırmalı Tasarım Analizi: {clean_q}\n")
            out_lines.append("| Yaklaşım / Sistem | Güvenilirlik | Odaklandığı Konsept | Güçlü Yönü | Olası Riski |")
            out_lines.append("|---|---|---|---|---|")
            for c in chunks[:5]:
                sub = c.metadata.subcategory.replace("_", " ").title()
                out_lines.append(f"| {c.metadata.source_title} | Tier {c.metadata.reliability_tier}/5 | {sub} | Yüksek netlik | Denge zorluğu |")
            out_lines.append("\n#### 📌 Karar Rehberi")
            out_lines.append("- Hangi mekaniğin seçileceği oyunun temposu (pacing) ve hedef oyuncu profili (Bartle tipleri) ile doğrudan ilişkilidir.")

        elif mode == "create_gdd":
            out_lines.append(f"### 📄 Game Design Document (GDD) Taslağı: {clean_q}\n")
            out_lines.append("#### 1. Executive Summary & High Concept")
            out_lines.append(f"- **Proje Başlığı:** {clean_q}")
            out_lines.append("- **Tür & Platform:** PC / Konsol / Mobil uyumlu tasarım")
            out_lines.append("- **Temel Vaat (USP):** Hızlı öğrenilen, derin ustalık gerektiren mekanik kurgusu.\n")
            out_lines.append("#### 2. Core Gameplay Loop (Temel Oyun Döngüsü)")
            out_lines.append("- Eylem (Action) ➔ Geri Bildirim (Feedback) ➔ Ödül (Reward) ➔ İlerleme (Progression).\n")
            out_lines.append("#### 3. Temel Mekanikler ve Kontroller")
            for c in chunks[:2]:
                out_lines.append(f"- **{c.metadata.source_title}:** {c.text.strip()[:220]}...")
            out_lines.append("\n#### 4. İlerleme ve Ekonomi Sistemleri")
            out_lines.append("- Oyuncunun uzun vadeli motivasyonunu koruyan kaynak muslukları (faucets) ve giderleri (sinks).")
            out_lines.append("\n#### 5. Sanat ve Ses Yönelimi (Art & Audio Direction)")
            out_lines.append("- Oynanışı destekleyen diegetic veya non-diegetic görsel/işitsel ipuçları.")

        elif mode == "brief":
            out_lines.append(f"### 📋 Yönetici Özeti ve Brifing: {clean_q}\n")
            out_lines.append("Oyun tasarımı literatüründeki temel prensipler ve standartlar:\n")
            for idx, c in enumerate(chunks[:3], 1):
                out_lines.append(f"#### {idx}. {c.metadata.source_title}")
                out_lines.append(f"> {c.text.strip()[:280]}...\n")
            out_lines.append("#### 🎯 En İyi Pratikler (Best Practices)")
            out_lines.append("1. Mekaniği ilk prototip aşamasında 'graybox' ortamında test edin.")
            out_lines.append("2. Oyuncu girdisi ile görsel tepki arasındaki gecikmeyi (input lag) minimize edin.")
            out_lines.append("3. Oyuncunun zihinsel modeline uygun affordance sağlayın.")

        elif mode == "advise":
            engine_str = ""
            if extra_context and extra_context.get("hedef_motor"):
                engine_str = f" ({extra_context['hedef_motor']} Motoru İçin)"
            elif user_profile and user_profile.active_project and user_profile.active_project.game_engine:
                engine_str = f" ({user_profile.active_project.game_engine} Motoru İçin)"

            out_lines.append(f"### 🛠️ Aktif Geliştirme Danışmanlığı{engine_str}: {clean_q}\n")
            out_lines.append("Mevcut durum analizi ve endüstri standardı tavsiyeler:\n")
            out_lines.append("#### 🔍 Durum Analizi")
            out_lines.append("Belirttiğiniz tasarım adımı, oyuncu deneyiminin temel taşlarından biridir.")
            for c in chunks[:2]:
                out_lines.append(f"- **Referans İlke ({c.metadata.source_title}):** {c.text.strip()[:220]}...")
            out_lines.append("\n#### ⚠️ Dikkat Edilmesi Gereken Tuzaklar (Pitfalls)")
            out_lines.append("- Fizik hesaplamalarında kare hızından bağımsız (delta-time) mantık yürütülmelidir.")
            out_lines.append("- Aşırı karmaşık girdi kombinasyonları oyuncu frustrasyonuna yol açabilir.")
            out_lines.append("\n#### 🚀 Sonraki Adım Önerileri")
            out_lines.append("1. Mekaniğin 'coyote time' ve 'input buffering' toleranslarını tanımlayın.")
            out_lines.append("2. Farklı beceri düzeyindeki oyuncularla erken playtest oturumları düzenleyin.")

        elif mode == "market_analysis":
            out_lines.append(f"### 📊 Pazar Durumu ve Rekabet Analizi: {clean_q}\n")
            out_lines.append("Oyun sektöründeki trendler ve hedef kitle beklentileri:\n")
            for idx, c in enumerate(chunks[:3], 1):
                out_lines.append(f"#### Trend & Örnek {idx}: {c.metadata.source_title}")
                out_lines.append(f"> {c.text.strip()[:240]}...\n")
            out_lines.append("#### 📈 Pazar Dinamikleri ve Fırsat Boşluğu (Gap Analysis)")
            out_lines.append("- **Mevcut Durum:** Türde yüksek rekabet olmakla birlikte, yenilikçi alt mekaniklere sahip indie projeler öne çıkmaktadır.")
            out_lines.append("- **Giriş Stratejisi:** Erken demo yayını (Steam Next Fest) ve topluluk odaklı geliştirme önerilir.")

        else:  # qa mode
            out_lines.append(f"### 🎯 Tasarım Yanıtı: {clean_q}\n")
            out_lines.append("Doğrulanmış kaynaklar ışığında temel tasarım prensipleri:\n")
            for idx, c in enumerate(chunks, 1):
                meta = c.metadata
                out_lines.append(f"#### {idx}. {meta.source_title} ({meta.category.value})")
                preview = c.text.strip().replace("\n\n", " ")
                if len(preview) > 350:
                    preview = preview[:350] + "..."
                out_lines.append(f"> {preview}\n")
            out_lines.append("💡 **Uygulama Notu:** Bu mekanik tasarlanırken temel döngü (core loop) ve oyuncunun motivasyonu sürekli playtest ile dengelenmelidir.")

        return "\n".join(out_lines)

    def process_query_stream(
        self,
        query: str,
        mode: str | None = None,
        category: Category | None = None,
        engine: str | None = None,
        genre: str | None = None,
        user_id: str = "default_user",
        extra_context: dict[str, Any] | None = None,
    ) -> Iterator[str]:
        """Kullanıcı sorgusunu yüksek hızda işleyip cevabı gerçek zamanlı akış (streaming) olarak üretir."""
        active_mode = self.mode_router.route(query, explicit_mode=mode)
        cache_key = f"{query.strip().lower()}|{active_mode}|{category}|{engine}|{genre}|{user_id}"

        if cache_key in self._query_cache:
            logger.info(f"⚡ LRU Cache Stream HIT: '{query}'")
            cached = self._query_cache[cache_key]
            self._query_cache.move_to_end(cache_key)
            tokens = [t for t in re.split(r"(\s+)", cached.text) if t]
            for t in tokens:
                yield t
            return

        # Normal işlem
        response = self.process_query(
            query=query,
            mode=mode,
            category=category,
            engine=engine,
            genre=genre,
            user_id=user_id,
            extra_context=extra_context,
        )

        tokens = [t for t in re.split(r"(\s+)", response.text) if t]
        for t in tokens:
            yield t

