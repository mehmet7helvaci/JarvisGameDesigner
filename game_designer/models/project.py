"""Oyun tasarımı projeleri ve Blender (.blend) dosya referans modelleri."""

from datetime import datetime, timezone
from pathlib import Path
import uuid
from pydantic import BaseModel, Field

from game_designer.models.user_profile import ActiveProject


def format_file_size(size_bytes: int) -> str:
    """Byte cinsinden dosya boyutunu okunabilir formata dönüştürür."""
    if size_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_idx = 0
    size = float(size_bytes)
    while size >= 1024.0 and unit_idx < len(units) - 1:
        size /= 1024.0
        unit_idx += 1
    return f"{size:.1f} {units[unit_idx]}" if unit_idx > 0 else f"{int(size)} B"


SUPPORTED_3D_EXTENSIONS = {".blend", ".fbx", ".gltf", ".glb", ".obj", ".dae", ".bvh"}
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tga"}
SUPPORTED_ASEPRITE_EXTENSIONS = {".aseprite", ".ase"}
SUPPORTED_EXTENSIONS = SUPPORTED_3D_EXTENSIONS | SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_ASEPRITE_EXTENSIONS


def detect_asset_category(file_path_or_name: str) -> str:
    """Dosya adı ve uzantısına göre otomatik varlık kategorisi belirler (Türkçe ve İngilizce destekli)."""
    import re
    path = Path(file_path_or_name)
    stem_lower = path.stem.lower()
    ext = path.suffix.lower()

    # Kelime belirteçleri (tokens)
    tokens = set(re.split(r"[-_.\s0-9]+", stem_lower))

    def matches(keywords: list[str]) -> bool:
        for kw in keywords:
            # Kısa kelimeler (örn: ev, man, guy, box, gun, fx) mutlaka bağımsız token olarak eşleşmelidir
            if len(kw) <= 3:
                if kw in tokens:
                    return True
            else:
                if kw in tokens or kw in stem_lower:
                    return True
        return False

    # Animasyon hareket anahtar kelimeleri
    anim_keywords = [
        "anim", "walk", "run", "idle", "jump", "attack", "dance", "death", "crawl", "pose",
        "sprint", "motion", "hit", "combo", "fall", "climb", "roll",
        "yuru", "yurume", "kos", "kosma", "zipla", "ziplama", "saldir", "saldiri", "darbe",
        "olum", "animasyon", "dans", "hareket", "tirman", "ucus", "durus",
    ]

    # Aseprite dosyaları: Animasyon anahtar kelimeleri varsa "Animasyon", aksi halde "2D Sprite / Piksel Sanatı"
    if ext in SUPPORTED_ASEPRITE_EXTENSIONS:
        if matches(anim_keywords):
            return "Animasyon"
        return "2D Sprite / Piksel Sanatı"

    # 1. Animasyon: .bvh uzantısı veya animasyon hareket anahtar kelimeleri
    if ext == ".bvh" or matches(anim_keywords):
        return "Animasyon"

    # 2. Karakter: Oyuncu, kahraman, düşman, yaratık, NPC
    char_keywords = [
        "hero", "char", "enemy", "player", "npc", "monster", "boss", "guy", "woman", "man",
        "creature", "body", "soldier", "warrior", "knight", "human", "avatar", "robot",
        "karakter", "kahraman", "dusman", "canavar", "oyuncu", "savasci", "sovalye", "asker",
        "yaratik", "insan",
    ]
    if matches(char_keywords):
        return "Karakter"

    # 3. Çevre / Seviye: Harita, zemin, bina, doğa, sahne, zindan
    env_keywords = [
        "level", "map", "env", "scene", "terrain", "world", "room", "dungeon", "ground",
        "building", "house", "tree", "rock", "nature", "platform",
        "harita", "dunya", "seviye", "cevre", "zemin", "zindan", "oda", "bina", "ev",
        "agac", "kaya", "arazi", "sahne", "mekan", "doga",
    ]
    if matches(env_keywords):
        return "Çevre/Level"

    # 4. Prop / Eşya: Silah, kutu, mobilya, aksesuar, nesne
    prop_keywords = [
        "weapon", "sword", "prop", "gun", "shield", "item", "chest", "box", "barrel",
        "door", "chair", "table", "pickup", "loot", "lamp", "knife", "bow",
        "silah", "kilic", "bicak", "tufek", "tabanca", "kalkan", "yay", "kutu",
        "sandik", "kapi", "esya", "obje", "sandalye", "masa", "iksir", "fener",
    ]
    if matches(prop_keywords):
        return "Prop"

    # 5. Araç: Araba, uçak, gemi, tank, motor
    vehicle_keywords = [
        "car", "vehicle", "ship", "plane", "bike", "tank", "truck", "helicopter", "boat",
        "araba", "arac", "gemi", "ucak", "motor", "bisiklet", "tekne", "helikopter",
    ]
    if matches(vehicle_keywords):
        return "Araç"

    # 6. VFX / Işıklandırma / Büyü
    vfx_keywords = [
        "vfx", "fx", "particle", "light", "fire", "smoke", "explosion", "spark", "magic",
        "efekt", "ates", "duman", "patlama", "isik", "parilti", "buyu",
    ]
    if matches(vfx_keywords):
        return "VFX/Diğer"

    # 2D Görsel genel fallback'i
    if ext in SUPPORTED_IMAGE_EXTENSIONS:
        return "2D Sprite / Piksel Sanatı"

    return "Genel"


