"""Comprehensive Tests for 2D Viewport Fixes, Aseprite Integration, and Tank 3D Mesh.

Covers:
1. Pure-Python Aseprite binary parser (header, frames, chunks, color depths 32/16/8 bpp, linked cels, palette).
2. Viewport 2D image handling (PNG, JPG, animated GIF with real-time frame playback and stepping).
3. Viewport pan and zoom on 2D images without reverting to 3D mode.
4. Nearest-Neighbor (pixel) vs Lanczos (smooth) scaling filter toggle.
5. Detailed 3D tank mesh generation (hull, treads, turret, barrel, muzzle brake) for tank/panzer/vehicle assets.
6. Aseprite executable locator (Program Files, Steam, AppData) and open_aseprite_file handler.
7. Category detection for Aseprite and 2D images, and SUPPORTED_EXTENSIONS set.
"""

import io
from pathlib import Path
import struct
from unittest.mock import MagicMock, patch
import zlib
from PIL import Image
import pytest

from game_designer.data.project_manager import (
    ProjectManager,
    find_aseprite_executable,
)
from game_designer.models.project import (
    SUPPORTED_3D_EXTENSIONS,
    SUPPORTED_ASEPRITE_EXTENSIONS,
    SUPPORTED_EXTENSIONS,
    SUPPORTED_IMAGE_EXTENSIONS,
    detect_asset_category,
)
from game_designer.ui.app import GameDesignerApp
from game_designer.ui.aseprite_parser import (
    AsepriteFile,
    AsepriteParser,
    create_minimal_aseprite,
    parse_aseprite_file,
)
from game_designer.ui.viewport import (
    Viewport3DCanvas,
    generate_category_mesh,
    generate_speeder_mesh,
    generate_tank_mesh,
)


# =============================================================================
# 1. ASEPRITE PARSER TESTS
# =============================================================================

def test_aseprite_parser_header_validation():
    """Aseprite başlık doğrulama hatalarını ve geçerli başlık okumasını test eder."""
    # 1. Çok kısa veri
    with pytest.raises(ValueError, match="çok küçük"):
        parse_aseprite_file(b"short_bytes")

    # 2. Geçersiz sihirli sayı (magic)
    bad_magic = bytearray(128)
    struct.pack_into("<IH", bad_magic, 0, 128, 0x1234)
    with pytest.raises(ValueError, match="Geçersiz Aseprite sihirli sayısı"):
        parse_aseprite_file(bytes(bad_magic))

    # 3. Geçersiz çözünürlük
    zero_size = bytearray(128)
    struct.pack_into("<IH", zero_size, 0, 128, 0xA5E0)
    struct.pack_into("<HH", zero_size, 8, 0, 0)
    with pytest.raises(ValueError, match="Geçersiz Aseprite çözünürlüğü"):
        parse_aseprite_file(bytes(zero_size))

    # 4. Desteklenmeyen renk derinliği
    bad_bpp = bytearray(128)
    struct.pack_into("<IH", bad_bpp, 0, 128, 0xA5E0)
    struct.pack_into("<HH", bad_bpp, 8, 16, 16)
    struct.pack_into("<H", bad_bpp, 12, 24)  # 24 bpp desteklenmez (yalnızca 8, 16, 32)
    with pytest.raises(ValueError, match="Desteklenmeyen Aseprite renk derinliği"):
        parse_aseprite_file(bytes(bad_bpp))


def test_aseprite_parser_32bpp_rgba_and_compression():
    """32 bpp RGBA sıkıştırılmış ve ham Cel bloklarının doğru ayrıştırıldığını test eder."""
    # 4x4 Kırmızı ve Mavi kareler
    red_pixels = bytes([255, 0, 0, 255] * 16)
    blue_pixels = bytes([0, 0, 255, 255] * 16)

    # ZLIB sıkıştırmalı
    ase_comp = create_minimal_aseprite(4, 4, [(red_pixels, 100), (blue_pixels, 200)], color_depth=32, compress=True)
    anim_comp = parse_aseprite_file(ase_comp)
    assert anim_comp.num_frames == 2
    assert anim_comp.durations == [100, 200]
    assert anim_comp.frames[0].getpixel((0, 0)) == (255, 0, 0, 255)
    assert anim_comp.frames[1].getpixel((0, 0)) == (0, 0, 255, 255)
    assert anim_comp.total_duration_ms == 300

    # Ham (uncompressed)
    ase_raw = create_minimal_aseprite(4, 4, [(red_pixels, 80)], color_depth=32, compress=False)
    anim_raw = parse_aseprite_file(ase_raw)
    assert anim_raw.frames[0].getpixel((0, 0)) == (255, 0, 0, 255)


