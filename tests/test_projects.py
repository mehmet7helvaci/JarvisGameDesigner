"""Tests for ProjectManager, BlendFileRef, GameProject, and two-way sync."""

from datetime import datetime, timezone
import os
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

import pytest

from game_designer.data.project_manager import ProjectManager
from game_designer.data.user_profile import UserProfileStore
from game_designer.models.project import BlendFileRef, GameProject, format_file_size
from game_designer.plugin import GameDesignerPlugin
from game_designer.utils.shortcut import create_desktop_shortcut, get_desktop_path, get_pythonw_executable
from plugin import JarvisGameDesignPlugin


# =============================================================================
# 1. BlendFileRef & File Size Tests
# =============================================================================

def test_format_file_size():
    """format_file_size fonksiyonunun doğru birim dönüşümleri yaptığını test eder."""
    assert format_file_size(0) == "0 B"
    assert format_file_size(-10) == "0 B"
    assert format_file_size(500) == "500 B"
    assert format_file_size(1024) == "1.0 KB"
    assert format_file_size(1024 * 1024) == "1.0 MB"
    assert format_file_size(15 * 1024 * 1024) == "15.0 MB"
    assert format_file_size(2 * 1024 * 1024 * 1024) == "2.0 GB"


def test_blend_file_ref_lifecycle(temp_dir):
    """BlendFileRef modelinin oluşturulmasını ve disk istatistiklerini kontrol eder."""
    real_file = temp_dir / "hero.blend"
    real_file.write_bytes(b"BLENDER_TEST_DATA" * 100)

    ref = BlendFileRef(
        name="hero.blend",
        file_path=str(real_file),
        category="Karakter",
        notes="Ana karakter 3D modeli",
    )

    assert ref.exists() is True
    ref.refresh_stats()
    assert ref.file_size_bytes == 1700
    assert "KB" in ref.file_size_formatted
    assert ref.last_modified is not None

    # Var olmayan dosya testi
    fake_ref = BlendFileRef(
        name="ghost.blend",
        file_path=str(temp_dir / "non_existent.blend"),
        category="Prop",
    )
    assert fake_ref.exists() is False
    assert fake_ref.refresh_stats() is False


# =============================================================================
# 2. GameProject Model Tests
# =============================================================================

def test_game_project_model_and_blend_operations(temp_dir):
    """GameProject modelinin blend dosyası ekleme, güncelleme ve silme mantığını test eder."""
    proj = GameProject(
        name="Cyberpunk Samurai",
        game_engine="Unreal Engine 5",
        genre="Action RPG",
        development_phase="prototype",
        description="Neon temalı aksiyon oyunu",
        key_features=["Katana Combat", "Cyber Dash"],
    )

    # ActiveProject dönüşümü
    active_model = proj.to_active_project()
    assert active_model.project_name == "Cyberpunk Samurai"
    assert active_model.game_engine == "Unreal Engine 5"
    assert active_model.key_features == ["Katana Combat", "Cyber Dash"]

    # Blend dosyası ekleme
    blend_path = str(temp_dir / "sword.blend")
    ref = BlendFileRef(name="sword.blend", file_path=blend_path, category="Prop")
    proj.add_or_update_blend_file(ref)
    assert len(proj.blend_files) == 1
    assert proj.get_blend_file(ref.id) is not None
    assert proj.get_blend_file(blend_path) is not None

    # Aynı yolla tekrar ekleme (güncelleme olmalı, çoğaltma değil)
    ref_updated = BlendFileRef(name="sword_v2.blend", file_path=blend_path, category="Silah")
    proj.add_or_update_blend_file(ref_updated)
    assert len(proj.blend_files) == 1
    assert proj.blend_files[0].category == "Silah"

    # Silme
    assert proj.remove_blend_file(ref.id) is True
    assert len(proj.blend_files) == 0
    assert proj.remove_blend_file("non_existent_id") is False


