"""Jarvis Game Designer Plugin root entry point and adapter."""

import os
from typing import Any

from game_designer.plugin import GameDesignerPlugin, JarvisPlugin

# Jarvis Core uyumluluğu için isteğe bağlı import
try:
    from jarvis_core.core.plugin_interface import IJarvisPlugin
except ImportError:
    # Jarvis Core yüklü değilse temel JarvisPlugin arayüzünü kullan
    class IJarvisPlugin:  # type: ignore
        pass


class JarvisGameDesignPlugin(IJarvisPlugin, GameDesignerPlugin):
    """Jarvis Core asistanına ve PyQt6 arayüzüne bağlanan ana plugin adaptörü."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    @property
    def name(self) -> str:
        return "Jarvis Game Design"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Oyun tasarımı konusunda uzmanlaşmış RAG tabanlı AI bilgi danışmanı."

    def initialize(self, auto_load_seeds: bool = True) -> bool:
        """Eklentiyi başlat."""
        res = super().initialize(auto_load_seeds=auto_load_seeds)
        return bool(res)

    def get_intents(self) -> list[str]:
        """Jarvis ana niyet tetikleyicileri."""
        return [
            "oyun tasarımı",
            "game design",
            "oyun geliştir",
            "mekanik tasarla",
            "bölüm tasarımı",
            "gdd oluştur",
            "core loop",
            "projeleri listele",
            "aktif proje",
            "aktif proje yap",
            "proje seç",
            "blend dosyaları",
        ]

    async def process_intent(self, intent: str, entities: dict[str, Any] | None = None) -> str:
        """Jarvis asenkron niyet işleme döngüsü."""
        entities = entities or {}
        user_text = entities.get("text", "")

        if intent == "projeleri listele":
            projects = self.list_projects()
            if not projects:
                return "Henüz kayıtlı bir oyun tasarımı projesi bulunmuyor."
            lines = ["📂 **Kayıtlı Oyun Projeleri:**"]
            for p in projects:
                status = "🌟 [AKTİF]" if p.is_active else "  "
                lines.append(f"{status} **{p.name}** ({p.game_engine or 'Belirtilmedi'} | {p.genre or 'Tür yok'}) - {len(p.blend_files)} Blend dosyası")
            return "\n".join(lines)

        if intent in ("aktif proje", "aktif proje yap", "proje seç"):
            target_proj_name = entities.get("project_name") or entities.get("name") or entities.get("proje")
            if target_proj_name:
                try:
                    proj = self.set_active_project(target_proj_name)
                    return f"🌟 Aktif proje başarıyla '{proj.name}' olarak belirlendi ve Jarvis ile eşitlendi."
                except Exception as e:
                    return f"Aktif proje belirlenemedi: {e}"

            active = self.get_active_project()
            if not active:
                return "Şu anda seçili aktif bir proje yok."
            return (
                f"🌟 **Aktif Proje:** {active.name}\n"
                f"- Motor: {active.game_engine or 'Belirtilmedi'}\n"
                f"- Tür: {active.genre or 'Belirtilmedi'}\n"
                f"- Aşama: {active.development_phase or 'concept'}\n"
                f"- Blender Dosyaları: {len(active.blend_files)} adet\n"
                f"- Özellikler: {', '.join(active.key_features) if active.key_features else 'Belirtilmedi'}"
            )

        if intent == "blend dosyaları":
            target_proj_name = entities.get("project_name") or entities.get("name")
            target_proj = self.get_project(target_proj_name) if target_proj_name else self.get_active_project()
            if not target_proj:
                return "Blender dosyalarını listelemek için önce bir proje seçilmelidir."
            if not target_proj.blend_files:
                return f"'{target_proj.name}' projesinde henüz eklenmiş .blend dosyası yok."
            lines = [f"🎨 **'{target_proj.name}' Projesine Ait Blend Dosyaları:**"]
            for b in target_proj.blend_files:
                status_icon = "✅" if b.exists() else "❌ (Kayıp)"
                lines.append(f"- **{b.name}** [{b.category}] ({b.file_size_formatted}) {status_icon} - `{b.file_path}`")
            return "\n".join(lines)

        if not user_text:
            return "Oyun tasarımı hakkında nasıl yardımcı olabilirim?"

        mode = entities.get("mode")
        engine = entities.get("engine")
        genre = entities.get("genre")
        response = self.query(user_text, mode=mode, engine=engine, genre=genre)
        return response.text

    def get_ui_widgets(self) -> list[Any]:
        """PyQt6 UI arayüz bileşenleri (opsiyonel)."""
        try:
            from PyQt6.QtWidgets import QMessageBox, QPushButton
            from jarvis_core.config import COLOR_ACCENT_CYAN
        except ImportError:
            return []

        btn = QPushButton("[ 🎮 OYUN TASARIM ASİSTANI ]")
        btn.setStyleSheet(
            f"background: rgba(6, 11, 20, 0.9); border: 1px solid {COLOR_ACCENT_CYAN}; color: {COLOR_ACCENT_CYAN}; padding: 10px; font-weight: bold;"
        )

        def show_info():
            msg = QMessageBox()
            msg.setWindowTitle("Jarvis Game Design")
            msg.setText("Oyun Tasarım Asistanı aktif.\nSoru-Cevap, Analiz, GDD ve Danışmanlık modları hazır.")
            msg.exec()

        btn.clicked.connect(show_info)
        return [btn]

    def get_background_daemons(self) -> list[Any]:
        return []

    def shutdown(self) -> None:
        super().shutdown()


__all__ = ["GameDesignerPlugin", "JarvisGameDesignPlugin", "JarvisPlugin"]