def test_aseprite_parser_16bpp_grayscale_alpha():
    """16 bpp Gri tonlama + Alfa modunun doğru RGBA'ya çevrildiğini test eder."""
    # 4x4 gri tonlama: değer=180, alfa=220
    gray_pixels = bytes([180, 220] * 16)
    ase_16 = create_minimal_aseprite(4, 4, [(gray_pixels, 150)], color_depth=16)
    anim_16 = parse_aseprite_file(ase_16)

    assert anim_16.num_frames == 1
    assert anim_16.color_depth == 16
    pixel = anim_16.frames[0].getpixel((0, 0))
    assert pixel == (180, 180, 180, 220)


def test_aseprite_parser_8bpp_indexed_palette():
    """8 bpp İndeksli palet bloğunun (0x2019) ve şeffaf rengin doğru çözüldüğünü test eder."""
    pal = [
        (0, 0, 0, 0),        # 0: Şeffaf
        (255, 200, 50, 255),  # 1: Altın sarısı
        (10, 120, 200, 255),  # 2: Mavi
    ]
    # İlk piksel 1 (altın), ikinci piksel 2 (mavi), kalanı 0 (şeffaf)
    idx_pixels = bytearray([1, 2] + [0] * 14)
    ase_8 = create_minimal_aseprite(4, 4, [(bytes(idx_pixels), 100)], color_depth=8, palette=pal)
    anim_8 = parse_aseprite_file(ase_8)

    assert anim_8.num_frames == 1
    assert anim_8.color_depth == 8
    assert anim_8.frames[0].getpixel((0, 0)) == (255, 200, 50, 255)
    assert anim_8.frames[0].getpixel((1, 0)) == (10, 120, 200, 255)
    assert anim_8.frames[0].getpixel((2, 0)) == (0, 0, 0, 0)


def test_aseprite_parser_linked_cels():
    """Bağlantılı Cel (Linked Cel, cel_type=1) içeren çoklu kareleri doğrular."""
    raw0 = bytes([50, 150, 250, 255] * 16)
    comp0 = zlib.compress(raw0)
    cel_hdr0 = struct.pack("<HhhBHh5sHH", 0, 0, 0, 255, 2, 0, b"\x00" * 5, 4, 4)
    chunk0 = struct.pack("<IH", 6 + len(cel_hdr0) + len(comp0), 0x2005) + cel_hdr0 + comp0
    f0 = struct.pack("<IHHH2sI", 16 + len(chunk0), 0xF1FA, 1, 100, b"\x00" * 2, 1) + chunk0

    # Kare 1: Kare 0'daki cel'e referans verir (linked cel)
    cel_hdr1 = struct.pack("<HhhBHh5sH", 0, 0, 0, 255, 1, 0, b"\x00" * 5, 0)
    chunk1 = struct.pack("<IH", 6 + len(cel_hdr1), 0x2005) + cel_hdr1
    f1 = struct.pack("<IHHH2sI", 16 + len(chunk1), 0xF1FA, 1, 120, b"\x00" * 2, 1) + chunk1

    hdr = bytearray(128)
    struct.pack_into("<IH", hdr, 0, 128 + len(f0) + len(f1), 0xA5E0)
    struct.pack_into("<H", hdr, 6, 2)
    struct.pack_into("<HH", hdr, 8, 4, 4)
    struct.pack_into("<H", hdr, 12, 32)
    struct.pack_into("<I", hdr, 14, 1)
    struct.pack_into("<H", hdr, 18, 100)

    ase_data = bytes(hdr) + f0 + f1
    anim = parse_aseprite_file(ase_data)
    assert anim.num_frames == 2
    assert anim.frames[0].getpixel((0, 0)) == (50, 150, 250, 255)
    assert anim.frames[1].getpixel((0, 0)) == (50, 150, 250, 255)


