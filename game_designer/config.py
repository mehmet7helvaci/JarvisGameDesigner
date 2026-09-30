"""Konfigürasyon yönetimi modülü."""

import os
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator

# Proje ana dizinini bul
_CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _CURRENT_DIR.parent

# .env dosyasını yükle
load_dotenv(PROJECT_ROOT / ".env")


class ChunkingConfig(BaseModel):
    """Metin parçalama ayarları."""

    strategy: str = "semantic"
    min_chunk_size: int = 200
    max_chunk_size: int = 1500
    overlap: int = 100
    preserve_paragraphs: bool = True
    preserve_headings: bool = True
    metadata_inheritance: bool = True


class EmbeddingConfig(BaseModel):
    """Embedding model ayarları."""

    model: str = "all-MiniLM-L6-v2"
    device: str = Field(default_factory=lambda: os.getenv("EMBEDDING_DEVICE", "cpu"))
    normalize_embeddings: bool = True
    batch_size: int = 64


class RetrievalConfig(BaseModel):
    """Arama ve re-ranking ayarları."""

    top_k: int = 10
    rerank_top_n: int = 5
    similarity_threshold: float = 0.3
    use_metadata_filter: bool = True
    hybrid_search: bool = True
    hybrid_alpha: float = 0.7


class GenerationConfig(BaseModel):
    """Gemini LLM üretim ayarları."""

    model: str = Field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    temperature: float = 0.3
    brainstorm_temperature: float = 0.7
    max_output_tokens: int = 4096
    top_p: float = 0.85
    top_k_tokens: int = 40


class ConfidenceConfig(BaseModel):
    """Güvenilirlik puanlama ağırlıkları."""

    retrieval_weight: float = 0.35
    source_tier_weight: float = 0.25
    multi_source_weight: float = 0.20
    coverage_weight: float = 0.20
    fallback_threshold: float = 50.0


class ScrapingEthicsConfig(BaseModel):
    """Scraping etik ve sınır kuralları."""

    respect_robots_txt: bool = True
    rate_limit_seconds: float = 3.0
    identify_bot: bool = True
    user_agent: str = "JarvisGameDesignerBot/1.0 (+https://github.com/jarvis-game-designer)"
    cache_responses: bool = True
    max_articles_per_run: int = 50


class ScheduleConfig(BaseModel):
    """Zamanlanmış görev konfigürasyonu."""

    auto_scrape_enabled: bool = True
    auto_scrape_cron: str = "0 3 * * 1"
    maintenance_enabled: bool = True
    maintenance_cron: str = "0 4 * * 0"


class Settings(BaseModel):
    """Uygulama genel ayarları."""

    app_name: str = "Jarvis Game Designer"
    version: str = "0.1.0"
    project_root: Path = PROJECT_ROOT
    data_dir: Path = PROJECT_ROOT / "data"
    chroma_db_dir: Path = PROJECT_ROOT / "data" / "chroma_db"
    user_profiles_dir: Path = PROJECT_ROOT / "data" / "user_profiles"
    projects_dir: Path = PROJECT_ROOT / "data" / "projects"
    scraper_cache_dir: Path = PROJECT_ROOT / "data" / "scraper_cache"
    logs_dir: Path = PROJECT_ROOT / "data" / "logs"
    seeds_dir: Path = PROJECT_ROOT / "seeds"

    gemini_api_key: str | None = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY"))

    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    confidence: ConfidenceConfig = Field(default_factory=ConfidenceConfig)
    scraping: ScrapingEthicsConfig = Field(default_factory=ScrapingEthicsConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)

    @model_validator(mode="after")
    def _sync_subdirs(self) -> "Settings":
        if self.projects_dir == PROJECT_ROOT / "data" / "projects" and self.data_dir != PROJECT_ROOT / "data":
            self.projects_dir = self.data_dir / "projects"
        return self

    @classmethod
    def load(cls, config_path: str | Path | None = None, **overrides: Any) -> "Settings":
        """Konfigürasyon dosyasından (YAML/JSON) ve/veya parametrelerden Settings üretir."""
        data: dict[str, Any] = {}
        if config_path:
            p = Path(config_path)
            if p.exists() and p.is_file():
                try:
                    if p.suffix.lower() in [".yaml", ".yml"]:
                        import yaml
                        with open(p, "r", encoding="utf-8") as f:
                            loaded = yaml.safe_load(f)
                            if isinstance(loaded, dict):
                                data.update(loaded)
                    elif p.suffix.lower() == ".json":
                        import json
                        with open(p, "r", encoding="utf-8") as f:
                            loaded = json.load(f)
                            if isinstance(loaded, dict):
                                data.update(loaded)
                except Exception as e:
                    from game_designer.utils.logger import logger
                    logger.warning(f"Konfigürasyon dosyası okunamadı ({p}): {e}")

        data.update(overrides)
        settings = cls(**data)
        settings.ensure_directories()
        return settings

    def ensure_directories(self) -> None:
        """Gerekli tüm veri klasörlerinin var olduğundan emin olur."""
        for path in [
            self.data_dir,
            self.chroma_db_dir,
            self.user_profiles_dir,
            self.projects_dir,
            self.scraper_cache_dir,
            self.logs_dir,
            self.seeds_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)


def get_settings(config_path: str | Path | None = None, **overrides: Any) -> Settings:
    """Settings nesnesini üretir veya konfigürasyondan yükler."""
    return Settings.load(config_path=config_path, **overrides)

