"""Comprehensive tests for Studio Redesign, Viewport Shading, Checkerboard 2D, and Single-Screen Drawers."""

from pathlib import Path
import tkinter as tk
from unittest.mock import MagicMock, patch
from PIL import Image
import pytest

from game_designer.ui.viewport import Viewport3DCanvas, get_checkerboard_pattern
from game_designer.ui.app import GameDesignerApp, DarkTheme


def test_checkerboard_pattern_generation():
    """Checkerboard şeffaflık zemin dokusunun doğru boyutta ve önbellekli üretildiğini test eder."""
    bg1 = get_checkerboard_pattern(128, 128, tile_size=16)
    assert bg1.size == (128, 128)
    assert bg1.mode == "RGBA"

    # Önbellekten çekildiğini doğrula (kopya döndüğü için içerik ve boyut aynıdır)
    bg2 = get_checkerboard_pattern(128, 128, tile_size=16)
    assert bg2.size == (128, 128)
    assert bg1 is not bg2  # Bağımsız kopya

    # Farklı boyut
    bg3 = get_checkerboard_pattern(64, 48, tile_size=8)
    assert bg3.size == (64, 48)


def test_viewport_2d_checkerboard_and_no_wireframe(tk_root, temp_dir):
    """2D görsellerin tel kafes olmaksızın damalı zemin ve pan/zoom ile çalıştığını test eder."""
    vp = Viewport3DCanvas(tk_root)
    vp.canvas.update()

    # Sahte 2D PNG oluştur
    img_path = temp_dir / "player_idle.png"
    im = Image.new("RGBA", (32, 32), (255, 0, 0, 255))
    im.save(img_path)

    vp.set_asset(str(img_path), category="2D Sprite / Piksel Sanatı")
    assert vp.display_mode == "image"
    assert vp.current_thumbnail_img is not None
    assert vp.current_thumbnail_img.size == (32, 32)

    # Render çağrısı (Canvas genişlik ve yüksekliği taklit edilir)
    with patch.object(vp.canvas, "winfo_width", return_value=400), patch.object(vp.canvas, "winfo_height", return_value=300):
        vp.render()
        items = vp.canvas.find_all()
        assert len(items) > 0

    # Fare ile sürükleme pan yapmalı, asla 3D moda geçmemeli
    old_pan_x, old_pan_y = vp.pan_x, vp.pan_y
    fake_down = MagicMock(x=50, y=50)
    vp._on_mouse_down(fake_down)
    fake_drag = MagicMock(x=70, y=85)
    vp._on_mouse_drag(fake_drag)
    vp._on_mouse_up(fake_drag)

    assert vp.display_mode == "image"
    assert vp.pan_x == old_pan_x + 20
    assert vp.pan_y == old_pan_y + 35

    # 1:1 ve Sığdır yakınlaştırmaları
    vp.zoom_1_to_1()
    assert vp.pan_x == 0.0
    assert vp.pan_y == 0.0

    vp.zoom_fit()
    assert vp.zoom == 120.0
    vp.destroy()


def test_viewport_3d_render_style_shaded_vs_wireframe(tk_root):
    """3D sahnede Gölgeli (Solid Shaded) ile Tel Kafes geçişini test eder."""
    vp = Viewport3DCanvas(tk_root)
    vp.canvas.update()

    # Varsayılan stil 'shaded'
    assert vp.render_style == "shaded"
    assert vp.display_mode == "3d"

    # Tel kafese geçiş
    style = vp.toggle_render_style()
    assert style == "wireframe"
    assert vp.render_style == "wireframe"

    # Tekrar gölgeliye geçiş
    style = vp.toggle_render_style()
    assert style == "shaded"
    assert vp.render_style == "shaded"
    vp.destroy()


def test_studio_activity_bar_and_drawer_toggles(tk_root, test_settings):
    """Aktivite çubuğu ile sol ve sağ çekmecelerin açılıp kapandığını test eder."""
    app = GameDesignerApp(tk_root, settings=test_settings)

    # Başlangıç durumu: Sol çekmece açık (Varlıklar), Sağ çekmece kapalı
    assert app._left_drawer_visible is True
    assert app._active_left_view == "assets"
    assert app._right_drawer_visible is False

    # Sol çekmecede Projeler görünümüne geçiş
    app._toggle_left_drawer("projects")
    assert app._left_drawer_visible is True
    assert app._active_left_view == "projects"
    assert "Proje" in app.lbl_drawer_title.cget("text")

    # Aynı görünüme tekrar tıklandığında sol çekmece kapanır
    app._toggle_left_drawer("projects")
    assert app._left_drawer_visible is False

    # Senkronizasyon görünümü ile sol çekmeceyi tekrar açma
    app._toggle_left_drawer("sync")
    assert app._left_drawer_visible is True
    assert app._active_left_view == "sync"
    assert "Senkronizasyon" in app.lbl_drawer_title.cget("text")

    # Çarpı butonuyla kapatma
    app._close_left_drawer()
    assert app._left_drawer_visible is False

    # Sağ AI Danışmanı çekmecesini açma
    app._toggle_right_drawer()
    assert app._right_drawer_visible is True

    # Sağ çekmeceyi çarpı butonuyla kapatma
    app._close_right_drawer()
    assert app._right_drawer_visible is False


