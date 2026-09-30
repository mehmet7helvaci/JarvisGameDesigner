"""Sorgu ve arama modelleri."""

from typing import Any
from pydantic import BaseModel, Field

from game_designer.models.document import DocumentMetadata
from game_designer.models.taxonomy import Category


class QueryInput(BaseModel):
    """Kullanıcıdan veya Jarvis ana uygulamasından gelen sorgu girdisi."""

    query: str
    mode: str | None = None
    category_filter: Category | None = None
    engine_filter: str | None = None
    genre_filter: str | None = None
    top_k: int = 10
    user_id: str | None = None
    extra_context: dict[str, Any] = Field(default_factory=dict)


class RewrittenQuery(BaseModel):
    """Sorgu yeniden yazıcı (Query Rewriter) tarafından zenginleştirilmiş sorgu."""

    original_query: str
    rewritten_query: str
    search_queries: list[str] = Field(default_factory=list)
    detected_language: str = "tr"
    detected_intent: str = "qa"
    detected_category: Category | None = None
    detected_engine: str | None = None
    detected_genre: str | None = None


class RetrievedChunk(BaseModel):
    """Vektör veritabanından çekilen ve benzerlik skoru hesaplanan döküman parçası."""

    chunk_id: str
    text: str
    score: float
    metadata: DocumentMetadata
