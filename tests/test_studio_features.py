"""Comprehensive Tests for Jarvis Game Designer Studio Overhaul.

Covers:
1. Auto-categorization heuristics for 3D/animation formats (.blend, .fbx, .obj, .gltf, .glb, .bvh, .dae).
2. Instant asset addition & drag-and-drop handler without blocking dialogs.
3. 3D Viewport canvas, camera projection, OBJ parsing, BVH skeleton parsing, and Blender thumbnail extraction.
4. High-speed AI advisor optimizations (LRU query cache, parallel retrieval, streaming text, pre-warming).
5. Custom icon existence and desktop shortcut creation with icon location.
"""

from collections import OrderedDict
import io
from pathlib import Path
import struct
import tkinter as tk
from unittest.mock import MagicMock, patch
from PIL import Image
import pytest

from game_designer.core.rag_engine import RagEngine
from game_designer.data.embedding_manager import EmbeddingManager
from game_designer.models.project import (
    SUPPORTED_3D_EXTENSIONS,
    BlendFileRef,
    detect_asset_category,
)
from game_designer.models.response import GameDesignerResponse
from game_designer.ui.app import DarkTheme, GameDesignerApp
from game_designer.ui.viewport import (
    Viewport3DCanvas,
    extract_blend_thumbnail,
    generate_category_mesh,
    generate_default_3d_mesh,
    get_animated_skeleton_bones,
    parse_bvh_skeleton,
    parse_glb_or_gltf,
    parse_obj_mesh,
)
from game_designer.utils.shortcut import create_desktop_shortcut





# =============================================================================
# 1. AUTO-CATEGORIZATION HEURISTICS TESTS
# =============================================================================

def test_detect_asset_category_all_types():
    """Tüm 3D ve animasyon dosya adlarının doğru kategorilere otomatik eşlendiğini test eder."""
    # Animasyonlar (.bvh veya anahtar kelimeler)
    assert detect_asset_category("hero_walk_cycle.fbx") == "Animasyon"
    assert detect_asset_category("run_forward.bvh") == "Animasyon"
    assert detect_asset_category("zombie_crawl_anim.blend") == "Animasyon"
    assert detect_asset_category("idle_pose.gltf") == "Animasyon"
    assert detect_asset_category("dance_celebration.glb") == "Animasyon"

    # Karakterler
    assert detect_asset_category("warrior_hero.blend") == "Karakter"
    assert detect_asset_category("goblin_enemy.obj") == "Karakter"
    assert detect_asset_category("npc_villager.dae") == "Karakter"
    assert detect_asset_category("boss_creature.fbx") == "Karakter"

    # Çevre / Seviye
    assert detect_asset_category("dungeon_room_01.glb") == "Çevre/Level"
    assert detect_asset_category("forest_terrain.blend") == "Çevre/Level"
    assert detect_asset_category("castle_building.obj") == "Çevre/Level"
    assert detect_asset_category("sci_fi_map.gltf") == "Çevre/Level"

    # Prop / Nesne
    assert detect_asset_category("iron_sword.obj") == "Prop"
    assert detect_asset_category("wooden_chest_prop.fbx") == "Prop"
    assert detect_asset_category("laser_gun.blend") == "Prop"
    assert detect_asset_category("healing_potion_item.dae") == "Prop"

    # Araç
    assert detect_asset_category("sports_car.blend") == "Araç"
    assert detect_asset_category("pirate_ship.fbx") == "Araç"
    assert detect_asset_category("tank_heavy.obj") == "Araç"

    # VFX
    assert detect_asset_category("fire_explosion_fx.blend") == "VFX/Diğer"
    assert detect_asset_category("smoke_particle.fbx") == "VFX/Diğer"

    # Genel / Varsayılan
    assert detect_asset_category("misc_asset_12.blend") == "Genel"


def test_supported_extensions_set():
    """Desteklenen 3D format uzantıları kümesini doğrular."""
    assert ".blend" in SUPPORTED_3D_EXTENSIONS
    assert ".fbx" in SUPPORTED_3D_EXTENSIONS
    assert ".obj" in SUPPORTED_3D_EXTENSIONS
    assert ".gltf" in SUPPORTED_3D_EXTENSIONS
    assert ".glb" in SUPPORTED_3D_EXTENSIONS
    assert ".dae" in SUPPORTED_3D_EXTENSIONS
    assert ".bvh" in SUPPORTED_3D_EXTENSIONS


