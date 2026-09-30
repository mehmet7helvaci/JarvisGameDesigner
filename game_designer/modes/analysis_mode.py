"""Oyun Analiz Modu (MDA Framework tabanlı)."""

from typing import TYPE_CHECKING, Any
from game_designer.models.response import GameDesignerResponse
from game_designer.models.taxonomy import Category
from game_designer.modes.base_mode import BaseMode

if TYPE_CHECKING:
    from game_designer.core.rag_engine import RagEngine


class AnalysisMode(BaseMode):
    """Oyunları ve mekanikleri MDA Framework prensipleriyle inceleyen analiz modu."""

    @property
    def name(self) -> str:
        return "analyze_game"

    @property
    def default_temperature(self) -> float:
        return 0.3

    @property
    def default_max_tokens(self) -> int:
        return 8192

    def execute(
        self,
        query: str,
        rag_engine: "RagEngine",
        user_id: str = "default_user",
        category: Category | None = None,
        engine: str | None = None,
        genre: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> GameDesignerResponse:
        enriched_query = f"{query} - Detaylı MDA Framework (Mechanics, Dynamics, Aesthetics) ve oyun tasarımı analizi."
        return rag_engine.process_query(
            query=enriched_query,
            mode=self.name,
            category=category,
            engine=engine,
            genre=genre,
            user_id=user_id,
            extra_context=context,
        )
