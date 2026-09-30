"""Etkileşim modları için temel soyut sınıf (BaseMode)."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from game_designer.models.response import GameDesignerResponse
from game_designer.models.taxonomy import Category

if TYPE_CHECKING:
    from game_designer.core.rag_engine import RagEngine


class BaseMode(ABC):
    """Tüm oyun tasarımı etkileşim modlarının türetileceği temel sınıf."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Modun benzersiz adı."""
        ...

    @property
    def default_temperature(self) -> float:
        """Modun varsayılan LLM sıcaklık değeri."""
        return 0.3

    @property
    def default_max_tokens(self) -> int:
        """Modun varsayılan maksimum token sayısı."""
        return 4096

    @abstractmethod
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
        """Moda özel mantığı ve RAG orkestrasyonunu çalıştırır."""
        ...