# =============================================================================
# 2. INSTANT ASSET ADDITION & UI INTEGRATION TESTS
# =============================================================================

def test_instant_asset_addition_without_dialogs(tk_root, test_settings, temp_dir):
    """Tek tıkla veya sürükle-bırak ile varlık eklemenin form açmadan anında gerçekleştiğini test eder."""
    app = GameDesignerApp(tk_root, settings=test_settings)
    proj = app.plugin.create_project(name="Instant Add Studio Test", activate=True)
    app._refresh_all_data()

    # Sahte bir FBX animasyon dosyası oluştur
    anim_file = temp_dir / "warrior_run_cycle.fbx"
    anim_file.write_bytes(b"FBX_MOCK_ANIMATION_DATA" * 50)

    # Anında ekleme fonksiyonunu çağır
    app._handle_instant_asset_add(str(anim_file))

    # Projede dosya var mı ve kategorisi 'Animasyon' mu?
    updated_proj = app.plugin.get_project(proj.id)
    assert len(updated_proj.blend_files) == 1
    added_asset = updated_proj.blend_files[0]
    assert added_asset.name == "warrior_run_cycle.fbx"
    assert added_asset.category == "Animasyon"
    assert added_asset.file_format == "fbx"

    # Viewport'un güncellendiğini doğrula
    assert app.viewport_3d.current_file_path == anim_file
    assert app.viewport_3d.current_format == ".fbx"


def test_multiple_files_dropped_handling(tk_root, test_settings, temp_dir):
    """Sürükle-bırak olayının birden çok dosyayı tek seferde başarıyla eklediğini test eder."""
    app = GameDesignerApp(tk_root, settings=test_settings)
    proj = app.plugin.create_project(name="Drop Multi Test", activate=True)
    app._refresh_all_data()

    f1 = temp_dir / "hero_model.blend"
    f1.write_bytes(b"B1")
    f2 = temp_dir / "dungeon_map.glb"
    f2.write_bytes(b"B2")
    f3 = temp_dir / "magic_sword.obj"
    f3.write_bytes(b"v 0 0 0\nv 1 1 1\nf 1 2\n")

    app._on_files_dropped([str(f1), str(f2), str(f3)])

    updated = app.plugin.get_project(proj.id)
    assert len(updated.blend_files) == 3
    cats = {b.name: b.category for b in updated.blend_files}
    assert cats["hero_model.blend"] == "Karakter"
    assert cats["dungeon_map.glb"] == "Çevre/Level"
    assert cats["magic_sword.obj"] == "Prop"


# =============================================================================
# 3. 3D VIEWPORT & BLENDER THUMBNAIL TESTS
# =============================================================================

def test_obj_mesh_parsing_and_normalization(temp_dir):
    """OBJ dosyası tepe ve yüzeylerinin doğru ayrıştırılıp merkezlendiğini test eder."""
    obj_file = temp_dir / "test_cube.obj"
    obj_content = (
        "v -1.0 -1.0 1.0\n"
        "v 1.0 -1.0 1.0\n"
        "v -1.0 1.0 1.0\n"
        "v 1.0 1.0 1.0\n"
        "f 1 2 4 3\n"
    )
    obj_file.write_text(obj_content, encoding="utf-8")

    vertices, faces = parse_obj_mesh(obj_file)
    assert len(vertices) == 4
    assert len(faces) == 1
    assert faces[0] == [0, 1, 3, 2]
    # Normalizasyon sonucu koordinatlar [-1.5, 1.5] aralığında olmalı
    for vx, vy, vz in vertices:
        assert abs(vx) <= 1.5
        assert abs(vy) <= 1.5
        assert abs(vz) <= 1.5