def test_aseprite_file_class_api(temp_dir):
    """AsepriteFile sınıfının dosya yolu ve bayt arayüzünü test eder."""
    raw = bytes([0, 255, 128, 255] * 16)
    ase_bytes = create_minimal_aseprite(4, 4, [(raw, 90)], color_depth=32)
    file_path = temp_dir / "character.aseprite"
    file_path.write_bytes(ase_bytes)

    # 1. Dosya yolu ile yükleme
    ase_file = AsepriteFile(file_path)
    assert ase_file.width == 4
    assert ase_file.height == 4
    assert ase_file.num_frames == 1
    assert ase_file.durations == [90]
    assert len(ase_file.frames) == 1
    assert ase_file.frames[0].size == (4, 4)

    # 2. Olmayan dosya hatası
    with pytest.raises(FileNotFoundError):
        AsepriteFile(temp_dir / "missing.aseprite")

    # 3. Geçersiz tip hatası
    with pytest.raises(TypeError):
        AsepriteFile(12345)  # type: ignore


# =============================================================================
# 2. VIEWPORT 2D IMAGE & ANIMATED GIF TESTS
# =============================================================================

def test_viewport_2d_image_loading_and_pan_zoom(tk_root, temp_dir):
    """2D resimlerin (PNG/JPG) yüklenmesini, fareyle sürüklemede pan yapılmasını ve zoom'u test eder."""
    img_path = temp_dir / "tank_sprite.png"
    test_img = Image.new("RGBA", (32, 32), (30, 144, 255, 255))
    test_img.save(img_path, format="PNG")

    vp = Viewport3DCanvas(tk_root)
    vp.set_asset(str(img_path))

    # Görsel modunun aktif olduğunu doğrula
    assert vp.display_mode == "image"
    assert vp.current_format == ".png"
    assert vp.current_thumbnail_img is not None
    assert vp.current_thumbnail_img.size == (32, 32)

    # Fareyle sürükleme testi (Pan hareketi 2D modunu bozmamalı)
    event_down = MagicMock(x=50, y=50)
    vp._on_mouse_down(event_down)
    event_drag = MagicMock(x=70, y=80)
    vp._on_mouse_drag(event_drag)
    vp._on_mouse_up(event_drag)

    assert vp.display_mode == "image"  # 3D'ye dönmemeli!
    assert vp.pan_x == 20.0
    assert vp.pan_y == 30.0

    # Fare tekerleği ile zoom
    initial_zoom = vp.zoom
    event_wheel = MagicMock(delta=120)
    vp._on_mouse_wheel(event_wheel)
    assert vp.zoom > initial_zoom

    # Piksel / Yumuşak ölçekleme filtresi değiştirme
    assert vp.scaling_mode == "pixel"
    new_mode = vp.toggle_scaling_filter()
    assert new_mode == "smooth"
    assert vp.scaling_mode == "smooth"
    new_mode = vp.toggle_scaling_filter()
    assert new_mode == "pixel"


def test_viewport_animated_gif_playback_and_stepping(tk_root, temp_dir):
    """Çok kareli GIF animasyonunun karelerinin çıkarılmasını ve kontrollerini test eder."""
    gif_path = temp_dir / "tank_driving.gif"
    frame1 = Image.new("RGBA", (16, 16), (255, 0, 0, 255))
    frame2 = Image.new("RGBA", (16, 16), (0, 255, 0, 255))
    frame3 = Image.new("RGBA", (16, 16), (0, 0, 255, 255))
    frame1.save(
        gif_path,
        save_all=True,
        append_images=[frame2, frame3],
        duration=[80, 100, 120],
        loop=0,
    )

    vp = Viewport3DCanvas(tk_root)
    vp.set_asset(str(gif_path))

    assert vp.display_mode == "image"
    assert len(vp.animation_frames) == 3
    assert vp.current_frame_index == 0

    # Kare adım butonları (Next / Prev)
    assert vp.next_frame() == 1
    assert vp.next_frame() == 2
    assert vp.next_frame() == 0  # Başa sarmalı
    assert vp.prev_frame() == 2
    assert vp.prev_frame() == 1

    # Oynatma / Duraklatma ve Döngü kontrolleri
    assert vp.is_animating is True
    vp.pause_animation()
    assert vp.is_animating is False
    vp.play_animation()
    assert vp.is_animating is True
    vp.toggle_animation()
    assert vp.is_animating is False

    assert vp.is_looping is True
    assert vp.toggle_loop() is False
    assert vp.is_looping is False