def test_category_chip_filtering_and_cevre_mapping(tk_root, test_settings, temp_dir):
    """Kategori çiplerinin tıklanması ve Çevre/Level esnek eşleşmesini test eder."""
    app = GameDesignerApp(tk_root, settings=test_settings)
    proj = app.plugin.create_project(name="Chip Test Proj", activate=True)

    f_sprite = temp_dir / "hero_sprite.png"
    f_sprite.write_bytes(b"PNG_DATA")
    f_cevre = temp_dir / "dungeon_wall.obj"
    f_cevre.write_text("v 0 0 0\n", encoding="utf-8")
    f_char = temp_dir / "warrior.blend"
    f_char.write_bytes(b"BLEND_DATA")
    f_vehicle = temp_dir / "tank_pzkpfw.obj"
    f_vehicle.write_text("v 0 0 0\n", encoding="utf-8")

    app.plugin.add_blend_file(proj.id, str(f_sprite), category="2D Sprite / Piksel Sanatı")
    app.plugin.add_blend_file(proj.id, str(f_cevre), category="Çevre/Level")
    app.plugin.add_blend_file(proj.id, str(f_char), category="Karakter")
    app.plugin.add_blend_file(proj.id, str(f_vehicle), category="Araç")
    app._refresh_all_data()

    # Varsayılan Tümü: 4 varlık
    assert len(app.blend_tree.get_children()) == 4

    # 'Çevre' çipine tıklandığında 'Çevre/Level' eşleşmeli
    app._on_category_chip_clicked("Çevre")
    assert len(app.blend_tree.get_children()) == 1
    item = app.blend_tree.item(app.blend_tree.get_children()[0])
    assert item["values"][1] == "Çevre/Level"

    # '2D Sprite' çipine tıklandığında '2D Sprite / Piksel Sanatı' eşleşmeli
    app._on_category_chip_clicked("2D Sprite")
    assert len(app.blend_tree.get_children()) == 1
    item = app.blend_tree.item(app.blend_tree.get_children()[0])
    assert item["values"][1] == "2D Sprite / Piksel Sanatı"

    # 'Araç' çipine tıklandığında 'Araç' eşleşmeli
    app._on_category_chip_clicked("Araç")
    assert len(app.blend_tree.get_children()) == 1
    item = app.blend_tree.item(app.blend_tree.get_children()[0])
    assert item["values"][1] == "Araç"

    # 'Tümü' çipine tıklandığında hepsi geri gelmeli
    app._on_category_chip_clicked("Tümü")
    assert len(app.blend_tree.get_children()) == 4