def test_bvh_skeleton_parsing(temp_dir):
    """BVH iskelet kemiklerinin ve eklem ofsetlerinin ayrıştırıldığını test eder."""
    bvh_file = temp_dir / "test_anim.bvh"
    bvh_content = (
        "HIERARCHY\n"
        "ROOT Hips\n"
        "{\n"
        "  OFFSET 0.0 0.0 0.0\n"
        "  CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation\n"
        "  JOINT Chest\n"
        "  {\n"
        "    OFFSET 0.0 5.0 0.0\n"
        "  }\n"
        "}\n"
        "MOTION\n"
        "Frames: 1\n"
    )
    bvh_file.write_text(bvh_content, encoding="utf-8")

    bones = parse_bvh_skeleton(bvh_file)
    assert len(bones) >= 1


def test_extract_blend_thumbnail_with_mock_test_block(temp_dir):
    """Blender dosyası TEST bloğu okuyucusunun küçük resmi çıkardığını test eder."""
    blend_file = temp_dir / "thumb_test.blend"

    # 12-byte Blender başlığı (64-bit, little endian, v4.0)
    header = b"BLENDER-v400"

    # TEST bloğu: 4 byte 'TEST', 4 byte size, 8 byte pointer, 4 byte sdna, 4 byte count
    # Resim: 16x16 RGBA
    w, h = 16, 16
    pixel_data = b"\x00\xff\xcc\xff" * (w * h)
    payload = struct.pack("<II", w, h) + pixel_data
    block_size = len(payload)

    block_header = b"TEST" + struct.pack("<I", block_size) + (b"\x00" * 16)
    endb = b"ENDB" + (b"\x00" * 20)

    blend_file.write_bytes(header + block_header + payload + endb)

    img = extract_blend_thumbnail(blend_file)
    assert img is not None
    assert img.size == (16, 16)


def test_viewport_canvas_rotation_and_zoom(tk_root):
    """Viewport3DCanvas bileşeninin döndürme ve yakınlaştırma matematiklerini doğrular."""
    vp = Viewport3DCanvas(tk_root)
    initial_yaw = vp.yaw
    initial_pitch = vp.pitch
    initial_zoom = vp.zoom

    # Fare sürükleme simülasyonu
    vp._last_mouse_x = 100
    vp._last_mouse_y = 100
    vp._is_dragging = True

    event = MagicMock()
    event.x = 150
    event.y = 80
    vp._on_mouse_drag(event)

    assert vp.yaw != initial_yaw
    assert vp.pitch != initial_pitch

    # Yakınlaştırma
    vp._zoom(1.2)
    assert vp.zoom > initial_zoom

    # Sıfırlama
    vp.reset_camera()
    assert vp.yaw == initial_yaw
    assert vp.pitch == initial_pitch


# =============================================================================
# 4. HIGH-SPEED AI ADVISOR OPTIMIZATION TESTS
# =============================================================================

def test_lru_query_cache_instant_repeated_response(test_settings):
    """RagEngine bellek içi LRU önbelleğinin tekrarlanan sorguları anında döndürdüğünü test eder."""
    engine = RagEngine(settings=test_settings)

    q = "Platform oyunlarında zıplama mekaniği ivmesi nasıl olmalıdır?"

    # İlk sorgu: normal işleme
    res1 = engine.process_query(q, mode="query")
    assert res1.text
    assert len(engine._query_cache) == 1

    # İkinci sorgu: önbellekten doğrudan ve anında dönmeli
    res2 = engine.process_query(q, mode="query")
    assert res2.text == res1.text
    assert res2.confidence == res1.confidence


def test_embedding_manager_pre_warm(test_settings):
    """EmbeddingManager.pre_warm fonksiyonunun hatasız modeli ısıttığını test eder."""
    em = EmbeddingManager(settings=test_settings)
    assert em._model is None
    em.pre_warm()
    assert em._model is not None


def test_query_stream_generation(test_settings):
    """process_query_stream fonksiyonunun cevabı kelime/token akışı olarak ürettiğini test eder."""
    engine = RagEngine(settings=test_settings)
    q = "Roguelike oyunlarında permadeath dengesi"

    tokens = list(engine.process_query_stream(q, mode="query"))
    assert len(tokens) > 5
    full_streamed_text = "".join(tokens)
    assert len(full_streamed_text) > 20


# =============================================================================
# 5. CUSTOM ICON & DESKTOP SHORTCUT TESTS
# =============================================================================

