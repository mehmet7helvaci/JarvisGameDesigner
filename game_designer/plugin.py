"""Jarvis Game Designer Plugin — Ana giriş noktası ve Jarvis arayüz entegrasyonu."""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path
import threading
from typing import Any

from game_designer.config import Settings, get_settings
from game_designer.core.rag_engine import RagEngine
from game_designer.data.chroma_manager import ChromaManager
from game_designer.data.document_processor import DocumentProcessor
from game_designer.data.embedding_manager import EmbeddingManager
from game_designer.data.project_manager import ProjectManager
from game_designer.data.user_profile import UserProfileStore
from game_designer.models.document import RawDocument
from game_designer.models.project import BlendFileRef, GameProject
from game_designer.models.response import GameDesignerResponse
from game_designer.models.taxonomy import Category, SourceType
from game_designer.models.user_profile import ActiveProject, UserProfile
from game_designer.modes import MODES_REGISTRY
from game_designer.scraper.scheduler import ScraperScheduler
from game_designer.utils.logger import logger


class JarvisPlugin(ABC):
    """Tüm Jarvis eklentilerinin (plugins) uygulaması gereken standart arayüz."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Eklentinin benzersiz adı."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Eklenti versiyonu (SemVer)."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Eklentinin kısa açıklaması."""
        ...

    @abstractmethod
    def initialize(self) -> bool:
        """Eklentiyi başlat (DB bağlantısı, model yükleme vb.)."""
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """Eklentiyi temiz bir şekilde kapat."""
        ...

    @abstractmethod
    def handle_query(self, query: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Ana sorgu işleme metodu."""
        ...

    @abstractmethod
    def get_capabilities(self) -> list[str]:
        """Eklentinin desteklediği yeteneklerin listesi."""
        ...


class GameDesignerPlugin(JarvisPlugin):
    """Jarvis Game Designer Plugin — Oyun tasarımı uzman modülü."""

    def __init__(self, config_path: str | Path | None = None, **overrides: Any) -> None:
        self.settings: Settings = get_settings(config_path=config_path, **overrides)
        self.embedding_manager: EmbeddingManager | None = None
        self.chroma_manager: ChromaManager | None = None
        self.doc_processor: DocumentProcessor | None = None
        self.user_profile_store: UserProfileStore | None = None
        self.project_manager: ProjectManager | None = None
        self.rag_engine: RagEngine | None = None
        self.scheduler: ScraperScheduler | None = None
        self._is_initialized = False

    @property
    def name(self) -> str:
        return "game_designer"

    @property
    def version(self) -> str:
        return self.settings.version

    @property
    def description(self) -> str:
        return "Oyun tasarımı konusunda uzmanlaşmış RAG tabanlı bilgi yardımcısı"

    def get_capabilities(self) -> list[str]:
        return [
            "query",              # Soru-Cevap
            "analyze_game",       # Oyun Analizi
            "brainstorm",         # Beyin Fırtınası
            "compare",            # Karşılaştırma
            "create_gdd",         # GDD Oluşturma
            "brief",              # Brifing/Özet
            "advise",             # Aktif Danışmanlık
            "market_analysis",    # Pazar Analizi
        ]

    def initialize(self, auto_load_seeds: bool = True) -> bool:
        """Eklentiyi başlatır, veritabanını ve RAG motorunu hazır hale getirir."""
        if self._is_initialized:
            return True

        logger.info(f"Jarvis Game Designer Plugin v{self.version} başlatılıyor...")
        self.settings.ensure_directories()

        self.embedding_manager = EmbeddingManager(self.settings)
        self.chroma_manager = ChromaManager(self.settings, self.embedding_manager)
        self.doc_processor = DocumentProcessor(self.settings)
        self.user_profile_store = UserProfileStore(self.settings)
        self.project_manager = ProjectManager(self.settings, self.user_profile_store)

        self.rag_engine = RagEngine(
            settings=self.settings,
            chroma_manager=self.chroma_manager,
            user_profile_store=self.user_profile_store,
        )

        self.scheduler = ScraperScheduler(
            settings=self.settings,
            chroma_manager=self.chroma_manager,
            doc_processor=self.doc_processor,
        )

        # Eğer veritabanı tamamen boşsa ve seed dizini mevcutsa başlangıç verilerini yükle
        if auto_load_seeds and self.chroma_manager.count() == 0 and self.settings.seeds_dir.exists():
            from seeds.loader import load_all_seeds
            try:
                loaded = load_all_seeds(
                    settings=self.settings,
                    chroma_manager=self.chroma_manager,
                    doc_processor=self.doc_processor,
                )
                logger.info(f"Başlangıç seed kütüphanesi otomatik yüklendi: {loaded} chunk.")
            except Exception as e:
                logger.warning(f"Seed kütüphanesi otomatik yüklenirken hata: {e}")

        self._is_initialized = True
        logger.info("Jarvis Game Designer Plugin başarıyla başlatıldı.")

        # Vektör modelini ve önbelleği arka planda ısıt
        try:
            threading.Thread(target=self.chroma_manager.pre_warm, daemon=True).start()
        except Exception:
            pass

        return True

    def shutdown(self) -> None:
        """Eklentiyi ve arka plan scheduler'ı kapatır."""
        logger.info("Jarvis Game Designer Plugin kapatılıyor...")
        if self.scheduler:
            self.scheduler.stop()
        self._is_initialized = False
        logger.info("Plugin kapatıldı.")

    def _ensure_initialized(self) -> None:
        if not self._is_initialized or self.rag_engine is None or self.project_manager is None:
            self.initialize()

    def handle_query(self, query: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Jarvis çekirdeği için genel çağrı kapısı."""
        self._ensure_initialized()
        resp = self.query(query, context=context)
        return {
            "text": resp.text,
            "confidence": resp.confidence,
            "mode": resp.mode,
            "sources": [s.model_dump() for s in resp.sources],
            "is_fallback": resp.is_fallback,
        }

    # === TEMEL YETENEK METOTLARI ===

    def query(
        self,
        query: str,
        mode: str | None = None,
        context: dict[str, Any] | None = None,
        category: Category | None = None,
        engine: str | None = None,
        genre: str | None = None,
        user_id: str = "default_user",
    ) -> GameDesignerResponse:
        """Genel Soru-Cevap veya otomatik mod yönlendirmeli sorgulama."""
        self._ensure_initialized()
        assert self.rag_engine is not None
        return self.rag_engine.process_query(
            query=query,
            mode=mode,
            category=category,
            engine=engine,
            genre=genre,
            user_id=user_id,
            extra_context=context,
        )

    def query_stream(
        self,
        question: str,
        mode: str | None = None,
        category: Category | None = None,
        engine: str | None = None,
        genre: str | None = None,
        user_id: str = "default_user",
        context: dict[str, Any] | None = None,
    ) -> Iterator[str]:
        """Sorguyu gerçek zamanlı kelime/token akışı (streaming) olarak döndürür."""
        self._ensure_initialized()
        assert self.rag_engine is not None
        return self.rag_engine.process_query_stream(
            query=question,
            mode=mode,
            category=category,
            engine=engine,
            genre=genre,
            user_id=user_id,
            extra_context=context,
        )

    def analyze_game(
        self,
        game_or_mechanic: str,
        context: dict[str, Any] | None = None,
        user_id: str = "default_user",
    ) -> GameDesignerResponse:
        """MDA Framework tabanlı oyun veya mekanik analizi."""
        self._ensure_initialized()
        mode_handler = MODES_REGISTRY["analyze_game"]
        return mode_handler.execute(
            query=game_or_mechanic,
            rag_engine=self.rag_engine,
            user_id=user_id,
            context=context,
        )

    def brainstorm(
        self,
        topic: str,
        context: dict[str, Any] | None = None,
        user_id: str = "default_user",
    ) -> GameDesignerResponse:
        """Mekanik, ilerleme veya sistem konularında beyin fırtınası."""
        self._ensure_initialized()
        mode_handler = MODES_REGISTRY["brainstorm"]
        return mode_handler.execute(
            query=topic,
            rag_engine=self.rag_engine,
            user_id=user_id,
            context=context,
        )

    def compare(
        self,
        item_a: str,
        item_b: str | None = None,
        context: dict[str, Any] | None = None,
        user_id: str = "default_user",
    ) -> GameDesignerResponse:
        """İki mekanik, sistem veya yaklaşımı karşılaştırır."""
        self._ensure_initialized()
        query = f"{item_a} ile {item_b} karşılaştırması" if item_b else item_a
        mode_handler = MODES_REGISTRY["compare"]
        return mode_handler.execute(
            query=query,
            rag_engine=self.rag_engine,
            user_id=user_id,
            context=context,
        )

    def create_gdd(
        self,
        concept: str,
        context: dict[str, Any] | None = None,
        user_id: str = "default_user",
    ) -> GameDesignerResponse:
        """Standart Oyun Tasarım Dökümanı (GDD) taslağı oluşturur."""
        self._ensure_initialized()
        mode_handler = MODES_REGISTRY["create_gdd"]
        return mode_handler.execute(
            query=concept,
            rag_engine=self.rag_engine,
            user_id=user_id,
            context=context,
        )

    def brief(
        self,
        topic: str,
        context: dict[str, Any] | None = None,
        user_id: str = "default_user",
    ) -> GameDesignerResponse:
        """Konu hakkında yönetici özeti ve temel prensipler brifingi sunar."""
        self._ensure_initialized()
        mode_handler = MODES_REGISTRY["brief"]
        return mode_handler.execute(
            query=topic,
            rag_engine=self.rag_engine,
            user_id=user_id,
            context=context,
        )

    def advise(
        self,
        current_situation: str,
        context: dict[str, Any] | None = None,
        user_id: str = "default_user",
    ) -> GameDesignerResponse:
        """Kullanıcının aktif projesine ve motoruna göre anlık danışmanlık sağlar."""
        self._ensure_initialized()
        mode_handler = MODES_REGISTRY["advise"]
        return mode_handler.execute(
            query=current_situation,
            rag_engine=self.rag_engine,
            user_id=user_id,
            context=context,
        )

    def market_analysis(
        self,
        genre_or_platform: str,
        context: dict[str, Any] | None = None,
        user_id: str = "default_user",
    ) -> GameDesignerResponse:
        """Pazar trendleri ve rekabet ortamı analizi yapar."""
        self._ensure_initialized()
        mode_handler = MODES_REGISTRY["market_analysis"]
        return mode_handler.execute(
            query=genre_or_platform,
            rag_engine=self.rag_engine,
            user_id=user_id,
            context=context,
        )

    # === VERİ EKLEME VE PROFİL YÖNETİMİ ===

    def ingest_document(self, raw_doc: RawDocument) -> int:
        """Ham bir dokümanı parçalara ayırıp vektör veritabanına ekler."""
        self._ensure_initialized()
        assert self.doc_processor is not None
        assert self.chroma_manager is not None
        chunks = self.doc_processor.process_document(raw_doc)
        return self.chroma_manager.add_chunks(chunks)

    def ingest_text(
        self,
        title: str,
        content: str,
        category: Category = Category.CORE_MECHANICS,
        subcategory: str = "general",
        tags: list[str] | None = None,
        source_type: SourceType = SourceType.ARTICLE,
        source_url: str | None = None,
        author: str | None = None,
        game_engines: list[str] | None = None,
        game_genres: list[str] | None = None,
        is_verified: bool = True,
    ) -> int:
        """Metin içeriğini doğrudan döküman olarak ekler."""
        raw_doc = RawDocument(
            title=title,
            content=content,
            category=category,
            subcategory=subcategory,
            tags=tags or [],
            source_type=source_type,
            source_url=source_url,
            author=author,
            game_engines=game_engines or [],
            game_genres=game_genres or [],
            is_verified=is_verified,
        )
        return self.ingest_document(raw_doc)

    def set_user_active_project(
        self,
        user_id: str,
        project_name: str,
        game_engine: str | None = None,
        genre: str | None = None,
        development_phase: str | None = None,
        key_features: list[str] | None = None,
        known_challenges: list[str] | None = None,
        notes: str = "",
    ) -> ActiveProject:
        """Kullanıcının aktif geliştirdiği proje detaylarını günceller ve ProjectManager ile senkronize eder."""
        self._ensure_initialized()
        assert self.user_profile_store is not None
        assert self.project_manager is not None

        # ProjectManager üzerinde var olan projeyi güncelle veya yeni proje oluştur
        existing = self.project_manager.get_project(project_name)
        if existing:
            self.project_manager.update_project(
                existing.id,
                user_id=user_id,
                game_engine=game_engine if game_engine is not None else existing.game_engine,
                genre=genre if genre is not None else existing.genre,
                development_phase=development_phase if development_phase is not None else existing.development_phase,
                key_features=key_features if key_features is not None else existing.key_features,
                known_challenges=known_challenges if known_challenges is not None else existing.known_challenges,
                notes=notes if notes else existing.notes,
            )
            self.project_manager.set_active_project(existing.id, user_id=user_id)
        else:
            self.project_manager.create_project(
                name=project_name,
                game_engine=game_engine,
                genre=genre,
                development_phase=development_phase or "concept",
                notes=notes,
                key_features=key_features or [],
                known_challenges=known_challenges or [],
                activate=True,
                user_id=user_id,
            )

        proj = ActiveProject(
            project_name=project_name,
            game_engine=game_engine,
            genre=genre,
            development_phase=development_phase,
            key_features=key_features or [],
            known_challenges=known_challenges or [],
            notes=notes,
        )
        self.user_profile_store.update_active_project(user_id, proj)
        return proj

    def get_user_profile(self, user_id: str = "default_user") -> UserProfile:
        """Kullanıcı profil verisini döndürür."""
        self._ensure_initialized()
        assert self.user_profile_store is not None
        return self.user_profile_store.get_or_create_profile(user_id)

    # === OYUN PROJESİ VE BLENDER (.BLEND) YÖNETİMİ ===

    def list_projects(self) -> list[GameProject]:
        """Tüm kayıtlı oyun projelerini listeler."""
        self._ensure_initialized()
        assert self.project_manager is not None
        return self.project_manager.list_projects()

    def get_project(self, name_or_id: str) -> GameProject | None:
        """Adına veya ID'sine göre projeyi getirir."""
        self._ensure_initialized()
        assert self.project_manager is not None
        return self.project_manager.get_project(name_or_id)

    def create_project(
        self,
        name: str,
        game_engine: str | None = None,
        genre: str | None = None,
        development_phase: str = "concept",
        description: str = "",
        notes: str = "",
        key_features: list[str] | None = None,
        known_challenges: list[str] | None = None,
        gdd_snippets: list[str] | None = None,
        activate: bool = False,
        user_id: str = "default_user",
        engine: str | None = None,
        **kwargs: Any,
    ) -> GameProject:
        """Yeni bir oyun tasarımı projesi oluşturur."""
        self._ensure_initialized()
        assert self.project_manager is not None
        actual_engine = game_engine or engine or kwargs.get("game_engine") or kwargs.get("engine")
        return self.project_manager.create_project(
            name=name,
            game_engine=actual_engine,
            genre=genre,
            development_phase=development_phase,
            description=description,
            notes=notes,
            key_features=key_features,
            known_challenges=known_challenges,
            gdd_snippets=gdd_snippets,
            activate=activate,
            user_id=user_id,
        )

    def update_project(
        self,
        name_or_id: str,
        user_id: str = "default_user",
        **kwargs: Any,
    ) -> GameProject:
        """Mevcut bir oyun projesini günceller."""
        self._ensure_initialized()
        assert self.project_manager is not None
        return self.project_manager.update_project(name_or_id, user_id=user_id, **kwargs)

    def delete_project(self, name_or_id: str, user_id: str = "default_user") -> bool:
        """Projeyi siler."""
        self._ensure_initialized()
        assert self.project_manager is not None
        return self.project_manager.delete_project(name_or_id, user_id=user_id)

    def set_active_project(self, name_or_id: str, user_id: str = "default_user") -> GameProject:
        """Projeyi aktif proje olarak belirler ve Jarvis profil hafızasına işler."""
        self._ensure_initialized()
        assert self.project_manager is not None
        return self.project_manager.set_active_project(name_or_id, user_id=user_id)

    def get_active_project(self, user_id: str = "default_user") -> GameProject | None:
        """Mevcut aktif projeyi getirir."""
        self._ensure_initialized()
        assert self.project_manager is not None
        return self.project_manager.get_active_project(user_id=user_id)

    def add_blend_file(
        self,
        project_name_or_id: str,
        file_path: str,
        category: str | None = None,
        notes: str = "",
        name: str | None = None,
    ) -> BlendFileRef:
        """Belirtilen projeye 3D/Blender (.blend, .fbx, .obj, .gltf, .bvh vb.) dosya referansı ekler."""
        self._ensure_initialized()
        assert self.project_manager is not None
        return self.project_manager.add_blend_file(
            project_name_or_id=project_name_or_id,
            file_path=file_path,
            category=category,
            notes=notes,
            name=name,
        )

    def get_blend_files(
        self,
        project_name_or_id: str,
        category: str | None = None,
    ) -> list[BlendFileRef]:
        """Projeye ait Blender dosyalarını getirir."""
        self._ensure_initialized()
        assert self.project_manager is not None
        return self.project_manager.get_blend_files(
            project_name_or_id=project_name_or_id,
            category=category,
        )

    def remove_blend_file(
        self,
        project_name_or_id: str,
        blend_file_id_or_path: str,
    ) -> bool:
        """Projeden Blender dosya referansını kaldırır."""
        self._ensure_initialized()
        assert self.project_manager is not None
        return self.project_manager.remove_blend_file(
            project_name_or_id=project_name_or_id,
            blend_file_id_or_path=blend_file_id_or_path,
        )

    def open_blend_file(
        self,
        file_path_or_id: str,
        project_name_or_id: str | None = None,
    ) -> bool:
        """Blender (.blend) dosyasını sistemin varsayılan uygulamasıyla açar."""
        self._ensure_initialized()
        assert self.project_manager is not None
        return self.project_manager.open_blend_file(
            file_path_or_id=file_path_or_id,
            project_name_or_id=project_name_or_id,
        )