# =============================================================================
# 3. ProjectManager Operations Tests
# =============================================================================

def test_project_manager_crud_and_active_sync(test_settings, temp_dir):
    """ProjectManager CRUD işlemleri ve aktif proje eşzamanlama testleri."""
    pm = ProjectManager(settings=test_settings)
    assert test_settings.projects_dir.exists()

    # 1. Proje Oluşturma
    p1 = pm.create_project(
        name="Project Chrono",
        game_engine="Godot",
        genre="Metroidvania",
        development_phase="concept",
        description="Zaman manipülasyonu içeren 2D platform oyunu",
        key_features=["Time Rewind", "Shadow Clone"],
    )
    assert p1.name == "Project Chrono"
    # İlk oluşturulan proje otomatik aktif olur
    assert p1.is_active is True
    assert pm.get_active_project().id == p1.id

    # 2. İkinci Proje Oluşturma
    p2 = pm.create_project(
        name="Space Colony",
        game_engine="Unity",
        genre="Simulation",
        activate=False,
    )
    assert p2.name == "Space Colony"
    assert p2.is_active is False
    assert pm.get_active_project().id == p1.id  # P1 halen aktif

    # 3. Aynı isimde proje oluşturma hatası
    with pytest.raises(ValueError, match="zaten mevcut"):
        pm.create_project(name="Project Chrono")

    # 4. Boş isim hatası
    with pytest.raises(ValueError, match="boş olamaz"):
        pm.create_project(name="   ")

    # 5. Listeleme ve Sıralama (Aktif proje ilk sırada gelmeli)
    all_projs = pm.list_projects()
    assert len(all_projs) == 2
    assert all_projs[0].id == p1.id

    # 6. İsme ve ID'ye Göre Getirme (Case-insensitive)
    assert pm.get_project("project chrono") is not None
    assert pm.get_project(p2.id) is not None
    assert pm.get_project("Bilinmeyen Proje") is None

    # 7. Aktif Projeyi Değiştirme
    pm.set_active_project(p2.id)
    active = pm.get_active_project()
    assert active.id == p2.id
    assert active.name == "Space Colony"

    # UserProfileStore ile eşzamanlandı mı?
    profile = pm.user_profile_store.get_or_create_profile("default_user")
    assert profile.active_project is not None
    assert profile.active_project.project_name == "Space Colony"

    # 8. Proje Güncelleme
    updated = pm.update_project(
        p2.id,
        genre="Sci-Fi Colony Sim",
        notes="Alpha versiyonu hazırlandı.",
    )
    assert updated.genre == "Sci-Fi Colony Sim"
    assert updated.notes == "Alpha versiyonu hazırlandı."

    # 9. Silme ve Aktif Proje Temizliği
    assert pm.delete_project(p2.id) is True
    assert pm.get_project(p2.id) is None
    # Silinen proje aktifti, temizlendi mi?
    assert pm.get_active_project() is None


