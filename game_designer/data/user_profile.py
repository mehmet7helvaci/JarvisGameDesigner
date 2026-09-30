"""Kullanıcı profili ve hafıza depolama yöneticisi."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from game_designer.config import Settings, get_settings
from game_designer.models.user_profile import ActiveProject, InteractionSummary, UserProfile
from game_designer.utils.logger import logger
from game_designer.utils.text_utils import extract_keywords

KNOWN_ENGINES = ["unity", "unreal", "unreal engine", "godot", "gamemaker", "defold", "bevy", "roblox"]
KNOWN_GENRES = ["rpg", "fps", "roguelike", "roguelite", "puzzle", "platformer", "strategy", "moba", "survival", "horror", "simulation", "metroidvania", "deckbuilder"]


class UserProfileStore:
    """Kullanıcı profillerini JSON tabanlı yerel diskte saklayan ve yöneten sınıf."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.storage_dir = self.settings.user_profiles_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_profile_path(self, user_id: str) -> Path:
        """Güvenli dosya yolu üretir."""
        safe_id = re.sub(r"[^\w\-]", "_", user_id)
        return self.storage_dir / f"{safe_id}.json"

    def get_or_create_profile(self, user_id: str = "default_user", display_name: str = "Developer") -> UserProfile:
        """Belirtilen kullanıcı profilini getirir, yoksa yenisini oluşturup kaydeder."""
        path = self._get_profile_path(user_id)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return UserProfile.model_validate(data)
            except Exception as e:
                logger.error(f"Profil okuma hatası ({path}): {e}. Yeni profil oluşturuluyor.")

        # Yeni profil oluştur
        now = datetime.now(timezone.utc)
        profile = UserProfile(
            user_id=user_id,
            display_name=display_name,
            preferred_language="tr",
            created_at=now,
            updated_at=now,
        )
        self.save_profile(profile)
        return profile

    def save_profile(self, profile: UserProfile) -> None:
        """Profili diske kaydeder."""
        path = self._get_profile_path(profile.user_id)
        profile.updated_at = datetime.now(timezone.utc)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json_str = profile.model_dump_json(indent=2)
                f.write(json_str)
        except Exception as e:
            logger.error(f"Profil kaydedilirken hata: {e}")

    def update_active_project(self, user_id: str, project: ActiveProject) -> UserProfile:
        """Aktif proje bilgisini günceller."""
        profile = self.get_or_create_profile(user_id)
        profile.active_project = project
        self.save_profile(profile)
        logger.info(f"Kullanıcı '{user_id}' için aktif proje güncellendi: {project.project_name}")
        return profile

    def record_interaction(self, user_id: str, query: str, mode: str, summary: str = "") -> None:
        """Etkileşimi geçmişe kaydeder ve profili günceller."""
        profile = self.get_or_create_profile(user_id)

        # Son 50 etkileşimi koru
        item = InteractionSummary(
            timestamp=datetime.now(timezone.utc),
            query=query[:200],
            mode=mode,
            summary=summary[:300] if summary else "",
        )
        profile.interaction_history.append(item)
        if len(profile.interaction_history) > 50:
            profile.interaction_history = profile.interaction_history[-50:]

        # Konu takibi
        keywords = extract_keywords(query, max_keywords=3)
        for kw in keywords:
            if kw not in profile.favorite_topics:
                profile.favorite_topics.append(kw)
        if len(profile.favorite_topics) > 10:
            profile.favorite_topics = profile.favorite_topics[-10:]

        # Sorgudan tercih edilen motor veya tür sezme
        self._extract_preferences_from_text(profile, query)

        self.save_profile(profile)

    def _extract_preferences_from_text(self, profile: UserProfile, text: str) -> None:
        """Sorgu metninden motor veya tür tercihlerini otomatik sezerek profile ekler."""
        text_lower = text.lower()
        for engine in KNOWN_ENGINES:
            if engine in text_lower:
                title_engine = engine.title()
                if title_engine not in profile.preferred_game_engines:
                    profile.preferred_game_engines.append(title_engine)

        for genre in KNOWN_GENRES:
            if genre in text_lower:
                upper_genre = genre.upper() if len(genre) <= 3 else genre.title()
                if upper_genre not in profile.preferred_genres:
                    profile.preferred_genres.append(upper_genre)
