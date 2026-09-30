"""Sorgu zenginleştirme, çeviri ve kategori sezme modülü."""

import re
from game_designer.models.query import RewrittenQuery
from game_designer.models.taxonomy import Category
from game_designer.utils.language_utils import detect_language, get_english_terms_for_query

CATEGORY_KEYWORDS: dict[Category, list[str]] = {
    Category.CORE_MECHANICS: ["core loop", "döngü", "oyun döngüsü", "mekanik", "temel mekanik", "gameplay loop", "jump", "movement", "zıplama", "zıpla", "hareket", "dash", "koşma", "yürüme", "fizik"],
    Category.GAME_SYSTEMS: ["ekonomi", "crafting", "üretim", "envanter", "inventory", "progression", "ilerleme", "yetenek ağacı", "skill tree"],
    Category.GAME_BALANCE: ["denge", "balance", "stat", "tuning", "power creep", "nerf", "buff", "meta"],
    Category.CONTROLS_INPUT: ["kontrol", "input", "gamepad", "klavye", "mouse", "dokunmatik", "touch", "coyote time", "input buffer", "buffer"],
    Category.LEVEL_DESIGN: ["level design", "bölüm tasarımı", "seviye tasarımı", "pacing", "flow", "akış", "checkpoints"],
    Category.AI_DESIGN: ["ai", "yapay zeka", "behavior tree", "fsm", "pathfinding", "navmesh", "düşman zekası"],
    Category.MULTIPLAYER: ["multiplayer", "çok oyunculu", "netcode", "eşleşme", "matchmaking", "co-op"],
    Category.NARRATIVE: ["hikaye", "narrative", "diyalog", "lore", "world building", "senaryo", "karakter hikayesi", "karakter gelişimi"],
    Category.UX_UI: ["ux", "ui", "arayüz", "hud", "menü", "affordance", "feedforward", "feedback"],
    Category.AUDIO_DESIGN: ["audio", "ses", "müzik", "sfx", "sound design", "foley"],
    Category.VISUAL_DESIGN: ["art style", "görsel", "art direction", "renk paleti", "shader", "animasyon"],
    Category.PLAYER_PSYCHOLOGY: ["motivasyon", "engagement", "bağımlılık", "compulsion", "flow state", "psikoloji"],
    Category.PLAYER_TYPES: ["bartle", "achiever", "explorer", "socializer", "killer", "oyuncu tipleri"],
    Category.ACCESSIBILITY: ["erişilebilirlik", "accessibility", "renk körü", "altyazı", "remapping"],
    Category.MONETIZATION: ["monetizasyon", "f2p", "battle pass", "gacha", "mikro ödeme", "reklam"],
    Category.MARKET_ANALYSIS: ["pazar", "trend", "rakip", "steam", "satış", "market", "istatistik", "indirme", "indirmeler", "gelir"],
    Category.ANALYTICS: ["analitik", "kpi", "retention", "churn", "dau", "mau", "arpu"],
    Category.GDD: ["gdd", "game design document", "oyun dökümanı", "tasarım belgesi", "pitch"],
    Category.PROTOTYPING: ["prototip", "graybox", "playtest", "test etme", "erken aşama"],
    Category.POSTMORTEM: ["postmortem", "post-mortem", "neler öğrendik", "dersler", "başarısızlık"],
    Category.GENRE_RPG: ["rpg", "rol yapma", "quest", "görev", "loot", "karakter geliştirme"],
    Category.GENRE_FPS: ["fps", "first person shooter", "nişancı", "aim", "silah"],
    Category.GENRE_STRATEGY: ["strateji", "rts", "sıra tabanlı", "turn-based", "taktik"],
    Category.GENRE_MOBILE: ["mobil", "hypercasual", "casual", "touch controls", "idle"],
    Category.GENRE_PUZZLE: ["bulmaca", "puzzle", "zeka"],
    Category.GENRE_PLATFORMER: ["platform", "platformer", "zıplama", "metroidvania"],
    Category.GENRE_SIMULATION: ["simülasyon", "simulation", "tycoon", "yönetim"],
}

ENGINE_PATTERNS = ["unity", "unreal", "unreal engine", "godot", "gamemaker", "defold", "bevy", "roblox"]
GENRE_PATTERNS = ["rpg", "fps", "roguelike", "roguelite", "puzzle", "platformer", "strategy", "moba", "survival", "horror", "simulation", "metroidvania", "deckbuilder"]


