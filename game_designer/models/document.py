"""Doküman ve parça (chunk) modelleri."""

from datetime import date, datetime, timezone
from typing import Any
from pydantic import BaseModel, Field, field_validator

from game_designer.models.taxonomy import Category, SourceType, get_default_tier_for_source


class DocumentMetadata(BaseModel):
    """Her bilgi parçasının zorunlu metadata'sı."""

    # Birincil sınıflandırma
    category: Category
    subcategory: str = Field(default="general")
    tags: list[str] = Field(default_factory=list)

    # Kaynak bilgisi
    source_type: SourceType
    source_url: str | None = None
    source_title: str
    author: str | None = None
    publication_date: date | None = None

    # Kalite ve güvenilirlik
    reliability_tier: int = Field(default=3, ge=1, le=5)
    is_verified: bool = False

    # Teknik bağlam
    game_engines: list[str] = Field(default_factory=list)
    game_genres: list[str] = Field(default_factory=list)

    # Sistem
    chunk_id: str
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_verified_at: datetime | None = None

    @field_validator("reliability_tier", mode="before")
    @classmethod
    def set_tier_if_missing(cls, v: Any, info: Any) -> int:
        if v is None:
            source_type = info.data.get("source_type", SourceType.ARTICLE)
            return get_default_tier_for_source(source_type)
        return int(v)

    def to_chroma_metadata(self) -> dict[str, str | int | float | bool]:
        """ChromaDB için düzleştirilmiş (flattened) metadata sözlüğü döndürür."""
        return {
            "category": self.category.value if isinstance(self.category, Category) else str(self.category),
            "subcategory": self.subcategory,
            "tags": ",".join(self.tags),
            "source_type": self.source_type.value if isinstance(self.source_type, SourceType) else str(self.source_type),
            "source_url": self.source_url or "",
            "source_title": self.source_title,
            "author": self.author or "",
            "publication_date": self.publication_date.isoformat() if self.publication_date else "",
            "reliability_tier": int(self.reliability_tier),
            "is_verified": bool(self.is_verified),
            "game_engines": ",".join(self.game_engines),
            "game_genres": ",".join(self.game_genres),
            "chunk_id": self.chunk_id,
            "ingested_at": self.ingested_at.isoformat() if self.ingested_at else "",
            "last_verified_at": self.last_verified_at.isoformat() if self.last_verified_at else "",
        }

    @classmethod
    def from_chroma_metadata(cls, meta: dict[str, Any]) -> "DocumentMetadata":
        """ChromaDB düzleştirilmiş metadata sözlüğünden DocumentMetadata üretir."""
        raw_tags = meta.get("tags", "")
        tags = [t.strip() for t in raw_tags.split(",") if t.strip()] if isinstance(raw_tags, str) else list(raw_tags or [])
        
        raw_engines = meta.get("game_engines", "")
        engines = [e.strip() for e in raw_engines.split(",") if e.strip()] if isinstance(raw_engines, str) else list(raw_engines or [])
        
        raw_genres = meta.get("game_genres", "")
        genres = [g.strip() for g in raw_genres.split(",") if g.strip()] if isinstance(raw_genres, str) else list(raw_genres or [])

        pub_date_raw = meta.get("publication_date")
        pub_date: date | None = None
        if pub_date_raw:
            try:
                pub_date = date.fromisoformat(str(pub_date_raw)[:10])
            except ValueError:
                pub_date = None

        ingested_at_raw = meta.get("ingested_at")
        ingested_at = datetime.now(timezone.utc)
        if ingested_at_raw:
            try:
                ingested_at = datetime.fromisoformat(str(ingested_at_raw))
            except ValueError:
                pass

        last_verified_raw = meta.get("last_verified_at")
        last_verified_at: datetime | None = None
        if last_verified_raw:
            try:
                last_verified_at = datetime.fromisoformat(str(last_verified_raw))
            except ValueError:
                pass

        cat_val = meta.get("category", Category.CORE_MECHANICS.value)
        try:
            category = Category(cat_val)
        except ValueError:
            category = Category.CORE_MECHANICS

        st_val = meta.get("source_type", SourceType.ARTICLE.value)
        try:
            source_type = SourceType(st_val)
        except ValueError:
            source_type = SourceType.ARTICLE

        return cls(
            category=category,
            subcategory=str(meta.get("subcategory", "general")),
            tags=tags,
            source_type=source_type,
            source_url=str(meta.get("source_url") or "") or None,
            source_title=str(meta.get("source_title", "Unknown Source")),
            author=str(meta.get("author") or "") or None,
            publication_date=pub_date,
            reliability_tier=int(meta.get("reliability_tier", 3)),
            is_verified=bool(meta.get("is_verified", False)),
            game_engines=engines,
            game_genres=genres,
            chunk_id=str(meta.get("chunk_id", "")),
            ingested_at=ingested_at,
            last_verified_at=last_verified_at,
        )


class DocumentChunk(BaseModel):
    """RAG pipeline içinde depolanan ve kullanılan birim chunk."""

    chunk_id: str
    text: str
    metadata: DocumentMetadata
    embedding: list[float] | None = None


class RawDocument(BaseModel):
    """Scraper veya döküman işleyiciye giren ham döküman yapısı."""

    title: str
    content: str
    category: Category = Category.CORE_MECHANICS
    subcategory: str = "general"
    tags: list[str] = Field(default_factory=list)
    source_type: SourceType = SourceType.ARTICLE
    source_url: str | None = None
    author: str | None = None
    publication_date: date | None = None
    game_engines: list[str] = Field(default_factory=list)
    game_genres: list[str] = Field(default_factory=list)
    is_verified: bool = False
