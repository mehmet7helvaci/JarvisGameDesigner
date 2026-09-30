from datetime import date
from typing import Any
from pydantic import BaseModel, Field

from game_designer.models.taxonomy import SourceType


class SourceCitation(BaseModel):
    """Cevapta referans gösterilen kaynak bilgisi."""

    title: str
    url: str | None = None
    source_type: SourceType = SourceType.ARTICLE
    reliability_tier: int = Field(default=3, ge=1, le=5)
    chunk_id: str = ""
    publication_date: date | None = None
    is_stale: bool = False


class ConfidenceBreakdown(BaseModel):
    """Güvenilirlik skorunun alt bileşenleri."""

    avg_retrieval: float
    avg_tier: float
    multi_source_bonus: float
    context_coverage: float
    final_score: float
    level: str
    badge: str

    @property
    def safe_badge(self) -> str:
        """Emoji içermeyen ASCII güvenli rozet temsili."""
        return (
            self.badge.replace("🟢", "[HIGH]")
            .replace("🟡", "[MED]")
            .replace("🟠", "[LOW]")
            .replace("🔴", "[LOW]")
        )


class GameDesignerResponse(BaseModel):
    """Kullanıcıya veya Jarvis asistanına döndürülen standart cevap nesnesi."""

    text: str
    confidence: float
    confidence_breakdown: ConfidenceBreakdown | None = None
    sources: list[SourceCitation] = Field(default_factory=list)
    mode: str = "qa"
    is_fallback: bool = False
    suggested_followups: list[str] = Field(default_factory=list)
    raw_data: dict[str, Any] = Field(default_factory=dict)

    @property
    def plain_text(self) -> str:
        """Emojilerden arındırılmış düz metin çıktısı."""
        return (
            self.text.replace("🟢", "[HIGH]")
            .replace("🟡", "[MED]")
            .replace("🟠", "[LOW]")
            .replace("🔴", "[POOR]")
            .replace("⚠️", "[!]")
        )