class QueryRewriter:
    """Sorguyu arama motoru için optimize eden, kategori ve motor parametrelerini sezen sınıf."""

    def rewrite(self, query: str) -> RewrittenQuery:
        """Kullanıcı sorgusunu analiz eder ve genişletilmiş arama sorgularına dönüştürür.

        Args:
            query: Ham kullanıcı sorgusu.

        Returns:
            RewrittenQuery nesnesi.
        """
        clean_q = query.strip()
        core_q = clean_q.split(" - ")[0].strip() if " - " in clean_q else clean_q
        lang = detect_language(core_q)

        # İngilizce terim karşılıklarını topla (çekirdek sorgudan)
        en_terms = get_english_terms_for_query(core_q)
        if not en_terms and clean_q != core_q:
            en_terms = get_english_terms_for_query(clean_q)

        # Kategori, motor ve tür sezme (önce çekirdek sorgu, sonra tam metin)
        detected_category = self._detect_category(core_q) or self._detect_category(clean_q)
        detected_engine = self._detect_engine(core_q) or self._detect_engine(clean_q)
        detected_genre = self._detect_genre(core_q) or self._detect_genre(clean_q)

        # Arama sorguları havuzu oluştur (öncelik çekirdek kullanıcı sorusunda)
        search_queries: list[str] = [core_q]
        if en_terms:
            search_queries.append(" ".join(en_terms))
            search_queries.append(f"{core_q} {' '.join(en_terms[:3])}")

        # Sorgudaki doğrudan İngilizce/latin veya oyun terimlerini izole et
        latin_words = [
            w for w in re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", core_q)
            if w.lower() not in {"bir", "ile", "icin", "olan", "neden", "nelerdir", "nasil", "nedir", "oyun", "oyununda", "tasarlanir"}
        ]
        if latin_words:
            isolated_latin = " ".join(latin_words)
            if isolated_latin not in search_queries:
                search_queries.append(isolated_latin)
            if en_terms:
                combined_latin = f"{isolated_latin} {' '.join(en_terms[:2])}"
                if combined_latin not in search_queries:
                    search_queries.append(combined_latin)

        if clean_q != core_q and clean_q not in search_queries:
            search_queries.append(clean_q)

        # Birincil arama sorgusu: çekirdek soru ve İngilizce anahtar terimler
        rewritten = core_q
        if en_terms:
            rewritten = f"{core_q} ({', '.join(en_terms[:4])})"

        return RewrittenQuery(
            original_query=clean_q,
            rewritten_query=rewritten,
            search_queries=search_queries,
            detected_language=lang,
            detected_category=detected_category,
            detected_engine=detected_engine,
            detected_genre=detected_genre,
        )

    def _detect_category(self, text: str) -> Category | None:
        """Metin içindeki terimlere göre en olası ana kategoriyi belirler.
        
        Tasarım konuları (mekanik, sistem, seviye vb.) tür kategorilerinden önceliklidir.
        """
        t_lower = text.lower()
        best_cat: Category | None = None
        max_matches = 0

        # Önce tasarım kategorilerini kontrol et (GENRE_ hariç)
        for cat, keywords in CATEGORY_KEYWORDS.items():
            if cat.value.startswith("genre_"):
                continue
            matches = sum(1 for kw in keywords if kw in t_lower)
            if matches > max_matches:
                max_matches = matches
                best_cat = cat

        if best_cat is not None and max_matches > 0:
            return best_cat

        # Eğer tasarım kategorisi bulunamazsa tür kategorilerine bak
        for cat, keywords in CATEGORY_KEYWORDS.items():
            if not cat.value.startswith("genre_"):
                continue
            matches = sum(1 for kw in keywords if kw in t_lower)
            if matches > max_matches:
                max_matches = matches
                best_cat = cat

        return best_cat

    def _detect_engine(self, text: str) -> str | None:
        """Metinde oyun motoru adı geçip geçmediğini belirler."""
        t_lower = text.lower()
        for eng in ENGINE_PATTERNS:
            if re.search(rf"\b{re.escape(eng)}\b", t_lower):
                return eng.title()
        return None

    def _detect_genre(self, text: str) -> str | None:
        """Metinde oyun türü adı geçip geçmediğini belirler."""
        t_lower = text.lower()
        for genre in GENRE_PATTERNS:
            if re.search(rf"\b{re.escape(genre)}\b", t_lower):
                return genre.title()
        return None