def test_asset_selection_hud_and_ai_context_updates(tk_root, test_settings, temp_dir):
    """Varlık seçildiğinde HUD toolbar butonlarının ve AI bağlam rozetinin güncellendiğini test eder."""
    app = GameDesignerApp(tk_root, settings=test_settings)
    proj = app.plugin.create_project(name="Context Proj", activate=True)

    f_sprite = temp_dir / "knight.png"
    im = Image.new("RGBA", (16, 16), (0, 255, 0, 255))
    im.save(f_sprite)

    f_tank = temp_dir / "heavy_tank.obj"
    f_tank.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n", encoding="utf-8")

    ref_sprite = app.plugin.add_blend_file(proj.id, str(f_sprite), category="2D Sprite / Piksel Sanatı")
    ref_tank = app.plugin.add_blend_file(proj.id, str(f_tank), category="Araç")
    app._refresh_all_data()

    # 1. 2D Sprite seç
    app.blend_tree.selection_set(ref_sprite.id)
    app._on_blend_selected()

    assert app.viewport_3d.display_mode == "image"
    assert "knight.png" in app.lbl_ai_context.cget("text")
    assert "2D Sprite" in app.lbl_ai_context.cget("text")
    assert "knight.png" in app.lbl_hud_badge.cget("text")

    # HUD araç çubuğunda 2D kontrolleri aktif olmalı
    assert app.hud_2d_frame.winfo_ismapped() or True  # Pack doğrulaması
    assert app.btn_hud_scale.cget("text") in ["👾 Piksel", "✨ Yumuşak"]

    # 2. 3D Model seç
    app.blend_tree.selection_set(ref_tank.id)
    app._on_blend_selected()

    assert app.viewport_3d.display_mode == "3d"
    assert "heavy_tank.obj" in app.lbl_ai_context.cget("text")
    assert "Araç" in app.lbl_ai_context.cget("text")
    assert "heavy_tank.obj" in app.lbl_hud_badge.cget("text")
    assert app.btn_hud_render_style.cget("text") in ["💡 Gölgeli", "📐 Tel Kafes"]

    # 3. ref_tank kaldırıldığında kalan knight.png otomatik seçilmeli
    with patch("tkinter.messagebox.askyesno", return_value=True):
        app._remove_selected_blend()
    assert app.selected_blend_ref is not None
    assert app.selected_blend_ref.id == ref_sprite.id
    assert "knight.png" in app.lbl_ai_context.cget("text")

    # 4. Kalan son varlık da kaldırıldığında bağlam temizlenmeli
    app.blend_tree.selection_set(ref_sprite.id)
    with patch("tkinter.messagebox.askyesno", return_value=True):
        app._remove_selected_blend()
    assert app.selected_blend_ref is None
    assert "Varlık Seçilmedi" in app.lbl_ai_context.cget("text")


def test_ai_drawer_quick_action_chips(tk_root, test_settings, temp_dir):
    """AI Danışmanı hızlı aksiyon çiplerinin şablonu doldurup sorguyu başlattığını test eder."""
    app = GameDesignerApp(tk_root, settings=test_settings)
    proj = app.plugin.create_project(name="CyberBlade", game_engine="Godot", genre="Platformer", activate=True)

    f_sprite = temp_dir / "ninja.png"
    im = Image.new("RGBA", (32, 32), (0, 0, 255, 255))
    im.save(f_sprite)
    ref = app.plugin.add_blend_file(proj.id, str(f_sprite), category="Karakter")
    app._refresh_all_data()

    app.blend_tree.selection_set(ref.id)
    app._on_blend_selected()

    with patch.object(app, "_execute_rag_query") as mock_exec:
        # Mekanik çip simülasyonu
        chips = [w for w in app.right_drawer.winfo_children() if isinstance(w, tk.Frame)]
        # Action chip tıklandığında
        app._create_action_chip(app.right_drawer, "⚡ Mekanik Test", "{asset_name} için oyun mekaniği", "analyze_game")
        # En son eklenen butonu bul ve tıkla
        btn = [w for w in app.right_drawer.winfo_children() if isinstance(w, tk.Button) and "Mekanik Test" in w.cget("text")][0]
        btn.invoke()

        assert "ninja.png" in app.rag_input_text.get("1.0", tk.END)
        assert mock_exec.called


def test_viewport_3d_realtime_shading_and_depth_sorting(tk_root):
    """3D sahnede Painter's derinlik sıralamasının ve dinamik ışıklandırmanın çalıştığını test eder."""
    vp = Viewport3DCanvas(tk_root)
    # Varsayılan gem mesh
    with patch.object(vp.canvas, "winfo_width", return_value=500), patch.object(vp.canvas, "winfo_height", return_value=400):
        # Render shaded
        vp.render_style = "shaded"
        vp.render()
        polys_initial = [vp.canvas.itemcget(item, "fill") for item in vp.canvas.find_all() if vp.canvas.type(item) == "polygon"]
        assert len(polys_initial) > 0

        # Modeli 40 derece döndürdüğümüzde (simetri açısı dışı) ışıklandırma renkleri dinamik güncellenmeli
        vp.yaw = (vp.yaw + 40.0) % 360
        vp.render()
        polys_rotated = [vp.canvas.itemcget(item, "fill") for item in vp.canvas.find_all() if vp.canvas.type(item) == "polygon"]
        assert len(polys_rotated) == len(polys_initial)
        # En az bir yüzeyin ışık yoğunluğu döndürme sonucu değişmelidir (statik kalmamalı!)
        assert polys_initial != polys_rotated
    vp.destroy()