class BlendFileRef(BaseModel):
    """Bir projeye ait 3D (.blend, .fbx, .obj, .gltf vb.) dosya referansı."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    file_path: str
    category: str = "Genel"  # "Karakter", "Çevre/Level", "Animasyon", "Prop", "Araç", "VFX/Diğer", "Genel"
    notes: str = ""
    file_size_bytes: int = 0
    file_size_formatted: str = "0 B"
    last_modified: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def file_name(self) -> str:
        """Dosya adı takma adı (name ile eşdeğer)."""
        return self.name

    @property
    def file_format(self) -> str:
        """Dosya uzantısı (örn. 'blend', 'fbx', 'obj', 'glb')."""
        ext = Path(self.file_path).suffix.lstrip(".").lower()
        return ext if ext else "blend"

    def exists(self) -> bool:
        """Dosyanın diskte mevcut olup olmadığını kontrol eder."""
        try:
            return Path(self.file_path).is_file()
        except Exception:
            return False

    def refresh_stats(self) -> bool:
        """Diskteki dosyanın boyut ve son değişiklik bilgilerini günceller."""
        try:
            p = Path(self.file_path)
            if p.is_file():
                stat = p.stat()
                self.file_size_bytes = stat.st_size
                self.file_size_formatted = format_file_size(stat.st_size)
                self.last_modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                return True
        except Exception:
            pass
        return False


class GameProject(BaseModel):
    """Oyun tasarımı projesi veri modeli."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    game_engine: str | None = None  # Unity, Unreal, Godot vb.
    genre: str | None = None  # RPG, FPS, Roguelike, Platformer vb.
    development_phase: str | None = "concept"  # concept, prototype, production, polish
    description: str = ""
    notes: str = ""
    key_features: list[str] = Field(default_factory=list)
    known_challenges: list[str] = Field(default_factory=list)
    gdd_snippets: list[str] = Field(default_factory=list)
    blend_files: list[BlendFileRef] = Field(default_factory=list)
    is_active: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_active_project(self) -> ActiveProject:
        """UserProfileStore ile senkronizasyon için ActiveProject modeline dönüştürür."""
        return ActiveProject(
            project_name=self.name,
            game_engine=self.game_engine,
            genre=self.genre,
            development_phase=self.development_phase,
            key_features=list(self.key_features),
            known_challenges=list(self.known_challenges),
            notes=self.notes or self.description,
        )

    @staticmethod
    def _matches_blend_ref(ref: BlendFileRef, target: str) -> bool:
        """Hedef ID, dosya adı veya dosya yolunun ref ile eşleşip eşleşmediğini kontrol eder."""
        target_clean = target.strip()
        if not target_clean:
            return False

        # 1. ID eşleşmesi (büyük/küçük harf duyarsız)
        if ref.id.lower() == target_clean.lower():
            return True

        # 2. Dosya adı eşleşmesi
        if ref.name.lower() == target_clean.lower():
            return True

        # 3. Dosya yolu eşleşmesi (büyük/küçük harf ve eğik çizgi duyarsız)
        ref_norm_simple = ref.file_path.replace("/", "\\").lower()
        target_norm_simple = target_clean.replace("/", "\\").lower()
        if ref_norm_simple == target_norm_simple:
            return True

        # 4. Çözümlenmiş mutlak yol eşleşmesi
        try:
            ref_resolved = str(Path(ref.file_path).resolve()).lower()
            target_resolved = str(Path(target_clean).resolve()).lower()
            if ref_resolved == target_resolved:
                return True
        except Exception:
            pass

        return False

    def add_or_update_blend_file(self, blend_ref: BlendFileRef) -> BlendFileRef:
        """Blend dosya referansını ekler veya mevcut olanı günceller."""
        for idx, existing in enumerate(self.blend_files):
            if self._matches_blend_ref(existing, blend_ref.id) or self._matches_blend_ref(existing, blend_ref.file_path):
                blend_ref.id = existing.id
                self.blend_files[idx] = blend_ref
                self.updated_at = datetime.now(timezone.utc)
                return blend_ref

        self.blend_files.append(blend_ref)
        self.updated_at = datetime.now(timezone.utc)
        return blend_ref

    def remove_blend_file(self, blend_file_id_or_path: str) -> bool:
        """ID, dosya adı veya dosya yoluna göre Blend dosyasını kaldırır."""
        original_len = len(self.blend_files)
        self.blend_files = [
            f for f in self.blend_files
            if not self._matches_blend_ref(f, blend_file_id_or_path)
        ]
        if len(self.blend_files) < original_len:
            self.updated_at = datetime.now(timezone.utc)
            return True
        return False

    def get_blend_file(self, blend_file_id_or_path: str) -> BlendFileRef | None:
        """ID, dosya adı veya dosya yoluna göre Blend dosyasını bulur."""
        for f in self.blend_files:
            if self._matches_blend_ref(f, blend_file_id_or_path):
                return f
        return None

