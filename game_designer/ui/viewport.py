"""Jarvis Game Designer — Etkileşimli 3D & Görsel Önizleme Viewport Modülü.

Blender (.blend), OBJ, FBX, GLTF, GLB, BVH ve diğer 3D/Animasyon varlıklarının
Tkinter Canvas üzerinde gerçek zamanlı döndürülebilir ve yakınlaştırılabilir 3D
önizlemesini, canlı iskelet animasyonlarını (walk/run/idle döngüleri) ve gömülü
Blender / GLTF küçük resimlerinin (embedded thumbnail) çıkarılmasını sağlar.
"""

from collections.abc import Sequence
import io
import json
import math
import os
from pathlib import Path
import struct
import tkinter as tk
from tkinter import ttk
from typing import Any
from PIL import Image, ImageTk

from game_designer.utils.logger import logger


def extract_blend_thumbnail(blend_path: str | Path) -> Image.Image | None:
    """Blender (.blend) dosyasından gömülü küçük resmi (thumbnail) çıkarır.

    Blender, dosya kaydedilirken 'TEST' bloğu içerisine küçük resim yazar.
    Bu fonksiyon TEST bloğunu veya gömülü PNG/JPEG imzasını doğrudan okur.
    """
    path = Path(blend_path)
    if not path.is_file():
        return None

    try:
        with open(path, "rb") as f:
            header = f.read(12)
            if not header.startswith(b"BLENDER"):
                return None

            pointer_size = 4 if header[7:8] == b"_" else 8
            is_little_endian = header[8:9] == b"v"
            endian_char = "<" if is_little_endian else ">"

            file_limit = 16 * 1024 * 1024
            while f.tell() < file_limit:
                block_code = f.read(4)
                if not block_code or len(block_code) < 4:
                    break

                size_bytes = f.read(4)
                if len(size_bytes) < 4:
                    break
                block_size = struct.unpack(f"{endian_char}I", size_bytes)[0]

                skip_bytes = pointer_size + 4 + 4
                f.seek(skip_bytes, os.SEEK_CUR)

                if block_code == b"TEST":
                    test_data = f.read(block_size)
                    if len(test_data) >= 8:
                        w, h = struct.unpack(f"{endian_char}II", test_data[:8])
                        if 16 <= w <= 1024 and 16 <= h <= 1024:
                            raw_pixels = test_data[8:8 + (w * h * 4)]
                            if len(raw_pixels) == w * h * 4:
                                img = Image.frombytes("RGBA", (w, h), raw_pixels)
                                return img.transpose(Image.FLIP_TOP_BOTTOM)

                    png_pos = test_data.find(b"\x89PNG\r\n\x1a\n")
                    if png_pos != -1:
                        try:
                            return Image.open(io.BytesIO(test_data[png_pos:]))
                        except Exception:
                            pass

                    jpg_pos = test_data.find(b"\xff\xd8\xff")
                    if jpg_pos != -1:
                        try:
                            return Image.open(io.BytesIO(test_data[jpg_pos:]))
                        except Exception:
                            pass

                elif block_code == b"ENDB":
                    break
                else:
                    f.seek(block_size, os.SEEK_CUR)

    except Exception as e:
        logger.debug(f"Blender thumbnail ayıklama istisnası ({path.name}): {e}")

    # Fallback: Dosyanın ilk 4 MB'ında PNG veya JPEG arama
    try:
        with open(path, "rb") as f:
            chunk = f.read(4 * 1024 * 1024)
            png_idx = chunk.find(b"\x89PNG\r\n\x1a\n")
            if png_idx != -1:
                return Image.open(io.BytesIO(chunk[png_idx:]))
            jpg_idx = chunk.find(b"\xff\xd8\xff\xe0")
            if jpg_idx != -1:
                return Image.open(io.BytesIO(chunk[jpg_idx:]))
    except Exception:
        pass

    return None


def parse_obj_mesh(file_path: str | Path) -> tuple[list[tuple[float, float, float]], list[list[int]]]:
    """Basit .obj dosyasını ayrıştırarak tepe (vertex) ve yüzey (face) indekslerini döndürür."""
    vertices: list[tuple[float, float, float]] = []
    faces: list[list[int]] = []

    path = Path(file_path)
    if not path.is_file():
        return vertices, faces

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line.startswith("v "):
                    parts = line.split()[1:4]
                    if len(parts) == 3:
                        try:
                            vertices.append((float(parts[0]), float(parts[1]), float(parts[2])))
                        except ValueError:
                            pass
                elif line.startswith("f "):
                    parts = line.split()[1:]
                    face_indices: list[int] = []
                    for p in parts:
                        try:
                            v_idx = int(p.split("/")[0])
                            if v_idx > 0:
                                face_indices.append(v_idx - 1)
                            elif v_idx < 0:
                                face_indices.append(len(vertices) + v_idx)
                        except (ValueError, IndexError):
                            pass
                    if len(face_indices) >= 2:
                        faces.append(face_indices)

        # Modeli merkeze al ve [-1, 1] aralığına normalize et
        if vertices:
            xs = [v[0] for v in vertices]
            ys = [v[1] for v in vertices]
            zs = [v[2] for v in vertices]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            min_z, max_z = min(zs), max(zs)

            cx = (min_x + max_x) / 2.0
            cy = (min_y + max_y) / 2.0
            cz = (min_z + max_z) / 2.0

            max_span = max(max_x - min_x, max_y - min_y, max_z - min_z) or 1.0
            scale = 1.6 / max_span

            normalized = [
                ((v[0] - cx) * scale, (v[1] - cy) * scale, (v[2] - cz) * scale)
                for v in vertices
            ]
            vertices = normalized

    except Exception as e:
        logger.warning(f"OBJ ayrıştırma hatası ({path}): {e}")

    return vertices, faces