def test_viewport_aseprite_file_loading_and_playback(tk_root, temp_dir):
    """Aseprite dosyasının Viewport3DCanvas içinde tam animasyonlu oynatıldığını test eder."""
    f1 = bytes([255, 100, 0, 255] * 16)
    f2 = bytes([0, 200, 255, 255] * 16)
    ase_bytes = create_minimal_aseprite(4, 4, [(f1, 60), (f2, 120)], color_depth=32)

    ase_path = temp_dir / "panzer_sprite.aseprite"
    ase_path.write_bytes(ase_bytes)

    vp = Viewport3DCanvas(tk_root)
    vp.set_asset(str(ase_path))

    assert vp.display_mode == "image"
    assert vp.current_format == ".aseprite"
    assert len(vp.animation_frames) == 2
    assert vp.frame_durations == [60, 120]
    assert vp.current_frame_index == 0
    assert vp.is_animating is True

    # Adımlama testi
    vp.next_frame()
    assert vp.current_frame_index == 1


# =============================================================================
# 3. 3D TANK MESH PROCEDURAL GENERATION TESTS
# =============================================================================

def test_3d_tank_mesh_generation():
    """3D tank geometrisi üretiminin eksiksiz parçalar (gövde, palet, taret, namlu) içerdiğini test eder."""
    verts, faces = generate_tank_mesh()
    assert len(verts) >= 40
    assert len(faces) >= 20

    # Speeder geometrisi
    s_verts, s_faces = generate_speeder_mesh()
    assert len(s_verts) >= 6
    assert len(s_faces) >= 4

    # 1. Kategori "Araç" olduğunda tank geometrisi sunulmalı
    t_verts, t_faces = generate_category_mesh("Araç")
    assert len(t_verts) == len(verts)
    assert len(t_faces) == len(faces)

    # 2. Varlık adında "tank" veya "panzer" geçtiğinde doğrudan tank geometrisi sunulmalı
    t2_verts, t2_faces = generate_category_mesh("Genel", "panzer_iv.blend")
    assert len(t2_verts) == len(verts)

    t3_verts, t3_faces = generate_category_mesh("Karakter", "heavy_tank_boss.fbx")
    assert len(t3_verts) == len(verts)

    # 3. Eğer açıkça speeder/plane istenmişse speeder geometrisi sunulmalı
    sp_verts, _ = generate_category_mesh("Araç", "space_speeder.obj")
    assert len(sp_verts) == len(s_verts)


# =============================================================================
# 4. ASEPRITE LOCATOR & INTEGRATION TESTS
# =============================================================================

def test_find_aseprite_executable():
    """Aseprite çalıştırılabilir dosyasının sistemde, Steam'de ve AppData'da arandığını test eder."""
    # 1. shutil.which üzerinden bulunması
    with patch("shutil.which", return_value="C:\\Fake\\Aseprite\\aseprite.exe"):
        found = find_aseprite_executable()
        assert found == "C:\\Fake\\Aseprite\\aseprite.exe"

    # 2. Glob üzerinden Steam / Program Files araması
    with patch("shutil.which", return_value=None):
        with patch("glob.glob", side_effect=lambda pat: ["C:\\Steam\\steamapps\\common\\Aseprite\\aseprite.exe"] if "Steam" in pat else []):
            found = find_aseprite_executable()
            assert found == "C:\\Steam\\steamapps\\common\\Aseprite\\aseprite.exe"

    # 3. Hiçbir yerde bulunamaması
    with patch("shutil.which", return_value=None):
        with patch("glob.glob", return_value=[]):
            found = find_aseprite_executable()
            assert found is None