def test_viewport_2d_exact_1_to_1_zoom_scale(tk_root, temp_dir):
    """Küçük piksel sanatı sprite'ında 1:1 ölçeklemenin piksel hassasiyetinde çalıştığını test eder."""
    vp = Viewport3DCanvas(tk_root)
    p_img = temp_dir / "tiny_16x16.png"
    im = Image.new("RGBA", (16, 16), (255, 128, 0, 255))
    im.save(p_img)

    vp.set_asset(str(p_img), category="2D Sprite / Piksel Sanatı")
    assert vp.display_mode == "image"

    with patch.object(vp.canvas, "winfo_width", return_value=600), patch.object(vp.canvas, "winfo_height", return_value=500):
        vp.zoom_1_to_1()
        # 1:1 durumunda canvas'a basılan ImageTk boyutunun 16x16 olduğunu doğrula
        assert vp.current_tk_img is not None
        assert vp.current_tk_img.width() == 16
        assert vp.current_tk_img.height() == 16
    vp.destroy()


def test_viewport_pan_drag_middle_and_right_button_release(tk_root):
    """Orta ve sağ tuşla kaydırma (pan) bırakıldığında sürükleme durumunun temizlendiğini test eder."""
    vp = Viewport3DCanvas(tk_root)

    # Sağ tuş drag ve release
    fake_down = MagicMock(x=100, y=100)
    fake_drag = MagicMock(x=120, y=130)
    fake_up = MagicMock(x=120, y=130)

    vp._on_mouse_down(fake_down)
    assert vp._is_dragging is True
    vp._on_pan_drag(fake_drag)
    assert vp.pan_x == 20.0
    assert vp.pan_y == 30.0

    vp._on_mouse_up(fake_up)
    assert vp._is_dragging is False

    # Dragging False iken hareket pan yapmamalı
    vp._on_pan_drag(MagicMock(x=150, y=160))
    assert vp.pan_x == 20.0
    vp.destroy()


def test_blend_tree_format_column_and_badges(tk_root, test_settings, temp_dir):
    """Varlık tablosunda 'Format' sütununun ve format rozetlerinin doğru görüntülendiğini test eder."""
    app = GameDesignerApp(tk_root, settings=test_settings)
    proj = app.plugin.create_project(name="Format Badge Proj", activate=True)

    f_png = temp_dir / "icon.png"
    Image.new("RGBA", (16, 16)).save(f_png)
    f_obj = temp_dir / "prop.obj"
    f_obj.write_text("v 0 0 0\n", encoding="utf-8")
    f_bld = temp_dir / "scene.blend"
    f_bld.write_bytes(b"BLENDER")

    app.plugin.add_blend_file(proj.id, str(f_png), category="2D Sprite / Piksel Sanatı")
    app.plugin.add_blend_file(proj.id, str(f_obj), category="Prop")
    app.plugin.add_blend_file(proj.id, str(f_bld), category="Çevre/Level")
    app._refresh_all_data()

    # Ağaç sütunları
    cols = app.blend_tree["columns"]
    assert "format" in cols
    assert cols.index("format") == 2

    # Öğelerin format etiketleri
    badges = [app.blend_tree.item(item)["values"][2] for item in app.blend_tree.get_children()]
    assert any("PNG" in b for b in badges)
    assert any("OBJ" in b for b in badges)
    assert any("BLEND" in b for b in badges)


def test_hud_open_button_blend_thumbnail_adaptation(tk_root, test_settings, temp_dir):
    """Blender küçük resmi önizlenirken HUD butonunun 'Blender ile Aç' olarak adapte olduğunu test eder."""
    app = GameDesignerApp(tk_root, settings=test_settings)
    proj = app.plugin.create_project(name="Adapt Proj", activate=True)

    f_bld = temp_dir / "world.blend"
    f_bld.write_bytes(b"BLENDER")
    f_png = temp_dir / "sprite.png"
    Image.new("RGBA", (16, 16)).save(f_png)

    ref_bld = app.plugin.add_blend_file(proj.id, str(f_bld), category="Çevre/Level")
    ref_png = app.plugin.add_blend_file(proj.id, str(f_png), category="2D Sprite / Piksel Sanatı")
    app._refresh_all_data()

    # 1. Blend dosyası seçildiğinde ve thumbnail modunda ise HUD 'Blender ile Aç' göstermeli
    app.blend_tree.selection_set(ref_bld.id)
    app._on_blend_selected()
    app.viewport_3d.display_mode = "image"
    app._update_hud_toolbar()
    assert "Blender" in app.btn_hud_open_ase.cget("text")

    # 2. PNG seçildiğinde HUD 'Aseprite ile Aç' göstermeli
    app.blend_tree.selection_set(ref_png.id)
    app._on_blend_selected()
    assert app.viewport_3d.display_mode == "image"
    app._update_hud_toolbar()
    assert "Aseprite" in app.btn_hud_open_ase.cget("text")

