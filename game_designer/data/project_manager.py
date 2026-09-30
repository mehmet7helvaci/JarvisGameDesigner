"""Oyun Tasarımı Projeleri ve Blender Dosyaları Yönetim Modülü."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from game_designer.config import Settings, get_settings
from game_designer.data.user_profile import UserProfileStore
from game_designer.models.project import BlendFileRef, GameProject, detect_asset_category
from game_designer.utils.logger import logger


class ProjectManager:
    """Oyun tasarımı projelerini ve ilişkili Blender 3D dosyalarını yöneten sınıf.

    Projeler 'data/projects/' altında JSON dosyaları olarak saklanır ve
    Jarvis UserProfileStore ile iki yönlü tam eşzamanlı çalışır.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        user_profile_store: UserProfileStore | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.projects_dir = self.settings.projects_dir
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.active_file = self.projects_dir / "active_project.json"
        self.user_profile_store = user_profile_store or UserProfileStore(self.settings)

    def _get_project_path(self, project_id: str) -> Path:
        """Proje ID'sine göre dosya yolunu döndürür."""
        safe_id = re.sub(r"[^\w\-]", "_", project_id)
        return self.projects_dir / f"{safe_id}.json"

    def list_projects(self) -> list[GameProject]:
        """Kayıtlı tüm projeleri döndürür. Aktif proje en üstte yer alır."""
        projects: list[GameProject] = []
        active_id = self._read_active_project_id()

        for file_path in self.projects_dir.glob("*.json"):
            if file_path.name == "active_project.json":
                continue
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                proj = GameProject.model_validate(data)
                proj.is_active = (proj.id == active_id)
                # Blend dosyası istatistiklerini güncelle
                for blend in proj.blend_files:
                    blend.refresh_stats()
                projects.append(proj)
            except Exception as e:
                logger.warning(f"Proje dosyası okunamadı ({file_path}): {e}")

        # Aktif olan önce, ardından güncellenme tarihine göre azalan sıralama (naive/aware uyumlu)
        def _sort_key(p: GameProject) -> tuple[int, float]:
            dt = p.updated_at or p.created_at
            if dt is None:
                ts = 0.0
            else:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                ts = dt.timestamp()
            return (1 if p.is_active else 0, ts)

        projects.sort(key=_sort_key, reverse=True)
        return projects

    def get_project(self, name_or_id: str) -> GameProject | None:
        """ID veya proje adına göre projeyi bulur (büyük/küçük harf duyarsız)."""
        target = name_or_id.strip().lower()
        if not target:
            return None

        # Doğrudan dosya ID kontrolü
        direct_path = self._get_project_path(name_or_id)
        if direct_path.exists():
            try:
                with open(direct_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                proj = GameProject.model_validate(data)
                if proj.id.lower() == target or proj.name.strip().lower() == target:
                    active_id = self._read_active_project_id()
                    proj.is_active = (proj.id == active_id)
                    for blend in proj.blend_files:
                        blend.refresh_stats()
                    return proj
            except Exception as e:
                logger.warning(f"Proje okunamadı ({direct_path}): {e}")

        # Tüm projeleri tara
        for proj in self.list_projects():
            if proj.id.lower() == target or proj.name.strip().lower() == target:
                return proj

        return None

    def create_project(
        self,
        name: str,
        game_engine: str | None = None,
        genre: str | None = None,
        development_phase: str = "concept",
        description: str = "",
        notes: str = "",
        key_features: list[str] | None = None,
        known_challenges: list[str] | None = None,
        gdd_snippets: list[str] | None = None,
        activate: bool = False,
        user_id: str = "default_user",
        engine: str | None = None,
        **kwargs: Any,
    ) -> GameProject:
        """Yeni bir oyun projesi oluşturur ve diske kaydeder."""
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Proje adı boş olamaz.")

        existing = self.get_project(clean_name)
        if existing:
            raise ValueError(f"'{clean_name}' adında bir proje zaten mevcut.")

        actual_engine = game_engine or engine or kwargs.get("game_engine") or kwargs.get("engine")
        now = datetime.now(timezone.utc)
        proj = GameProject(
            name=clean_name,
            game_engine=actual_engine,
            genre=genre,
            development_phase=development_phase,
            description=description,
            notes=notes,
            key_features=key_features or [],
            known_challenges=known_challenges or [],
            gdd_snippets=gdd_snippets or [],
            created_at=now,
            updated_at=now,
        )

        self.save_project(proj)

        # İlk proje ise veya activate talep edilmişse aktif yap
        all_projects = self.list_projects()
        if activate or len(all_projects) == 1:
            self.set_active_project(proj.id, user_id=user_id)
            proj.is_active = True

        logger.info(f"Yeni proje oluşturuldu: '{proj.name}' (ID: {proj.id})")
        return proj

    def save_project(self, project: GameProject) -> None:
        """Projeyi JSON dosyasına kaydeder."""
        project.updated_at = datetime.now(timezone.utc)
        path = self._get_project_path(project.id)
        temp_path = path.with_suffix(".tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(project.model_dump_json(indent=2))
            temp_path.replace(path)
        except Exception as e:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            logger.error(f"Proje kaydedilirken hata ({path}): {e}")
            raise

    def update_project(
        self,
        name_or_id: str,
        user_id: str = "default_user",
        **kwargs: Any,
    ) -> GameProject:
        """Mevcut bir projenin bilgilerini günceller."""
        proj = self.get_project(name_or_id)
        if not proj:
            raise ValueError(f"Güncellenecek proje bulunamadı: '{name_or_id}'")

        if "engine" in kwargs and "game_engine" not in kwargs:
            kwargs["game_engine"] = kwargs.pop("engine")

        allowed_fields = {
            "name",
            "game_engine",
            "genre",
            "development_phase",
            "description",
            "notes",
            "key_features",
            "known_challenges",
            "gdd_snippets",
        }

        # İsim değişiyorsa benzersizlik kontrolü
        if "name" in kwargs and kwargs["name"]:
            new_name = kwargs["name"].strip()
            if new_name.lower() != proj.name.lower():
                dup = self.get_project(new_name)
                if dup and dup.id != proj.id:
                    raise ValueError(f"'{new_name}' adında başka bir proje zaten mevcut.")
                proj.name = new_name

        for key, val in kwargs.items():
            if key in allowed_fields and key != "name" and val is not None:
                setattr(proj, key, val)

        self.save_project(proj)

        # Eğer aktif proje güncellendiyse active_project.json ve Jarvis UserProfileStore'u da güncelle
        if proj.is_active:
            active_data = {
                "active_project_id": proj.id,
                "project_name": proj.name,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            temp_active = self.active_file.with_suffix(".tmp")
            try:
                with open(temp_active, "w", encoding="utf-8") as f:
                    json.dump(active_data, f, indent=2, ensure_ascii=False)
                temp_active.replace(self.active_file)
            except Exception:
                pass
            self._sync_active_to_profile(proj, user_id=user_id)

        logger.info(f"Proje güncellendi: '{proj.name}' (ID: {proj.id})")
        return proj

    def delete_project(self, name_or_id: str, user_id: str = "default_user") -> bool:
        """Projeyi siler. Silinen proje aktif ise aktiflik durumunu temizler."""
        proj = self.get_project(name_or_id)
        if not proj:
            return False

        path = self._get_project_path(proj.id)
        if path.exists():
            path.unlink()

        if proj.is_active:
            self._clear_active_project(user_id=user_id)

        logger.info(f"Proje silindi: '{proj.name}' (ID: {proj.id})")
        return True

    def set_active_project(self, name_or_id: str, user_id: str = "default_user") -> GameProject:
        """Projeyi aktif proje olarak belirler ve Jarvis profiliyle eşitler."""
        proj = self.get_project(name_or_id)
        if not proj:
            raise ValueError(f"Aktif yapılacak proje bulunamadı: '{name_or_id}'")

        # active_project.json dosyasını atomik güncelle
        active_data = {
            "active_project_id": proj.id,
            "project_name": proj.name,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        temp_active = self.active_file.with_suffix(".tmp")
        with open(temp_active, "w", encoding="utf-8") as f:
            json.dump(active_data, f, indent=2, ensure_ascii=False)
        temp_active.replace(self.active_file)

        proj.is_active = True
        self._sync_active_to_profile(proj, user_id=user_id)
        logger.info(f"Aktif proje belirlendi: '{proj.name}' (ID: {proj.id})")
        return proj

    def get_active_project(self, user_id: str = "default_user") -> GameProject | None:
        """Şu anda aktif olan projeyi döndürür."""
        active_id = self._read_active_project_id()
        if active_id:
            proj = self.get_project(active_id)
            if proj:
                proj.is_active = True
                return proj
            else:
                # Yetim kalmış active_project.json kaydını temizle
                try:
                    if self.active_file.exists():
                        self.active_file.unlink()
                except Exception:
                    pass

        # Eğer active_file yoksa UserProfile'daki aktif projeyi kontrol et
        try:
            profile = self.user_profile_store.get_or_create_profile(user_id)
            if profile.active_project:
                matched = self.get_project(profile.active_project.project_name)
                if matched:
                    self.set_active_project(matched.id, user_id=user_id)
                    return matched
        except Exception:
            pass

        return None

    def _read_active_project_id(self) -> str | None:
        """active_project.json dosyasından aktif proje ID'sini okur."""
        if not self.active_file.exists():
            return None
        try:
            with open(self.active_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("active_project_id")
        except Exception as e:
            logger.warning(f"Aktif proje dosyası okunamadı: {e}")
            return None

    def _sync_active_to_profile(self, project: GameProject, user_id: str = "default_user") -> None:
        """Aktif projeyi Jarvis UserProfileStore ile eşitler."""
        try:
            active_model = project.to_active_project()
            self.user_profile_store.update_active_project(user_id, active_model)
        except Exception as e:
            logger.error(f"UserProfileStore senkronizasyon hatası: {e}")

    def _clear_active_project(self, user_id: str = "default_user") -> None:
        """Aktif proje durumunu temizler."""
        if self.active_file.exists():
            try:
                self.active_file.unlink()
            except Exception:
                pass
        try:
            profile = self.user_profile_store.get_or_create_profile(user_id)
            profile.active_project = None
            self.user_profile_store.save_profile(profile)
        except Exception as e:
            logger.warning(f"Profil aktif proje temizlenemedi: {e}")

    # === BLENDER (.BLEND) DOSYALARI İŞLEMLERİ ===

    def add_blend_file(
        self,
        project_name_or_id: str,
        file_path: str,
        category: str | None = None,
        notes: str = "",
        name: str | None = None,
    ) -> BlendFileRef:
        """Bir projeye 3D/Blender (.blend, .fbx, .obj, .gltf, .bvh vb.) dosya referansı ekler."""
        proj = self.get_project(project_name_or_id)
        if not proj:
            raise ValueError(f"Proje bulunamadı: '{project_name_or_id}'")

        resolved_path = str(Path(file_path).resolve())
        file_name = name or Path(resolved_path).name or "untitled.asset"

        detected = detect_asset_category(resolved_path)
        if category is None:
            final_category = detected
        elif category == "Genel" and detected != "Genel":
            final_category = detected
        else:
            final_category = category or "Genel"

        blend_ref = BlendFileRef(
            name=file_name,
            file_path=resolved_path,
            category=final_category,
            notes=notes,
        )
        blend_ref.refresh_stats()

        updated_ref = proj.add_or_update_blend_file(blend_ref)
        self.save_project(proj)
        logger.info(f"3D Varlık dosyası eklendi: '{blend_ref.name}' ({final_category}) -> Proje: '{proj.name}'")
        return updated_ref

    def get_blend_files(
        self,
        project_name_or_id: str,
        category: str | None = None,
    ) -> list[BlendFileRef]:
        """Projeye ait Blender dosyalarını listeler."""
        proj = self.get_project(project_name_or_id)
        if not proj:
            return []

        files = list(proj.blend_files)
        # İstatistikleri güncelle
        for f in files:
            f.refresh_stats()

        if category:
            cat_norm = category.strip().lower()
            files = [f for f in files if f.category.strip().lower() == cat_norm]

        return files

    def remove_blend_file(
        self,
        project_name_or_id: str,
        blend_file_id_or_path: str,
    ) -> bool:
        """Projeden bir Blend dosya referansını kaldırır."""
        proj = self.get_project(project_name_or_id)
        if not proj:
            return False

        removed = proj.remove_blend_file(blend_file_id_or_path)
        if removed:
            self.save_project(proj)
            logger.info(f"Blend dosyası kaldırıldı ({blend_file_id_or_path}) -> Proje: '{proj.name}'")
        return removed

    def open_blend_file(
        self,
        file_path_or_id: str,
        project_name_or_id: str | None = None,
    ) -> bool:
        """Blender (.blend) dosyasını sistemin varsayılan uygulamasıyla (Blender) açar."""
        target_path: Path | None = None

        # Önce projede aranıyorsa kontrol et
        if project_name_or_id:
            proj = self.get_project(project_name_or_id)
            if proj:
                blend_ref = proj.get_blend_file(file_path_or_id)
                if blend_ref:
                    target_path = Path(blend_ref.file_path)

        # Doğrudan yol verilmişse veya bulunamadıysa doğrudan path kontrolü
        if target_path is None:
            p = Path(file_path_or_id)
            if p.is_file():
                target_path = p
            else:
                # Tüm projelerde id ara
                for proj in self.list_projects():
                    blend_ref = proj.get_blend_file(file_path_or_id)
                    if blend_ref:
                        target_path = Path(blend_ref.file_path)
                        break

        if target_path is None or not target_path.is_file():
            raise FileNotFoundError(f"Blender dosyası diskte bulunamadı: '{file_path_or_id}'")

        if target_path.suffix.lower() in [".ase", ".aseprite"]:
            return self.open_aseprite_file(str(target_path), project_name_or_id=project_name_or_id)

        str_path = str(target_path.resolve())

        try:
            if sys.platform == "win32":
                try:
                    os.startfile(str_path)
                except OSError as os_err:
                    # Windows dosya ilişkilendirmesi yoksa (WinError 1155) Blender çalıştırılabilir dosyasını ara
                    blender_exe = find_blender_executable()
                    if blender_exe:
                        subprocess.Popen([blender_exe, str_path])
                    else:
                        raise RuntimeError(
                            f"Blender dosyası açılamadı ({os_err}). Sistemde Blender kurulu olmayabilir veya .blend uzantısı Blender ile ilişkilendirilmemiş."
                        ) from os_err
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str_path])
            else:
                subprocess.Popen(["xdg-open", str_path])
            logger.info(f"Blender dosyası açıldı: {str_path}")
            return True
        except Exception as e:
            logger.error(f"Blender dosyası açılırken hata ({str_path}): {e}")
            raise

    def open_aseprite_file(
        self,
        file_path_or_id: str,
        project_name_or_id: str | None = None,
    ) -> bool:
        """Aseprite (.ase / .aseprite) dosyasını sistemin varsayılan uygulaması veya Aseprite ile açar."""
        target_path: Path | None = None

        if project_name_or_id:
            proj = self.get_project(project_name_or_id)
            if proj:
                blend_ref = proj.get_blend_file(file_path_or_id)
                if blend_ref:
                    target_path = Path(blend_ref.file_path)

        if target_path is None:
            p = Path(file_path_or_id)
            if p.is_file():
                target_path = p
            else:
                for proj in self.list_projects():
                    blend_ref = proj.get_blend_file(file_path_or_id)
                    if blend_ref:
                        target_path = Path(blend_ref.file_path)
                        break

        if target_path is None or not target_path.is_file():
            raise FileNotFoundError(f"Aseprite dosyası diskte bulunamadı: '{file_path_or_id}'")

        str_path = str(target_path.resolve())

        try:
            is_ase = target_path.suffix.lower() in [".ase", ".aseprite"]
            ase_exe = find_aseprite_executable()

            # Resim dosyası Aseprite ile açılmak isteniyorsa ve exe mevcutsa doğrudan exe ile aç
            if not is_ase and ase_exe:
                subprocess.Popen([ase_exe, str_path])
                logger.info(f"Görsel dosyası Aseprite ile açıldı ({ase_exe}): {str_path}")
                return True

            if sys.platform == "win32":
                try:
                    os.startfile(str_path)
                except OSError as os_err:
                    if ase_exe:
                        subprocess.Popen([ase_exe, str_path])
                    else:
                        raise RuntimeError(
                            f"Aseprite dosyası açılamadı ({os_err}). Sistemde Aseprite kurulu olmayabilir veya dosya uzantısı ilişkilendirilmemiş."
                        ) from os_err
            elif sys.platform == "darwin":
                if ase_exe:
                    subprocess.Popen([ase_exe, str_path])
                else:
                    subprocess.Popen(["open", str_path])
            else:
                if ase_exe:
                    subprocess.Popen([ase_exe, str_path])
                else:
                    subprocess.Popen(["xdg-open", str_path])
            logger.info(f"Aseprite dosyası açıldı: {str_path}")
            return True
        except Exception as e:
            logger.error(f"Aseprite dosyası açılırken hata ({str_path}): {e}")
            raise


def find_blender_executable() -> str | None:
    """Sistemde kurulu Blender çalıştırılabilir dosyasını arar."""
    import shutil
    which_blender = shutil.which("blender")
    if which_blender:
        return which_blender

    if sys.platform == "win32":
        import glob
        patterns = [
            r"C:\Program Files\Blender Foundation\Blender*\blender.exe",
            r"C:\Program Files (x86)\Blender Foundation\Blender*\blender.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Blender Foundation\Blender*\blender.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Blender Foundation\Blender*\blender.exe"),
        ]
        for pat in patterns:
            matches = glob.glob(pat)
            if matches:
                return sorted(matches, reverse=True)[0]
    return None


def find_aseprite_executable() -> str | None:
    """Sistemde kurulu Aseprite çalıştırılabilir dosyasını Program Files, Steam ve AppData'da arar."""
    import shutil
    which_ase = shutil.which("aseprite") or shutil.which("Aseprite")
    if which_ase:
        return which_ase

    if sys.platform == "win32":
        import glob
        patterns = [
            r"C:\Program Files\Aseprite\aseprite.exe",
            r"C:\Program Files (x86)\Aseprite\aseprite.exe",
            r"C:\Program Files\Steam\steamapps\common\Aseprite\aseprite.exe",
            r"C:\Program Files (x86)\Steam\steamapps\common\Aseprite\aseprite.exe",
            os.path.expandvars(r"%PROGRAMFILES%\Steam\steamapps\common\Aseprite\aseprite.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Steam\steamapps\common\Aseprite\aseprite.exe"),
            r"D:\Steam\steamapps\common\Aseprite\aseprite.exe",
            r"D:\SteamLibrary\steamapps\common\Aseprite\aseprite.exe",
            r"E:\SteamLibrary\steamapps\common\Aseprite\aseprite.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Aseprite\aseprite.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Aseprite\aseprite.exe"),
            os.path.expandvars(r"%APPDATA%\Aseprite\aseprite.exe"),
        ]
        for pat in patterns:
            matches = glob.glob(pat)
            if matches:
                return sorted(matches, reverse=True)[0]
    elif sys.platform == "darwin":
        for mac_path in [
            "/Applications/Aseprite.app/Contents/MacOS/aseprite",
            os.path.expanduser("~/Applications/Aseprite.app/Contents/MacOS/aseprite"),
            os.path.expanduser("~/Library/Application Support/Steam/steamapps/common/Aseprite/Aseprite.app/Contents/MacOS/aseprite"),
        ]:
            if Path(mac_path).is_file():
                return mac_path
    elif sys.platform.startswith("linux"):
        for linux_path in [
            "/usr/bin/aseprite",
            "/usr/local/bin/aseprite",
            os.path.expanduser("~/.steam/steam/steamapps/common/Aseprite/aseprite"),
            os.path.expanduser("~/.local/share/Steam/steamapps/common/Aseprite/aseprite"),
        ]:
            if Path(linux_path).is_file():
                return linux_path
    return None

