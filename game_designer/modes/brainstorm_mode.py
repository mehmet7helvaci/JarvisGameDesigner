"""Beyin Fırtınası Modu (Brainstorm Mode)."""

from typing import TYPE_CHECKING, Any
from game_designer.models.response import GameDesignerResponse
from game_designer.models.taxonomy import Category
from game_designer.modes.base_mode import BaseMode

if TYPE_CHECKING:
    from game_designer.core.rag_engine import RagEngine


class BrainstormMode(BaseMode):
    """Mekanik ve sistem fikirleri üreten yaratıcı beyin fırtınası modu."""

    @property
    def name(self) -> str:
        return "brainstorm"

    @property
    def default_temperature(self) -> float:
        # Kurallar gereği beyin fırtınasında yaratıcılık için 0.7 kullanılır
        return 0.7

    @property
    def default_max_tokens(self) -> int:
        return 4096

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
        enriched_query = f"{query} - En az 3-5 alternatif tasarım fikri, artıları/eksileri ve risk analizi ile birlikte."
        return rag_engine.process_query(
            query=enriched_query,
            mode=self.name,
            category=category,
            engine=engine,
            genre=genre,
            user_id=user_id,
            extra_context=context,
        )