def test_open_aseprite_file_integration(test_settings, temp_dir):
    """ProjectManager.open_aseprite_file metodunun doğru çalıştığını test eder."""
    pm = ProjectManager(settings=test_settings)
    proj = pm.create_project(name="Aseprite Test Project")

    ase_file = temp_dir / "tank_art.aseprite"
    ase_file.write_bytes(b"\x00" * 200)
    ref = pm.add_blend_file(proj.id, str(ase_file), category="2D Sprite / Piksel Sanatı")

    # 1. Windows startfile başarılı
    with patch("sys.platform", "win32"):
        with patch("os.startfile") as mock_startfile:
            res = pm.open_aseprite_file(ref.id, project_name_or_id=proj.id)
            assert res is True
            mock_startfile.assert_called_once()

    # 2. startfile OSError verdiğinde find_aseprite_executable fallback'i
    with patch("sys.platform", "win32"):
        with patch("os.startfile", side_effect=OSError("No association")):
            with patch("game_designer.data.project_manager.find_aseprite_executable", return_value="C:\\fake\\aseprite.exe"):
                with patch("subprocess.Popen") as mock_popen:
                    res = pm.open_aseprite_file(str(ase_file))
                    assert res is True
                    mock_popen.assert_called_once()

    # 3. Olmayan dosya hatası
    with pytest.raises(FileNotFoundError):
        pm.open_aseprite_file("non_existent_file.aseprite")


# =============================================================================
# 5. ASSET CATEGORIZATION & EXTENSIONS TESTS
# =============================================================================

def test_detect_asset_category_for_aseprite_and_images():
    """Aseprite ve 2D görseller için kategori tespitini test eder."""
    # Aseprite dosyaları
    assert detect_asset_category("player_run_anim.aseprite") == "Animasyon"
    assert detect_asset_category("hero_walk.ase") == "Animasyon"
    assert detect_asset_category("tank_sprite.aseprite") == "2D Sprite / Piksel Sanatı"
    assert detect_asset_category("tile_grass.ase") == "2D Sprite / Piksel Sanatı"

    # 2D görseller
    assert detect_asset_category("combat_tank.png") == "Araç"
    assert detect_asset_category("knight_warrior.jpg") == "Karakter"
    assert detect_asset_category("idle_loop.gif") == "Animasyon"
    assert detect_asset_category("misc_texture.png") == "2D Sprite / Piksel Sanatı"


def test_supported_extensions_expansion():
    """SUPPORTED_EXTENSIONS kümesinin tüm 3D, 2D ve Aseprite uzantılarını kapsadığını doğrular."""
    for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tga"]:
        assert ext in SUPPORTED_IMAGE_EXTENSIONS
        assert ext in SUPPORTED_EXTENSIONS

    for ext in [".aseprite", ".ase"]:
        assert ext in SUPPORTED_ASEPRITE_EXTENSIONS
        assert ext in SUPPORTED_EXTENSIONS

    for ext in [".blend", ".fbx", ".obj", ".gltf", ".glb", ".bvh", ".dae"]:
        assert ext in SUPPORTED_3D_EXTENSIONS
        assert ext in SUPPORTED_EXTENSIONS


# =============================================================================
# 6. APP UI BUTTONS & VIEWPORT INTEGRATION
# =============================================================================

def test_app_ui_aseprite_and_scaling_buttons(tk_root, test_settings):
    """GameDesignerApp UI üzerindeki Aseprite ve Viewport ölçekleme kontrollerini test eder."""
    app = GameDesignerApp(tk_root, settings=test_settings)
    app.plugin.create_project(name="UI Integration Project", activate=True)
    app._refresh_all_data()

    # Viewport kontrolleri
    assert hasattr(app, "_toggle_viewport_scaling")
    assert hasattr(app, "_next_viewport_frame")
    assert hasattr(app, "_prev_viewport_frame")
    assert hasattr(app, "_open_selected_aseprite")

    # Filtre listesinde "2D Sprite / Piksel Sanatı" seçeneğinin bulunduğunu doğrula
    assert "2D Sprite / Piksel Sanatı" in app.blend_cat_combo["values"]

    # Seçim olmadan Aseprite açma uyarısı
    with patch("tkinter.messagebox.showwarning") as mock_warn:
        app._open_selected_aseprite()
        mock_warn.assert_called_once()