def parse_bvh_skeleton(file_path: str | Path) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    """BVH animasyon dosyasından hiyerarşik kemik segmentlerini (bone lines) ayrıştırır."""
    bones: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
    path = Path(file_path)
    if not path.is_file():
        return bones

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            stack: list[tuple[float, float, float]] = [(0.0, 0.0, 0.0)]
            for line in f:
                line = line.strip()
                if "OFFSET" in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        try:
                            dx, dy, dz = float(parts[1]), float(parts[2]), float(parts[3])
                            parent_pos = stack[-1]
                            current_pos = (parent_pos[0] + dx, parent_pos[1] + dy, parent_pos[2] + dz)
                            bones.append((parent_pos, current_pos))
                            stack.append(current_pos)
                        except ValueError:
                            pass
                elif "{" in line:
                    pass
                elif "}" in line:
                    if len(stack) > 1:
                        stack.pop()
                elif "MOTION" in line:
                    break

        if bones:
            all_pts = [p for b in bones for p in b]
            xs = [p[0] for p in all_pts]
            ys = [p[1] for p in all_pts]
            zs = [p[2] for p in all_pts]
            cx = (min(xs) + max(xs)) / 2.0
            cy = (min(ys) + max(ys)) / 2.0
            cz = (min(zs) + max(zs)) / 2.0
            max_span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) or 1.0
            scale = 1.6 / max_span

            norm_bones = []
            for p1, p2 in bones:
                np1 = ((p1[0] - cx) * scale, (p1[1] - cy) * scale, (p1[2] - cz) * scale)
                np2 = ((p2[0] - cx) * scale, (p2[1] - cy) * scale, (p2[2] - cz) * scale)
                norm_bones.append((np1, np2))
            bones = norm_bones

    except Exception as e:
        logger.warning(f"BVH ayrıştırma hatası ({path}): {e}")

    return bones


def parse_glb_or_gltf(file_path: str | Path) -> tuple[list[tuple[float, float, float]], list[list[int]], Image.Image | None]:
    """GLB veya GLTF dosyasından tepe noktaları, yüzeyler veya gömülü görseli ayrıştırır."""
    path = Path(file_path)
    if not path.is_file():
        return [], [], None

    ext = path.suffix.lower()
    try:
        if ext == ".glb":
            with open(path, "rb") as f:
                data = f.read()

            # Gömülü resim ara (PNG / JPEG)
            png_idx = data.find(b"\x89PNG\r\n\x1a\n")
            if png_idx != -1:
                try:
                    img = Image.open(io.BytesIO(data[png_idx:]))
                    return [], [], img
                except Exception:
                    pass

            jpg_idx = data.find(b"\xff\xd8\xff")
            if jpg_idx != -1:
                try:
                    img = Image.open(io.BytesIO(data[jpg_idx:]))
                    return [], [], img
                except Exception:
                    pass

            # GLB Header (magic 0x46546C67 = 'glTF')
            if len(data) > 20 and data[:4] == b"glTF":
                json_len = struct.unpack("<I", data[12:16])[0]
                json_bytes = data[20:20 + json_len]
                gltf_dict = json.loads(json_bytes.decode("utf-8", errors="replace"))

                # Basit vertex çıkarımı
                if "accessors" in gltf_dict and "bufferViews" in gltf_dict:
                    bin_offset = 20 + json_len + 8
                    for acc in gltf_dict.get("accessors", []):
                        if acc.get("type") == "VEC3" and acc.get("componentType") == 5126:  # FLOAT
                            count = acc.get("count", 0)
                            bv_idx = acc.get("bufferView", 0)
                            if bv_idx < len(gltf_dict["bufferViews"]):
                                bv = gltf_dict["bufferViews"][bv_idx]
                                byte_offset = bin_offset + bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
                                if byte_offset + count * 12 <= len(data):
                                    verts = []
                                    for i in range(min(count, 800)):
                                        off = byte_offset + i * 12
                                        vx, vy, vz = struct.unpack("<fff", data[off:off + 12])
                                        verts.append((vx, vy, vz))
                                    if verts:
                                        # Normalize
                                        xs = [v[0] for v in verts]
                                        ys = [v[1] for v in verts]
                                        zs = [v[2] for v in verts]
                                        cx = (min(xs) + max(xs)) / 2.0
                                        cy = (min(ys) + max(ys)) / 2.0
                                        cz = (min(zs) + max(zs)) / 2.0
                                        span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) or 1.0
                                        scale = 1.6 / span
                                        norm_v = [((v[0] - cx) * scale, (v[1] - cy) * scale, (v[2] - cz) * scale) for v in verts]
                                        return norm_v, [], None

        elif ext == ".gltf":
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(50000)
            if "image/" in content:
                # Olası data URI kontrolü
                pass

    except Exception as e:
        logger.debug(f"GLTF/GLB ayrıştırma detayı ({path.name}): {e}")

    return [], [], None