def test_project_manager_blend_files(test_settings, temp_dir):
    """ProjectManager Blender (.blend) dosyaları ekleme, getirme ve silme testleri."""
    pm = ProjectManager(settings=test_settings)
    proj = pm.create_project(name="Viking Odyssey", game_engine="Unreal")

    # Geçici sahte .blend dosyaları oluştur
    blend1_path = temp_dir / "viking_warrior.blend"
    blend1_path.write_bytes(b"BLEND_HEADER_V1" + b"\x00" * 2048)

    blend2_path = temp_dir / "longship.blend"
    blend2_path.write_bytes(b"BLEND_HEADER_V2" + b"\x00" * 4096)

    # Blend dosyası ekleme
    ref1 = pm.add_blend_file(
        project_name_or_id=proj.id,
        file_path=str(blend1_path),
        category="Karakter",
        notes="Savaşçı ana mesh",
    )
    assert ref1.name == "viking_warrior.blend"
    assert ref1.category == "Karakter"
    assert ref1.file_size_bytes > 0

    ref2 = pm.add_blend_file(
        project_name_or_id=proj.id,
        file_path=str(blend2_path),
        category="Araç",
    )
    assert ref2.category == "Araç"

    # Listeleme
    blends = pm.get_blend_files(proj.id)
    assert len(blends) == 2

    # Kategori filtreleme
    char_blends = pm.get_blend_files(proj.id, category="Karakter")
    assert len(char_blends) == 1
    assert char_blends[0].id == ref1.id

    # Kaldırma
    assert pm.remove_blend_file(proj.id, ref1.id) is True
    assert len(pm.get_blend_files(proj.id)) == 1

    # Olmayan dosya açma hatası
    with pytest.raises(FileNotFoundError):
        pm.open_blend_file("non_existent_file.blend")

    # Mevcut dosyayı açma testi (os.startfile mock ile)
    with patch("os.startfile", create=True) as mock_startfile:
        opened = pm.open_blend_file(ref2.id, project_name_or_id=proj.id)
        assert opened is True
        mock_startfile.assert_called_once()


# =============================================================================
# 4. GameDesignerPlugin & Two-Way Sync Integration Tests
# =============================================================================

def test_plugin_project_methods_and_two_way_sync(test_settings):
    """GameDesignerPlugin üzerinden proje işlemlerini ve Jarvis profil entegrasyonunu test eder."""
    plugin = GameDesignerPlugin(
        project_root=test_settings.project_root,
        data_dir=test_settings.data_dir,
        chroma_db_dir=test_settings.chroma_db_dir,
        user_profiles_dir=test_settings.user_profiles_dir,
        projects_dir=test_settings.projects_dir,
        seeds_dir=test_settings.seeds_dir,
    )
    plugin.initialize()

    # 1. Plugin üzerinden proje oluştur
    proj = plugin.create_project(
        name="Pixel Dungeon",
        game_engine="Unity",
        genre="Roguelike",
        key_features=["Procedural Generation", "Permadeath"],
        activate=True,
    )
    assert proj.name == "Pixel Dungeon"

    # 2. list_projects & get_active_project
    projects = plugin.list_projects()
    assert len(projects) == 1
    active = plugin.get_active_project()
    assert active is not None
    assert active.name == "Pixel Dungeon"

    # 3. Jarvis `set_user_active_project` çağrıldığında iki yönlü eşitleme testi
    # Farklı bir proje adı verilince ProjectManager'da otomatik proje oluşturulmalı ve aktif olmalı!
    plugin.set_user_active_project(
        user_id="jarvis_user",
        project_name="Neon Abyss 2",
        game_engine="Godot",
        genre="Platformer",
        key_features=["Fast Run", "Grappling Hook"],
    )

    # ProjectManager'da Neon Abyss 2 oluştu mu?
    p_synced = plugin.get_project("Neon Abyss 2")
    assert p_synced is not None
    assert p_synced.game_engine == "Godot"
    assert p_synced.is_active is True

    # UserProfileStore'a yansıdı mı?
    profile = plugin.get_user_profile("jarvis_user")
    assert profile.active_project is not None
    assert profile.active_project.project_name == "Neon Abyss 2"


@pytest.mark.asyncio
async def test_jarvis_root_plugin_intents(test_settings):
    """Kök JarvisGameDesignPlugin sınıfının niyet işleme döngüsünü test eder."""
    plugin = JarvisGameDesignPlugin(
        project_root=test_settings.project_root,
        data_dir=test_settings.data_dir,
        chroma_db_dir=test_settings.chroma_db_dir,
        user_profiles_dir=test_settings.user_profiles_dir,
        projects_dir=test_settings.projects_dir,
        seeds_dir=test_settings.seeds_dir,
    )
    plugin.initialize(auto_load_seeds=False)

    # 1. Başlangıçta boş proje listesi intenti
    resp = await plugin.process_intent("projeleri listele")
    assert "Henüz kayıtlı bir oyun tasarımı projesi bulunmuyor" in resp

    # 2. Proje oluştur
    plugin.create_project(name="Mecha Storm", game_engine="Unreal", genre="Action", activate=True)

    # 3. Projeleri listele
    resp = await plugin.process_intent("projeleri listele")
    assert "Mecha Storm" in resp
    assert "[AKTİF]" in resp

    # 4. Aktif proje intenti
    resp_active = await plugin.process_intent("aktif proje")
    assert "Mecha Storm" in resp_active
    assert "Unreal" in resp_active


