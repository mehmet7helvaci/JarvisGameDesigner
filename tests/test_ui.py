"""Tests for GameDesignerApp Desktop UI."""

import os
from pathlib import Path
import tkinter as tk
from unittest.mock import MagicMock, patch
import pytest

from game_designer.models.project import GameProject
from game_designer.ui.app import DarkTheme, GameDesignerApp
import gui_launcher






def test_dark_theme_constants():
    """DarkTheme renk paletinin tanımlı olduğunu doğrular."""
    assert DarkTheme.BG_DARK == "#0f172a"
    assert DarkTheme.BG_CARD == "#1e293b"
    assert DarkTheme.ACCENT_CYAN == "#06b6d4"
    assert DarkTheme.SUCCESS == "#10b981"


def test_ui_app_lifecycle(tk_root, test_settings):
    """GameDesignerApp arayüzünün başlatılmasını, sekmelerin ve bileşenlerin hazırlandığını test eder."""
    app = GameDesignerApp(tk_root, settings=test_settings)

    # Tablar oluştu mu?
    assert app.notebook.tabs()
    assert len(app.notebook.tabs()) == 3

    # Proje oluştur
    p = app.plugin.create_project(name="UI Cyber Test", game_engine="Unity", genre="Action")
    app._refresh_all_data()

    # Ağaç görünümünde proje var mı?
    children = app.projects_tree.get_children()
    assert len(children) >= 1

    # Proje seçildiğinde detayların dolması
    app.projects_tree.selection_set(children[0])
    app._on_project_selected()
    assert "UI Cyber Test" in app.lbl_proj_title.cget("text")

    # Projeler klasörü açma fonksiyonu çağrısı (os.startfile mock ile)
    with patch("os.startfile", create=True) as mock_start:
        app._open_projects_folder()
        mock_start.assert_called_once()


def test_ui_rag_query_execution(tk_root, test_settings):
    """UI üzerinden RAG sorgusunun çalıştırılması ve arayüze aktarılması."""
    app = GameDesignerApp(tk_root, settings=test_settings)

    # Mock RAG response
    mock_response = MagicMock()
    mock_response.mode = "query"
    mock_response.text = "Wall jump mekaniği oyuncu ivmesini korumalıdır."
    mock_response.confidence.tier_badge = "[GÜVENİLİR]"
    mock_response.confidence.overall_score = 88.5
    mock_response.sources = []

    app._on_rag_success(mock_response)
    assert "[GÜVENİLİR]" in app.lbl_confidence.cget("text")
    assert "Wall jump" in app.rag_output_text.get("1.0", tk.END)

    # Hata durumunu test et
    app._on_rag_error("Simulated Error")
    assert "Simulated Error" in app.rag_output_text.get("1.0", tk.END)


def test_gui_launcher_entry():
    """gui_launcher modülünün launch fonksiyonunun hata durumunu güvenle yakaladığını test eder."""
    with patch("game_designer.ui.app.main", side_effect=RuntimeError("GUI Launch Fail")):
        with patch("tkinter.Tk"), patch("tkinter.messagebox.showerror") as mock_box, patch("sys.exit") as mock_exit:
            gui_launcher.launch()
            mock_box.assert_called_once()
            mock_exit.assert_called_once_with(1)


def test_ui_blend_category_filter(tk_root, test_settings, temp_dir):
    """UI üzerindeki kategori filtresinin Blender ağacını doğru filtrelediğini test eder."""
    app = GameDesignerApp(tk_root, settings=test_settings)
    proj = app.plugin.create_project(name="Filter UI Test", activate=True)

    f1 = temp_dir / "hero.blend"
    f1.write_bytes(b"B1")
    f2 = temp_dir / "level.blend"
    f2.write_bytes(b"B2")

    app.plugin.add_blend_file(proj.id, str(f1), category="Karakter")
    app.plugin.add_blend_file(proj.id, str(f2), category="Çevre/Level")
    app._refresh_all_data()

    # Varsayılan Tümü: 2 dosya
    assert len(app.blend_tree.get_children()) == 2

    # Karakter filtresi: 1 dosya
    app.blend_cat_filter_var.set("Karakter")
    app._refresh_blend_table()
    children = app.blend_tree.get_children()
    assert len(children) == 1
    item = app.blend_tree.item(children[0])
    assert item["values"][1] == "Karakter"

    # Çevre/Level filtresi: 1 dosya
    app.blend_cat_filter_var.set("Çevre/Level")
    app._refresh_blend_table()
    assert len(app.blend_tree.get_children()) == 1


def test_ui_projects_tree_double_click_activate(tk_root, test_settings):
    """Projeler ağacında çift tıklamanın projeyi aktif yaptığını test eder."""
    app = GameDesignerApp(tk_root, settings=test_settings)
    p1 = app.plugin.create_project(name="Proj 1", activate=True)
    p2 = app.plugin.create_project(name="Proj 2", activate=False)
    app._refresh_all_data()

    assert app.plugin.get_active_project().id == p1.id

    # p2 seçip _set_selected_as_active tetikle
    app.projects_tree.selection_set(p2.id)
    app._on_project_selected()
    with patch("tkinter.messagebox.showinfo"):
        app._set_selected_as_active()

    assert app.plugin.get_active_project().id == p2.id