def test_custom_studio_icon_files_exist():
    """Özel fütüristik stüdyo ikon dosyalarının oluşturulduğunu ve geçerli olduğunu doğrular."""
    assets_dir = Path(__file__).resolve().parent.parent / "assets"
    ico_file = assets_dir / "icon.ico"
    png_file = assets_dir / "icon.png"

    assert ico_file.is_file()
    assert ico_file.stat().st_size > 0

    assert png_file.is_file()
    assert png_file.stat().st_size > 0

    # PNG resim boyutunu kontrol et
    img = Image.open(png_file)
    assert img.size == (256, 256)


def test_desktop_shortcut_uses_custom_icon(temp_dir):
    """Masaüstü kısayolu oluşturucunun özel .ico ikonunu parametre olarak aldığını test eder."""
    fake_target = temp_dir / "gui_launcher.pyw"
    fake_target.write_text("# launcher", encoding="utf-8")
    fake_ico = temp_dir / "custom_icon.ico"
    fake_ico.write_bytes(b"\x00\x00\x01\x00" + b"\x00" * 20)

    lnk_path = temp_dir / "Jarvis Studio Test.lnk"
    created = create_desktop_shortcut(
        shortcut_path=lnk_path,
        target_script=fake_target,
        working_dir=temp_dir,
        description="Jarvis Studio",
        icon_path=fake_ico,
    )
    assert created.exists()
    assert created.stat().st_size > 0


# =============================================================================
# 6. ENHANCED FEATURES & EDGE CASE TESTS
# =============================================================================

def test_turkish_asset_category_detection():
    """Türkçe dosya adlarının doğru kategorilere otomatik eşlendiğini test eder."""
    assert detect_asset_category("yurume_animasyonu.fbx") == "Animasyon"
    assert detect_asset_category("kosma_dongusu.bvh") == "Animasyon"
    assert detect_asset_category("ziplama_hareketi.blend") == "Animasyon"
    assert detect_asset_category("kahraman_savasci.blend") == "Karakter"
    assert detect_asset_category("dusman_canavar.obj") == "Karakter"
    assert detect_asset_category("zindan_haritasi.glb") == "Çevre/Level"
    assert detect_asset_category("cevre_duvari.gltf") == "Çevre/Level"
    assert detect_asset_category("efsanevi_kilic.obj") == "Prop"
    assert detect_asset_category("altin_sandik.fbx") == "Prop"
    assert detect_asset_category("yaris_arabasi.blend") == "Araç"
    assert detect_asset_category("ates_buyusu_efekti.dae") == "VFX/Diğer"


def test_drop_folder_recursive_asset_ingestion(tk_root, test_settings, temp_dir):
    """Klasör sürükleyip bırakıldığında alt klasörlerdeki tüm 3D varlıkların özyinelemeli bulunduğunu test eder."""
    app = GameDesignerApp(tk_root, settings=test_settings)
    proj = app.plugin.create_project(name="Drop Folder Test", activate=True)
    app._refresh_all_data()

    # İçiçe klasör yapısı oluştur
    folder = temp_dir / "my_game_assets"
    sub_anims = folder / "animations"
    sub_chars = folder / "characters"
    sub_anims.mkdir(parents=True, exist_ok=True)
    sub_chars.mkdir(parents=True, exist_ok=True)

    f1 = sub_anims / "run_cycle.fbx"
    f1.write_bytes(b"F1")
    f2 = sub_chars / "hero_warrior.obj"
    f2.write_bytes(b"v 0 0 0\nv 1 1 1\nf 1 2\n")

    # Klasörü doğrudan sürükle-bırak fonksiyonuna ver
    app._on_files_dropped([str(folder)])

    updated = app.plugin.get_project(proj.id)
    assert len(updated.blend_files) == 2
    cats = {b.name: b.category for b in updated.blend_files}
    assert cats["run_cycle.fbx"] == "Animasyon"
    assert cats["hero_warrior.obj"] == "Karakter"


def test_animated_skeleton_fk_generation():
    """İskelet animasyon hesaplayıcısının farklı hareket türlerinde doğru kemik hiyerarşisi ürettiğini test eder."""
    for mode in ["walk", "run", "idle", "jump", "attack"]:
        bones_t0 = get_animated_skeleton_bones(anim_type=mode, t=0.0)
        bones_t1 = get_animated_skeleton_bones(anim_type=mode, t=0.5)

        assert len(bones_t0) == 18
        assert len(bones_t1) == 18

        # Farklı zaman dilimlerinde kemik pozisyonlarının değiştiğini (canlı hareket) doğrula
        pos_t0 = bones_t0[12][1]  # sol diz/ayak ucu
        pos_t1 = bones_t1[12][1]
        assert pos_t0 != pos_t1