# =============================================================================
# 5. Desktop Shortcut Creation Tests
# =============================================================================

def test_shortcut_utility_paths_and_creation(temp_dir):
    """Masaüstü kısayolu oluşturma fonksiyonunun doğru çalıştığını test eder."""
    desktop = get_desktop_path()
    assert desktop is not None
    assert desktop.exists()

    pyw = get_pythonw_executable()
    assert pyw is not None
    assert "python" in pyw.lower()

    # İzole geçici klasörde kısayol oluşturma testi
    target_lnk = temp_dir / "Test Shortcut.lnk"
    fake_script = temp_dir / "test_gui.pyw"
    fake_script.write_text("# fake script", encoding="utf-8")

    created = create_desktop_shortcut(
        shortcut_path=target_lnk,
        target_script=fake_script,
        working_dir=temp_dir,
        description="Test LNK",
    )
    assert created.exists()
    assert created.stat().st_size > 0


# =============================================================================
# 6. Edge Cases & Boundary Conditions
# =============================================================================

def test_project_manager_edge_cases(test_settings, temp_dir):
    """Türkçe karakterler, bozuk dosyalar, çakışan adlar ve uç durum testleri."""
    pm = ProjectManager(settings=test_settings)

    # 1. Türkçe karakter ve sembol içeren proje adı
    tr_name = "Kayıp Şehir: Örümceğin Laneti & İntikam (2026)"
    p_tr = pm.create_project(name=tr_name, game_engine="Unreal Engine 5", genre="RPG")
    assert p_tr.name == tr_name
    assert pm.get_project(tr_name) is not None

    # 2. Boşluk ve Türkçe karakterli Blend dosyası
    tr_blend = temp_dir / "ana_kahraman_şövalye v1.2.blend"
    tr_blend.write_bytes(b"BLEND_TR_HEADER")
    ref = pm.add_blend_file(p_tr.id, str(tr_blend), category="Karakter", notes="Türkçe karakter testi")
    assert ref.name == "ana_kahraman_şövalye v1.2.blend"
    assert ref.exists() is True

    # 3. Var olmayan projeyi aktif yapma hatası
    with pytest.raises(ValueError, match="bulunamadı"):
        pm.set_active_project("non_existent_project_id_123")

    # 4. İkinci proje oluşturup, ilk projenin adını ikinciyle çakıştıracak şekilde güncellemeye çalışma
    p2 = pm.create_project(name="İkinci Proje")
    with pytest.raises(ValueError, match="başka bir proje zaten mevcut"):
        pm.update_project(p2.id, name=tr_name)

    # 5. Bozuk active_project.json dosyasından toparlanma
    active_file = test_settings.projects_dir / "active_project.json"
    active_file.write_text("{CORRUPTED_JSON", encoding="utf-8")
    # Bozuk json varken get_active_project çökmemeli, None veya fallback dönmeli
    active = pm.get_active_project()
    assert active is None or active.id == p_tr.id

    # 6. Projede olmayan blend dosyasını kaldırma
    assert pm.remove_blend_file(p_tr.id, "fake_blend_id") is False
    assert pm.remove_blend_file("fake_proj_id", ref.id) is False


