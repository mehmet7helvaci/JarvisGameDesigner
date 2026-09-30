#!/usr/bin/env pythonw
"""Jarvis Game Designer — Bağımsız Masaüstü GUI Başlatıcı."""

import os
from pathlib import Path
import sys

# Proje kök dizinini Python path'e ekle
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import io

# pythonw.exe altında sys.stdout ve sys.stderr None olabilir.
# Konsolsuz ortamda çökmeleri önlemek için güvenli stream'lere yönlendir
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

# Windows UTF-8 desteği ve Görev Yöneticisi / Taskbar Uygulama Kimliği
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure") and sys.stdout and not getattr(sys.stdout, "closed", True):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure") and sys.stderr and not getattr(sys.stderr, "closed", True):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Jarvis.GameDesigner.Studio.1.0")
    except Exception:
        pass


def launch():
    """GUI uygulamasını başlatır."""
    try:
        from game_designer.ui.app import main
        main()
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Jarvis Game Designer Başlatma Hatası",
                f"Uygulama başlatılırken bir hata oluştu:\n\n{e}\n\nDetay:\n{error_details}",
            )
            root.destroy()
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    launch()