def get_animated_skeleton_bones(anim_type: str = "walk", t: float = 0.0) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    """Zamana (t) ve animasyon türüne göre tam eklemli 3D karakter iskeletini canlandırır."""
    anim_type = anim_type.lower()
    if "run" in anim_type or "kos" in anim_type or "sprint" in anim_type:
        speed = 5.5
        bounce = abs(math.sin(t * speed)) * 0.12
        pitch_tilt = 0.22
        leg_amp = 0.58
        arm_amp = 0.65
    elif "idle" in anim_type or "durus" in anim_type or "bekle" in anim_type:
        speed = 2.0
        bounce = math.sin(t * speed) * 0.03
        pitch_tilt = 0.0
        leg_amp = 0.06
        arm_amp = 0.08
    elif "jump" in anim_type or "zipla" in anim_type or "ucus" in anim_type:
        speed = 3.2
        phase = (t * speed) % (2 * math.pi)
        bounce = max(-0.25, math.sin(phase) * 0.40)
        pitch_tilt = 0.12
        leg_amp = 0.32
        arm_amp = 0.45
    elif "attack" in anim_type or "saldir" in anim_type or "combo" in anim_type or "hit" in anim_type:
        speed = 4.2
        bounce = abs(math.sin(t * speed)) * 0.06
        pitch_tilt = 0.18
        leg_amp = 0.28
        arm_amp = 0.85
    else:  # walk / yürüme varsayılan
        speed = 3.6
        bounce = abs(math.sin(t * speed)) * 0.06
        pitch_tilt = 0.06
        leg_amp = 0.40
        arm_amp = 0.44

    cur_t = t * speed

    # Kalça ve Gövde
    hip_y = -0.05 + bounce
    hip_z = pitch_tilt * 0.2
    hips = (0.0, hip_y, hip_z)
    spine = (0.0, hip_y + 0.35, hip_z + pitch_tilt * 0.1)
    chest = (0.0, hip_y + 0.65, hip_z + pitch_tilt * 0.15)
    neck = (0.0, hip_y + 0.80, hip_z + pitch_tilt * 0.2)
    head = (0.0, hip_y + 1.02, hip_z + pitch_tilt * 0.22)

    # Bacaklar (180 derece ters faz)
    leg_l_angle = math.sin(cur_t) * leg_amp
    leg_r_angle = math.sin(cur_t + math.pi) * leg_amp

    hip_l = (-0.18, hip_y, hip_z)
    hip_r = (0.18, hip_y, hip_z)

    knee_l_y = hip_y - 0.42 + max(0.0, -leg_l_angle) * 0.12
    knee_l_z = hip_z + leg_l_angle * 0.45
    knee_l = (-0.18, knee_l_y, knee_l_z)
    foot_l_y = knee_l_y - 0.42 + max(0.0, leg_l_angle) * 0.08
    foot_l_z = knee_l_z + leg_l_angle * 0.4
    foot_l = (-0.18, foot_l_y, foot_l_z)
    toe_l = (-0.18, foot_l_y, foot_l_z + 0.12)

    knee_r_y = hip_y - 0.42 + max(0.0, -leg_r_angle) * 0.12
    knee_r_z = hip_z + leg_r_angle * 0.45
    knee_r = (0.18, knee_r_y, knee_r_z)
    foot_r_y = knee_r_y - 0.42 + max(0.0, leg_r_angle) * 0.08
    foot_r_z = knee_r_z + leg_r_angle * 0.4
    foot_r = (0.18, foot_r_y, foot_r_z)
    toe_r = (0.18, foot_r_y, foot_r_z + 0.12)

    # Kollar
    arm_l_angle = math.sin(cur_t + math.pi) * arm_amp
    arm_r_angle = math.sin(cur_t) * arm_amp

    shldr_l = (-0.32, hip_y + 0.62, hip_z)
    shldr_r = (0.32, hip_y + 0.62, hip_z)

    elbow_l = (-0.36, hip_y + 0.35, hip_z + arm_l_angle * 0.35)
    hand_l = (-0.36, hip_y + 0.10, hip_z + arm_l_angle * 0.60)

    elbow_r = (0.36, hip_y + 0.35, hip_z + arm_r_angle * 0.35)
    hand_r = (0.36, hip_y + 0.10, hip_z + arm_r_angle * 0.60)

    bones = [
        (hips, spine),
        (spine, chest),
        (chest, neck),
        (neck, head),
        (chest, shldr_l),
        (chest, shldr_r),
        (shldr_l, elbow_l),
        (elbow_l, hand_l),
        (shldr_r, elbow_r),
        (elbow_r, hand_r),
        (hips, hip_l),
        (hips, hip_r),
        (hip_l, knee_l),
        (knee_l, foot_l),
        (foot_l, toe_l),
        (hip_r, knee_r),
        (knee_r, foot_r),
        (foot_r, toe_r),
    ]
    return bones