# =============================================================================
# 7. ROBUSTNESS & EDGE CASE TESTS
# =============================================================================

def test_corrupted_image_and_aseprite_fallbacks(tk_root, temp_dir):
    """Bozuk görsel veya bozuk Aseprite dosyası verildiğinde uygulamanın çökmeden 3D yedeğe geçtiğini test eder."""
    bad_img = temp_dir / "corrupted.png"
    bad_img.write_bytes(b"not an image file content")

    bad_ase = temp_dir / "corrupted.aseprite"
    bad_ase.write_bytes(b"corrupt aseprite data")

    vp = Viewport3DCanvas(tk_root)

    # Bozuk PNG
    vp.set_asset(str(bad_img))
    assert vp.display_mode == "3d"
    assert len(vp.mesh_vertices) > 0

    # Bozuk Aseprite
    vp.set_asset(str(bad_ase))
    assert vp.display_mode == "3d"
    assert len(vp.mesh_vertices) > 0


def test_single_frame_gif(tk_root, temp_dir):
    """Tek karelik GIF dosyasının doğru yüklendiğini ve otomatik animasyon başlatmadığını test eder."""
    gif_path = temp_dir / "single.gif"
    img = Image.new("RGBA", (8, 8), (100, 200, 50, 255))
    img.save(gif_path, format="GIF")

    vp = Viewport3DCanvas(tk_root)
    vp.set_asset(str(gif_path))

    assert vp.display_mode == "image"
    assert len(vp.animation_frames) == 1
    assert vp.is_animating is False


def test_open_blend_file_redirects_to_aseprite_for_ase_files(test_settings, temp_dir):
    """open_blend_file metodunun .ase / .aseprite dosyalarında otomatik open_aseprite_file'a yönlendirdiğini test eder."""
    pm = ProjectManager(settings=test_settings)
    ase_file = temp_dir / "hero.ase"
    ase_file.write_bytes(b"\x00" * 50)

    with patch.object(pm, "open_aseprite_file", return_value=True) as mock_ase_open:
        res = pm.open_blend_file(str(ase_file))
        assert res is True
        mock_ase_open.assert_called_once()


def test_aseprite_parser_z_index_ordering():
    """Cel Z-Index değerinin doğru ayrıştırıldığını ve katman sırasını ezerek üstte çizildiğini doğrular."""
    red_pixels = zlib.compress(bytes([255, 0, 0, 255] * 16))
    green_pixels = zlib.compress(bytes([0, 255, 0, 255] * 16))

    # Cel 0: Katman 0, z_index = 10 (üstte olmalı), Yeşil
    cel0 = struct.pack("<HhhBHh5sHH", 0, 0, 0, 255, 2, 10, b"\x00" * 5, 4, 4) + green_pixels
    ch0 = struct.pack("<IH", 6 + len(cel0), 0x2005) + cel0

    # Cel 1: Katman 1, z_index = -5 (altta olmalı), Kırmızı
    cel1 = struct.pack("<HhhBHh5sHH", 1, 0, 0, 255, 2, -5, b"\x00" * 5, 4, 4) + red_pixels
    ch1 = struct.pack("<IH", 6 + len(cel1), 0x2005) + cel1

    chunks = ch0 + ch1
    fhdr = struct.pack("<IHHH2sI", 16 + len(chunks), 0xF1FA, 2, 100, b"\x00" * 2, 2)
    hdr = bytearray(128)
    struct.pack_into("<IH", hdr, 0, 128 + len(fhdr) + len(chunks), 0xA5E0)
    struct.pack_into("<H", hdr, 6, 1)
    struct.pack_into("<HH", hdr, 8, 4, 4)
    struct.pack_into("<H", hdr, 12, 32)

    anim = parse_aseprite_file(bytes(hdr) + fhdr + chunks)
    # Z-Index 10 olan Cel 0 (Yeşil) üstte olmalıdır
    assert anim.frames[0].getpixel((0, 0)) == (0, 255, 0, 255)


