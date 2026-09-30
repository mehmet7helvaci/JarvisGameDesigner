"""Kullanıcı profili ve hafıza veri modelleri."""

from datetime import datetime, timezone
from pydantic import BaseModel, Field


class ActiveProject(BaseModel):
    """Kullanıcının aktif olarak geliştirdiği proje bilgisi."""

    project_name: str
    game_engine: str | None = None       # Unity, Unreal, Godot vb.
    genre: str | None = None             # RPG, FPS, puzzle vb.
    development_phase: str | None = None # concept, prototype, production, polish
    key_features: list[str] = Field(default_factory=list)
    known_challenges: list[str] = Field(default_factory=list)
    notes: str = ""


class InteractionSummary(BaseModel):
    """Geçmiş etkileşim özeti."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    query: str
    mode: str
    summary: str = ""


class UserProfile(BaseModel):
    """Kullanıcı profil verisi — cevapları kişiselleştirmek için."""

    # Kimlik
    user_id: str
    display_name: str

    # Tercihler
    preferred_language: str = "tr"
    preferred_game_engines: list[str] = Field(default_factory=list)
    preferred_genres: list[str] = Field(default_factory=list)
    experience_level: str = "intermediate"  # beginner / intermediate / advanced

    # Aktif Proje
    active_project: ActiveProject | None = None

    # Geçmiş
    interaction_history: list[InteractionSummary] = Field(default_factory=list)
    favorite_topics: list[str] = Field(default_factory=list)

    # Sistem
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