def generate_default_3d_mesh(style: str = "cube") -> tuple[list[tuple[float, float, float]], list[list[int]]]:
    """Varsayılan 3D stüdyo geometrisi üretir."""
    if style == "gem":
        vertices = [
            (0.0, 1.0, 0.0),    # Tepe
            (0.8, 0.0, 0.0),    # Sağ
            (0.0, 0.0, 0.8),    # Ön
            (-0.8, 0.0, 0.0),   # Sol
            (0.0, 0.0, -0.8),   # Arka
            (0.0, -1.0, 0.0),   # Taban
        ]
        faces = [
            [0, 1, 2], [0, 2, 3], [0, 3, 4], [0, 4, 1],
            [5, 2, 1], [5, 3, 2], [5, 4, 3], [5, 1, 4],
        ]
        return vertices, faces

    # Varsayılan şık eğik küp
    s = 0.7
    vertices = [
        (-s, -s, -s), (s, -s, -s), (s, s, -s), (-s, s, -s),
        (-s, -s, s), (s, -s, s), (s, s, s), (-s, s, s),
    ]
    faces = [
        [0, 1, 2, 3],  # Ön
        [5, 4, 7, 6],  # Arka
        [4, 0, 3, 7],  # Sol
        [1, 5, 6, 2],  # Sağ
        [3, 2, 6, 7],  # Üst
        [4, 5, 1, 0],  # Alt
    ]
    return vertices, faces


def generate_category_mesh(category: str) -> tuple[list[tuple[float, float, float]], list[list[int]]]:
    """Kategoriye özgü yüksek kaliteli fütüristik 3D geometri üretir."""
    cat = (category or "").strip()

    if cat == "Karakter":
        # 3D Karakter / Mankeni (Kafa, Göğüs, Kol ve Bacak blokları)
        vertices = [
            # Kafa
            (-0.25, 0.9, -0.2), (0.25, 0.9, -0.2), (0.25, 1.3, -0.2), (-0.25, 1.3, -0.2),
            (-0.25, 0.9, 0.2), (0.25, 0.9, 0.2), (0.25, 1.3, 0.2), (-0.25, 1.3, 0.2),
            # Gövde / Zırh
            (-0.45, 0.1, -0.25), (0.45, 0.1, -0.25), (0.50, 0.85, -0.25), (-0.50, 0.85, -0.25),
            (-0.45, 0.1, 0.25), (0.45, 0.1, 0.25), (0.50, 0.85, 0.25), (-0.50, 0.85, 0.25),
            # Bacaklar
            (-0.4, -0.9, -0.2), (-0.1, -0.9, -0.2), (-0.1, 0.05, -0.2), (-0.4, 0.05, -0.2),
            (0.1, -0.9, -0.2), (0.4, -0.9, -0.2), (0.4, 0.05, -0.2), (0.1, 0.05, -0.2),
        ]
        faces = [
            # Kafa yüzeyleri
            [0, 1, 2, 3], [5, 4, 7, 6], [4, 0, 3, 7], [1, 5, 6, 2], [3, 2, 6, 7],
            # Gövde yüzeyleri
            [8, 9, 10, 11], [13, 12, 15, 14], [12, 8, 11, 15], [9, 13, 14, 10], [11, 10, 14, 15],
            # Sol & Sağ Bacak
            [16, 17, 18, 19], [20, 21, 22, 23],
        ]
        return vertices, faces

    elif cat == "Prop":
        # 3D Kılıç / Silah Geometrisi
        vertices = [
            # Bıçak ucu ve gövdesi
            (0.0, 1.4, 0.0),    # 0: Sivri uç
            (-0.15, 0.2, -0.04), # 1: Sol bıçak
            (0.15, 0.2, -0.04),  # 2: Sağ bıçak
            (0.0, 0.2, 0.06),    # 3: Bıçak orta sırtı
            (-0.15, 0.2, 0.04),  # 4
            (0.15, 0.2, 0.04),   # 5
            # Balçak / Guard
            (-0.55, 0.15, -0.1), (0.55, 0.15, -0.1), (0.55, 0.25, 0.1), (-0.55, 0.25, 0.1),
            # Kabza (Hilt) & Topuz (Pommel)
            (-0.08, -0.6, -0.06), (0.08, -0.6, -0.06), (0.08, 0.15, -0.06), (-0.08, 0.15, -0.06),
            (0.0, -0.85, 0.0),   # 14: Topuz
        ]
        faces = [
            # Bıçak yüzeyleri
            [0, 1, 3], [0, 3, 2], [0, 4, 1], [0, 2, 5],
            # Balçak
            [6, 7, 8, 9],
            # Kabza
            [10, 11, 12, 13],
            # Topuz
            [10, 11, 14],
        ]
        return vertices, faces

    elif cat == "Çevre/Level":
        # Basamaklı 3D Zemin / Zindan Platformu
        vertices = [
            # Alt ana platform
            (-1.2, -0.5, -1.2), (1.2, -0.5, -1.2), (1.2, -0.2, -1.2), (-1.2, -0.2, -1.2),
            (-1.2, -0.5, 1.2), (1.2, -0.5, 1.2), (1.2, -0.2, 1.2), (-1.2, -0.2, 1.2),
            # Üst yükselti / Yapı
            (-0.6, -0.2, -0.6), (0.6, -0.2, -0.6), (0.6, 0.4, -0.6), (-0.6, 0.4, -0.6),
            (-0.6, -0.2, 0.6), (0.6, -0.2, 0.6), (0.6, 0.4, 0.6), (-0.6, 0.4, 0.6),
            # Tepe Sütun / Monolit
            (-0.2, 0.4, -0.2), (0.2, 0.4, -0.2), (0.2, 1.1, -0.2), (-0.2, 1.1, -0.2),
            (-0.2, 0.4, 0.2), (0.2, 0.4, 0.2), (0.2, 1.1, 0.2), (-0.2, 1.1, 0.2),
        ]
        faces = [
            # Alt platform
            [0, 1, 2, 3], [5, 4, 7, 6], [4, 0, 3, 7], [1, 5, 6, 2], [3, 2, 6, 7],
            # Üst yükselti
            [8, 9, 10, 11], [13, 12, 15, 14], [12, 8, 11, 15], [9, 13, 14, 10], [11, 10, 14, 15],
            # Sütun
            [16, 17, 18, 19], [21, 20, 23, 22], [19, 18, 22, 23],
        ]
        return vertices, faces

    elif cat == "Araç":
        # Fütüristik Speeder / Araç Geometrisi
        vertices = [
            # Gövde burnu ve kokpit
            (0.0, 0.1, 1.2),    # Burun
            (-0.6, 0.0, -0.9),  # Sol arka
            (0.6, 0.0, -0.9),   # Sağ arka
            (0.0, 0.45, -0.2),  # Kokpit tepesi
            (-0.8, 0.15, -0.5), # Sol kanat
            (0.8, 0.15, -0.5),  # Sağ kanat
            (0.0, -0.2, -0.8),  # Taban arka
        ]
        faces = [
            [0, 4, 3], [0, 3, 5], [3, 4, 1], [3, 2, 5],
            [1, 6, 2, 3], [0, 1, 6], [0, 6, 2],
        ]
        return vertices, faces

    # Varsayılan: Kristal / Gem
    return generate_default_3d_mesh("gem")