def test_aseprite_parser_legacy_cel_chunk_format():
    """Eski (v1.1 öncesi 9 baytlık) Cel başlıklarının zlib sıkıştırmasını bozmadan çözüldüğünü test eder."""
    raw = zlib.compress(bytes([100, 150, 200, 255] * 16))
    cel = struct.pack("<HhhBHHH", 0, 0, 0, 255, 2, 4, 4) + raw
    ch = struct.pack("<IH", 6 + len(cel), 0x2005) + cel
    fhdr = struct.pack("<IHHH2sI", 16 + len(ch), 0xF1FA, 1, 100, b"\x00" * 2, 1)
    hdr = bytearray(128)
    struct.pack_into("<IH", hdr, 0, 128 + len(fhdr) + len(ch), 0xA5E0)
    struct.pack_into("<H", hdr, 6, 1)
    struct.pack_into("<HH", hdr, 8, 4, 4)
    struct.pack_into("<H", hdr, 12, 32)

    anim = parse_aseprite_file(bytes(hdr) + fhdr + ch)
    assert anim.frames[0].getpixel((0, 0)) == (100, 150, 200, 255)


def test_viewport_resets_pan_zoom_on_new_asset(tk_root, temp_dir):
    """Yeni varlık yüklendiğinde önceki pan/zoom kaymalarının sıfırlandığını test eder."""
    vp = Viewport3DCanvas(tk_root)
    vp.pan_x = 150.0
    vp.pan_y = -90.0
    vp.zoom = 350.0

    img = Image.new("RGBA", (16, 16), (255, 255, 0, 255))
    img_path = temp_dir / "tank_top_view.png"
    img.save(img_path)

    vp.set_asset(str(img_path))
    assert vp.pan_x == 0.0
    assert vp.pan_y == 0.0
    assert vp.zoom == 120.0


def test_batch_add_assets_resets_category_filter(tk_root, test_settings, temp_dir):
    """Kategori filtresi seçiliyken yeni varlık sürüklendiğinde filtrenin 'Tümü'ne sıfırlandığını test eder."""
    app = GameDesignerApp(tk_root, settings=test_settings)
    app.plugin.create_project(name="Filter Reset Project", activate=True)
    app._refresh_all_data()

    # Kullanıcı önce 'Animasyon' filtresi seçmiş olsun
    app.blend_cat_filter_var.set("Animasyon")

    tank_img = temp_dir / "battle_tank.png"
    tank_img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    # Dosya sürüklendiğinde
    app._on_files_dropped([str(tank_img)])

    # Filtre 'Tümü'ne dönmeli ve yeni varlık tabloda seçili olmalıdır
    assert app.blend_cat_filter_var.get() == "Tümü"
    assert app.selected_blend_ref is not None
    assert app.selected_blend_ref.name == "battle_tank.png"


def test_open_aseprite_file_with_image_uses_aseprite_executable(test_settings, temp_dir):
    """2D resim dosyası için Aseprite ile Aç butonuna basıldığında Aseprite çalıştırılabilir dosyasının açıldığını test eder."""
    pm = ProjectManager(settings=test_settings)
    proj = pm.create_project(name="Image Aseprite Test")
    img_file = temp_dir / "tank_art.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
    ref = pm.add_blend_file(proj.id, str(img_file))

    with patch("game_designer.data.project_manager.find_aseprite_executable", return_value="C:\\Aseprite\\aseprite.exe"):
        with patch("pathlib.Path.is_file", return_value=True):
            with patch("subprocess.Popen") as mock_popen:
                res = pm.open_aseprite_file(ref.id, project_name_or_id=proj.id)
                assert res is True
                mock_popen.assert_called_once_with(["C:\\Aseprite\\aseprite.exe", str(img_file.resolve())])


def test_on_files_dropped_ignores_unsupported_extensions(tk_root, test_settings, temp_dir):
    """Desteklenmeyen dosya uzantılarının sürükle-bırakta atlandığını test eder."""
    app = GameDesignerApp(tk_root, settings=test_settings)
    proj = app.plugin.create_project(name="Drop Ignore Test", activate=True)
    app._refresh_all_data()

    text_file = temp_dir / "notes.txt"
    text_file.write_text("not a game asset")

    app._on_files_dropped([str(text_file)])

    p = app.plugin.get_project(proj.id)
    assert len(p.blend_files) == 0