@pytest.mark.asyncio
async def test_jarvis_intents_edge_cases(test_settings, temp_dir):
    """Intent işleme uç durumları: boş projeler, blend dosyaları olmayan proje, vb."""
    plugin = JarvisGameDesignPlugin(
        project_root=test_settings.project_root,
        data_dir=test_settings.data_dir,
        chroma_db_dir=test_settings.chroma_db_dir,
        user_profiles_dir=test_settings.user_profiles_dir,
        projects_dir=test_settings.projects_dir,
        seeds_dir=test_settings.seeds_dir,
    )
    plugin.initialize(auto_load_seeds=False)

    # Aktif proje yokken blend dosyaları intenti
    resp = await plugin.process_intent("blend dosyaları")
    assert "önce bir proje seçilmelidir" in resp

    # Proje var ama blend dosyası yokken
    p = plugin.create_project(name="Boş Proje", activate=True)
    resp2 = await plugin.process_intent("blend dosyaları")
    assert "henüz eklenmiş .blend dosyası yok" in resp2

    # Blend dosyası eklendikten sonra
    b_file = temp_dir / "test.blend"
    b_file.write_bytes(b"XYZ")
    plugin.add_blend_file(p.id, str(b_file), category="Prop")
    resp3 = await plugin.process_intent("blend dosyaları")
    assert "test.blend" in resp3
    assert "[Prop]" in resp3


def test_blend_path_slashes_and_case_insensitivity(test_settings, temp_dir):
    """Eğik çizgi (/ vs \\), büyük/küçük harf ID ve dosya adı eşleşmesini test eder."""
    pm = ProjectManager(settings=test_settings)
    proj = pm.create_project(name="Slash Test Project")

    fake_file = temp_dir / "models" / "character.blend"
    fake_file.parent.mkdir(parents=True, exist_ok=True)
    fake_file.write_bytes(b"BLEND")

    ref = pm.add_blend_file(
        project_name_or_id=proj.id,
        file_path=str(fake_file),
        category="Karakter",
    )
    proj = pm.get_project(proj.id)
    assert proj is not None

    # 1. Forward slash ile get_blend_file
    forward_path = str(fake_file).replace("\\", "/")
    assert proj.get_blend_file(forward_path) is not None
    assert proj.get_blend_file(forward_path).id == ref.id

    # 2. Case-insensitive ID ile get_blend_file
    assert proj.get_blend_file(ref.id.upper()) is not None
    assert proj.get_blend_file(ref.id.lower()) is not None

    # 3. Yalnızca dosya adı ile get_blend_file
    assert proj.get_blend_file("character.blend") is not None
    assert proj.get_blend_file("CHARACTER.BLEND") is not None

    # 4. Forward slash ile remove_blend_file
    assert pm.remove_blend_file(proj.id, forward_path) is True
    assert len(pm.get_blend_files(proj.id)) == 0


def test_list_projects_mixed_datetimes(test_settings):
    """Zaman dilimi bilgisi olan ve olmayan (naive/aware) tarihlerde listelemenin çökmediğini doğrular."""
    pm = ProjectManager(settings=test_settings)

    # Birinci proje aware datetime ile
    p1 = pm.create_project(name="Aware Project")
    p1.updated_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    pm.save_project(p1)

    # İkinci proje naive datetime ile JSON'a yaz
    path2 = pm._get_project_path("naive_proj")
    naive_data = {
        "id": "naive_proj",
        "name": "Naive Project",
        "created_at": "2025-06-01T10:00:00",
        "updated_at": "2025-06-01T10:00:00",  # timezone offsetsiz
        "blend_files": [],
        "is_active": False,
    }
    path2.write_text(__import__("json").dumps(naive_data), encoding="utf-8")

    # list_projects çökmeden sıralamalıdır
    projects = pm.list_projects()
    assert len(projects) >= 2
    names = [p.name for p in projects]
    assert "Aware Project" in names
    assert "Naive Project" in names