class Viewport3DCanvas(tk.Frame):
    """Etkileşimli 3D & Görsel Önizleme Viewport Bileşeni."""

    def __init__(self, parent: tk.Widget, bg: str = "#0f172a", **kwargs: Any) -> None:
        super().__init__(parent, bg=bg, **kwargs)

        self.canvas_bg = bg
        self.canvas = tk.Canvas(self, bg=self.canvas_bg, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 3D Kamera Durumu
        self.yaw = 35.0
        self.pitch = -22.0
        self.zoom = 120.0
        self.pan_x = 0.0
        self.pan_y = 0.0

        # Fare Takip
        self._last_mouse_x = 0
        self._last_mouse_y = 0
        self._is_dragging = False

        # Aktif Varlık Bilgileri
        self.current_file_path: Path | None = None
        self.current_format: str = ""
        self.current_category: str = "Genel"
        self.current_thumbnail_img: Image.Image | None = None
        self.current_tk_img: ImageTk.PhotoImage | None = None
        self.display_mode: str = "3d"  # '3d' veya 'image'

        # Geometri ve İskelet
        self.mesh_vertices: list[tuple[float, float, float]] = []
        self.mesh_faces: list[list[int]] = []
        self.bvh_bones: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []

        # Canlı Animasyon & Otomatik Döndürme Döngüsü
        self.is_animating: bool = True
        self.auto_spin: bool = False
        self.anim_time: float = 0.0
        self.anim_subtype: str = "walk"
        self._anim_timer_id: str | None = None

        self._bind_events()
        self._load_fallback_scene()
        self._start_animation_loop()

    def _bind_events(self) -> None:
        """Fare ve yeniden boyutlandırma olaylarını bağlar."""
        self.canvas.bind("<Configure>", lambda e: self.render())
        self.canvas.bind("<Button-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)

        # Fare Tekerleği ile Zoom
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Button-4>", lambda e: self._zoom(1.15))
        self.canvas.bind("<Button-5>", lambda e: self._zoom(0.85))

        # Sağ Tık ile Pan
        self.canvas.bind("<Button-3>", self._on_mouse_down)
        self.canvas.bind("<B3-Motion>", self._on_pan_drag)

    def _start_animation_loop(self) -> None:
        """Saniyede ~30 kare canlı iskelet hareketi ve yumuşak sahne döngüsü."""
        self._anim_tick()

    def _anim_tick(self) -> None:
        """Animasyon adımı."""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        needs_render = False

        # Canlı iskelet animasyonu
        is_anim_asset = (self.current_category == "Animasyon" or self.current_format == ".bvh" or bool(self.bvh_bones))
        if self.is_animating and is_anim_asset and self.display_mode == "3d":
            self.anim_time += 0.04
            self.bvh_bones = get_animated_skeleton_bones(self.anim_subtype, self.anim_time)
            needs_render = True

        # Otomatik Döndürme (Turntable auto-spin)
        if self.auto_spin and self.display_mode == "3d":
            self.yaw = (self.yaw + 1.2) % 360
            needs_render = True

        if needs_render:
            self.render()

        try:
            self._anim_timer_id = self.after(33, self._anim_tick)
        except Exception:
            self._anim_timer_id = None

    def destroy(self) -> None:
        """Bileşen yok edilirken arka plan animasyon zamanlayıcısını iptal eder."""
        if self._anim_timer_id is not None:
            try:
                self.after_cancel(self._anim_timer_id)
            except Exception:
                pass
            self._anim_timer_id = None
        super().destroy()

    def toggle_animation(self) -> bool:
        """Animasyon oynatma / duraklatmayı değiştirir."""
        self.is_animating = not self.is_animating
        self.render()
        return self.is_animating

    def toggle_auto_spin(self) -> bool:
        """Otomatik 3D stüdyo döndürmesini açar/kapatır."""
        self.auto_spin = not self.auto_spin
        self.render()
        return self.auto_spin

    def _on_mouse_down(self, event: tk.Event) -> None:
        self._last_mouse_x = event.x
        self._last_mouse_y = event.y
        self._is_dragging = True

    def _on_mouse_up(self, event: tk.Event) -> None:
        self._is_dragging = False

    def _on_mouse_drag(self, event: tk.Event) -> None:
        if not self._is_dragging:
            return
        dx = event.x - self._last_mouse_x
        dy = event.y - self._last_mouse_y
        self._last_mouse_x = event.x
        self._last_mouse_y = event.y

        if self.display_mode == "image":
            self.display_mode = "3d"

        self.yaw = (self.yaw + dx * 0.7) % 360
        self.pitch = max(-89.0, min(89.0, self.pitch + dy * 0.7))
        self.render()

    def _on_pan_drag(self, event: tk.Event) -> None:
        dx = event.x - self._last_mouse_x
        dy = event.y - self._last_mouse_y
        self._last_mouse_x = event.x
        self._last_mouse_y = event.y
        self.pan_x += dx
        self.pan_y += dy
        self.render()

    def _on_mouse_wheel(self, event: tk.Event) -> None:
        if event.delta > 0:
            self._zoom(1.15)
        else:
            self._zoom(0.85)

    def _zoom(self, factor: float) -> None:
        self.zoom = max(20.0, min(600.0, self.zoom * factor))
        self.render()

    def reset_camera(self) -> None:
        """Kamera açısını ve yakınlaştırmayı varsayılana sıfırlar."""
        self.yaw = 35.0
        self.pitch = -22.0
        self.zoom = 120.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.render()

    def toggle_mode(self) -> None:
        """Görsel küçük resim ve 3D görünüm modları arasında geçiş yapar."""
        if self.current_thumbnail_img:
            self.display_mode = "3d" if self.display_mode == "image" else "image"
            self.render()

    def set_asset(self, file_path_str: str, category: str = "") -> None:
        """Viewport'ta görüntülenecek 3D veya animasyon dosyasını ayarlar."""
        path = Path(file_path_str)
        self.current_file_path = path
        ext = path.suffix.lower()
        self.current_format = ext
        stem_lower = path.stem.lower()

        # Alt animasyon türünü belirle (walk, run, jump, idle, attack)
        if any(k in stem_lower for k in ["run", "kos", "sprint"]):
            self.anim_subtype = "run"
        elif any(k in stem_lower for k in ["idle", "durus", "bekle"]):
            self.anim_subtype = "idle"
        elif any(k in stem_lower for k in ["jump", "zipla", "ucus"]):
            self.anim_subtype = "jump"
        elif any(k in stem_lower for k in ["attack", "saldir", "hit", "combo"]):
            self.anim_subtype = "attack"
        else:
            self.anim_subtype = "walk"

        # Kategori tespiti
        from game_designer.models.project import detect_asset_category
        resolved_category = category or detect_asset_category(str(path))
        self.current_category = resolved_category

        self.current_thumbnail_img = None
        self.mesh_vertices = []
        self.mesh_faces = []
        self.bvh_bones = []

        if ext == ".blend":
            thumb = extract_blend_thumbnail(path)
            if thumb:
                self.current_thumbnail_img = thumb
                self.display_mode = "image"
            else:
                self.display_mode = "3d"

            if resolved_category == "Animasyon":
                self.bvh_bones = get_animated_skeleton_bones(self.anim_subtype, self.anim_time)
            else:
                self.mesh_vertices, self.mesh_faces = generate_category_mesh(resolved_category)

        elif ext == ".obj":
            v, f = parse_obj_mesh(path)
            if v and f:
                self.mesh_vertices = v
                self.mesh_faces = f
            elif resolved_category == "Animasyon":
                self.bvh_bones = get_animated_skeleton_bones(self.anim_subtype, self.anim_time)
            else:
                self.mesh_vertices, self.mesh_faces = generate_category_mesh(resolved_category)
            self.display_mode = "3d"

        elif ext == ".bvh":
            bones = parse_bvh_skeleton(path)
            if bones:
                self.bvh_bones = bones
            else:
                self.bvh_bones = get_animated_skeleton_bones(self.anim_subtype, self.anim_time)
            self.display_mode = "3d"

        elif ext in [".glb", ".gltf"]:
            v, f, img = parse_glb_or_gltf(path)
            if img:
                self.current_thumbnail_img = img
                self.display_mode = "image"
            elif v:
                self.mesh_vertices = v
                self.mesh_faces = f
                self.display_mode = "3d"
            elif resolved_category == "Animasyon":
                self.bvh_bones = get_animated_skeleton_bones(self.anim_subtype, self.anim_time)
                self.display_mode = "3d"
            else:
                self.mesh_vertices, self.mesh_faces = generate_category_mesh(resolved_category)
                self.display_mode = "3d"

        else:
            # .fbx, .dae vb.
            if resolved_category == "Animasyon":
                self.bvh_bones = get_animated_skeleton_bones(self.anim_subtype, self.anim_time)
            else:
                self.mesh_vertices, self.mesh_faces = generate_category_mesh(resolved_category)
            self.display_mode = "3d"

        self.render()

    def _load_fallback_scene(self) -> None:
        """İlk açılışta gösterilecek şık stüdyo sahnesi."""
        self.mesh_vertices, self.mesh_faces = generate_default_3d_mesh("gem")
        self.display_mode = "3d"
        self.render()

    def render(self) -> None:
        """Viewport ekranını günceller ve çizer."""
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10 or h < 10:
            return

        cx = w / 2.0 + self.pan_x
        cy = h / 2.0 + self.pan_y

        # 1. Resim modu
        if self.display_mode == "image" and self.current_thumbnail_img:
            img = self.current_thumbnail_img.copy()
            img.thumbnail((max(50, w - 24), max(50, h - 24)), Image.Resampling.LANCZOS)
            self.current_tk_img = ImageTk.PhotoImage(img)
            self.canvas.create_image(cx, cy, image=self.current_tk_img, anchor=tk.CENTER)
            self._draw_hud(w, h, is_thumbnail=True)
            return

        # 2. 3D Izgara (Studio Ground Grid)
        self._draw_3d_grid(cx, cy)

        # 3. 3D Dönüşüm ve Projeksiyon
        rad_yaw = math.radians(self.yaw)
        rad_pitch = math.radians(self.pitch)
        cos_y, sin_y = math.cos(rad_yaw), math.sin(rad_yaw)
        cos_p, sin_p = math.cos(rad_pitch), math.sin(rad_pitch)

        def project(x: float, y: float, z: float) -> tuple[float, float, float]:
            x1 = x * cos_y + z * sin_y
            y1 = y
            z1 = -x * sin_y + z * cos_y

            x2 = x1
            y2 = y1 * cos_p - z1 * sin_p
            z2 = y1 * sin_p + z1 * cos_p

            persp = 1.0 / (1.0 + z2 * 0.15) if (1.0 + z2 * 0.15) > 0.05 else 1.0
            sx = cx + x2 * self.zoom * persp
            sy = cy - y2 * self.zoom * persp
            return sx, sy, z2

        # 4. İskelet / Canlı Animasyon Çizimi
        if self.bvh_bones:
            for p1, p2 in self.bvh_bones:
                s1 = project(*p1)
                s2 = project(*p2)
                # Kemik hattı (Neon Cyan)
                self.canvas.create_line(s1[0], s1[1], s2[0], s2[1], fill="#06b6d4", width=3, capstyle=tk.ROUND)
                # Eklem düğümü (Electric Lilac / Pearl)
                self.canvas.create_oval(s1[0] - 4, s1[1] - 4, s1[0] + 4, s1[1] + 4, fill="#f8fafc", outline="#8b5cf6", width=1.5)
                self.canvas.create_oval(s2[0] - 4, s2[1] - 4, s2[0] + 4, s2[1] + 4, fill="#f8fafc", outline="#8b5cf6", width=1.5)

        # 5. 3D Mesh / Poligon Çizimi (Painter's Algorithm)
        elif self.mesh_vertices and self.mesh_faces:
            projected_v = [project(*v) for v in self.mesh_vertices]

            faces_with_depth = []
            for face in self.mesh_faces:
                if len(face) < 2:
                    continue
                avg_z = sum(projected_v[idx][2] for idx in face) / len(face)
                faces_with_depth.append((avg_z, face))

            faces_with_depth.sort(key=lambda item: item[0])
            color_cycle = ["#1e293b", "#0f766e", "#1e3a8a", "#4338ca", "#0369a1", "#0284c7"]

            for i, (_, face) in enumerate(faces_with_depth):
                poly_pts = []
                for idx in face:
                    sx, sy, _ = projected_v[idx]
                    poly_pts.extend([sx, sy])

                fill_col = color_cycle[i % len(color_cycle)]
                if len(poly_pts) >= 6:
                    self.canvas.create_polygon(
                        poly_pts,
                        fill=fill_col,
                        outline="#38bdf8",
                        width=1.5,
                        joinstyle=tk.ROUND,
                    )
                elif len(poly_pts) == 4:
                    self.canvas.create_line(poly_pts, fill="#06b6d4", width=2)

            for sx, sy, _ in projected_v:
                self.canvas.create_oval(sx - 2, sy - 2, sx + 2, sy + 2, fill="#38bdf8", outline="")

        # 6. Eksen Gizmo'su (Sol Alt: X Kırmızı, Y Yeşil, Z Mavi)
        self._draw_gizmo(w, h, rad_yaw, rad_pitch)

        # 7. HUD & Canlı Kontrol Katmanı
        self._draw_hud(w, h, is_thumbnail=False)

    def _draw_3d_grid(self, cx: float, cy: float) -> None:
        """Zemin 3D referans ızgarasını çizer."""
        grid_size = 4
        step = 0.5
        y_floor = -0.9

        rad_yaw = math.radians(self.yaw)
        rad_pitch = math.radians(self.pitch)
        cos_y, sin_y = math.cos(rad_yaw), math.sin(rad_yaw)
        cos_p, sin_p = math.cos(rad_pitch), math.sin(rad_pitch)

        def proj_floor(x: float, z: float) -> tuple[float, float]:
            x1 = x * cos_y + z * sin_y
            z1 = -x * sin_y + z * cos_y
            x2 = x1
            y2 = y_floor * cos_p - z1 * sin_p
            z2 = y_floor * sin_p + z1 * cos_p
            persp = 1.0 / (1.0 + z2 * 0.15) if (1.0 + z2 * 0.15) > 0.05 else 1.0
            return cx + x2 * self.zoom * persp, cy - y2 * self.zoom * persp

        for i in range(-grid_size, grid_size + 1):
            val = i * step
            p1 = proj_floor(val, -grid_size * step)
            p2 = proj_floor(val, grid_size * step)
            color = "#1e293b" if i != 0 else "#38bdf8"
            self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill=color, width=1.5 if i == 0 else 1)

            p3 = proj_floor(-grid_size * step, val)
            p4 = proj_floor(grid_size * step, val)
            self.canvas.create_line(p3[0], p3[1], p4[0], p4[1], fill=color, width=1.5 if i == 0 else 1)

    def _draw_gizmo(self, w: int, h: int, rad_yaw: float, rad_pitch: float) -> None:
        """Köşe koordinat göstergesini (Gizmo) çizer."""
        gx, gy = 36, h - 36
        g_len = 22.0

        cos_y, sin_y = math.cos(rad_yaw), math.sin(rad_yaw)
        cos_p, sin_p = math.cos(rad_pitch), math.sin(rad_pitch)

        def g_proj(x: float, y: float, z: float) -> tuple[float, float]:
            x1 = x * cos_y + z * sin_y
            z1 = -x * sin_y + z * cos_y
            x2 = x1
            y2 = y * cos_p - z1 * sin_p
            return gx + x2 * g_len, gy - y2 * g_len

        px = g_proj(1.0, 0.0, 0.0)
        py = g_proj(0.0, 1.0, 0.0)
        pz = g_proj(0.0, 0.0, 1.0)

        self.canvas.create_line(gx, gy, px[0], px[1], fill="#ef4444", width=2)
        self.canvas.create_text(px[0] + 5, px[1], text="X", fill="#ef4444", font=("Segoe UI", 7, "bold"))

        self.canvas.create_line(gx, gy, py[0], py[1], fill="#10b981", width=2)
        self.canvas.create_text(py[0], py[1] - 5, text="Y", fill="#10b981", font=("Segoe UI", 7, "bold"))

        self.canvas.create_line(gx, gy, pz[0], pz[1], fill="#3b82f6", width=2)
        self.canvas.create_text(pz[0] - 5, pz[1], text="Z", fill="#3b82f6", font=("Segoe UI", 7, "bold"))

    def _draw_hud(self, w: int, h: int, is_thumbnail: bool = False) -> None:
        """Viewport üstündeki bilgi yazıları ve canlı durumu çizer."""
        fname = self.current_file_path.name if self.current_file_path else "Sahne Hazır (Varsayılan 3D)"
        fmt = self.current_format.upper().lstrip(".") or "3D"
        cat = self.current_category or "Varlık"

        # Üst Başlık Rozeti
        badge_text = f"🔷 [{cat}] {fname} ({fmt})"
        self.canvas.create_text(
            12, 12,
            text=badge_text,
            fill="#06b6d4",
            font=("Segoe UI", 9, "bold"),
            anchor=tk.NW,
        )

        # Durum ve İpuçları
        if is_thumbnail:
            tip_text = "📷 Blender/Gömülü Görsel Önizleme (3D görünüme geçmek için tıklayıp sürükleyin)"
        elif self.bvh_bones:
            status_symbol = "▶️ CANLI ANİMASYON" if self.is_animating else "⏸️ DURAKLATILDI"
            tip_text = f"🏃 {status_symbol} ({self.anim_subtype.upper()}) | Sol Tık: Çevir • Tekerlek: Zoom • Sağ Tık: Pan"
        else:
            spin_txt = " | 🔄 Turntable Açık" if self.auto_spin else ""
            tip_text = f"📐 3D Model Önizleme{spin_txt} | Sol Tık: Çevir • Tekerlek: Zoom • Sağ Tık: Pan"

        self.canvas.create_text(
            12, 32,
            text=tip_text,
            fill="#94a3b8",
            font=("Segoe UI", 8),
            anchor=tk.NW,
        )

        # Sağ üst köşe istatistiği
        if not is_thumbnail:
            if self.bvh_bones:
                stat_text = f"Kemikler: {len(self.bvh_bones)} | FPS: ~30"
            elif self.mesh_vertices:
                stat_text = f"Verts: {len(self.mesh_vertices)} | Polys: {len(self.mesh_faces)}"
            else:
                stat_text = "3D Sahne Aktif"

            self.canvas.create_text(
                w - 12, 12,
                text=stat_text,
                fill="#64748b",
                font=("Segoe UI", 8, "bold"),
                anchor=tk.NE,
            )
