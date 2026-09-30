"""Taksonomi ve sınıflandırma modelleri."""

from enum import Enum


class Category(str, Enum):
    """Ana bilgi kategorileri — MDA Framework + Schell's Elements bazlı."""

    # === MEKANİK (Mechanics) ===
    CORE_MECHANICS = "core_mechanics"           # Temel mekanikler, core loops
    GAME_SYSTEMS = "game_systems"               # Ekonomi, crafting, progression
    GAME_BALANCE = "game_balance"               # Denge, tuning, meta-game
    CONTROLS_INPUT = "controls_input"           # Kontrol şemaları, input handling

    # === DİNAMİK (Dynamics) ===
    LEVEL_DESIGN = "level_design"               # Seviye tasarımı, pacing, flow
    AI_DESIGN = "ai_design"                     # Oyun yapay zekası tasarımı
    MULTIPLAYER = "multiplayer"                 # Çok oyunculu tasarım

    # === ESTETİK (Aesthetics) ===
    NARRATIVE = "narrative"                     # Hikaye, dialog, world building
    UX_UI = "ux_ui"                             # Kullanıcı deneyimi/arayüzü
    AUDIO_DESIGN = "audio_design"               # Ses tasarımı
    VISUAL_DESIGN = "visual_design"             # Görsel yön, art direction

    # === OYUNCU (Player) ===
    PLAYER_PSYCHOLOGY = "player_psychology"     # Oyuncu motivasyonu, engagement
    PLAYER_TYPES = "player_types"               # Bartle, oyuncu profilleri
    ACCESSIBILITY = "accessibility"             # Erişilebilirlik

    # === İŞ (Business) ===
    MONETIZATION = "monetization"               # F2P, premium, battle pass
    MARKET_ANALYSIS = "market_analysis"         # Pazar trendleri, rekabet
    ANALYTICS = "analytics"                     # Oyuncu verileri, KPI'lar

    # === SÜREÇ (Process) ===
    GDD = "gdd"                                 # Game Design Document
    PROTOTYPING = "prototyping"                 # Prototipleme, playtesting
    POSTMORTEM = "postmortem"                   # Proje sonrası analizler

    # === TÜR-SPESİFİK (Genre-Specific) ===
    GENRE_RPG = "genre_rpg"
    GENRE_FPS = "genre_fps"
    GENRE_STRATEGY = "genre_strategy"
    GENRE_MOBILE = "genre_mobile"
    GENRE_PUZZLE = "genre_puzzle"
    GENRE_PLATFORMER = "genre_platformer"
    GENRE_SIMULATION = "genre_simulation"
    GENRE_OTHER = "genre_other"


class SourceType(str, Enum):
    """Kaynak türleri — güvenilirlik sıralamasına göre."""

    ACADEMIC_PAPER = "academic_paper"           # Tier 5 — En güvenilir
    BOOK = "book"                               # Tier 5
    GDC_TALK = "gdc_talk"                       # Tier 4
    POSTMORTEM = "postmortem"                   # Tier 4
    DEV_BLOG = "dev_blog"                       # Tier 3
    ARTICLE = "article"                         # Tier 3
    TUTORIAL = "tutorial"                       # Tier 2
    FORUM_DISCUSSION = "forum_discussion"       # Tier 1
    USER_SUBMITTED = "user_submitted"           # Tier 1 (doğrulanana kadar)


SOURCE_TIER_MAPPING: dict[SourceType, int] = {
    SourceType.ACADEMIC_PAPER: 5,
    SourceType.BOOK: 5,
    SourceType.GDC_TALK: 4,
    SourceType.POSTMORTEM: 4,
    SourceType.DEV_BLOG: 3,
    SourceType.ARTICLE: 3,
    SourceType.TUTORIAL: 2,
    SourceType.FORUM_DISCUSSION: 1,
    SourceType.USER_SUBMITTED: 1,
}


def get_default_tier_for_source(source_type: SourceType) -> int:
    """Verilen kaynak türü için varsayılan güvenilirlik katmanını döndürür (1-5)."""
    return SOURCE_TIER_MAPPING.get(source_type, 1)
