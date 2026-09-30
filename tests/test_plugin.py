"""Jarvis Game Designer Plugin ana sınıfı testleri."""

import pytest
from game_designer.models.taxonomy import Category, SourceType
from game_designer.plugin import GameDesignerPlugin


def test_plugin_lifecycle_and_capabilities(test_settings):
    plugin = GameDesignerPlugin(
        project_root=test_settings.project_root,
        data_dir=test_settings.data_dir,
        chroma_db_dir=test_settings.chroma_db_dir,
        user_profiles_dir=test_settings.user_profiles_dir,
        seeds_dir=test_settings.seeds_dir,
    )

    assert plugin.name == "game_designer"
    assert plugin.version == "0.1.0"
    assert len(plugin.get_capabilities()) == 8

    # Başlatma
    init_res = plugin.initialize()
    assert init_res is True

    # Kapatma
    plugin.shutdown()


def test_plugin_ingest_and_query_flow(test_settings):
    plugin = GameDesignerPlugin(
        project_root=test_settings.project_root,
        data_dir=test_settings.data_dir,
        chroma_db_dir=test_settings.chroma_db_dir,
        user_profiles_dir=test_settings.user_profiles_dir,
        seeds_dir=test_settings.seeds_dir,
    )
    plugin.initialize()

    # Döküman ekle
    added = plugin.ingest_text(
        title="Hades Progression Systems",
        content=(
            "# Hades Meta-Progression\n\n"
            "Hades blends rogue-lite permadeath with persistent narrative progression (Mirror of Night). "
            "Every death advances relationships with Olympic gods and provides Darkness for stat increases."
        ),
        category=Category.GAME_SYSTEMS,
        tags=["hades", "roguelike", "progression"],
        source_type=SourceType.GDC_TALK,
    )
    assert added >= 1

    # Soru sor
    res = plugin.query("Hades oyununda meta-progression ve permadeath nasıl çalışır?")
    assert res.confidence >= 50.0
    assert "Hades" in res.text
    assert len(res.sources) >= 1

    # Jarvis handle_query formatı
    dict_res = plugin.handle_query("Hades progression")
    assert "text" in dict_res
    assert "confidence" in dict_res
    assert "mode" in dict_res


def test_plugin_active_project_and_advisor(test_settings):
    plugin = GameDesignerPlugin(
        project_root=test_settings.project_root,
        data_dir=test_settings.data_dir,
        chroma_db_dir=test_settings.chroma_db_dir,
        user_profiles_dir=test_settings.user_profiles_dir,
        seeds_dir=test_settings.seeds_dir,
    )
    plugin.initialize()

    # Aktif proje ata
    plugin.set_user_active_project(
        user_id="user_test_99",
        project_name="Neon Samurai",
        game_engine="Godot",
        genre="Platformer",
        key_features=["Wall running", "Katana deflection"],
    )

    profile = plugin.get_user_profile("user_test_99")
    assert profile.active_project is not None
    assert profile.active_project.project_name == "Neon Samurai"
    assert profile.active_project.game_engine == "Godot"

    # İlgili mekanik dokümanını ekle
    plugin.ingest_text(
        title="Platformer Movement and Wall Run Mechanics",
        content=(
            "# Wall Running Design in 2D/3D Platformers\n\n"
            "Wall running requires defining entry angle thresholds, stickiness, surface normals, and raycast checks. "
            "In Godot, RayCast nodes can test wall normal vectors to preserve momentum and jump buffering."
        ),
        category=Category.CORE_MECHANICS,
        tags=["wall_running", "platformer", "movement", "godot"],
        source_type=SourceType.GDC_TALK,
    )

    # Danışmanlık iste
    advice = plugin.advise(
        "Karakterin duvarda koşma (wall run) mekaniğini yapıyorum, açıları nasıl ayarlamalıyım?",
        user_id="user_test_99",
    )
    assert advice is not None
    assert advice.mode == "advise"
    assert advice.is_fallback is False
    assert advice.confidence >= 50.0
    assert "Godot" in advice.text
    assert len(advice.sources) >= 1


def test_canonical_11_2_examples_with_seed_data(test_settings):
    """kurallar.md Bölüm 11.2'de sunulan örnek sorguların eksiksiz ve doğrulanmış çalıştığını teyit eder."""
    # Gerçek seed dizinini kullanarak plugin'i başlat
    from game_designer.config import PROJECT_ROOT

    plugin = GameDesignerPlugin(
        project_root=test_settings.project_root,
        data_dir=test_settings.data_dir,
        chroma_db_dir=test_settings.chroma_db_dir,
        user_profiles_dir=test_settings.user_profiles_dir,
        seeds_dir=PROJECT_ROOT / "seeds",
    )
    plugin.initialize(auto_load_seeds=True)

    # 1. Soru-Cevap (11.2)
    resp_qa = plugin.query("Core loop nasıl tasarlanır?")
    assert resp_qa.confidence >= 50.0
    assert resp_qa.is_fallback is False
    assert len(resp_qa.sources) >= 1

    # 2. Oyun Analizi (11.2)
    resp_analysis = plugin.analyze_game("Hades")
    assert resp_analysis.mode == "analyze_game"
    assert resp_analysis.confidence >= 50.0
    assert resp_analysis.is_fallback is False

    # 3. Beyin Fırtınası (11.2)
    resp_brainstorm = plugin.brainstorm(
        "Roguelike bir oyunda kalıcı progression sistemi",
        context={"engine": "Unity", "genre": "roguelike"},
    )
    assert resp_brainstorm.mode == "brainstorm"
    assert resp_brainstorm.confidence >= 50.0
    assert resp_brainstorm.is_fallback is False

    # 4. Aktif Danışmanlık (11.2)
    resp_advise = plugin.advise(
        "Karakterin yürüme animasyonlarını yapıyorum, inverse kinematics kullanıyorum"
    )
    assert resp_advise.mode == "advise"
    assert resp_advise.confidence >= 50.0
    assert resp_advise.is_fallback is False
    assert len(resp_advise.sources) >= 1

    plugin.shutdown()