def test_desktop_shortcut_turkish_characters_exact_target(temp_dir):
    """Masaüstü kısayolunun Türkçe karakter içeren yollarda bozulmadan oluşturulduğunu doğrular."""
    tr_dir = temp_dir / "OneDrive" / "Masaüstü Klasörü"
    tr_dir.mkdir(parents=True, exist_ok=True)

    fake_target = tr_dir / "başlatıcı_uygulama.pyw"
    fake_target.write_text("# fake", encoding="utf-8")

    shortcut_lnk = tr_dir / "Jarvis Test Kısayol.lnk"
    created = create_desktop_shortcut(
        shortcut_path=shortcut_lnk,
        target_script=fake_target,
        working_dir=tr_dir,
        description="Türkçe Karakter Test Kısayolu",
    )
    assert created.exists()
    assert created.stat().st_size > 0

    if sys.platform == "win32":
        import base64
        import subprocess

        inspect_ps = f"""
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$w = New-Object -ComObject WScript.Shell
$s = $w.CreateShortcut("{str(created.resolve())}")
Write-Output "ARGS: $($s.Arguments)"
Write-Output "DIR: $($s.WorkingDirectory)"
"""
        b64 = base64.b64encode(inspect_ps.encode("utf-16le")).decode("ascii")
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", b64],
            capture_output=True,
        )
        out = res.stdout.decode("utf-8", errors="replace")
        assert "Masaüstü Klasörü" in out
        assert "başlatıcı_uygulama.pyw" in out


@pytest.mark.asyncio
async def test_jarvis_intents_active_project_switch(test_settings):
    """Jarvis üzerinden 'aktif proje yap' veya 'proje seç' ile aktif projenin değiştirilebildiğini test eder."""
    plugin = JarvisGameDesignPlugin(
        project_root=test_settings.project_root,
        data_dir=test_settings.data_dir,
        chroma_db_dir=test_settings.chroma_db_dir,
        user_profiles_dir=test_settings.user_profiles_dir,
        projects_dir=test_settings.projects_dir,
        seeds_dir=test_settings.seeds_dir,
    )
    plugin.initialize(auto_load_seeds=False)

    plugin.create_project(name="Project Alpha", activate=True)
    plugin.create_project(name="Project Beta", activate=False)

    assert plugin.get_active_project().name == "Project Alpha"

    # Jarvis intent ile Project Beta'yı aktif yap
    resp = await plugin.process_intent("aktif proje yap", entities={"project_name": "Project Beta"})
    assert "başarıyla 'Project Beta' olarak belirlendi" in resp
    assert plugin.get_active_project().name == "Project Beta"


def test_open_blend_file_with_blender_fallback(test_settings, temp_dir):
    """open_blend_file'ın sistemde .blend ilişkisi yoksa find_blender_executable fallback'ine gittiğini test eder."""
    pm = ProjectManager(settings=test_settings)
    blend_file = temp_dir / "cube.blend"
    blend_file.write_bytes(b"TEST_BLEND")

    # 1. os.startfile WinError 1155 üretirse ve blender bulunursa subprocess çağrılır
    with patch("os.startfile", side_effect=OSError(1155, "No association")):
        with patch("game_designer.data.project_manager.find_blender_executable", return_value="C:\\fake\\blender.exe"):
            with patch("subprocess.Popen") as mock_popen:
                success = pm.open_blend_file(str(blend_file))
                assert success is True
                mock_popen.assert_called_once_with(["C:\\fake\\blender.exe", str(blend_file.resolve())])

    # 2. os.startfile WinError 1155 üretir ve blender bulunamazsa anlaşılır hata fırlatılır
    with patch("os.startfile", side_effect=OSError(1155, "No association")):
        with patch("game_designer.data.project_manager.find_blender_executable", return_value=None):
            with pytest.raises(RuntimeError, match="Blender kurulu olmayabilir"):
                pm.open_blend_file(str(blend_file))


