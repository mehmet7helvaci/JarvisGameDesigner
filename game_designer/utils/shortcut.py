"""Windows Masaüstü Kısayolu (.lnk) Oluşturma ve Yönetim Modülü."""

import os
from pathlib import Path
import subprocess
import sys

from game_designer.config import PROJECT_ROOT
from game_designer.utils.logger import logger


def get_desktop_path() -> Path:
    """Kullanıcının geçerli masaüstü klasör yolunu belirler."""
    onedrive_desktop = Path(r"c:\Users\mehme\OneDrive\Masaüstü")
    if onedrive_desktop.exists() and onedrive_desktop.is_dir():
        return onedrive_desktop

    # Standart Windows masaüstü veya genel Desktop
    user_home = Path.home()
    turkish_desktop = user_home / "OneDrive" / "Masaüstü"
    if turkish_desktop.exists():
        return turkish_desktop

    english_onedrive_desktop = user_home / "OneDrive" / "Desktop"
    if english_onedrive_desktop.exists():
        return english_onedrive_desktop

    standard_desktop = user_home / "Desktop"
    if standard_desktop.exists():
        return standard_desktop

    standard_tr_desktop = user_home / "Masaüstü"
    if standard_tr_desktop.exists():
        return standard_tr_desktop

    return user_home


def get_pythonw_executable() -> str:
    """Konsol penceresi açmadan çalışacak pythonw.exe yolunu döndürür."""
    py_exec = Path(sys.executable)
    pythonw = py_exec.parent / "pythonw.exe"
    if pythonw.exists():
        return str(pythonw)
    return str(py_exec)


def create_desktop_shortcut(
    shortcut_path: str | Path | None = None,
    target_script: str | Path | None = None,
    working_dir: str | Path | None = None,
    description: str = "Jarvis Game Designer - Oyun & Blender 3D Tasarım Asistanı",
    icon_path: str | Path | None = None,
) -> Path:
    """Masaüstüne gui_launcher.pyw'yi başlatan .lnk kısayolu oluşturur."""
    desktop = get_desktop_path()
    final_shortcut = Path(shortcut_path) if shortcut_path else (desktop / "Jarvis Game Designer.lnk")
    final_target = Path(target_script) if target_script else (PROJECT_ROOT / "gui_launcher.pyw")
    final_workdir = Path(working_dir) if working_dir else PROJECT_ROOT
    pythonw_exe = get_pythonw_executable()

    default_ico = PROJECT_ROOT / "assets" / "icon.ico"
    if icon_path:
        actual_icon = str(Path(icon_path).resolve())
    elif default_ico.is_file():
        actual_icon = str(default_ico.resolve())
    else:
        actual_icon = f"{pythonw_exe},0"

    final_shortcut.parent.mkdir(parents=True, exist_ok=True)

    if sys.platform == "win32":
        import base64

        # UTF-16LE kodlanmış PowerShell betiği ile tüm Türkçe karakterleri ve tırnakları %100 koru
        str_shortcut = str(final_shortcut.resolve())
        str_target = str(final_target.resolve())
        str_workdir = str(final_workdir.resolve())

        ps_script = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{str_shortcut}")
$Shortcut.TargetPath = "{pythonw_exe}"
$Shortcut.Arguments = '"{str_target}"'
$Shortcut.WorkingDirectory = "{str_workdir}"
$Shortcut.Description = "{description}"
$Shortcut.IconLocation = "{actual_icon}"
$Shortcut.Save()
"""
        b64_script = base64.b64encode(ps_script.encode("utf-16le")).decode("ascii")
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", b64_script],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                check=True,
            )
            logger.info(f"Masaüstü kısayolu oluşturuldu: {final_shortcut}")
            return final_shortcut
        except Exception as e:
            logger.error(f"PowerShell kısayol oluşturma hatası: {e}")
            raise RuntimeError(f"Kısayol oluşturulamadı: {e}") from e
    else:
        # Linux/macOS için .desktop veya symlink fallback
        desktop_file = final_shortcut.with_suffix(".desktop")
        content = (
            f"[Desktop Entry]\n"
            f"Type=Application\n"
            f"Name=Jarvis Game Designer\n"
            f"Exec={pythonw_exe} {final_target}\n"
            f"Path={final_workdir}\n"
            f"Terminal=false\n"
            f"Comment={description}\n"
        )
        desktop_file.write_text(content, encoding="utf-8")
        desktop_file.chmod(0o755)
        logger.info(f"Desktop launcher oluşturuldu: {desktop_file}")
        return desktop_file


if __name__ == "__main__":
    path = create_desktop_shortcut()
    print(f"Kısayol başarıyla oluşturuldu: {path}")
