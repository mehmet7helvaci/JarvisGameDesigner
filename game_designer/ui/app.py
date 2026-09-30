"""Jarvis Game Designer — Bağımsız Masaüstü Grafik Arayüzü (GUI).

Unreal / Blender Dark Studio tarzında profesyonel arayüz;
- Sürükle-bırak (Drag-and-Drop) ve tek tıkla otomatik kategorize edilen 3D & animasyon varlık rafı,
- Gerçek zamanlı etkileşimli 3D döndürülebilir ve yakınlaştırılabilir Viewport & Blender küçük resim (thumbnail) görüntüleyici,
- Yüksek hızlı, akışlı (streaming) RAG AI Oyun Tasarım Danışmanı ve hızlı aksiyon çipleri,
- Özel stüdyo ikonu ve Windows görev yöneticisi / görev çubuğu entegrasyonu sunar.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any
from PIL import Image, ImageTk

from game_designer.config import Settings, get_settings
from game_designer.models.project import (
    SUPPORTED_3D_EXTENSIONS,
    SUPPORTED_IMAGE_EXTENSIONS,
    SUPPORTED_ASEPRITE_EXTENSIONS,
    SUPPORTED_EXTENSIONS,
    BlendFileRef,
    GameProject,
    detect_asset_category,
    format_file_size,
)
from game_designer.plugin import GameDesignerPlugin
from game_designer.ui.viewport import Viewport3DCanvas
from game_designer.utils.logger import logger
from game_designer.utils.shortcut import create_desktop_shortcut, get_desktop_path


class DarkTheme:
    """Arayüz renk ve stil paleti — Unreal / Blender Dark Studio."""

    BG_DARK = "#0f172a"        # Ana koyu stüdyo arka planı
    BG_CARD = "#1e293b"        # Kart, raf ve panel arka planı
    BG_INPUT = "#334155"       # Girdi kutuları ve buton tabanı
    BORDER = "#475569"         # Çerçeve ve panel sınır çizgileri
    TEXT_MAIN = "#f8fafc"      # Ana parlak açık metin
    TEXT_MUTED = "#94a3b8"     # İkincil soluk stüdyo metni
    ACCENT_CYAN = "#06b6d4"    # Vurgu rengi neon cyan
    ACCENT_HOVER = "#0891b2"   # Hover cyan
    ACCENT_PURPLE = "#8b5cf6"  # İkincil vurgu mor / neon lilac
    SUCCESS = "#10b981"        # Başarı yeşili
    WARNING = "#f59e0b"        # Uyarı sarısı
    DANGER = "#ef4444"         # Tehlike kırmızısı
    FONT_FAMILY = "Segoe UI" if sys.platform == "win32" else "Helvetica"


class GameDesignerApp:
    """Jarvis Game Designer Bağımsız Masaüstü Uygulaması."""

    def __init__(self, root: tk.Tk, settings: Settings | None = None) -> None:
        self.root = root

        # Windows Yüksek Çözünürlük (DPI) ve Görev Yöneticisi Uygulama Kimliği
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                try:
                    import ctypes
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Jarvis.GameDesigner.Studio.1.0")
            except Exception:
                pass

        self.root.title("Jarvis Game Designer — 3D Studio & Oyun Tasarım İstasyonu")
        self.root.geometry("1280x840")
        self.root.minsize(1080, 720)
        self.root.configure(bg=DarkTheme.BG_DARK)

        # Proje ve Ayarlar
        self.settings: Settings = settings or get_settings()
        self.plugin = GameDesignerPlugin(
            project_root=self.settings.project_root,
            data_dir=self.settings.data_dir,
            chroma_db_dir=self.settings.chroma_db_dir,
            user_profiles_dir=self.settings.user_profiles_dir,
            projects_dir=self.settings.projects_dir,
            seeds_dir=self.settings.seeds_dir,
        )
        self.plugin.initialize(auto_load_seeds=False)

        # Uygulama İkonunu Ayarla (.ico ve .png)
        self._apply_app_icon()

        # Aktif durum
        self.selected_project: GameProject | None = None
        self.selected_blend_ref: BlendFileRef | None = None
        self._stream_running = False

        self._setup_styles()
        self._build_ui()
        self._setup_drag_and_drop()
        self._refresh_all_data()

    def _apply_app_icon(self) -> None:
        """Pencere başlığı ve görev çubuğu ikonunu yükler."""
        assets_dir = self.settings.project_root / "assets"
        icon_ico = assets_dir / "icon.ico"
        icon_png = assets_dir / "icon.png"

        if icon_ico.is_file():
            try:
                self.root.iconbitmap(str(icon_ico))
            except Exception:
                pass

            if sys.platform == "win32":
                try:
                    import ctypes
                    hwnd = self.root.winfo_id()
                    parent_hwnd = ctypes.windll.user32.GetParent(hwnd)
                    target_hwnd = parent_hwnd if parent_hwnd else hwnd
                    LR_LOADFROMFILE = 0x00000010
                    IMAGE_ICON = 1
                    WM_SETICON = 0x0080
                    hicon_big = ctypes.windll.user32.LoadImageW(None, str(icon_ico.resolve()), IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
                    hicon_small = ctypes.windll.user32.LoadImageW(None, str(icon_ico.resolve()), IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
                    if hicon_big:
                        ctypes.windll.user32.SendMessageW(target_hwnd, WM_SETICON, 1, hicon_big)
                    if hicon_small:
                        ctypes.windll.user32.SendMessageW(target_hwnd, WM_SETICON, 0, hicon_small)
                except Exception:
                    pass

        if icon_png.is_file():
            try:
                photo = ImageTk.PhotoImage(file=str(icon_png))
                self.root.iconphoto(True, photo)
                self._icon_photo_ref = photo  # Garbage collection koruması
            except Exception:
                pass

    def _setup_drag_and_drop(self) -> None:
        """Sürükle-bırak (Drag-and-Drop) kancalarını sisteme bağlar."""
        # Pytest ortamında pencere prosedürü kancalanması birden fazla örnekte bellek erişim uyarısı verir
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return

        try:
            import windnd
            windnd.hook_dropfiles(self.root, func=self._on_files_dropped)
            logger.info("Windows Drag-and-Drop (windnd) başarıyla bağlandı.")
        except Exception as e:
            logger.debug(f"Drag-and-Drop kancası yüklenemedi: {e}")

    def _on_files_dropped(self, files: list[Any]) -> None:
        """Kullanıcı dosyaları veya klasörleri pencereye sürükleyip bıraktığında çalışır."""
        if not files:
            return

        all_paths: list[str] = []
        for item in files:
            if isinstance(item, bytes):
                file_str = item.decode("mbcs", errors="replace")
            else:
                file_str = str(item)

            p = Path(file_str)
            if p.is_dir():
                for ext in SUPPORTED_EXTENSIONS:
                    for f in p.rglob(f"*{ext}"):
                        if f.is_file():
                            all_paths.append(str(f))
            elif p.is_file():
                if p.suffix.lower() in SUPPORTED_EXTENSIONS:
                    all_paths.append(str(p))

        if all_paths:
            self._batch_add_assets(all_paths)

    def _setup_styles(self) -> None:
        """Ttk widget stillerini Unreal / Blender Dark Studio temasına uyarlar."""
        style = ttk.Style()
        style.theme_use("clam")

        # Notebook (Sekmeler)
        style.configure(
            "TNotebook",
            background=DarkTheme.BG_DARK,
            borderwidth=0,
        )
        style.configure(
            "TNotebook.Tab",
            background=DarkTheme.BG_CARD,
            foreground=DarkTheme.TEXT_MUTED,
            padding=[18, 9],
            font=(DarkTheme.FONT_FAMILY, 10, "bold"),
            borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", DarkTheme.BG_DARK), ("active", DarkTheme.BG_INPUT)],
            foreground=[("selected", DarkTheme.ACCENT_CYAN), ("active", DarkTheme.TEXT_MAIN)],
        )

        # Frame stilleri
        style.configure("Dark.TFrame", background=DarkTheme.BG_DARK)
        style.configure("Card.TFrame", background=DarkTheme.BG_CARD, relief="flat")

        # Buton stilleri
        style.configure(
            "Primary.TButton",
            background=DarkTheme.ACCENT_CYAN,
            foreground="#021526",
            font=(DarkTheme.FONT_FAMILY, 9, "bold"),
            padding=[10, 6],
            borderwidth=0,
        )
        style.map(
            "Primary.TButton",
            background=[("active", DarkTheme.ACCENT_HOVER)],
            foreground=[("active", "#ffffff")],
        )

        style.configure(
            "Secondary.TButton",
            background=DarkTheme.BG_INPUT,
            foreground=DarkTheme.TEXT_MAIN,
            font=(DarkTheme.FONT_FAMILY, 9),
            padding=[10, 6],
            borderwidth=0,
        )
        style.map(
            "Secondary.TButton",
            background=[("active", DarkTheme.BORDER)],
        )

        style.configure(
            "Success.TButton",
            background=DarkTheme.SUCCESS,
            foreground="#021526",
            font=(DarkTheme.FONT_FAMILY, 9, "bold"),
            padding=[10, 6],
            borderwidth=0,
        )

        # Treeview (Tablo) stilleri
        style.configure(
            "Treeview",
            background=DarkTheme.BG_CARD,
            fieldbackground=DarkTheme.BG_CARD,
            foreground=DarkTheme.TEXT_MAIN,
            font=(DarkTheme.FONT_FAMILY, 9),
            rowheight=28,
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background=DarkTheme.BG_INPUT,
            foreground=DarkTheme.TEXT_MAIN,
            font=(DarkTheme.FONT_FAMILY, 9, "bold"),
            padding=[6, 6],
            borderwidth=0,
        )
        style.map(
            "Treeview",
            background=[("selected", DarkTheme.BG_INPUT)],
            foreground=[("selected", DarkTheme.ACCENT_CYAN)],
        )

        # Combobox
        style.configure(
            "TCombobox",
            fieldbackground=DarkTheme.BG_INPUT,
            background=DarkTheme.BG_INPUT,
            foreground=DarkTheme.TEXT_MAIN,
            darkcolor=DarkTheme.BG_INPUT,
            lightcolor=DarkTheme.BG_INPUT,
        )

    def _build_ui(self) -> None:
        """Ana stüdyo arayüzünü inşa eder."""
        # Üst Başlık Banner (Header)
        header = tk.Frame(self.root, bg=DarkTheme.BG_CARD, padx=16, pady=10)
        header.pack(fill=tk.X, padx=10, pady=(8, 4))

        title_box = tk.Frame(header, bg=DarkTheme.BG_CARD)
        title_box.pack(side=tk.LEFT, fill=tk.Y)

        title_row = tk.Frame(title_box, bg=DarkTheme.BG_CARD)
        title_row.pack(anchor=tk.W)

        tk.Label(
            title_row,
            text="🎮 JARVIS GAME DESIGNER",
            bg=DarkTheme.BG_CARD,
            fg=DarkTheme.ACCENT_CYAN,
            font=(DarkTheme.FONT_FAMILY, 14, "bold"),
        ).pack(side=tk.LEFT)

        tk.Label(
            title_row,
            text=" STUDIO",
            bg=DarkTheme.BG_CARD,
            fg=DarkTheme.ACCENT_PURPLE,
            font=(DarkTheme.FONT_FAMILY, 14, "bold"),
        ).pack(side=tk.LEFT)

        tk.Label(
            title_box,
            text="3D Varlık Önizleme • Sürükle-Bırak Tanımlama • Yüksek Hızlı AI Danışmanı",
            bg=DarkTheme.BG_CARD,
            fg=DarkTheme.TEXT_MUTED,
            font=(DarkTheme.FONT_FAMILY, 8),
        ).pack(anchor=tk.W)

        # Sağ üst aktif proje rozeti
        self.active_banner = tk.Label(
            header,
            text="Aktif Proje: Yükleniyor...",
            bg=DarkTheme.BG_INPUT,
            fg=DarkTheme.SUCCESS,
            font=(DarkTheme.FONT_FAMILY, 10, "bold"),
            padx=12,
            pady=6,
            relief="flat",
        )
        self.active_banner.pack(side=tk.RIGHT)

        # Sekme Yöneticisi (Notebook)
        self.notebook = ttk.Notebook(self.root, style="TNotebook")
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 10))

        # Sekme 1: Ana Stüdyo & 3D Varlık İstasyonu
        self.tab_projects = ttk.Frame(self.notebook, style="Dark.TFrame")
        self.notebook.add(self.tab_projects, text=" 🎮 Stüdyo & 3D Varlıklar ")
        self._build_studio_tab(self.tab_projects)

        # Sekme 2: Oyun Tasarımı Danışmanı (Geniş RAG AI Görünümü)
        self.tab_rag = ttk.Frame(self.notebook, style="Dark.TFrame")
        self.notebook.add(self.tab_rag, text=" 🤖 Tasarım Danışmanı (RAG AI) ")
        self._build_rag_tab(self.tab_rag)

        # Sekme 3: Senkronizasyon & Sistem Durumu
        self.tab_sync = ttk.Frame(self.notebook, style="Dark.TFrame")
        self.notebook.add(self.tab_sync, text=" 🔄 Senkronizasyon & Durum ")
        self._build_sync_tab(self.tab_sync)

    # =========================================================================
    # SEKME 1: ANA STÜDYO (UNREAL / BLENDER DARK STUDIO DÜZENİ)
    # =========================================================================

    def _build_studio_tab(self, parent: ttk.Frame) -> None:
        """Unreal/Blender Dark Studio tarzı ana çalışma alanını oluşturur."""
        main_paned = tk.PanedWindow(
            parent,
            orient=tk.HORIZONTAL,
            bg=DarkTheme.BORDER,
            sashwidth=5,
            sashrelief="flat",
        )
        main_paned.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # -------------------------------------------------------------
        # SOL SÜTUN: PROJELER & VARLIK RAFI
        # -------------------------------------------------------------
        left_container = tk.Frame(main_paned, bg=DarkTheme.BG_CARD, padx=8, pady=8)
        main_paned.add(left_container, minsize=380, width=460)

        left_paned = tk.PanedWindow(
            left_container,
            orient=tk.VERTICAL,
            bg=DarkTheme.BORDER,
            sashwidth=4,
            sashrelief="flat",
        )
        left_paned.pack(fill=tk.BOTH, expand=True)

        # 1. Üst Kısım: Projeler Listesi
        p_box = tk.Frame(left_paned, bg=DarkTheme.BG_CARD)
        left_paned.add(p_box, minsize=180, height=220)

        p_header = tk.Frame(p_box, bg=DarkTheme.BG_CARD)
        p_header.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            p_header,
            text="📂 Oyun Projeleri",
            bg=DarkTheme.BG_CARD,
            fg=DarkTheme.TEXT_MAIN,
            font=(DarkTheme.FONT_FAMILY, 11, "bold"),
        ).pack(side=tk.LEFT)

        p_btn_bar = tk.Frame(p_box, bg=DarkTheme.BG_CARD)
        p_btn_bar.pack(fill=tk.X, pady=(0, 6))

        ttk.Button(p_btn_bar, text="➕ Yeni", style="Primary.TButton", command=self._open_new_project_modal).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(p_btn_bar, text="✏️ Düzenle", style="Secondary.TButton", command=self._open_edit_project_modal).pack(side=tk.LEFT, padx=3)
        ttk.Button(p_btn_bar, text="🌟 Aktif Yap", style="Success.TButton", command=self._set_selected_as_active).pack(side=tk.LEFT, padx=3)
        ttk.Button(p_btn_bar, text="🗑️ Sil", style="Secondary.TButton", command=self._delete_selected_project).pack(side=tk.LEFT, padx=3)

        p_table_frame = tk.Frame(p_box, bg=DarkTheme.BG_CARD)
        p_table_frame.pack(fill=tk.BOTH, expand=True)

        p_cols = ("status", "name", "engine", "genre", "blends")
        self.projects_tree = ttk.Treeview(p_table_frame, columns=p_cols, show="headings", selectmode="browse")
        self.projects_tree.heading("status", text="Durum")
        self.projects_tree.heading("name", text="Proje Adı")
        self.projects_tree.heading("engine", text="Motor")
        self.projects_tree.heading("genre", text="Tür")
        self.projects_tree.heading("blends", text="Varlık")

        self.projects_tree.column("status", width=55, anchor=tk.CENTER)
        self.projects_tree.column("name", width=140)
        self.projects_tree.column("engine", width=80)
        self.projects_tree.column("genre", width=80)
        self.projects_tree.column("blends", width=55, anchor=tk.CENTER)

        p_scroll = ttk.Scrollbar(p_table_frame, orient=tk.VERTICAL, command=self.projects_tree.yview)
        self.projects_tree.configure(yscrollcommand=p_scroll.set)
        self.projects_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        p_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.projects_tree.bind("<<TreeviewSelect>>", self._on_project_selected)
        self.projects_tree.bind("<Double-1>", lambda e: self._set_selected_as_active())

        # 2. Alt Kısım: Varlık Rafı (Asset Shelf) & Sürükle-Bırak Alanı
        a_box = tk.Frame(left_paned, bg=DarkTheme.BG_CARD, pady=4)
        left_paned.add(a_box, minsize=260)

        # Sürükle-Bırak & Tek Tıkla Ekleme Çubuğu
        drop_banner = tk.Frame(a_box, bg=DarkTheme.BG_INPUT, padx=8, pady=8, relief="ridge", bd=1)
        drop_banner.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            drop_banner,
            text="📥 Sürükle & Bırak veya Tek Tıkla Ekle (3D, 2D Görsel, Aseprite)",
            bg=DarkTheme.BG_INPUT,
            fg=DarkTheme.ACCENT_CYAN,
            font=(DarkTheme.FONT_FAMILY, 9, "bold"),
        ).pack(side=tk.LEFT)

        ttk.Button(
            drop_banner,
            text="⚡ Dosya Seç & Ekle",
            style="Primary.TButton",
            command=self._quick_add_asset_dialog,
        ).pack(side=tk.RIGHT)

        # Varlık Kontrolleri & Kategori Filtresi
        a_ctrl_bar = tk.Frame(a_box, bg=DarkTheme.BG_CARD)
        a_ctrl_bar.pack(fill=tk.X, pady=(0, 6))

        ttk.Button(a_ctrl_bar, text="🚀 Blender ile Aç", style="Success.TButton", command=self._open_selected_blend).pack(side=tk.LEFT, padx=(0, 3))
        ttk.Button(a_ctrl_bar, text="🎨 Aseprite ile Aç", style="Primary.TButton", command=self._open_selected_aseprite).pack(side=tk.LEFT, padx=3)
        ttk.Button(a_ctrl_bar, text="🗑️ Kaldır", style="Secondary.TButton", command=self._remove_selected_blend).pack(side=tk.LEFT, padx=3)
        ttk.Button(a_ctrl_bar, text="🔄 Yenile", style="Secondary.TButton", command=self._refresh_blend_table).pack(side=tk.LEFT, padx=3)

        tk.Label(a_ctrl_bar, text="Filtre:", bg=DarkTheme.BG_CARD, fg=DarkTheme.TEXT_MUTED, font=(DarkTheme.FONT_FAMILY, 9)).pack(side=tk.LEFT, padx=(8, 2))
        self.blend_cat_filter_var = tk.StringVar(value="Tümü")
        self.blend_cat_combo = ttk.Combobox(
            a_ctrl_bar,
            textvariable=self.blend_cat_filter_var,
            values=["Tümü", "2D Sprite / Piksel Sanatı", "Animasyon", "Karakter", "Çevre/Level", "Prop", "Araç", "VFX/Diğer", "Genel"],
            state="readonly",
            width=14,
        )
        self.blend_cat_combo.pack(side=tk.LEFT, padx=2)
        self.blend_cat_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_blend_table())

        # Varlık Tablosu (Treeview)
        b_table_frame = tk.Frame(a_box, bg=DarkTheme.BG_CARD)
        b_table_frame.pack(fill=tk.BOTH, expand=True)

        b_cols = ("name", "category", "size", "modified", "status", "path")
        self.blend_tree = ttk.Treeview(b_table_frame, columns=b_cols, show="headings", selectmode="browse")
        self.blend_tree.heading("name", text="Varlık Adı")
        self.blend_tree.heading("category", text="Kategori (Otomatik)")
        self.blend_tree.heading("size", text="Boyut")
        self.blend_tree.heading("modified", text="Değişiklik")
        self.blend_tree.heading("status", text="Durum")
        self.blend_tree.heading("path", text="Dosya Yolu")

        self.blend_tree.column("name", width=130)
        self.blend_tree.column("category", width=95)
        self.blend_tree.column("size", width=65, anchor=tk.E)
        self.blend_tree.column("modified", width=105)
        self.blend_tree.column("status", width=65, anchor=tk.CENTER)
        self.blend_tree.column("path", width=150)

        b_scroll = ttk.Scrollbar(b_table_frame, orient=tk.VERTICAL, command=self.blend_tree.yview)
        self.blend_tree.configure(yscrollcommand=b_scroll.set)
        self.blend_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        b_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.blend_tree.bind("<<TreeviewSelect>>", self._on_blend_selected)
        self.blend_tree.bind("<Double-1>", lambda e: self._open_selected_blend())

        # -------------------------------------------------------------
        # SAĞ SÜTUN: 3D VIEWPORT (ÜST) + HIZLI AI DANIŞMANI (ALT)
        # -------------------------------------------------------------
        right_container = tk.Frame(main_paned, bg=DarkTheme.BG_DARK)
        main_paned.add(right_container, minsize=540)

        right_paned = tk.PanedWindow(
            right_container,
            orient=tk.VERTICAL,
            bg=DarkTheme.BORDER,
            sashwidth=5,
            sashrelief="flat",
        )
        right_paned.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # 1. SAĞ ÜST: ETKİLEŞİMLİ 3D VIEWPORT & ASSET INSPECTOR
        vp_section = tk.Frame(right_paned, bg=DarkTheme.BG_DARK)
        right_paned.add(vp_section, minsize=260, height=360)

        # Viewport başlık çubuğu & Araçlar
        vp_header = tk.Frame(vp_section, bg=DarkTheme.BG_DARK)
        vp_header.pack(fill=tk.X, pady=(0, 4))

        tk.Label(
            vp_header,
            text="👁️ 3D / Görsel Önizleme Viewport",
            bg=DarkTheme.BG_DARK,
            fg=DarkTheme.TEXT_MAIN,
            font=(DarkTheme.FONT_FAMILY, 11, "bold"),
        ).pack(side=tk.LEFT)

        ttk.Button(vp_header, text="🎯 Sıfırla", style="Secondary.TButton", command=self._reset_viewport_camera).pack(side=tk.RIGHT, padx=2)
        ttk.Button(vp_header, text="📷 / 📐 Mod", style="Secondary.TButton", command=self._toggle_viewport_mode).pack(side=tk.RIGHT, padx=2)
        ttk.Button(vp_header, text="🔄 3D Çevir", style="Secondary.TButton", command=self._toggle_viewport_spin).pack(side=tk.RIGHT, padx=2)
        ttk.Button(vp_header, text="👾 Piksel/Yumuşak", style="Secondary.TButton", command=self._toggle_viewport_scaling).pack(side=tk.RIGHT, padx=2)
        ttk.Button(vp_header, text="▶️ / ⏸️", style="Secondary.TButton", command=self._toggle_viewport_animation).pack(side=tk.RIGHT, padx=2)
        ttk.Button(vp_header, text="⏭️", style="Secondary.TButton", command=self._next_viewport_frame).pack(side=tk.RIGHT, padx=1)
        ttk.Button(vp_header, text="⏮️", style="Secondary.TButton", command=self._prev_viewport_frame).pack(side=tk.RIGHT, padx=1)

        # Viewport + Yan Inspector Paneli
        vp_content = tk.Frame(vp_section, bg=DarkTheme.BG_CARD)
        vp_content.pack(fill=tk.BOTH, expand=True)

        # 3D Canvas
        self.viewport_3d = Viewport3DCanvas(vp_content, bg=DarkTheme.BG_DARK)
        self.viewport_3d.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Yan Inspector Bilgi Kartı
        self.detail_card = tk.LabelFrame(
            vp_content,
            text=" 📌 Varlık & Proje Bilgisi ",
            bg=DarkTheme.BG_CARD,
            fg=DarkTheme.ACCENT_CYAN,
            font=(DarkTheme.FONT_FAMILY, 9, "bold"),
            padx=10,
            pady=6,
            relief="groove",
            width=260,
        )
        self.detail_card.pack(side=tk.RIGHT, fill=tk.Y, padx=(4, 0))
        self.detail_card.pack_propagate(False)

        self.lbl_proj_title = tk.Label(
            self.detail_card,
            text="Henüz proje seçilmedi",
            bg=DarkTheme.BG_CARD,
            fg=DarkTheme.TEXT_MAIN,
            font=(DarkTheme.FONT_FAMILY, 10, "bold"),
            anchor=tk.W,
            wraplength=230,
        )
        self.lbl_proj_title.pack(fill=tk.X)

        self.lbl_proj_meta = tk.Label(
            self.detail_card,
            text="Motor: - | Tür: -",
            bg=DarkTheme.BG_CARD,
            fg=DarkTheme.TEXT_MUTED,
            font=(DarkTheme.FONT_FAMILY, 8),
            anchor=tk.W,
        )
        self.lbl_proj_meta.pack(fill=tk.X, pady=1)

        self.lbl_proj_desc = tk.Label(
            self.detail_card,
            text="",
            bg=DarkTheme.BG_CARD,
            fg=DarkTheme.TEXT_MAIN,
            font=(DarkTheme.FONT_FAMILY, 8),
            anchor=tk.W,
            justify=tk.LEFT,
            wraplength=230,
        )
        self.lbl_proj_desc.pack(fill=tk.X, pady=2)

        # Varlık Özellikleri Alt Bölümü
        tk.Label(self.detail_card, text="--- Seçili 3D Varlık ---", bg=DarkTheme.BG_CARD, fg=DarkTheme.BORDER, font=(DarkTheme.FONT_FAMILY, 8)).pack(fill=tk.X, pady=(4, 2))
        self.lbl_asset_inspector = tk.Label(
            self.detail_card,
            text="Tablodan bir varlığa tıklayarak\nönizleme ve detayları inceleyin.",
            bg=DarkTheme.BG_CARD,
            fg=DarkTheme.ACCENT_CYAN,
            font=(DarkTheme.FONT_FAMILY, 8),
            justify=tk.LEFT,
            anchor=tk.W,
            wraplength=230,
        )
        self.lbl_asset_inspector.pack(fill=tk.X, pady=2)

        # 2. SAĞ ALT: AI GAME DESIGN ADVISOR (HIZLI & STREAMING)
        ai_section = tk.Frame(right_paned, bg=DarkTheme.BG_DARK)
        right_paned.add(ai_section, minsize=240)

        ai_header = tk.Frame(ai_section, bg=DarkTheme.BG_DARK)
        ai_header.pack(fill=tk.X, pady=(0, 4))

        tk.Label(
            ai_header,
            text="⚡ AI Tasarım Danışmanı (Hızlı Streaming RAG)",
            bg=DarkTheme.BG_DARK,
            fg=DarkTheme.TEXT_MAIN,
            font=(DarkTheme.FONT_FAMILY, 11, "bold"),
        ).pack(side=tk.LEFT)

        self.lbl_confidence = tk.Label(
            ai_header,
            text="Güvenilirlik: -",
            bg=DarkTheme.BG_INPUT,
            fg=DarkTheme.ACCENT_CYAN,
            font=(DarkTheme.FONT_FAMILY, 8, "bold"),
            padx=8,
            pady=2,
        )
        self.lbl_confidence.pack(side=tk.RIGHT)

        # Hızlı Aksiyon Çipleri (Quick Action Chips)
        chips_frame = tk.Frame(ai_section, bg=DarkTheme.BG_DARK)
        chips_frame.pack(fill=tk.X, pady=(0, 4))

        tk.Label(chips_frame, text="Hızlı:", bg=DarkTheme.BG_DARK, fg=DarkTheme.TEXT_MUTED, font=(DarkTheme.FONT_FAMILY, 8)).pack(side=tk.LEFT, padx=(0, 4))
        self._create_action_chip(chips_frame, "🎮 Mekanik Analiz", "Temel oynanış döngüsü (core gameplay loop) ve karakter kontrollerinin juice/gamelfeel analizi", "analyze_game")
        self._create_action_chip(chips_frame, "🏃 Animasyon Değerlendirme", "3D karakter ve animasyon geçişlerinde blend tree, kök hareketi (root motion) ve tepki süresi tasarımı", "query")
        self._create_action_chip(chips_frame, "📜 GDD Taslağı", "Oyun tasarım dökümanı (GDD) ana mekanikler, kamera sistemleri ve ilerleme döngüsü taslağı", "create_gdd")
        self._create_action_chip(chips_frame, "💡 Fikir Fırtınası", "Bu oyun türü için oyuncuyu bağlayan yenilikçi alt-mekanikler ve sürpriz elementler", "brainstorm")

        # Girdi ve Mod Seçimi Satırı
        ai_input_bar = tk.Frame(ai_section, bg=DarkTheme.BG_CARD, padx=8, pady=6)
        ai_input_bar.pack(fill=tk.X, pady=(0, 4))

        self.mode_var = tk.StringVar(value="query")
        self.mode_combo = ttk.Combobox(
            ai_input_bar,
            textvariable=self.mode_var,
            values=[
                "query (Soru-Cevap)",
                "advise (Aktif Proje Danışmanlığı)",
                "analyze_game (MDA Oyun Analizi)",
                "brainstorm (Beyin Fırtınası)",
                "compare (Karşılaştırma)",
                "create_gdd (GDD Taslağı)",
                "brief (Yönetici Brifingi)",
                "market_analysis (Pazar Analizi)",
            ],
            state="readonly",
            width=24,
        )
        self.mode_combo.pack(side=tk.LEFT, padx=(0, 6))

        self.rag_input_text = tk.Text(
            ai_input_bar,
            bg=DarkTheme.BG_INPUT,
            fg=DarkTheme.TEXT_MAIN,
            insertbackground=DarkTheme.TEXT_MAIN,
            font=(DarkTheme.FONT_FAMILY, 9),
            height=2,
            wrap=tk.WORD,
            relief="flat",
        )
        self.rag_input_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        self.rag_input_text.insert("1.0", "Karakter zıplama ve duvarda koşma (wall-run) mekaniği oyun hissiyatını nasıl güçlendirir?")

        self.btn_ask = ttk.Button(
            ai_input_bar,
            text="⚡ AI'ya Sor",
            style="Primary.TButton",
            command=self._execute_rag_query,
        )
        self.btn_ask.pack(side=tk.RIGHT, padx=(4, 0))

        # Çıktı & Kaynaklar Paneli
        ai_out_paned = tk.PanedWindow(ai_section, orient=tk.HORIZONTAL, bg=DarkTheme.BORDER, sashwidth=4)
        ai_out_paned.pack(fill=tk.BOTH, expand=True)

        out_text_frame = tk.Frame(ai_out_paned, bg=DarkTheme.BG_CARD)
        ai_out_paned.add(out_text_frame, minsize=320, width=480)

        self.rag_output_text = tk.Text(
            out_text_frame,
            bg=DarkTheme.BG_CARD,
            fg=DarkTheme.TEXT_MAIN,
            font=(DarkTheme.FONT_FAMILY, 9),
            wrap=tk.WORD,
            relief="flat",
            padx=8,
            pady=8,
        )
        out_scroll = ttk.Scrollbar(out_text_frame, orient=tk.VERTICAL, command=self.rag_output_text.yview)
        self.rag_output_text.configure(yscrollcommand=out_scroll.set)
        self.rag_output_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        out_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        sources_frame = tk.Frame(ai_out_paned, bg=DarkTheme.BG_CARD, padx=4, pady=4)
        ai_out_paned.add(sources_frame, minsize=140)

        tk.Label(sources_frame, text="📚 Dayanak Kaynaklar", bg=DarkTheme.BG_CARD, fg=DarkTheme.TEXT_MAIN, font=(DarkTheme.FONT_FAMILY, 9, "bold")).pack(anchor=tk.W)
        self.sources_listbox = tk.Listbox(
            sources_frame,
            bg=DarkTheme.BG_INPUT,
            fg=DarkTheme.TEXT_MAIN,
            selectbackground=DarkTheme.ACCENT_CYAN,
            selectforeground="#021526",
            font=(DarkTheme.FONT_FAMILY, 8),
            relief="flat",
        )
        self.sources_listbox.pack(fill=tk.BOTH, expand=True)

        self.lbl_rag_status = tk.Label(
            ai_section,
            text="Hazır. Hızlı çiplere tıklayabilir veya kendi sorunuzu sorabilirsiniz.",
            bg=DarkTheme.BG_DARK,
            fg=DarkTheme.TEXT_MUTED,
            font=(DarkTheme.FONT_FAMILY, 8),
            anchor=tk.W,
        )
        self.lbl_rag_status.pack(fill=tk.X, pady=(2, 0))

    def _create_action_chip(self, parent: tk.Widget, label: str, prompt: str, mode: str) -> None:
        """Hızlı eylem çipi oluşturur."""
        def on_click():
            self.rag_input_text.delete("1.0", tk.END)
            self.rag_input_text.insert("1.0", prompt)
            # Modu güncelle
            for val in self.mode_combo["values"]:
                if val.startswith(mode):
                    self.mode_var.set(val)
                    break
            self._execute_rag_query()

        btn = tk.Button(
            parent,
            text=label,
            bg=DarkTheme.BG_INPUT,
            fg=DarkTheme.TEXT_MAIN,
            activebackground=DarkTheme.ACCENT_CYAN,
            activeforeground="#021526",
            font=(DarkTheme.FONT_FAMILY, 8),
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            command=on_click,
        )
        btn.pack(side=tk.LEFT, padx=3)

    def _reset_viewport_camera(self) -> None:
        if hasattr(self, "viewport_3d"):
            self.viewport_3d.reset_camera()

    def _toggle_viewport_mode(self) -> None:
        if hasattr(self, "viewport_3d"):
            self.viewport_3d.toggle_mode()

    def _toggle_viewport_animation(self) -> None:
        if hasattr(self, "viewport_3d"):
            self.viewport_3d.toggle_animation()

    def _toggle_viewport_spin(self) -> None:
        if hasattr(self, "viewport_3d"):
            self.viewport_3d.toggle_auto_spin()

    # =========================================================================
    # SEKME 2: GENİŞLETİLMİŞ TASARIM DANIŞMANI (RAG AI CHAT & GDD STÜDYOSU)
    # =========================================================================

    def _build_rag_tab(self, parent: ttk.Frame) -> None:
        """Genişletilmiş RAG AI oyun tasarım danışmanı ve GDD stüdyo çalışma alanını oluşturur."""
        rag_paned = tk.PanedWindow(parent, orient=tk.HORIZONTAL, bg=DarkTheme.BORDER, sashwidth=5)
        rag_paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Sol Kontrol ve Prompt Paneli
        left_ctrl = tk.Frame(rag_paned, bg=DarkTheme.BG_CARD, padx=12, pady=12)
        rag_paned.add(left_ctrl, minsize=320, width=420)

        tk.Label(
            left_ctrl,
            text="🤖 AI Tasarım & GDD Stüdyosu",
            bg=DarkTheme.BG_CARD,
            fg=DarkTheme.ACCENT_CYAN,
            font=(DarkTheme.FONT_FAMILY, 12, "bold"),
        ).pack(anchor=tk.W, pady=(0, 4))

        tk.Label(
            left_ctrl,
            text="Oyun mekanikleri analizi, GDD dökümantasyonu, pazar araştırması ve beyin fırtınası.",
            bg=DarkTheme.BG_CARD,
            fg=DarkTheme.TEXT_MUTED,
            font=(DarkTheme.FONT_FAMILY, 8),
            wraplength=380,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 10))

        # Mod Seçimi
        tk.Label(left_ctrl, text="Çalışma Modu:", bg=DarkTheme.BG_CARD, fg=DarkTheme.TEXT_MAIN, font=(DarkTheme.FONT_FAMILY, 9, "bold")).pack(anchor=tk.W)
        self.rag_tab_mode_var = tk.StringVar(value="analyze_game (MDA Oyun Analizi)")
        tab_mode_combo = ttk.Combobox(
            left_ctrl,
            textvariable=self.rag_tab_mode_var,
            values=[
                "analyze_game (MDA Oyun Analizi)",
                "create_gdd (GDD Taslağı Oluştur)",
                "advise (Aktif Proje Danışmanlığı)",
                "brainstorm (Mekanik Beyin Fırtınası)",
                "compare (Karşılaştırma)",
                "market_analysis (Pazar Analizi)",
                "brief (Yönetici Brifingi)",
                "query (Genel Soru-Cevap)",
            ],
            state="readonly",
        )
        tab_mode_combo.pack(fill=tk.X, pady=(2, 10))

        # Hızlı Şablonlar
        tk.Label(left_ctrl, text="Tasarım Konuları / Şablonlar:", bg=DarkTheme.BG_CARD, fg=DarkTheme.TEXT_MAIN, font=(DarkTheme.FONT_FAMILY, 9, "bold")).pack(anchor=tk.W)
        chips_f = tk.Frame(left_ctrl, bg=DarkTheme.BG_CARD)
        chips_f.pack(fill=tk.X, pady=(2, 10))

        def set_tab_prompt(txt: str, m: str) -> None:
            self.rag_tab_prompt_text.delete("1.0", tk.END)
            self.rag_tab_prompt_text.insert("1.0", txt)
            for v in tab_mode_combo["values"]:
                if v.startswith(m):
                    self.rag_tab_mode_var.set(v)
                    break

        ttk.Button(chips_f, text="🎮 Karakter Kontrol & Juice", style="Secondary.TButton",
                   command=lambda: set_tab_prompt("Karakter hareketlerinde coyote time, input buffering ve jump cut mekanikleri nasıl tasarlanır?", "analyze_game")).pack(fill=tk.X, pady=2)
        ttk.Button(chips_f, text="🏃 Animasyon & Blend Tree", style="Secondary.TButton",
                   command=lambda: set_tab_prompt("Yürüme, koşma ve zıplama geçişlerinde root motion ve blend tree mimarisi nasıl kurulur?", "query")).pack(fill=tk.X, pady=2)
        ttk.Button(chips_f, text="📜 Kapsamlı GDD Taslağı", style="Secondary.TButton",
                   command=lambda: set_tab_prompt("Aktif oyun projemiz için ana oynanış döngüsü, kamera sistemleri ve progression döngüsü GDD taslağı oluştur.", "create_gdd")).pack(fill=tk.X, pady=2)
        ttk.Button(chips_f, text="💡 Yenilikçi Mekanik Fırtınası", style="Secondary.TButton",
                   command=lambda: set_tab_prompt("Bu türe özgü, daha önce denenmemiş zaman manipülasyonu veya kanca mekaniği fikirleri üret.", "brainstorm")).pack(fill=tk.X, pady=2)

        # Prompt Giriş Kutusu
        tk.Label(left_ctrl, text="Tasarım Sorusu / Analiz Konusu:", bg=DarkTheme.BG_CARD, fg=DarkTheme.TEXT_MAIN, font=(DarkTheme.FONT_FAMILY, 9, "bold")).pack(anchor=tk.W, pady=(6, 2))
        self.rag_tab_prompt_text = tk.Text(
            left_ctrl,
            bg=DarkTheme.BG_INPUT,
            fg=DarkTheme.TEXT_MAIN,
            insertbackground=DarkTheme.TEXT_MAIN,
            font=(DarkTheme.FONT_FAMILY, 9),
            height=6,
            wrap=tk.WORD,
            relief="flat",
        )
        self.rag_tab_prompt_text.pack(fill=tk.X, pady=(0, 10))
        self.rag_tab_prompt_text.insert("1.0", "Karakter hareketlerinde coyote time, input buffering ve jump cut mekanikleri nasıl tasarlanır?")

        btn_run = ttk.Button(
            left_ctrl,
            text="⚡ Derinlemesine Analiz Üret",
            style="Primary.TButton",
            command=self._execute_rag_tab_query,
        )
        btn_run.pack(fill=tk.X, pady=(0, 8))

        # Sağ Sonuç & GDD Çıktı Paneli
        right_res = tk.Frame(rag_paned, bg=DarkTheme.BG_CARD, padx=12, pady=12)
        rag_paned.add(right_res, minsize=460)

        out_header = tk.Frame(right_res, bg=DarkTheme.BG_CARD)
        out_header.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            out_header,
            text="📑 Üretilen Tasarım Analizi & GDD",
            bg=DarkTheme.BG_CARD,
            fg=DarkTheme.TEXT_MAIN,
            font=(DarkTheme.FONT_FAMILY, 11, "bold"),
        ).pack(side=tk.LEFT)

        ttk.Button(out_header, text="📋 Yanıtı Kopyala", style="Secondary.TButton", command=self._copy_rag_tab_output).pack(side=tk.RIGHT, padx=3)
        ttk.Button(out_header, text="💾 GDD Olarak Kaydet", style="Success.TButton", command=self._export_gdd_to_file).pack(side=tk.RIGHT, padx=3)

        self.rag_tab_output_text = tk.Text(
            right_res,
            bg=DarkTheme.BG_DARK,
            fg=DarkTheme.TEXT_MAIN,
            font=(DarkTheme.FONT_FAMILY, 10),
            wrap=tk.WORD,
            relief="flat",
            padx=12,
            pady=12,
        )
        tab_out_scroll = ttk.Scrollbar(right_res, orient=tk.VERTICAL, command=self.rag_tab_output_text.yview)
        self.rag_tab_output_text.configure(yscrollcommand=tab_out_scroll.set)
        self.rag_tab_output_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tab_out_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _copy_rag_tab_output(self) -> None:
        text = self.rag_tab_output_text.get("1.0", tk.END).strip()
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            messagebox.showinfo("Kopyalandı", "Tasarım analizi panoya kopyalandı.")

    def _export_gdd_to_file(self) -> None:
        text = self.rag_tab_output_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Uyarı", "Kaydedilecek analiz metni henüz üretilmedi.")
            return

        fp = filedialog.asksaveasfilename(
            title="GDD / Tasarım Dokümanını Kaydet",
            defaultextension=".md",
            filetypes=[("Markdown Belgesi (*.md)", "*.md"), ("Metin Belgesi (*.txt)", "*.txt"), ("Tüm Dosyalar", "*.*")],
        )
        if fp:
            try:
                Path(fp).write_text(text, encoding="utf-8")
                messagebox.showinfo("Başarılı", f"Doküman başarıyla kaydedildi:\n{fp}")
            except Exception as e:
                messagebox.showerror("Hata", f"Dosya kaydedilemedi: {e}")

    def _execute_rag_tab_query(self) -> None:
        prompt = self.rag_tab_prompt_text.get("1.0", tk.END).strip()
        if not prompt:
            return
        mode = self.rag_tab_mode_var.get().split()[0]
        self.rag_tab_output_text.delete("1.0", tk.END)
        self.rag_tab_output_text.insert("1.0", "⚡ Jarvis AI analizi üretiliyor, lütfen bekleyin...\n\n")

        def worker():
            engine = self.selected_project.game_engine if self.selected_project else None
            genre = self.selected_project.genre if self.selected_project else None
            try:
                resp = self.plugin.query(prompt, mode=mode, engine=engine, genre=genre)
                self.root.after(0, lambda: self._on_rag_tab_complete(resp))
            except Exception as e:
                self.root.after(0, lambda err=str(e): self.rag_tab_output_text.insert(tk.END, f"\nHata: {err}"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_rag_tab_complete(self, response: Any) -> None:
        self.rag_tab_output_text.delete("1.0", tk.END)
        self.rag_tab_output_text.insert("1.0", response.text)

    # =========================================================================
    # SEKME 3: SENKRONİZASYON VE DURUM
    # =========================================================================

    def _build_sync_tab(self, parent: ttk.Frame) -> None:
        """İki yönlü senkronizasyon ve sistem durum sekmesini oluşturur."""
        sync_container = tk.Frame(parent, bg=DarkTheme.BG_DARK, padx=20, pady=20)
        sync_container.pack(fill=tk.BOTH, expand=True)

        card = tk.LabelFrame(
            sync_container,
            text=" 🔄 İki Yönlü Eşzamanlılık ve Depolama Entegrasyonu ",
            bg=DarkTheme.BG_CARD,
            fg=DarkTheme.ACCENT_CYAN,
            font=(DarkTheme.FONT_FAMILY, 11, "bold"),
            padx=20,
            pady=16,
            relief="groove",
        )
        card.pack(fill=tk.BOTH, expand=True)

        info_text = (
            "Jarvis Game Designer iki yönlü paylaşımlı mimari kullanır:\n"
            "• Bağımsız arayüzden veya Blender'dan kaydedilen tüm projeler anında diske (data/projects/) yazılır.\n"
            "• Jarvis asistanı aktif projeyi otomatik algılar ve oyun geliştirme sohbetlerinde projeyi temel alır.\n"
            "• Masaüstü kısayolu özel stüdyo ikonu ile pythonw.exe bağımsız GUI'yi başlatır."
        )
        tk.Label(
            card,
            text=info_text,
            bg=DarkTheme.BG_CARD,
            fg=DarkTheme.TEXT_MAIN,
            font=(DarkTheme.FONT_FAMILY, 10),
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 16))

        self.lbl_sync_active = tk.Label(card, text="• Aktif Proje: -", bg=DarkTheme.BG_CARD, fg=DarkTheme.SUCCESS, font=(DarkTheme.FONT_FAMILY, 10, "bold"))
        self.lbl_sync_active.pack(anchor=tk.W, pady=3)

        self.lbl_sync_p_count = tk.Label(card, text="• Toplam Proje Sayısı: -", bg=DarkTheme.BG_CARD, fg=DarkTheme.TEXT_MAIN, font=(DarkTheme.FONT_FAMILY, 10))
        self.lbl_sync_p_count.pack(anchor=tk.W, pady=3)

        self.lbl_sync_b_count = tk.Label(card, text="• Toplam Varlık/Blender Dosyası: -", bg=DarkTheme.BG_CARD, fg=DarkTheme.TEXT_MAIN, font=(DarkTheme.FONT_FAMILY, 10))
        self.lbl_sync_b_count.pack(anchor=tk.W, pady=3)

        self.lbl_sync_chroma = tk.Label(card, text="• Vektör Veritabanı Bilgi Parçaları: -", bg=DarkTheme.BG_CARD, fg=DarkTheme.TEXT_MAIN, font=(DarkTheme.FONT_FAMILY, 10))
        self.lbl_sync_chroma.pack(anchor=tk.W, pady=3)

        p_dir = str(self.settings.projects_dir.resolve())
        self.lbl_sync_path = tk.Label(card, text=f"• Projeler Depolama Dizini: {p_dir}", bg=DarkTheme.BG_CARD, fg=DarkTheme.TEXT_MUTED, font=(DarkTheme.FONT_FAMILY, 9))
        self.lbl_sync_path.pack(anchor=tk.W, pady=3)

        desktop_lnk = str((get_desktop_path() / "Jarvis Game Designer.lnk").resolve())
        self.lbl_sync_lnk = tk.Label(card, text=f"• Masaüstü Kısayolu: {desktop_lnk}", bg=DarkTheme.BG_CARD, fg=DarkTheme.TEXT_MUTED, font=(DarkTheme.FONT_FAMILY, 9))
        self.lbl_sync_lnk.pack(anchor=tk.W, pady=3)

        btn_frame = tk.Frame(card, bg=DarkTheme.BG_CARD)
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(
            btn_frame,
            text="📁 Projeler Klasörünü Aç",
            style="Primary.TButton",
            command=self._open_projects_folder,
        ).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(
            btn_frame,
            text="🖥️ Masaüstü Kısayolu Oluştur / Yenile",
            style="Secondary.TButton",
            command=self._create_or_refresh_shortcut,
        ).pack(side=tk.LEFT, padx=8)

        ttk.Button(
            btn_frame,
            text="🔄 Durumu Yeniden Eşitle",
            style="Success.TButton",
            command=self._refresh_all_data,
        ).pack(side=tk.LEFT, padx=8)

    # =========================================================================
    # VERİ GÜNCELLEME VE ETKİLEŞİM İŞLEMCİLERİ
    # =========================================================================

    def _refresh_all_data(self) -> None:
        """Tüm proje, blender/varlık ve durum verilerini yeniler."""
        projects = self.plugin.list_projects()
        active = self.plugin.get_active_project()

        if active:
            self.active_banner.config(text=f"🌟 Aktif Proje: {active.name} ({active.game_engine or 'Genel'})", fg=DarkTheme.SUCCESS)
        else:
            self.active_banner.config(text="⚠️ Aktif Proje Seçilmedi", fg=DarkTheme.WARNING)

        for item in self.projects_tree.get_children():
            self.projects_tree.delete(item)

        total_blends = 0
        for p in projects:
            status = "🌟 AKTİF" if p.is_active else ""
            b_count = len(p.blend_files)
            total_blends += b_count
            self.projects_tree.insert(
                "",
                tk.END,
                iid=p.id,
                values=(status, p.name, p.game_engine or "-", p.genre or "-", f"{b_count} dosya"),
            )

        if self.selected_project:
            matched = next((p for p in projects if p.id == self.selected_project.id), None)
            if matched:
                self.selected_project = matched
                self.projects_tree.selection_set(matched.id)
            elif projects:
                self.selected_project = projects[0]
                self.projects_tree.selection_set(projects[0].id)
        elif projects:
            self.selected_project = active or projects[0]
            self.projects_tree.selection_set(self.selected_project.id)

        self._update_selected_project_view()

        if hasattr(self, "lbl_sync_active"):
            self.lbl_sync_active.config(text=f"• Aktif Proje: {active.name if active else 'Yok'}")
            self.lbl_sync_p_count.config(text=f"• Toplam Proje Sayısı: {len(projects)}")
            self.lbl_sync_b_count.config(text=f"• Toplam Varlık/Blender Dosyası: {total_blends}")
            try:
                c_count = self.plugin.chroma_manager.count() if self.plugin.chroma_manager else 0
                self.lbl_sync_chroma.config(text=f"• Vektör Veritabanı Bilgi Parçaları: {c_count} chunk")
            except Exception:
                self.lbl_sync_chroma.config(text="• Vektör Veritabanı Bilgi Parçaları: Bağlantı kuruluyor...")

    def _on_project_selected(self, event: Any = None) -> None:
        """Tablodan proje seçildiğinde çalışır."""
        selected_ids = self.projects_tree.selection()
        if not selected_ids:
            return
        proj_id = selected_ids[0]
        proj = self.plugin.get_project(proj_id)
        if proj:
            self.selected_project = proj
            self._update_selected_project_view()

    def _update_selected_project_view(self) -> None:
        """Seçili projenin detay kartını ve varlık tablosunu günceller."""
        if not self.selected_project:
            self.lbl_proj_title.config(text="Henüz bir proje seçilmedi")
            self.lbl_proj_meta.config(text="Motor: - | Tür: - | Aşama: -")
            self.lbl_proj_desc.config(text="")
            self._refresh_blend_table()
            return

        p = self.selected_project
        status_txt = " [🌟 AKTİF]" if p.is_active else ""
        self.lbl_proj_title.config(text=f"{p.name}{status_txt}")
        self.lbl_proj_meta.config(
            text=f"Motor: {p.game_engine or 'Belirtilmedi'} | Tür: {p.genre or 'Belirtilmedi'} | Aşama: {p.development_phase or 'concept'}"
        )
        desc_parts = []
        if p.description:
            desc_parts.append(p.description)
        if p.key_features:
            desc_parts.append(f"Özellikler: {', '.join(p.key_features)}")
        if p.notes:
            desc_parts.append(f"Notlar: {p.notes}")
        self.lbl_proj_desc.config(text="\n".join(desc_parts) if desc_parts else "Açıklama girilmedi.")

        self._refresh_blend_table()

    def _refresh_blend_table(self) -> None:
        """Seçili projenin 3D varlık tablosunu günceller."""
        for item in self.blend_tree.get_children():
            self.blend_tree.delete(item)

        if not self.selected_project:
            return

        cat_filter = getattr(self, "blend_cat_filter_var", None)
        active_cat = cat_filter.get().strip() if cat_filter else "Tümü"

        first_blend = None
        for blend in self.selected_project.blend_files:
            if active_cat and active_cat != "Tümü" and blend.category.strip().lower() != active_cat.lower():
                continue
            blend.refresh_stats()
            status_txt = "✅ Diskte Var" if blend.exists() else "❌ Kayıp"
            mod_txt = blend.last_modified.strftime("%Y-%m-%d %H:%M") if blend.last_modified else "-"
            self.blend_tree.insert(
                "",
                tk.END,
                iid=blend.id,
                values=(
                    blend.name,
                    blend.category,
                    blend.file_size_formatted,
                    mod_txt,
                    status_txt,
                    blend.file_path,
                ),
            )
            if first_blend is None:
                first_blend = blend

        # Eğer seçili varlık yoksa ilk varlığı otomatik seç ve viewport'a ver
        if first_blend and not self.selected_blend_ref:
            self.blend_tree.selection_set(first_blend.id)
            self._on_blend_selected()

    def _on_blend_selected(self, event: Any = None) -> None:
        """Tablodan bir varlık seçildiğinde Viewport ve Inspector'ı günceller."""
        selected_items = self.blend_tree.selection()
        if not selected_items or not self.selected_project:
            return

        blend_id = selected_items[0]
        blend = self.selected_project.get_blend_file(blend_id)
        if not blend:
            return

        self.selected_blend_ref = blend
        # 1. 3D Viewport'a varlığı ve kategoriyi yükle
        if hasattr(self, "viewport_3d"):
            self.viewport_3d.set_asset(blend.file_path, category=blend.category)

        # 2. Inspector kartını güncelle
        ext = blend.file_format.upper()
        inspector_text = (
            f"Ad: {blend.name}\n"
            f"Format: {ext}\n"
            f"Kategori: {blend.category}\n"
            f"Boyut: {blend.file_size_formatted}\n"
            f"Konum: {Path(blend.file_path).parent.name} / {Path(blend.file_path).name}"
        )
        if hasattr(self, "lbl_asset_inspector"):
            self.lbl_asset_inspector.config(text=inspector_text)

    # --- HIZLI VE SÜRÜKLE-BIRAK VARLIK EKLEME ---

    def _batch_add_assets(self, file_paths: list[str]) -> None:
        """Birden çok 3D/animasyon dosyasını tek seferde otomatik sınıflandırıp ekler."""
        if not file_paths:
            return

        target_proj = self.selected_project or self.plugin.get_active_project()
        if not target_proj:
            projects = self.plugin.list_projects()
            if projects:
                target_proj = projects[0]
            else:
                target_proj = self.plugin.create_project(
                    name="Genel Oyun Projesi",
                    game_engine="Unreal Engine 5",
                    genre="Action",
                    activate=True,
                )
            self.selected_project = target_proj

        first_ref = None
        for fp in file_paths:
            path = Path(fp)
            if not path.is_file():
                continue
            auto_category = detect_asset_category(str(path))
            try:
                ref = self.plugin.add_blend_file(
                    project_name_or_id=target_proj.id,
                    file_path=str(path),
                    category=auto_category,
                    notes=f"Otomatik eklendi: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
                )
                if first_ref is None:
                    first_ref = ref
                logger.info(f"Varlık anında eklendi: '{ref.name}' -> [{auto_category}]")
            except Exception as e:
                logger.error(f"Varlık ekleme hatası ({path.name}): {e}")

        # Yeni eklenen varlıkların filtrelere takılmadan tabloda görünmesi için filtreyi 'Tümü' yap
        if hasattr(self, "blend_cat_filter_var"):
            self.blend_cat_filter_var.set("Tümü")

        self.selected_project = self.plugin.get_project(target_proj.id)
        self._refresh_all_data()

        if first_ref and first_ref.id in self.blend_tree.get_children():
            self.blend_tree.selection_set(first_ref.id)
            self._on_blend_selected()

    def _handle_instant_asset_add(self, file_path_str: str) -> None:
        """Dosyayı doğrudan otomatik sınıflandırıp aktif/seçili projeye ekler."""
        self._batch_add_assets([file_path_str])

    def _quick_add_asset_dialog(self) -> None:
        """Kullanıcının bilgisayarından tek tıkla dosya seçip anında eklemesini sağlar."""
        if not self.selected_project:
            self._open_new_project_modal()
            if not self.selected_project:
                return

        file_paths = filedialog.askopenfilenames(
            title="Oyun Varlığı Seçin (3D, 2D Görsel, Sprite, Aseprite)",
            filetypes=[
                ("Tüm Desteklenen Varlıklar", "*.blend;*.fbx;*.gltf;*.glb;*.obj;*.dae;*.bvh;*.png;*.jpg;*.jpeg;*.gif;*.webp;*.bmp;*.tga;*.aseprite;*.ase"),
                ("2D Görseller & Sprite (*.png;*.jpg;*.gif;*.webp;*.bmp;*.tga)", "*.png;*.jpg;*.jpeg;*.gif;*.webp;*.bmp;*.tga"),
                ("Aseprite Dosyası (*.aseprite;*.ase)", "*.aseprite;*.ase"),
                ("Blender Projesi (*.blend)", "*.blend"),
                ("FBX / Animasyon (*.fbx;*.bvh)", "*.fbx;*.bvh"),
                ("3D Mesh (*.obj;*.gltf;*.glb;*.dae)", "*.obj;*.gltf;*.glb;*.dae"),
                ("Tüm Dosyalar", "*.*"),
            ],
        )
        if not file_paths:
            return

        self._batch_add_assets(list(file_paths))

    def _add_blend_file_dialog(self) -> None:
        """Geriye dönük uyumluluk: _quick_add_asset_dialog çağrısı."""
        self._quick_add_asset_dialog()

    def _open_selected_blend(self) -> None:
        """Seçilen 3D dosyasını sistemin varsayılan programıyla (Blender) açar."""
        selected_items = self.blend_tree.selection()
        if not selected_items:
            messagebox.showwarning("Uyarı", "Lütfen açmak için bir 3D / Blender dosyası seçin.")
            return

        blend_id = selected_items[0]
        try:
            self.plugin.open_blend_file(file_path_or_id=blend_id, project_name_or_id=self.selected_project.id if self.selected_project else None)
        except Exception as e:
            messagebox.showerror("Açma Hatası", f"Dosya açılamadı:\n{e}\n\nBlender veya uygun bir 3D görüntüleyici kurulu olduğundan emin olun.")

    def _open_selected_aseprite(self) -> None:
        """Seçilen Aseprite / görsel dosyasını Aseprite ile açar."""
        selected_items = self.blend_tree.selection()
        if not selected_items:
            messagebox.showwarning("Uyarı", "Lütfen açmak için bir dosya seçin.")
            return

        blend_id = selected_items[0]
        try:
            self.plugin.open_aseprite_file(
                file_path_or_id=blend_id,
                project_name_or_id=self.selected_project.id if self.selected_project else None,
            )
        except Exception as e:
            messagebox.showerror(
                "Aseprite Açma Hatası",
                f"Dosya Aseprite ile açılamadı:\n{e}\n\nAseprite'ın bilgisayarınızda (Steam, Program Files veya AppData) kurulu olduğundan emin olun.",
            )

    def _toggle_viewport_scaling(self) -> None:
        """Viewport piksel / yumuşak ölçekleme filtresini değiştirir."""
        if hasattr(self, "viewport_3d"):
            self.viewport_3d.toggle_scaling_filter()

    def _next_viewport_frame(self) -> None:
        """Viewport animasyonunda sonraki kareye adım atar."""
        if hasattr(self, "viewport_3d"):
            self.viewport_3d.next_frame()

    def _prev_viewport_frame(self) -> None:
        """Viewport animasyonunda önceki kareye adım atar."""
        if hasattr(self, "viewport_3d"):
            self.viewport_3d.prev_frame()

    def _remove_selected_blend(self) -> None:
        """Seçili varlık referansını projeden kaldırır."""
        selected_items = self.blend_tree.selection()
        if not selected_items or not self.selected_project:
            messagebox.showwarning("Uyarı", "Lütfen kaldırılacak dosyayı seçin.")
            return

        blend_id = selected_items[0]
        confirmed = messagebox.askyesno("Kaldır", "Bu dosya referansını projeden kaldırmak istediğinize emin misiniz?\n(Asıl dosya diskten silinmez)")
        if not confirmed:
            return

        try:
            self.plugin.remove_blend_file(self.selected_project.id, blend_id)
            self.selected_project = self.plugin.get_project(self.selected_project.id)
            self._refresh_all_data()
        except Exception as e:
            messagebox.showerror("Hata", f"Dosya kaldırılamadı: {e}")

    # --- PROJE MODAL VE İŞLEMLERİ ---

    def _open_new_project_modal(self) -> None:
        """Yeni proje ekleme penceresi açar."""
        self._project_dialog(title="Yeni Oyun Projesi Ekle", is_edit=False)

    def _open_edit_project_modal(self) -> None:
        """Mevcut projeyi düzenleme penceresi açar."""
        if not self.selected_project:
            messagebox.showwarning("Uyarı", "Lütfen önce düzenlenecek projeyi seçin.")
            return
        self._project_dialog(title=f"Projeyi Düzenle: {self.selected_project.name}", is_edit=True, project=self.selected_project)

    def _project_dialog(self, title: str, is_edit: bool, project: GameProject | None = None) -> None:
        """Proje ekleme veya düzenleme için form penceresi."""
        dlg = tk.Toplevel(self.root)
        dlg.title(title)
        dlg.geometry("540x540")
        dlg.minsize(500, 480)
        dlg.configure(bg=DarkTheme.BG_CARD)
        dlg.transient(self.root)
        dlg.grab_set()

        pad = 8
        form_frame = tk.Frame(dlg, bg=DarkTheme.BG_CARD, padx=16, pady=16)
        form_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(form_frame, text="Proje Adı (*):", bg=DarkTheme.BG_CARD, fg=DarkTheme.TEXT_MAIN, font=(DarkTheme.FONT_FAMILY, 9, "bold")).pack(anchor=tk.W)
        name_entry = tk.Entry(form_frame, bg=DarkTheme.BG_INPUT, fg=DarkTheme.TEXT_MAIN, insertbackground=DarkTheme.TEXT_MAIN)
        name_entry.pack(fill=tk.X, pady=(2, pad))
        if project:
            name_entry.insert(0, project.name)

        grid_f = tk.Frame(form_frame, bg=DarkTheme.BG_CARD)
        grid_f.pack(fill=tk.X, pady=(0, pad))

        tk.Label(grid_f, text="Oyun Motoru:", bg=DarkTheme.BG_CARD, fg=DarkTheme.TEXT_MAIN).grid(row=0, column=0, sticky=tk.W)
        engine_entry = ttk.Combobox(grid_f, values=["Unreal Engine 5", "Unity", "Godot", "GameMaker", "Custom C++", "Diğer"])
        engine_entry.grid(row=1, column=0, sticky=tk.EW, padx=(0, 8))
        if project and project.game_engine:
            engine_entry.set(project.game_engine)

        tk.Label(grid_f, text="Oyun Türü:", bg=DarkTheme.BG_CARD, fg=DarkTheme.TEXT_MAIN).grid(row=0, column=1, sticky=tk.W)
        genre_entry = ttk.Combobox(grid_f, values=["Action RPG", "Platformer", "Roguelike", "FPS / Shooter", "Survival Horror", "Puzzle", "Strateji", "Diğer"])
        genre_entry.grid(row=1, column=1, sticky=tk.EW)
        if project and project.genre:
            genre_entry.set(project.genre)

        grid_f.columnconfigure(0, weight=1)
        grid_f.columnconfigure(1, weight=1)

        tk.Label(form_frame, text="Geliştirme Aşaması:", bg=DarkTheme.BG_CARD, fg=DarkTheme.TEXT_MAIN).pack(anchor=tk.W)
        phase_combo = ttk.Combobox(form_frame, values=["concept", "prototype", "production", "polish", "released"])
        phase_combo.pack(fill=tk.X, pady=(2, pad))
        phase_combo.set(project.development_phase if project and project.development_phase else "concept")

        tk.Label(form_frame, text="Açıklama / Proje Özeti:", bg=DarkTheme.BG_CARD, fg=DarkTheme.TEXT_MAIN).pack(anchor=tk.W)
        desc_text = tk.Text(form_frame, bg=DarkTheme.BG_INPUT, fg=DarkTheme.TEXT_MAIN, height=2, relief="flat")
        desc_text.pack(fill=tk.X, pady=(2, pad))
        if project and project.description:
            desc_text.insert("1.0", project.description)

        tk.Label(form_frame, text="Notlar (Tasarım kararları, GDD notları vb.):", bg=DarkTheme.BG_CARD, fg=DarkTheme.TEXT_MAIN).pack(anchor=tk.W)
        notes_text = tk.Text(form_frame, bg=DarkTheme.BG_INPUT, fg=DarkTheme.TEXT_MAIN, height=2, relief="flat")
        notes_text.pack(fill=tk.X, pady=(2, pad))
        if project and project.notes:
            notes_text.insert("1.0", project.notes)

        tk.Label(form_frame, text="Ana Mekanikler / Özellikler (Virgülle ayırın):", bg=DarkTheme.BG_CARD, fg=DarkTheme.TEXT_MAIN).pack(anchor=tk.W)
        feat_entry = tk.Entry(form_frame, bg=DarkTheme.BG_INPUT, fg=DarkTheme.TEXT_MAIN)
        feat_entry.pack(fill=tk.X, pady=(2, pad))
        if project and project.key_features:
            feat_entry.insert(0, ", ".join(project.key_features))

        btn_bar = tk.Frame(form_frame, bg=DarkTheme.BG_CARD)
        btn_bar.pack(fill=tk.X, pady=(12, 0))

        def save_action():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Hata", "Proje adı zorunludur.", parent=dlg)
                return
            engine = engine_entry.get().strip() or None
            genre = genre_entry.get().strip() or None
            phase = phase_combo.get().strip() or "concept"
            desc = desc_text.get("1.0", tk.END).strip()
            notes = notes_text.get("1.0", tk.END).strip()
            feat_raw = feat_entry.get().strip()
            features = [f.strip() for f in feat_raw.split(",") if f.strip()]

            try:
                if is_edit and project:
                    updated = self.plugin.update_project(
                        project.id,
                        name=name,
                        game_engine=engine,
                        genre=genre,
                        development_phase=phase,
                        description=desc,
                        notes=notes,
                        key_features=features,
                    )
                    self.selected_project = updated
                else:
                    new_proj = self.plugin.create_project(
                        name=name,
                        game_engine=engine,
                        genre=genre,
                        development_phase=phase,
                        description=desc,
                        notes=notes,
                        key_features=features,
                        activate=True,
                    )
                    self.selected_project = new_proj

                self._refresh_all_data()
                dlg.destroy()
            except Exception as ex:
                messagebox.showerror("Hata", f"Proje kaydedilemedi: {ex}", parent=dlg)

        ttk.Button(btn_bar, text="💾 Kaydet", style="Primary.TButton", command=save_action).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_bar, text="İptal", style="Secondary.TButton", command=dlg.destroy).pack(side=tk.RIGHT)

    def _set_selected_as_active(self) -> None:
        """Seçili projeyi aktif yapar."""
        if not self.selected_project:
            messagebox.showwarning("Uyarı", "Lütfen aktif yapmak istediğiniz projeyi seçin.")
            return

        try:
            self.plugin.set_active_project(self.selected_project.id)
            self._refresh_all_data()
            messagebox.showinfo("Başarılı", f"'{self.selected_project.name}' aktif proje olarak belirlendi ve Jarvis ile eşitlendi.")
        except Exception as e:
            messagebox.showerror("Hata", f"Aktif proje belirlenemedi: {e}")

    def _delete_selected_project(self) -> None:
        """Seçili projeyi onay alarak siler."""
        if not self.selected_project:
            messagebox.showwarning("Uyarı", "Lütfen silinecek projeyi seçin.")
            return

        confirmed = messagebox.askyesno(
            "Silme Onayı",
            f"'{self.selected_project.name}' projesini silmek istediğinize emin misiniz?\n(Disk üzerindeki asıl 3D dosyaları silinmez, yalnızca proje kaydı kaldırılır)",
        )
        if not confirmed:
            return

        try:
            self.plugin.delete_project(self.selected_project.id)
            self.selected_project = None
            self._refresh_all_data()
        except Exception as e:
            messagebox.showerror("Hata", f"Proje silinemedi: {e}")

    # =========================================================================
    # YÜKSEK HIZLI & STREAMING RAG AI SORGULAMA İŞLEMİ
    # =========================================================================

    def _execute_rag_query(self) -> None:
        """RAG AI danışman sorgusunu gerçek zamanlı akış (streaming) ile çalıştırır."""
        query_text = self.rag_input_text.get("1.0", tk.END).strip()
        if not query_text:
            messagebox.showwarning("Uyarı", "Lütfen bir soru veya analiz konusu girin.")
            return

        selected_mode_raw = self.mode_var.get()
        mode = selected_mode_raw.split()[0]

        self._current_query_id = getattr(self, "_current_query_id", 0) + 1
        query_id = self._current_query_id

        self.btn_ask.config(state=tk.DISABLED)
        self.lbl_rag_status.config(text="⚡ Yüksek Hızlı AI Danışmanı yanıt üretiyor...")
        self.rag_output_text.delete("1.0", tk.END)
        self.sources_listbox.delete(0, tk.END)

        def worker():
            start_time = time.perf_counter()
            try:
                engine = self.selected_project.game_engine if self.selected_project else None
                genre = self.selected_project.genre if self.selected_project else None

                # Doğrudan yanıtı al (rag_engine bellek içi LRU cache kullanır)
                final_response = self.plugin.query(query_text, mode=mode, engine=engine, genre=genre)
                elapsed = time.perf_counter() - start_time

                if query_id != self._current_query_id:
                    return

                # Önbellek vuruşu (cache hit) veya hızlı sentez durumunda anında ekrana bas
                if elapsed < 0.05:
                    self.root.after(0, lambda r=final_response, e=elapsed: self._render_full_response(r, e))
                    return

                # Akışlı aktarım
                import re
                tokens = [t for t in re.split(r"(\s+)", final_response.text) if t]
                for idx, token in enumerate(tokens):
                    if query_id != self._current_query_id:
                        return
                    self.root.after(0, lambda t=token: self._append_stream_token(t))
                    if idx % 4 == 0:
                        time.sleep(0.001)

                self.root.after(0, lambda r=final_response, e=elapsed: self._on_rag_streaming_complete(r, e))

            except Exception as e:
                if query_id == self._current_query_id:
                    self.root.after(0, lambda err=str(e): self._on_rag_error(err))

        threading.Thread(target=worker, daemon=True).start()

    def _render_full_response(self, response: Any, elapsed: float) -> None:
        """Önbellekten dönen yanıtı anında arayüze aktarır."""
        self.rag_output_text.delete("1.0", tk.END)
        self.rag_output_text.insert("1.0", response.text)
        self._on_rag_streaming_complete(response, elapsed)

    def _append_stream_token(self, token: str) -> None:
        """Akıştan gelen kelime/token'ı arayüze ekler."""
        self.rag_output_text.insert(tk.END, token)
        self.rag_output_text.see(tk.END)

    def _on_rag_streaming_complete(self, response: Any, elapsed: float) -> None:
        """Akış tamamlandığında güven rozetini ve kaynakları eşitler."""
        self.btn_ask.config(state=tk.NORMAL)
        self.lbl_rag_status.config(text=f"Tamamlandı ({elapsed:.2f}s | Mod: {response.mode})")

        badge_text = response.confidence.tier_badge
        score_val = response.confidence.overall_score
        self.lbl_confidence.config(text=f"{badge_text} - %{score_val:.0f}")

        # Kaynaklar
        self.sources_listbox.delete(0, tk.END)
        if response.sources:
            for s in response.sources:
                cat_val = s.category.value if hasattr(s.category, "value") else s.category
                self.sources_listbox.insert(tk.END, f"[{cat_val}] {s.title} (%{s.similarity_score * 100:.0f})")
        else:
            self.sources_listbox.insert(tk.END, "Kaynak alıntısı yok (Doğrudan sentez)")

    def _on_rag_success(self, response: Any) -> None:
        """Test uyumluluğu ve doğrudan yanıt yazımı."""
        self.btn_ask.config(state=tk.NORMAL)
        self.lbl_rag_status.config(text=f"Tamamlandı (Mod: {response.mode})")

        badge_text = response.confidence.tier_badge
        score_val = response.confidence.overall_score
        self.lbl_confidence.config(text=f"{badge_text} - %{score_val:.0f}")

        self.rag_output_text.delete("1.0", tk.END)
        self.rag_output_text.insert("1.0", response.text)

        self.sources_listbox.delete(0, tk.END)
        if response.sources:
            for s in response.sources:
                cat_val = s.category.value if hasattr(s.category, "value") else s.category
                self.sources_listbox.insert(tk.END, f"[{cat_val}] {s.title} (%{s.similarity_score * 100:.0f})")
        else:
            self.sources_listbox.insert(tk.END, "Kaynak alıntısı yok (Doğrudan sentez)")

    def _on_rag_error(self, err_msg: str) -> None:
        """RAG sorgusu hata verdiğinde."""
        self.btn_ask.config(state=tk.NORMAL)
        self.lbl_rag_status.config(text="Hata oluştu.")
        self.rag_output_text.delete("1.0", tk.END)
        self.rag_output_text.insert("1.0", f"Hata: {err_msg}")

    # --- SİSTEM & KISAYOL İŞLEMLERİ ---

    def _open_projects_folder(self) -> None:
        """Depolama klasörünü Windows Gezgini'nde açar."""
        p_dir = str(self.settings.projects_dir.resolve())
        try:
            if sys.platform == "win32":
                os.startfile(p_dir)
            else:
                import subprocess
                subprocess.Popen(["xdg-open", p_dir])
        except Exception as e:
            messagebox.showerror("Hata", f"Klasör açılamadı: {e}")

    def _create_or_refresh_shortcut(self) -> None:
        """Masaüstü kısayolunu özel stüdyo ikonu ile oluşturur veya günceller."""
        try:
            lnk = create_desktop_shortcut()
            messagebox.showinfo("Başarılı", f"Masaüstü kısayolu başarıyla oluşturuldu / güncellendi:\n{lnk}")
            self._refresh_all_data()
        except Exception as e:
            messagebox.showerror("Hata", f"Kısayol oluşturulurken hata: {e}")


def main() -> None:
    """Uygulama ana giriş kapısı."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                import ctypes
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Jarvis.GameDesigner.Studio.1.0")
        except Exception:
            pass

    root = tk.Tk()
    app = GameDesignerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
