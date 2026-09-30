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

        # Modern Tek Ekranlı Çekmece Durumları
        self._left_drawer_visible: bool = True
        self._right_drawer_visible: bool = False
        self._active_left_view: str = "assets"
        self._chip_buttons: dict[str, tk.Button] = {}
        self._act_buttons: dict[str, tk.Button] = {}

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
        """Modern, tek ekranlı (Blender / VS Code / Figma tarzı) stüdyo arayüzünü inşa eder."""
        # 1. Üst İnce Stüdyo Çubuğu (Header Bar)
        header = tk.Frame(self.root, bg="#090d16", padx=14, pady=6, bd=1, relief="ridge")
        header.pack(fill=tk.X, padx=0, pady=0)

        title_box = tk.Frame(header, bg="#090d16")
        title_box.pack(side=tk.LEFT, fill=tk.Y)

        title_row = tk.Frame(title_box, bg="#090d16")
        title_row.pack(anchor=tk.W)

        tk.Label(
            title_row,
            text="🎮 JARVIS GAME DESIGNER",
            bg="#090d16",
            fg=DarkTheme.ACCENT_CYAN,
            font=(DarkTheme.FONT_FAMILY, 12, "bold"),
        ).pack(side=tk.LEFT)

        tk.Label(
            title_row,
            text=" STUDIO",
            bg="#090d16",
            fg=DarkTheme.ACCENT_PURPLE,
            font=(DarkTheme.FONT_FAMILY, 12, "bold"),
        ).pack(side=tk.LEFT)

        # Sağ üst: Aktif proje rozeti ve hızlı klasör açıcı
        right_hdr = tk.Frame(header, bg="#090d16")
        right_hdr.pack(side=tk.RIGHT)

        self.active_banner = tk.Label(
            right_hdr,
            text="Aktif Proje: Yükleniyor...",
            bg=DarkTheme.BG_INPUT,
            fg=DarkTheme.SUCCESS,
            font=(DarkTheme.FONT_FAMILY, 9, "bold"),
            padx=10,
            pady=4,
            relief="flat",
        )
        self.active_banner.pack(side=tk.RIGHT, padx=4)

        btn_open_folder = tk.Button(
            right_hdr,
            text="📁 Projeler Dizini",
            bg=DarkTheme.BG_INPUT,
            fg=DarkTheme.TEXT_MUTED,
            activebackground=DarkTheme.ACCENT_CYAN,
            activeforeground="#021526",
            font=(DarkTheme.FONT_FAMILY, 8),
            relief="flat",
            padx=8,
            pady=4,
            cursor="hand2",
            command=self._open_projects_folder,
        )
        btn_open_folder.pack(side=tk.RIGHT, padx=4)

        # Testler ve geriye dönük uyumluluk için Notebook referansı
        self.notebook = ttk.Notebook(self.root, style="TNotebook")
        self.tab_projects = ttk.Frame(self.notebook, style="Dark.TFrame")
        self.tab_rag = ttk.Frame(self.notebook, style="Dark.TFrame")
        self.tab_sync = ttk.Frame(self.notebook, style="Dark.TFrame")
        self.notebook.add(self.tab_projects, text=" 🎮 Stüdyo & 3D Varlıklar ")
        self.notebook.add(self.tab_rag, text=" 🤖 Tasarım Danışmanı (RAG AI) ")
        self.notebook.add(self.tab_sync, text=" 🔄 Senkronizasyon & Durum ")

        # 2. Ana Çalışma Alanı (Single-Screen Workspace)
        self.workspace_frame = tk.Frame(self.root, bg=DarkTheme.BG_DARK)
        self.workspace_frame.pack(fill=tk.BOTH, expand=True)

        # A. Sol Dikey Aktivite Çubuğu (~50px genişlik)
        self._build_activity_bar(self.workspace_frame)

        # B. Açılır/Kapanır Sol Çekmece (Varlıklar, Projeler, Senkronizasyon)
        self._build_left_drawer(self.workspace_frame)

        # C. Açılır/Kapanır Sağ Çekmece (AI Danışmanı)
        self._build_right_drawer(self.workspace_frame)

        # D. Merkezi Viewport & Tuval Alanı (Kalan tüm genişliği doldurur)
        self._build_central_canvas(self.workspace_frame)

        # İlk çekmece görünümünü ayarla
        self._show_left_drawer_view("assets")
        self._update_activity_bar_buttons()

    def _build_activity_bar(self, parent: tk.Widget) -> None:
        """Sol aktivite çubuğunu (~56px) oluşturur (VS Code / Blender Studio stili)."""
        self.activity_bar = tk.Frame(parent, bg="#070b14", width=56, bd=1, relief="ridge")
        self.activity_bar.pack(side=tk.LEFT, fill=tk.Y)
        self.activity_bar.pack_propagate(False)

        tk.Label(self.activity_bar, text="⚡", bg="#070b14", fg=DarkTheme.ACCENT_CYAN, font=(DarkTheme.FONT_FAMILY, 14, "bold"), pady=8).pack(fill=tk.X)

        self._act_buttons = {}

        def make_act_btn(key: str, icon: str, short_lbl: str, cmd):
            btn = tk.Button(
                self.activity_bar,
                text=f"{icon}\n{short_lbl}",
                bg="#070b14",
                fg=DarkTheme.TEXT_MUTED,
                activebackground=DarkTheme.BG_INPUT,
                activeforeground=DarkTheme.ACCENT_CYAN,
                font=(DarkTheme.FONT_FAMILY, 7, "bold"),
                relief="flat",
                bd=0,
                pady=6,
                cursor="hand2",
                command=cmd,
            )
            btn.pack(fill=tk.X, pady=2)
            self._act_buttons[key] = btn
            return btn

        make_act_btn("projects", "📁", "Projeler", lambda: self._toggle_left_drawer("projects"))
        make_act_btn("assets", "🎨", "Varlıklar", lambda: self._toggle_left_drawer("assets"))
        make_act_btn("ai", "🤖", "AI Danışman", self._toggle_right_drawer)
        make_act_btn("sync", "🔄", "Ayarlar", lambda: self._toggle_left_drawer("sync"))

    def _build_left_drawer(self, parent: tk.Widget) -> None:
        """Açılır/kapanır sol çekmeceyi inşa eder."""
        self.left_drawer = tk.Frame(parent, bg=DarkTheme.BG_CARD, width=390, bd=1, relief="ridge")
        self.left_drawer.pack(side=tk.LEFT, fill=tk.Y)
        self.left_drawer.pack_propagate(False)

        # Çekmece Üst Başlık Çubuğu & Kapat Butonu
        d_hdr = tk.Frame(self.left_drawer, bg=DarkTheme.BG_CARD, padx=10, pady=8)
        d_hdr.pack(fill=tk.X)

        self.lbl_drawer_title = tk.Label(
            d_hdr,
            text="🎨 Varlık Rafı",
            bg=DarkTheme.BG_CARD,
            fg=DarkTheme.ACCENT_CYAN,
            font=(DarkTheme.FONT_FAMILY, 11, "bold"),
        )
        self.lbl_drawer_title.pack(side=tk.LEFT)

        btn_close_left = tk.Button(
            d_hdr,
            text="✕",
            bg=DarkTheme.BG_CARD,
            fg=DarkTheme.TEXT_MUTED,
            activebackground=DarkTheme.BG_INPUT,
            activeforeground="#ef4444",
            font=(DarkTheme.FONT_FAMILY, 10, "bold"),
            relief="flat",
            bd=0,
            padx=6,
            cursor="hand2",
            command=self._close_left_drawer,
        )
        btn_close_left.pack(side=tk.RIGHT)

        # 3 Farklı Çekmece Görünümü
        self.drawer_assets_view = tk.Frame(self.left_drawer, bg=DarkTheme.BG_CARD, padx=8, pady=4)
        self.drawer_projects_view = tk.Frame(self.left_drawer, bg=DarkTheme.BG_CARD, padx=8, pady=4)
        self.drawer_sync_view = tk.Frame(self.left_drawer, bg=DarkTheme.BG_CARD, padx=10, pady=8)

        self._setup_assets_drawer_view(self.drawer_assets_view)
        self._setup_projects_drawer_view(self.drawer_projects_view)
        self._setup_sync_drawer_view(self.drawer_sync_view)

    def _setup_assets_drawer_view(self, parent: tk.Frame) -> None:
        """Varlık çekmecesi: Sürükle-bırak dropzone, kategori çipleri, tablo ve açma butonları."""
        drop_card = tk.Frame(parent, bg=DarkTheme.BG_INPUT, padx=8, pady=8, bd=1, relief="ridge")
        drop_card.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            drop_card,
            text="📥 Sürükle & Bırak veya Dosya Ekle\n(3D Mesh, 2D Görsel, Sprite, Aseprite)",
            bg=DarkTheme.BG_INPUT,
            fg=DarkTheme.ACCENT_CYAN,
            font=(DarkTheme.FONT_FAMILY, 8, "bold"),
            justify=tk.LEFT,
        ).pack(side=tk.LEFT)

        ttk.Button(
            drop_card,
            text="📁 Dosya Ekle",
            style="Primary.TButton",
            command=self._quick_add_asset_dialog,
        ).pack(side=tk.RIGHT, padx=2)

        # Kategori Filtre Çipleri
        chips_frame = tk.Frame(parent, bg=DarkTheme.BG_CARD)
        chips_frame.pack(fill=tk.X, pady=(0, 6))

        chip_names = ["Tümü", "2D Sprite", "Animasyon", "Karakter", "Çevre", "Prop", "Araç"]
        self._chip_buttons = {}
        for cat in chip_names:
            btn = tk.Button(
                chips_frame,
                text=cat,
                bg="#0891b2" if cat == "Tümü" else DarkTheme.BG_INPUT,
                fg="#ffffff" if cat == "Tümü" else DarkTheme.TEXT_MUTED,
                activebackground="#0891b2",
                activeforeground="#ffffff",
                font=(DarkTheme.FONT_FAMILY, 8, "bold" if cat == "Tümü" else "normal"),
                relief="flat",
                padx=5,
                pady=2,
                cursor="hand2",
                command=lambda c=cat: self._on_category_chip_clicked(c),
            )
            btn.pack(side=tk.LEFT, padx=1, pady=1)
            self._chip_buttons[cat] = btn

        # Geriye dönük uyumluluk için combobox ve StringVar
        self.blend_cat_filter_var = tk.StringVar(value="Tümü")
        self.blend_cat_combo = ttk.Combobox(
            parent,
            textvariable=self.blend_cat_filter_var,
            values=["Tümü", "2D Sprite / Piksel Sanatı", "Animasyon", "Karakter", "Çevre/Level", "Prop", "Araç", "VFX/Diğer", "Genel"],
            state="readonly",
            height=6,
        )

        # Tablo Çerçevesi
        b_table_frame = tk.Frame(parent, bg=DarkTheme.BG_CARD)
        b_table_frame.pack(fill=tk.BOTH, expand=True)

        b_cols = ("name", "category", "format", "size", "modified", "status", "path")
        self.blend_tree = ttk.Treeview(b_table_frame, columns=b_cols, show="headings", selectmode="browse")
        self.blend_tree.heading("name", text="Varlık")
        self.blend_tree.heading("category", text="Kategori")
        self.blend_tree.heading("format", text="Format")
        self.blend_tree.heading("size", text="Boyut")
        self.blend_tree.heading("modified", text="Değişiklik")
        self.blend_tree.heading("status", text="Durum")
        self.blend_tree.heading("path", text="Dosya Yolu")

        self.blend_tree.column("name", width=110)
        self.blend_tree.column("category", width=80)
        self.blend_tree.column("format", width=65, anchor=tk.CENTER)
        self.blend_tree.column("size", width=55, anchor=tk.E)
        self.blend_tree.column("modified", width=85)
        self.blend_tree.column("status", width=65, anchor=tk.CENTER)
        self.blend_tree.column("path", width=100)

        b_scroll = ttk.Scrollbar(b_table_frame, orient=tk.VERTICAL, command=self.blend_tree.yview)
        self.blend_tree.configure(yscrollcommand=b_scroll.set)
        self.blend_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        b_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.blend_tree.bind("<<TreeviewSelect>>", self._on_blend_selected)
        self.blend_tree.bind("<Double-1>", lambda e: self._open_selected_blend())

        # Sağ Tık Bağlam Menüsü
        self.blend_tree_menu = tk.Menu(self.root, tearoff=0, bg=DarkTheme.BG_CARD, fg=DarkTheme.TEXT_MAIN)
        self.blend_tree_menu.add_command(label="🧊 Blender ile Aç", command=self._open_selected_blend)
        self.blend_tree_menu.add_command(label="🎨 Aseprite ile Aç", command=self._open_selected_aseprite)
        self.blend_tree_menu.add_separator()
        self.blend_tree_menu.add_command(label="🗑️ Projeden Kaldır", command=self._remove_selected_blend)

        def _on_tree_right_click(event: tk.Event) -> None:
            row_id = self.blend_tree.identify_row(event.y)
            if row_id:
                self.blend_tree.selection_set(row_id)
                self._on_blend_selected()
                try:
                    self.blend_tree_menu.post(event.x_root, event.y_root)
                except Exception:
                    pass

        self.blend_tree.bind("<Button-3>", _on_tree_right_click)

        # Varlık Hızlı Butonları
        a_btns = tk.Frame(parent, bg=DarkTheme.BG_CARD)
        a_btns.pack(fill=tk.X, pady=(6, 2))

        ttk.Button(a_btns, text="🧊 Blender", style="Success.TButton", command=self._open_selected_blend).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(a_btns, text="🎨 Aseprite", style="Primary.TButton", command=self._open_selected_aseprite).pack(side=tk.LEFT, padx=2)
        ttk.Button(a_btns, text="🗑️ Kaldır", style="Secondary.TButton", command=self._remove_selected_blend).pack(side=tk.LEFT, padx=2)
        ttk.Button(a_btns, text="🔄 Yenile", style="Secondary.TButton", command=self._refresh_blend_table).pack(side=tk.RIGHT, padx=(2, 0))

    def _setup_projects_drawer_view(self, parent: tk.Frame) -> None:
        """Proje yönetimi görünümü."""
        p_btn_bar = tk.Frame(parent, bg=DarkTheme.BG_CARD)
        p_btn_bar.pack(fill=tk.X, pady=(0, 6))

        ttk.Button(p_btn_bar, text="➕ Yeni", style="Primary.TButton", command=self._open_new_project_modal).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(p_btn_bar, text="✏️ Düzenle", style="Secondary.TButton", command=self._open_edit_project_modal).pack(side=tk.LEFT, padx=2)
        ttk.Button(p_btn_bar, text="🌟 Aktif", style="Success.TButton", command=self._set_selected_as_active).pack(side=tk.LEFT, padx=2)
        ttk.Button(p_btn_bar, text="🗑️ Sil", style="Secondary.TButton", command=self._delete_selected_project).pack(side=tk.RIGHT)

        p_table_frame = tk.Frame(parent, bg=DarkTheme.BG_CARD)
        p_table_frame.pack(fill=tk.BOTH, expand=True)

        p_cols = ("status", "name", "engine", "genre", "blends")
        self.projects_tree = ttk.Treeview(p_table_frame, columns=p_cols, show="headings", selectmode="browse")
        self.projects_tree.heading("status", text="Durum")
        self.projects_tree.heading("name", text="Proje Adı")
        self.projects_tree.heading("engine", text="Motor")
        self.projects_tree.heading("genre", text="Tür")
        self.projects_tree.heading("blends", text="Varlık")

        self.projects_tree.column("status", width=55, anchor=tk.CENTER)
        self.projects_tree.column("name", width=125)
        self.projects_tree.column("engine", width=75)
        self.projects_tree.column("genre", width=75)
        self.projects_tree.column("blends", width=50, anchor=tk.CENTER)

        p_scroll = ttk.Scrollbar(p_table_frame, orient=tk.VERTICAL, command=self.projects_tree.yview)
        self.projects_tree.configure(yscrollcommand=p_scroll.set)
        self.projects_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        p_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.projects_tree.bind("<<TreeviewSelect>>", self._on_project_selected)
        self.projects_tree.bind("<Double-1>", lambda e: self._set_selected_as_active())

        # Proje Detay Kartı
        self.detail_card = tk.LabelFrame(
            parent,
            text=" 📌 Seçili Proje ",
            bg=DarkTheme.BG_CARD,
            fg=DarkTheme.ACCENT_CYAN,
            font=(DarkTheme.FONT_FAMILY, 9, "bold"),
            padx=8,
            pady=4,
            relief="groove",
        )
        self.detail_card.pack(fill=tk.X, pady=(6, 0))

        self.lbl_proj_title = tk.Label(
            self.detail_card,
            text="Henüz proje seçilmedi",
            bg=DarkTheme.BG_CARD,
            fg=DarkTheme.TEXT_MAIN,
            font=(DarkTheme.FONT_FAMILY, 9, "bold"),
            anchor=tk.W,
            wraplength=350,
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
        self.lbl_proj_meta.pack(fill=tk.X)

        self.lbl_proj_desc = tk.Label(
            self.detail_card,
            text="",
            bg=DarkTheme.BG_CARD,
            fg=DarkTheme.TEXT_MAIN,
            font=(DarkTheme.FONT_FAMILY, 8),
            anchor=tk.W,
            justify=tk.LEFT,
            wraplength=350,
        )
        self.lbl_proj_desc.pack(fill=tk.X)

        self.lbl_asset_inspector = tk.Label(
            self.detail_card,
            text="",
            bg=DarkTheme.BG_CARD,
            fg=DarkTheme.ACCENT_CYAN,
            font=(DarkTheme.FONT_FAMILY, 8),
            anchor=tk.W,
            justify=tk.LEFT,
            wraplength=350,
        )

    def _setup_sync_drawer_view(self, parent: tk.Frame) -> None:
        """Senkronizasyon ve sistem durumu görünümü."""
        tk.Label(
            parent,
            text="Jarvis İki Yönlü Eşzamanlılık",
            bg=DarkTheme.BG_CARD,
            fg=DarkTheme.ACCENT_CYAN,
            font=(DarkTheme.FONT_FAMILY, 10, "bold"),
        ).pack(anchor=tk.W, pady=(0, 8))

        self.lbl_sync_active = tk.Label(parent, text="• Aktif Proje: -", bg=DarkTheme.BG_CARD, fg=DarkTheme.SUCCESS, font=(DarkTheme.FONT_FAMILY, 9, "bold"), anchor=tk.W)
        self.lbl_sync_active.pack(fill=tk.X, pady=2)

        self.lbl_sync_p_count = tk.Label(parent, text="• Toplam Proje: -", bg=DarkTheme.BG_CARD, fg=DarkTheme.TEXT_MAIN, font=(DarkTheme.FONT_FAMILY, 9), anchor=tk.W)
        self.lbl_sync_p_count.pack(fill=tk.X, pady=2)

        self.lbl_sync_b_count = tk.Label(parent, text="• Toplam Varlık Dosyası: -", bg=DarkTheme.BG_CARD, fg=DarkTheme.TEXT_MAIN, font=(DarkTheme.FONT_FAMILY, 9), anchor=tk.W)
        self.lbl_sync_b_count.pack(fill=tk.X, pady=2)

        self.lbl_sync_chroma = tk.Label(parent, text="• Vektör Veritabanı: -", bg=DarkTheme.BG_CARD, fg=DarkTheme.TEXT_MAIN, font=(DarkTheme.FONT_FAMILY, 9), anchor=tk.W)
        self.lbl_sync_chroma.pack(fill=tk.X, pady=2)

        p_dir = str(self.settings.projects_dir.resolve())
        self.lbl_sync_path = tk.Label(parent, text=f"• Konum: {p_dir}", bg=DarkTheme.BG_CARD, fg=DarkTheme.TEXT_MUTED, font=(DarkTheme.FONT_FAMILY, 8), anchor=tk.W, wraplength=350, justify=tk.LEFT)
        self.lbl_sync_path.pack(fill=tk.X, pady=4)

        desktop_lnk = str((get_desktop_path() / "Jarvis Game Designer.lnk").resolve())
        self.lbl_sync_lnk = tk.Label(parent, text=f"• Kısayol: {desktop_lnk}", bg=DarkTheme.BG_CARD, fg=DarkTheme.TEXT_MUTED, font=(DarkTheme.FONT_FAMILY, 8), anchor=tk.W, wraplength=350, justify=tk.LEFT)
        self.lbl_sync_lnk.pack(fill=tk.X, pady=2)

        btn_box = tk.Frame(parent, bg=DarkTheme.BG_CARD)
        btn_box.pack(fill=tk.X, pady=(16, 0))

        ttk.Button(btn_box, text="📁 Projeler Klasörü", style="Primary.TButton", command=self._open_projects_folder).pack(fill=tk.X, pady=3)
        ttk.Button(btn_box, text="🖥️ Masaüstü Kısayolu", style="Secondary.TButton", command=self._create_or_refresh_shortcut).pack(fill=tk.X, pady=3)
        ttk.Button(btn_box, text="🔄 Durumu Yeniden Eşitle", style="Success.TButton", command=self._refresh_all_data).pack(fill=tk.X, pady=3)

    def _build_central_canvas(self, parent: tk.Widget) -> None:
        """Merkezi tam ekran tuval alanı ve yüzen HUD pill araç çubuğu."""
        self.center_area = tk.Frame(parent, bg=DarkTheme.BG_DARK)
        self.center_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 3D & 2D Etkileşimli Canvas
        self.viewport_3d = Viewport3DCanvas(self.center_area, bg=DarkTheme.BG_DARK)
        self.viewport_3d.pack(fill=tk.BOTH, expand=True)
        self.viewport_3d.on_anim_state_change = lambda is_anim: getattr(self, "btn_hud_play", None) and self.btn_hud_play.config(text="⏸" if is_anim else "▶")

        # Yüzen HUD Pill Araç Çubuğu (Floating HUD Pill Toolbar)
        self.hud_pill = tk.Frame(self.center_area, bg="#0d172c", bd=1, relief="ridge", padx=10, pady=5)
        self.hud_pill.place(relx=0.5, y=14, anchor="n")

        # 2D Kontrolleri
        self.hud_2d_frame = tk.Frame(self.hud_pill, bg="#0d172c")

        self.btn_hud_zoom = tk.Button(
            self.hud_2d_frame,
            text="🔍 1:1 / Sığdır",
            bg=DarkTheme.BG_INPUT,
            fg=DarkTheme.TEXT_MAIN,
            activebackground=DarkTheme.ACCENT_CYAN,
            font=(DarkTheme.FONT_FAMILY, 8),
            relief="flat",
            padx=6,
            pady=3,
            cursor="hand2",
            command=self._toggle_viewport_zoom,
        )
        self.btn_hud_zoom.pack(side=tk.LEFT, padx=2)

        self.btn_hud_scale = tk.Button(
            self.hud_2d_frame,
            text="👾 Piksel / Smooth",
            bg=DarkTheme.BG_INPUT,
            fg=DarkTheme.TEXT_MAIN,
            activebackground=DarkTheme.ACCENT_CYAN,
            font=(DarkTheme.FONT_FAMILY, 8),
            relief="flat",
            padx=6,
            pady=3,
            cursor="hand2",
            command=self._toggle_viewport_scaling,
        )
        self.btn_hud_scale.pack(side=tk.LEFT, padx=2)

        self.btn_hud_open_ase = tk.Button(
            self.hud_2d_frame,
            text="🎨 Aseprite ile Aç",
            bg="#0891b2",
            fg="#ffffff",
            activebackground="#0e7490",
            font=(DarkTheme.FONT_FAMILY, 8, "bold"),
            relief="flat",
            padx=6,
            pady=3,
            cursor="hand2",
            command=self._open_selected_aseprite,
        )
        self.btn_hud_open_ase.pack(side=tk.LEFT, padx=2)

        self.hud_anim_frame = tk.Frame(self.hud_2d_frame, bg="#0d172c")
        self.btn_hud_play = tk.Button(
            self.hud_anim_frame,
            text="▶/⏸",
            bg=DarkTheme.BG_INPUT,
            fg=DarkTheme.ACCENT_CYAN,
            font=(DarkTheme.FONT_FAMILY, 8, "bold"),
            relief="flat",
            padx=5,
            pady=3,
            cursor="hand2",
            command=self._toggle_viewport_animation,
        )
        self.btn_hud_play.pack(side=tk.LEFT, padx=1)

        tk.Button(
            self.hud_anim_frame,
            text="◀",
            bg=DarkTheme.BG_INPUT,
            fg=DarkTheme.TEXT_MAIN,
            font=(DarkTheme.FONT_FAMILY, 8),
            relief="flat",
            padx=4,
            pady=3,
            cursor="hand2",
            command=self._prev_viewport_frame,
        ).pack(side=tk.LEFT, padx=1)

        tk.Button(
            self.hud_anim_frame,
            text="▶",
            bg=DarkTheme.BG_INPUT,
            fg=DarkTheme.TEXT_MAIN,
            font=(DarkTheme.FONT_FAMILY, 8),
            relief="flat",
            padx=4,
            pady=3,
            cursor="hand2",
            command=self._next_viewport_frame,
        ).pack(side=tk.LEFT, padx=1)
        self.hud_anim_frame.pack(side=tk.LEFT, padx=4)

        # 3D Kontrolleri
        self.hud_3d_frame = tk.Frame(self.hud_pill, bg="#0d172c")

        self.btn_hud_render_style = tk.Button(
            self.hud_3d_frame,
            text="💡 Gölgeli / 📐 Tel Kafes",
            bg=DarkTheme.BG_INPUT,
            fg=DarkTheme.TEXT_MAIN,
            activebackground=DarkTheme.ACCENT_CYAN,
            font=(DarkTheme.FONT_FAMILY, 8),
            relief="flat",
            padx=6,
            pady=3,
            cursor="hand2",
            command=self._toggle_viewport_render_style,
        )
        self.btn_hud_render_style.pack(side=tk.LEFT, padx=2)

        self.btn_hud_spin = tk.Button(
            self.hud_3d_frame,
            text="🔄 Otomatik Döndür",
            bg=DarkTheme.BG_INPUT,
            fg=DarkTheme.TEXT_MAIN,
            activebackground=DarkTheme.ACCENT_CYAN,
            font=(DarkTheme.FONT_FAMILY, 8),
            relief="flat",
            padx=6,
            pady=3,
            cursor="hand2",
            command=self._toggle_viewport_spin,
        )
        self.btn_hud_spin.pack(side=tk.LEFT, padx=2)

        self.btn_hud_reset = tk.Button(
            self.hud_3d_frame,
            text="🎯 Sıfırla",
            bg=DarkTheme.BG_INPUT,
            fg=DarkTheme.TEXT_MAIN,
            activebackground=DarkTheme.BORDER,
            font=(DarkTheme.FONT_FAMILY, 8),
            relief="flat",
            padx=6,
            pady=3,
            cursor="hand2",
            command=self._reset_viewport_camera,
        )
        self.btn_hud_reset.pack(side=tk.LEFT, padx=2)

        self.btn_hud_open_blend = tk.Button(
            self.hud_3d_frame,
            text="🧊 Blender ile Aç",
            bg="#10b981",
            fg="#021526",
            activebackground="#059669",
            font=(DarkTheme.FONT_FAMILY, 8, "bold"),
            relief="flat",
            padx=6,
            pady=3,
            cursor="hand2",
            command=self._open_selected_blend,
        )
        self.btn_hud_open_blend.pack(side=tk.LEFT, padx=2)

        # Mod Değiştirme Butonu
        tk.Button(
            self.hud_pill,
            text="📷/📐 Mod",
            bg=DarkTheme.BG_INPUT,
            fg=DarkTheme.TEXT_MUTED,
            activebackground=DarkTheme.ACCENT_CYAN,
            font=(DarkTheme.FONT_FAMILY, 8),
            relief="flat",
            padx=6,
            pady=3,
            cursor="hand2",
            command=self._toggle_viewport_mode,
        ).pack(side=tk.RIGHT, padx=2)

        # Sol Altta Yüzen Varlık Bilgi Rozeti
        self.hud_info_badge = tk.Frame(self.center_area, bg="#091122", bd=1, relief="ridge", padx=10, pady=5)
        self.hud_info_badge.place(x=16, rely=1.0, y=-16, anchor="sw")

        self.lbl_hud_badge = tk.Label(
            self.hud_info_badge,
            text="🔷 Sahne Hazır",
            bg="#091122",
            fg=DarkTheme.ACCENT_CYAN,
            font=(DarkTheme.FONT_FAMILY, 8, "bold"),
        )
        self.lbl_hud_badge.pack(side=tk.LEFT)

    def _build_right_drawer(self, parent: tk.Widget) -> None:
        """Açılır/kapanır sağ AI Danışmanı çekmecesini oluşturur."""
        self.right_drawer = tk.Frame(parent, bg=DarkTheme.BG_CARD, width=420, bd=1, relief="ridge")
        self.right_drawer.pack_propagate(False)

        # Üst Başlık Çubuğu & Kapat Butonu
        r_hdr = tk.Frame(self.right_drawer, bg=DarkTheme.BG_CARD, padx=10, pady=8)
        r_hdr.pack(fill=tk.X)

        tk.Label(
            r_hdr,
            text="🤖 AI Tasarım Danışmanı",
            bg=DarkTheme.BG_CARD,
            fg=DarkTheme.ACCENT_CYAN,
            font=(DarkTheme.FONT_FAMILY, 11, "bold"),
        ).pack(side=tk.LEFT)

        self.lbl_confidence = tk.Label(
            r_hdr,
            text="Güvenilirlik: -",
            bg=DarkTheme.BG_INPUT,
            fg=DarkTheme.ACCENT_CYAN,
            font=(DarkTheme.FONT_FAMILY, 8, "bold"),
            padx=6,
            pady=2,
            relief="flat",
        )
        self.lbl_confidence.pack(side=tk.LEFT, padx=6)

        btn_close_right = tk.Button(
            r_hdr,
            text="✕",
            bg=DarkTheme.BG_CARD,
            fg=DarkTheme.TEXT_MUTED,
            activebackground=DarkTheme.BG_INPUT,
            activeforeground="#ef4444",
            font=(DarkTheme.FONT_FAMILY, 10, "bold"),
            relief="flat",
            bd=0,
            padx=6,
            cursor="hand2",
            command=self._close_right_drawer,
        )
        btn_close_right.pack(side=tk.RIGHT)

        # Aktif Varlık & Proje Bağlam Rozeti
        self.lbl_ai_context = tk.Label(
            self.right_drawer,
            text="🎯 Bağlam: Varlık Seçilmedi",
            bg=DarkTheme.BG_INPUT,
            fg=DarkTheme.ACCENT_PURPLE,
            font=(DarkTheme.FONT_FAMILY, 8, "bold"),
            padx=8,
            pady=3,
            anchor=tk.W,
        )
        self.lbl_ai_context.pack(fill=tk.X, padx=8, pady=(0, 6))

        # Hızlı Aksiyon Çipleri
        chips_bar = tk.Frame(self.right_drawer, bg=DarkTheme.BG_CARD, padx=8)
        chips_bar.pack(fill=tk.X, pady=(0, 4))

        self._create_action_chip(chips_bar, "⚡ Mekanik Analizi", "{asset_name} ({category}) için core gameplay loop, kontroller ve gamefeel juice analizi yap.", "analyze_game")
        self._create_action_chip(chips_bar, "🏃 Animasyon Yorumu", "{asset_name} için kök hareketi (root motion), blend tree ve tepki süresi animasyon tasarımı.", "query")
        self._create_action_chip(chips_bar, "📋 GDD", "{project_name} projemiz ve {asset_name} için mekanikler ve ilerleme döngüsü GDD taslağı oluştur.", "create_gdd")
        self._create_action_chip(chips_bar, "💡 Fikir", "{project_name} projesinde {category} kategorisinde oyuncuyu bağlayan yenilikçi mekanikler türet.", "brainstorm")

        # Mod Seçimi ve Girdi Alanı
        in_bar = tk.Frame(self.right_drawer, bg=DarkTheme.BG_CARD, padx=8, pady=4)
        in_bar.pack(fill=tk.X)

        self.mode_var = tk.StringVar(value="query (Soru-Cevap)")
        self.mode_combo = ttk.Combobox(
            in_bar,
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
        )
        self.mode_combo.pack(fill=tk.X, pady=(0, 4))

        self.rag_input_text = tk.Text(
            in_bar,
            bg=DarkTheme.BG_INPUT,
            fg=DarkTheme.TEXT_MAIN,
            insertbackground=DarkTheme.TEXT_MAIN,
            font=(DarkTheme.FONT_FAMILY, 9),
            height=3,
            wrap=tk.WORD,
            relief="flat",
        )
        self.rag_input_text.pack(fill=tk.X, pady=(0, 4))
        self.rag_input_text.insert("1.0", "Karakter zıplama ve duvarda koşma mekaniği oyun hissiyatını nasıl güçlendirir?")

        ask_bar = tk.Frame(in_bar, bg=DarkTheme.BG_CARD)
        ask_bar.pack(fill=tk.X)

        self.btn_ask = ttk.Button(
            ask_bar,
            text="⚡ AI'ya Sor",
            style="Primary.TButton",
            command=self._execute_rag_query,
        )
        self.btn_ask.pack(side=tk.RIGHT)

        ttk.Button(ask_bar, text="📋 Kopyala", style="Secondary.TButton", command=self._copy_rag_tab_output).pack(side=tk.LEFT, padx=2)
        ttk.Button(ask_bar, text="💾 GDD Kaydet", style="Secondary.TButton", command=self._export_gdd_to_file).pack(side=tk.LEFT, padx=2)

        # Yanıt Alanı ve Kaynaklar
        out_frame = tk.Frame(self.right_drawer, bg=DarkTheme.BG_CARD, padx=8, pady=4)
        out_frame.pack(fill=tk.BOTH, expand=True)

        self.rag_output_text = tk.Text(
            out_frame,
            bg=DarkTheme.BG_DARK,
            fg=DarkTheme.TEXT_MAIN,
            font=(DarkTheme.FONT_FAMILY, 9),
            wrap=tk.WORD,
            relief="flat",
            padx=8,
            pady=8,
        )
        out_scroll = ttk.Scrollbar(out_frame, orient=tk.VERTICAL, command=self.rag_output_text.yview)
        self.rag_output_text.configure(yscrollcommand=out_scroll.set)
        self.rag_output_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        out_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Geriye dönük uyumluluk için rag_tab_output_text bağlama
        self.rag_tab_output_text = self.rag_output_text

        # Kaynaklar Paneli
        src_frame = tk.Frame(self.right_drawer, bg=DarkTheme.BG_CARD, padx=8, pady=2)
        src_frame.pack(fill=tk.X)
        tk.Label(src_frame, text="📚 Dayanak Kaynaklar", bg=DarkTheme.BG_CARD, fg=DarkTheme.TEXT_MUTED, font=(DarkTheme.FONT_FAMILY, 8, "bold")).pack(anchor=tk.W)

        self.sources_listbox = tk.Listbox(
            src_frame,
            bg=DarkTheme.BG_INPUT,
            fg=DarkTheme.TEXT_MAIN,
            selectbackground=DarkTheme.ACCENT_CYAN,
            selectforeground="#021526",
            font=(DarkTheme.FONT_FAMILY, 8),
            relief="flat",
            height=3,
        )
        self.sources_listbox.pack(fill=tk.X, pady=(2, 4))

        self.lbl_rag_status = tk.Label(
            self.right_drawer,
            text="Hazır. Hızlı çiplere tıklayabilir veya sorunuzu sorabilirsiniz.",
            bg=DarkTheme.BG_CARD,
            fg=DarkTheme.TEXT_MUTED,
            font=(DarkTheme.FONT_FAMILY, 8),
            anchor=tk.W,
            padx=8,
            pady=2,
        )
        self.lbl_rag_status.pack(fill=tk.X)

    def _toggle_left_drawer(self, view_name: str) -> None:
        """Sol çekmeceyi açar, kapatır veya görünümünü değiştirir."""
        if self._left_drawer_visible and self._active_left_view == view_name:
            self._close_left_drawer()
            return

        self._show_left_drawer_view(view_name)
        if not self._left_drawer_visible:
            self.left_drawer.pack(side=tk.LEFT, fill=tk.Y, before=self.center_area)
            self._left_drawer_visible = True
        self._update_activity_bar_buttons()

    def _close_left_drawer(self) -> None:
        """Sol çekmeceyi gizler."""
        if self._left_drawer_visible:
            self.left_drawer.pack_forget()
            self._left_drawer_visible = False
            self._update_activity_bar_buttons()

    def _show_left_drawer_view(self, view_name: str) -> None:
        """Sol çekmece içindeki görünümü ayarlar."""
        self._active_left_view = view_name
        self.drawer_assets_view.pack_forget()
        self.drawer_projects_view.pack_forget()
        self.drawer_sync_view.pack_forget()

        if view_name == "assets":
            self.lbl_drawer_title.config(text="🎨 Varlık Rafı")
            self.drawer_assets_view.pack(fill=tk.BOTH, expand=True)
        elif view_name == "projects":
            self.lbl_drawer_title.config(text="📁 Proje Yöneticisi")
            self.drawer_projects_view.pack(fill=tk.BOTH, expand=True)
        elif view_name == "sync":
            self.lbl_drawer_title.config(text="🔄 Senkronizasyon & Ayarlar")
            self.drawer_sync_view.pack(fill=tk.BOTH, expand=True)

    def _toggle_right_drawer(self) -> None:
        """Sağ AI Danışmanı çekmecesini açar veya kapatır."""
        if self._right_drawer_visible:
            self._close_right_drawer()
        else:
            self.right_drawer.pack(side=tk.RIGHT, fill=tk.Y)
            self._right_drawer_visible = True
            self._update_activity_bar_buttons()

    def _close_right_drawer(self) -> None:
        """Sağ AI Danışmanı çekmecesini gizler."""
        if self._right_drawer_visible:
            self.right_drawer.pack_forget()
            self._right_drawer_visible = False
            self._update_activity_bar_buttons()

    def _update_activity_bar_buttons(self) -> None:
        """Aktivite çubuğundaki butonların aktif/pasif stillerini günceller."""
        if not hasattr(self, "_act_buttons"):
            return

        for key, btn in self._act_buttons.items():
            is_active = False
            if key == "ai":
                is_active = self._right_drawer_visible
            else:
                is_active = (self._left_drawer_visible and self._active_left_view == key)

            if is_active:
                btn.config(bg=DarkTheme.BG_INPUT, fg=DarkTheme.ACCENT_CYAN)
            else:
                btn.config(bg="#070b14", fg=DarkTheme.TEXT_MUTED)

    def _set_category_filter(self, cat: str) -> None:
        """Kategori filtre çipini ve tablosunu senkronize olarak günceller."""
        for c_name, btn in getattr(self, "_chip_buttons", {}).items():
            if c_name == cat:
                btn.config(bg="#0891b2", fg="#ffffff", font=(DarkTheme.FONT_FAMILY, 8, "bold"))
            else:
                btn.config(bg=DarkTheme.BG_INPUT, fg=DarkTheme.TEXT_MUTED, font=(DarkTheme.FONT_FAMILY, 8, "normal"))

        if cat == "2D Sprite":
            self.blend_cat_filter_var.set("2D Sprite / Piksel Sanatı")
        elif cat == "Çevre":
            self.blend_cat_filter_var.set("Çevre/Level")
        else:
            self.blend_cat_filter_var.set(cat)

        self._refresh_blend_table()

    def _on_category_chip_clicked(self, cat: str) -> None:
        """Kategori filtre çipine tıklandığında."""
        self._set_category_filter(cat)

    def _toggle_viewport_zoom(self) -> None:
        """1:1 piksel ve sığdırma arasında geçiş yapar."""
        if hasattr(self, "viewport_3d"):
            if abs(self.viewport_3d.zoom - 120.0) < 5.0 and self.viewport_3d.pan_x == 0.0 and self.viewport_3d.pan_y == 0.0:
                self.viewport_3d.zoom_1_to_1()
            else:
                self.viewport_3d.zoom_fit()
            self._update_hud_toolbar()

    def _toggle_viewport_render_style(self) -> None:
        """Gölgeli ve tel kafes modları arasında geçiş yapar."""
        if hasattr(self, "viewport_3d"):
            self.viewport_3d.toggle_render_style()
            self._update_hud_toolbar()

    def _toggle_viewport_scaling(self) -> None:
        """Piksel ve yumuşak ölçekleme filtresini değiştirir."""
        if hasattr(self, "viewport_3d"):
            self.viewport_3d.toggle_scaling_filter()
            self._update_hud_toolbar()

    def _next_viewport_frame(self) -> None:
        """Sonraki kareye geçer."""
        if hasattr(self, "viewport_3d"):
            self.viewport_3d.next_frame()
            self._update_hud_toolbar()

    def _prev_viewport_frame(self) -> None:
        """Önceki kareye geçer."""
        if hasattr(self, "viewport_3d"):
            self.viewport_3d.prev_frame()
            self._update_hud_toolbar()

    def _toggle_viewport_animation(self) -> None:
        """Animasyonu duraklatır veya oynatır."""
        if hasattr(self, "viewport_3d"):
            is_anim = self.viewport_3d.toggle_animation()
            if hasattr(self, "btn_hud_play"):
                self.btn_hud_play.config(text="⏸" if is_anim else "▶")
            self._update_hud_toolbar()

    def _toggle_viewport_spin(self) -> None:
        """3D sahne turntable döndürmesini açar/kapatır."""
        if hasattr(self, "viewport_3d"):
            self.viewport_3d.toggle_auto_spin()
            self._update_hud_toolbar()

    def _reset_viewport_camera(self) -> None:
        """Kamerayı varsayılana sıfırlar."""
        if hasattr(self, "viewport_3d"):
            self.viewport_3d.reset_camera()
            self._update_hud_toolbar()

    def _toggle_viewport_mode(self) -> None:
        """2D / 3D görünüm modları arasında geçiş yapar."""
        if hasattr(self, "viewport_3d"):
            self.viewport_3d.toggle_mode()
            self._update_hud_toolbar()

    def _create_action_chip(self, parent: tk.Widget, label: str, prompt_template: str, mode: str) -> None:
        """Hızlı eylem çipi oluşturur (Aktif varlık bağlamı ile zenginleştirilmiş)."""
        def on_click():
            p_name = self.selected_project.name if self.selected_project else "Oyun Projesi"
            if self.selected_blend_ref:
                a_name = self.selected_blend_ref.name
                a_cat = self.selected_blend_ref.category
            elif hasattr(self, "viewport_3d") and self.viewport_3d.current_file_path:
                a_name = self.viewport_3d.current_file_path.name
                a_cat = self.viewport_3d.current_category or "Genel"
            else:
                a_name = "Varlık"
                a_cat = "Genel"

            final_prompt = prompt_template.format(
                project_name=p_name,
                asset_name=a_name,
                category=a_cat,
            ) if "{" in prompt_template else prompt_template

            self.rag_input_text.delete("1.0", tk.END)
            self.rag_input_text.insert("1.0", final_prompt)
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
            pady=3,
            cursor="hand2",
            command=on_click,
        )
        btn.pack(side=tk.LEFT, padx=2, pady=2)

    def _update_hud_toolbar(self) -> None:
        """HUD araç çubuğunu aktif varlığın 2D / 3D moduna göre günceller."""
        if not hasattr(self, "viewport_3d") or not hasattr(self, "hud_pill"):
            return

        is_image = (self.viewport_3d.display_mode == "image")
        if is_image:
            self.hud_3d_frame.pack_forget()
            self.hud_2d_frame.pack(side=tk.LEFT)
            if self.viewport_3d.animation_frames and len(self.viewport_3d.animation_frames) > 1:
                self.hud_anim_frame.pack(side=tk.LEFT, padx=4)
                is_anim = self.viewport_3d.is_animating
                self.btn_hud_play.config(text="⏸" if is_anim else "▶")
            else:
                self.hud_anim_frame.pack_forget()
            scale_label = "👾 Piksel" if self.viewport_3d.scaling_mode == "pixel" else "✨ Yumuşak"
            self.btn_hud_scale.config(text=scale_label)

            # 2D Görünümünde Blender vs Aseprite açma butonu adaptasyonu
            is_blend = bool(self.viewport_3d.current_format == ".blend")
            if is_blend:
                self.btn_hud_open_ase.config(
                    text="🧊 Blender ile Aç",
                    bg="#10b981",
                    activebackground="#059669",
                    fg="#021526",
                    command=self._open_selected_blend,
                )
            else:
                self.btn_hud_open_ase.config(
                    text="🎨 Aseprite ile Aç",
                    bg="#0891b2",
                    activebackground="#0e7490",
                    fg="#ffffff",
                    command=self._open_selected_aseprite,
                )
        else:
            self.hud_2d_frame.pack_forget()
            self.hud_3d_frame.pack(side=tk.LEFT)
            style_label = "💡 Gölgeli" if getattr(self.viewport_3d, "render_style", "shaded") == "shaded" else "📐 Tel Kafes"
            self.btn_hud_render_style.config(text=style_label)
            self.btn_hud_spin.config(
                bg="#0891b2" if self.viewport_3d.auto_spin else DarkTheme.BG_INPUT,
                fg="#ffffff" if self.viewport_3d.auto_spin else DarkTheme.TEXT_MAIN,
            )

        self._update_hud_info_badge()

    def _update_hud_info_badge(self) -> None:
        """Sol alttaki varlık rozetini günceller."""
        if not hasattr(self, "lbl_hud_badge"):
            return

        if not self.selected_blend_ref and not getattr(self.viewport_3d, "current_file_path", None):
            self.lbl_hud_badge.config(text="🔷 Jarvis Game Studio  |  Hazır")
            return

        if self.selected_blend_ref:
            ref = self.selected_blend_ref
            fname = ref.name
            cat = ref.category
            size_txt = ref.file_size_formatted
        else:
            p = self.viewport_3d.current_file_path
            fname = p.name if p else "Sahne"
            cat = self.viewport_3d.current_category or "Varlık"
            try:
                size_txt = format_file_size(p.stat().st_size) if p else "-"
            except Exception:
                size_txt = "-"

        if self.viewport_3d.display_mode == "image" and self.viewport_3d.current_thumbnail_img:
            dim = f"{self.viewport_3d.current_thumbnail_img.width}x{self.viewport_3d.current_thumbnail_img.height} px"
            if self.viewport_3d.animation_frames and len(self.viewport_3d.animation_frames) > 1:
                cur_k = self.viewport_3d.current_frame_index + 1
                tot_k = len(self.viewport_3d.animation_frames)
                dim += f" • Kare {cur_k}/{tot_k}"
        elif self.viewport_3d.bvh_bones:
            dim = f"{len(self.viewport_3d.bvh_bones)} Kemik İskelet"
        elif self.viewport_3d.mesh_vertices:
            style = "Gölgeli" if getattr(self.viewport_3d, "render_style", "shaded") == "shaded" else "Tel Kafes"
            dim = f"{len(self.viewport_3d.mesh_vertices)} Verts • {len(self.viewport_3d.mesh_faces)} Polys • {style}"
        else:
            dim = "3D Sahne"

        self.lbl_hud_badge.config(text=f"🔷 {fname}  •  [{cat}]  •  {dim}  •  {size_txt}")

    def _copy_rag_tab_output(self) -> None:
        """Tasarım analizi metnini panoya kopyalar."""
        text = self.rag_output_text.get("1.0", tk.END).strip()
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            messagebox.showinfo("Kopyalandı", "Tasarım analizi panoya kopyalandı.")

    def _export_gdd_to_file(self) -> None:
        """Tasarım dökümanını dosyaya (.md/.txt) kaydeder."""
        text = self.rag_output_text.get("1.0", tk.END).strip()
        if not text and hasattr(self, "rag_tab_output_text") and self.rag_tab_output_text != self.rag_output_text:
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
        """Geriye dönük uyumluluk: _execute_rag_query çağrısı."""
        self._execute_rag_query()

    def _on_rag_tab_complete(self, response: Any) -> None:
        """Geriye dönük uyumluluk."""
        self._on_rag_success(response)

    def _build_studio_tab(self, parent: ttk.Frame) -> None:
        """Geriye dönük uyumluluk sekme tutucusu."""
        pass

    def _build_rag_tab(self, parent: ttk.Frame) -> None:
        """Geriye dönük uyumluluk sekme tutucusu."""
        pass

    def _build_sync_tab(self, parent: ttk.Frame) -> None:
        """Geriye dönük uyumluluk sekme tutucusu."""
        pass

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
            if active_cat and active_cat != "Tümü":
                act_norm = active_cat.lower()
                cat_norm = blend.category.strip().lower()
                if cat_norm != act_norm and act_norm not in cat_norm and cat_norm not in act_norm:
                    continue
            blend.refresh_stats()
            status_txt = "✅ Diskte Var" if blend.exists() else "❌ Kayıp"
            mod_txt = blend.last_modified.strftime("%Y-%m-%d %H:%M") if blend.last_modified else "-"
            ext_clean = (blend.file_format or "").lower().lstrip(".")
            if ext_clean in ["png", "jpg", "jpeg", "webp", "bmp"]:
                fmt_badge = f"🎨 {ext_clean.upper()}"
            elif ext_clean in ["ase", "aseprite"]:
                fmt_badge = f"👾 {ext_clean.upper()}"
            elif ext_clean == "gif":
                fmt_badge = "🎞️ GIF"
            elif ext_clean == "blend":
                fmt_badge = "🧊 BLEND"
            elif ext_clean == "obj":
                fmt_badge = "📐 OBJ"
            elif ext_clean in ["gltf", "glb"]:
                fmt_badge = "🌐 GLTF"
            elif ext_clean == "bvh":
                fmt_badge = "🏃 BVH"
            elif ext_clean == "fbx":
                fmt_badge = "🦴 FBX"
            else:
                fmt_badge = f"📦 {ext_clean.upper() or '3D'}"

            self.blend_tree.insert(
                "",
                tk.END,
                iid=blend.id,
                values=(
                    blend.name,
                    blend.category,
                    fmt_badge,
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

        # 3. Yüzen HUD araç çubuğunu ve bilgi rozetini güncelle
        if hasattr(self, "_update_hud_toolbar"):
            self._update_hud_toolbar()

        # 4. AI Danışmanı aktif bağlam rozetini güncelle
        if hasattr(self, "lbl_ai_context"):
            p_name = self.selected_project.name if self.selected_project else "Proje"
            self.lbl_ai_context.config(text=f"🎯 Bağlam: {blend.name} [{blend.category}] • {p_name}")

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
        self._set_category_filter("Tümü")

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
        blend_id = selected_items[0] if selected_items else (self.selected_blend_ref.id if self.selected_blend_ref else None)
        if not blend_id:
            messagebox.showwarning("Uyarı", "Lütfen açmak için bir 3D / Blender dosyası seçin.")
            return

        try:
            self.plugin.open_blend_file(file_path_or_id=blend_id, project_name_or_id=self.selected_project.id if self.selected_project else None)
        except Exception as e:
            messagebox.showerror("Açma Hatası", f"Dosya açılamadı:\n{e}\n\nBlender veya uygun bir 3D görüntüleyici kurulu olduğundan emin olun.")

    def _open_selected_aseprite(self) -> None:
        """Seçilen Aseprite / görsel dosyasını Aseprite ile açar."""
        selected_items = self.blend_tree.selection()
        blend_id = selected_items[0] if selected_items else (self.selected_blend_ref.id if self.selected_blend_ref else None)
        if not blend_id:
            messagebox.showwarning("Uyarı", "Lütfen açmak için bir dosya seçin.")
            return

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
            if self.selected_blend_ref and self.selected_blend_ref.id == blend_id:
                self.selected_blend_ref = None
                if hasattr(self, "lbl_asset_inspector"):
                    self.lbl_asset_inspector.config(text="")
                if hasattr(self, "_update_hud_toolbar"):
                    self._update_hud_toolbar()
                if hasattr(self, "lbl_ai_context"):
                    p_name = self.selected_project.name if self.selected_project else "Proje"
                    self.lbl_ai_context.config(text=f"🎯 Bağlam: {p_name} (Varlık Seçilmedi)")
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
