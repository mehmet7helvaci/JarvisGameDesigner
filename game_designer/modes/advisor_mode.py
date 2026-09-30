"""Aktif Geliştirme Danışmanı Modu (Advisor Mode)."""

from typing import TYPE_CHECKING, Any
from game_designer.models.response import GameDesignerResponse
from game_designer.models.taxonomy import Category
from game_designer.modes.base_mode import BaseMode

if TYPE_CHECKING:
    from game_designer.core.rag_engine import RagEngine


class AdvisorMode(BaseMode):
    """Kullanıcının aktif projesine ve motoruna göre anlık danışmanlık sunan mod."""

    @property
    def name(self) -> str:
        return "advise"

    @property
    def default_temperature(self) -> float:
        return 0.4

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
        # Kullanıcının aktif proje bilgisini profilden çek
        profile = rag_engine.user_profile_store.get_or_create_profile(user_id)
        effective_engine = engine
        effective_genre = genre

        if profile.active_project:
            if not effective_engine and profile.active_project.game_engine:
                effective_engine = profile.active_project.game_engine
            if not effective_genre and profile.active_project.genre:
                effective_genre = profile.active_project.genre

        advisor_context = dict(context) if context else {}
        if effective_engine:
            advisor_context["hedef_motor"] = effective_engine
        if effective_genre:
            advisor_context["hedef_tur"] = effective_genre

        enriched_query = (
            f"{query} - Aktif geliştirme danışmanlığı: Olası tuzaklar, motor spesifik pratikler, risk analizi ve sonraki adım tavsiyeleri."
        )

        return rag_engine.process_query(
            query=enriched_query,
            mode=self.name,
            category=category,
            engine=effective_engine,
            genre=effective_genre,
            user_id=user_id,
            extra_context=advisor_context,
        )