def test_category_procedural_meshes():
    """Her kategori için geçerli 3D yüzey ve tepe noktaları üretildiğini doğrular."""
    for cat in ["Karakter", "Prop", "Çevre/Level", "Araç", "VFX/Diğer", "Genel"]:
        verts, faces = generate_category_mesh(cat)
        assert len(verts) >= 4
        assert len(faces) >= 1


def test_glb_parsing_with_mock_glb(temp_dir):
    """GLB dosyasından gömülü PNG resminin veya tepe noktalarının ayrıştırıldığını test eder."""
    glb_path = temp_dir / "sample.glb"

    # Minimal geçerli bir PNG resmi oluştur
    png_bytes = io.BytesIO()
    test_img = Image.new("RGBA", (64, 64), color=(6, 182, 212, 255))
    test_img.save(png_bytes, format="PNG")
    raw_png = png_bytes.getvalue()

    # GLB gövdesi içine PNG göm
    glb_data = b"glTF\x02\x00\x00\x00\x00\x10\x00\x00" + b"\x00" * 32 + raw_png
    glb_path.write_bytes(glb_data)

    verts, faces, img = parse_glb_or_gltf(glb_path)
    assert img is not None
    assert img.size == (64, 64)


def test_viewport_animation_and_spin_toggles(tk_root):
    """Viewport animasyon ve 3D döndürme kontrollerinin durum değiştirdiğini test eder."""
    vp = Viewport3DCanvas(tk_root)
    assert vp.is_animating is True
    assert vp.auto_spin is False

    # Animasyonu duraklat
    state1 = vp.toggle_animation()
    assert state1 is False
    assert vp.is_animating is False

    # Tekrar oynat
    state2 = vp.toggle_animation()
    assert state2 is True
    assert vp.is_animating is True

    # 3D Çevirmeyi aç
    spin1 = vp.toggle_auto_spin()
    assert spin1 is True
    assert vp.auto_spin is True

    vp.destroy()


def test_ai_advisor_race_condition_counter(tk_root, test_settings):
    """Eşzamanlı sorgularda yarış durumunun (race condition) ID sayacı ile engellendiğini test eder."""
    app = GameDesignerApp(tk_root, settings=test_settings)
    assert getattr(app, "_current_query_id", 0) == 0

    with patch.object(app.plugin, "query") as mock_query:
        mock_resp = MagicMock()
        mock_resp.text = "Hızlı yanıt"
        mock_resp.mode = "query"
        mock_resp.confidence.tier_badge = "[GÜVENİLİR]"
        mock_resp.confidence.overall_score = 90.0
        mock_resp.sources = []
        mock_query.return_value = mock_resp

        app.rag_input_text.delete("1.0", tk.END)
        app.rag_input_text.insert("1.0", "Mekanik 1")
        app._execute_rag_query()
        assert app._current_query_id == 1

        app.rag_input_text.delete("1.0", tk.END)
        app.rag_input_text.insert("1.0", "Mekanik 2")
        app._execute_rag_query()
        assert app._current_query_id == 2


def test_gdd_studio_tab_copy_and_export(tk_root, test_settings, temp_dir):
    """Sekme 2'deki GDD dökümanı panoya kopyalama ve dosyaya kaydetme özelliklerini test eder."""
    app = GameDesignerApp(tk_root, settings=test_settings)
    sample_gdd = "# Game Design Document\n## Mechanics\n- Wall running"
    app.rag_tab_output_text.delete("1.0", tk.END)
    app.rag_tab_output_text.insert("1.0", sample_gdd)

    # Dışa aktarma testi
    target_md = temp_dir / "output_gdd.md"
    with patch("tkinter.filedialog.asksaveasfilename", return_value=str(target_md)):
        with patch("tkinter.messagebox.showinfo"):
            app._export_gdd_to_file()

    assert target_md.is_file()
    assert "Wall running" in target_md.read_text(encoding="utf-8")
