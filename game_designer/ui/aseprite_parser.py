"""Pure-Python Aseprite (.aseprite / .ase) Binary File Parser.

Aseprite dosya biçimi teknik şartnamesine uygun olarak binary başlıkları,
kareleri (frames), renk derinliklerini (32 bpp RGBA, 16 bpp Grayscale+Alpha, 8 bpp İndeksli),
ham veya zlib sıkıştırmalı Cel bloklarını (0x2005) ve Palet bloklarını (0x2019, 0x0004, 0x0011)
ayrıştırır. Her kareyi Pillow (PIL) Image ve milisaniye süresi olarak sunar.
"""

from dataclasses import dataclass, field
import io
import os
from pathlib import Path
import struct
from typing import BinaryIO
import zlib
from PIL import Image

from game_designer.utils.logger import logger

ASE_HEADER_MAGIC = 0xA5E0
ASE_FRAME_MAGIC = 0xF1FA

CHUNK_OLD_PALETTE_4 = 0x0004
CHUNK_OLD_PALETTE_11 = 0x0011
CHUNK_LAYER = 0x2004
CHUNK_CEL = 0x2005
CHUNK_CEL_EXTRA = 0x2006
CHUNK_COLOR_PROFILE = 0x2007
CHUNK_EXTERNAL_FILES = 0x2008
CHUNK_MASK = 0x2016
CHUNK_PATH = 0x2017
CHUNK_TAGS = 0x2018
CHUNK_PALETTE = 0x2019
CHUNK_USER_DATA = 0x2020
CHUNK_SLICE = 0x2022
CHUNK_TILES = 0x2023


@dataclass
class AsepriteFrame:
    """Tek bir Aseprite karesinin görseli ve süresi."""

    index: int
    duration_ms: int
    image: Image.Image


@dataclass
class AsepriteAnimation:
    """Aseprite dosyasının ayrıştırılmış animasyon içeriği."""

    width: int
    height: int
    color_depth: int  # 32, 16 veya 8 bpp
    num_frames: int
    frames: list[Image.Image] = field(default_factory=list)
    durations: list[int] = field(default_factory=list)
    file_path: Path | None = None

    @property
    def total_duration_ms(self) -> int:
        return sum(self.durations)

    def get_frame(self, index: int) -> Image.Image | None:
        if 0 <= index < len(self.frames):
            return self.frames[index]
        return None


class AsepriteParser:
    """Aseprite (.ase / .aseprite) dosya ayrıştırıcısı."""

    def __init__(self, data: bytes, file_path: Path | None = None) -> None:
        self.data = data
        self.file_path = file_path
        self.pos = 0

        self.file_size: int = 0
        self.magic: int = 0
        self.num_frames: int = 0
        self.width: int = 0
        self.height: int = 0
        self.color_depth: int = 32
        self.transparent_index: int = 0
        self.default_speed: int = 100

        # Renk paleti (RGBA tüpleri)
        self.palette: list[tuple[int, int, int, int]] = [(0, 0, 0, 255)] * 256
        # İki boyutlu cel önbelleği (linked cel çözümlemesi için: [frame_idx][layer_idx] -> (x, y, opacity, image))
        self.cels_by_frame_layer: dict[tuple[int, int], tuple[int, int, int, Image.Image]] = {}

    def parse(self) -> AsepriteAnimation:
        """Aseprite ikili verisini ayrıştırarak AsepriteAnimation nesnesi döndürür."""
        if len(self.data) < 128:
            raise ValueError(f"Geçersiz Aseprite dosyası: Dosya boyutu çok küçük ({len(self.data)} bayt)")

        self._read_header()

        frames: list[Image.Image] = []
        durations: list[int] = []

        for frame_idx in range(self.num_frames):
            if self.pos >= len(self.data):
                break
            frame_img, frame_dur = self._read_frame(frame_idx)
            frames.append(frame_img)
            durations.append(frame_dur)

        # Boş frame koruması
        if not frames:
            blank = Image.new("RGBA", (max(1, self.width), max(1, self.height)), (0, 0, 0, 0))
            frames = [blank]
            durations = [self.default_speed or 100]

        return AsepriteAnimation(
            width=self.width,
            height=self.height,
            color_depth=self.color_depth,
            num_frames=len(frames),
            frames=frames,
            durations=durations,
            file_path=self.file_path,
        )

    def _read_header(self) -> None:
        """128 baytlık dosya başlığını okur ve doğrular."""
        (
            self.file_size,
            self.magic,
            self.num_frames,
            self.width,
            self.height,
            self.color_depth,
        ) = struct.unpack_from("<IHHHHH", self.data, 0)

        if self.magic != ASE_HEADER_MAGIC:
            raise ValueError(
                f"Geçersiz Aseprite sihirli sayısı (magic): 0x{self.magic:04X} (Beklenen: 0x{ASE_HEADER_MAGIC:04X})"
            )

        if self.width <= 0 or self.height <= 0:
            raise ValueError(f"Geçersiz Aseprite çözünürlüğü: {self.width}x{self.height}")

        if self.color_depth not in (8, 16, 32):
            raise ValueError(f"Desteklenmeyen Aseprite renk derinliği: {self.color_depth} bpp")

        # Hız (speed) ve şeffaf indeks
        speed = struct.unpack_from("<H", self.data, 18)[0]
        self.default_speed = speed if speed > 0 else 100
        self.transparent_index = self.data[28]

        # Başlangıç paletini şeffaf indeksli olarak hazırla
        for i in range(256):
            if i == self.transparent_index:
                self.palette[i] = (0, 0, 0, 0)
            else:
                self.palette[i] = (i, i, i, 255)

        self.pos = 128

    def _read_frame(self, frame_idx: int) -> tuple[Image.Image, int]:
        """Bir kareyi ve içindeki chunk'ları okur."""
        if self.pos + 16 > len(self.data):
            blank = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
            return blank, self.default_speed

        frame_start = self.pos
        bytes_in_frame, frame_magic, old_chunks, frame_duration, _, new_chunks = struct.unpack_from(
            "<IHHH2sI", self.data, self.pos
        )

        if frame_magic != ASE_FRAME_MAGIC:
            logger.warning(
                f"Kare #{frame_idx} sihirli sayısı geçersiz (0x{frame_magic:04X}). Okumaya devam ediliyor..."
            )

        total_chunks = new_chunks if old_chunks == 0xFFFF else old_chunks

        dur_ms = frame_duration if frame_duration > 0 else self.default_speed
        self.pos += 16

        frame_end = min(len(self.data), frame_start + bytes_in_frame)
        cels_in_frame: list[tuple[int, int, int, int, Image.Image]] = []  # (z_index, layer, x, y, image)

        # Kare içindeki chunk'ları oku
        chunk_count = 0
        while self.pos + 6 <= frame_end and chunk_count < (total_chunks or 9999):
            chunk_size, chunk_type = struct.unpack_from("<IH", self.data, self.pos)
            if chunk_size < 6 or self.pos + chunk_size > len(self.data):
                break

            chunk_body = self.data[self.pos + 6 : self.pos + chunk_size]

            if chunk_type == CHUNK_PALETTE:
                self._parse_palette_chunk(chunk_body)
            elif chunk_type in (CHUNK_OLD_PALETTE_4, CHUNK_OLD_PALETTE_11):
                self._parse_old_palette_chunk(chunk_body, chunk_type)
            elif chunk_type == CHUNK_CEL:
                cel_info = self._parse_cel_chunk(chunk_body, frame_idx)
                if cel_info is not None:
                    cels_in_frame.append(cel_info)

            self.pos += chunk_size
            chunk_count += 1

        self.pos = max(self.pos, frame_end)

        # Cel'leri Z-Index ve Layer sırasına göre sıralayıp kare üzerine birleştir (Composite)
        cels_in_frame.sort(key=lambda item: (item[0], item[1]))

        frame_canvas = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        for _, layer_idx, cx, cy, cel_img in cels_in_frame:
            layer_canvas = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
            layer_canvas.paste(cel_img, (cx, cy))
            frame_canvas = Image.alpha_composite(frame_canvas, layer_canvas)

        return frame_canvas, dur_ms

    def _parse_palette_chunk(self, body: bytes) -> None:
        """Yeni palet bloğunu (0x2019) ayrıştırır."""
        if len(body) < 12:
            return

        new_size, first_idx, last_idx = struct.unpack_from("<III", body, 0)
        offset = 12 + 8  # 12 bayt başlık + 8 bayt reserved

        for idx in range(first_idx, min(last_idx + 1, new_size)):
            if offset + 6 > len(body):
                break
            entry_flags, r, g, b, a = struct.unpack_from("<HBBBB", body, offset)
            offset += 6
            if entry_flags & 1:  # İsim alanı var
                if offset + 2 <= len(body):
                    str_len = struct.unpack_from("<H", body, offset)[0]
                    offset += 2 + str_len

            if idx >= len(self.palette):
                self.palette.extend([(0, 0, 0, 255)] * (idx - len(self.palette) + 1))
            self.palette[idx] = (r, g, b, a)

    def _parse_old_palette_chunk(self, body: bytes, chunk_type: int) -> None:
        """Eski palet bloklarını (0x0004 veya 0x0011) ayrıştırır."""
        if len(body) < 2:
            return

        num_packets = struct.unpack_from("<H", body, 0)[0]
        offset = 2
        skip_accum = 0

        for _ in range(num_packets):
            if offset + 2 > len(body):
                break
            skip = body[offset]
            count = body[offset + 1]
            count = 256 if count == 0 else count
            offset += 2
            skip_accum += skip

            for c in range(count):
                if offset + 3 > len(body):
                    break
                r, g, b = body[offset], body[offset + 1], body[offset + 2]
                offset += 3
                if chunk_type == CHUNK_OLD_PALETTE_4:
                    r = min(255, int(r * 255 / 63))
                    g = min(255, int(g * 255 / 63))
                    b = min(255, int(b * 255 / 63))

                idx = skip_accum + c
                if idx >= len(self.palette):
                    self.palette.extend([(0, 0, 0, 255)] * (idx - len(self.palette) + 1))
                self.palette[idx] = (r, g, b, 255)
            skip_accum += count

    def _parse_cel_chunk(
        self, body: bytes, frame_idx: int
    ) -> tuple[int, int, int, int, Image.Image] | None:
        """Cel bloğunu (0x2005) ayrıştırıp (z_index, layer_idx, x, y, image) döndürür."""
        if len(body) < 9:
            return None

        layer_idx, cel_x, cel_y, opacity, cel_type = struct.unpack_from("<HhhBH", body, 0)
        z_index = 0
        if len(body) >= 11:
            z_index = struct.unpack_from("<h", body, 9)[0]

        # Cel tipine göre piksel okuma
        cel_img: Image.Image | None = None

        if cel_type == 1:
            # Linked Cel: Başka bir karedeki cel'i kullan
            if len(body) >= 18:
                linked_frame = struct.unpack_from("<H", body, 16)[0]
            elif len(body) >= 11:
                linked_frame = struct.unpack_from("<H", body, 9)[0]
            else:
                return None

            if (linked_frame, layer_idx) in self.cels_by_frame_layer:
                lx, ly, lop, limg = self.cels_by_frame_layer[(linked_frame, layer_idx)]
                return (z_index, layer_idx, lx, ly, limg)
            return None

        # Tip 0 (Ham) veya Tip 2 (Sıkıştırılmış)
        # Modern Aseprite: 16 bayt cel başlığı (layer:2, x:2, y:2, op:1, type:2, z:2, res:5 = 16 bayt) + 4 bayt w,h
        # Eski Aseprite: 9 bayt cel başlığı (layer:2, x:2, y:2, op:1, type:2 = 9 bayt) + 4 bayt w,h
        bpp_bytes = 4 if self.color_depth == 32 else (2 if self.color_depth == 16 else 1)

        def is_zlib(offset_idx: int) -> bool:
            if len(body) >= offset_idx + 2:
                b0, b1 = body[offset_idx], body[offset_idx + 1]
                return b0 == 0x78 and (b0 * 256 + b1) % 31 == 0
            return False

        header_offset = 16
        if cel_type == 2:
            if len(body) >= 22 and is_zlib(20):
                header_offset = 16
            elif len(body) >= 15 and is_zlib(13):
                header_offset = 9
            else:
                header_offset = 16 if len(body) >= 20 else 9
        elif cel_type == 0:
            if len(body) >= 20:
                wm, hm = struct.unpack_from("<HH", body, 16)
                if wm > 0 and hm > 0 and (wm * hm * bpp_bytes == len(body) - 20):
                    header_offset = 16
                elif len(body) >= 13:
                    wo, ho = struct.unpack_from("<HH", body, 9)
                    if wo > 0 and ho > 0 and (wo * ho * bpp_bytes == len(body) - 13):
                        header_offset = 9
            elif len(body) >= 13:
                header_offset = 9
        else:
            return None

        if len(body) < header_offset + 4:
            return None

        cel_w, cel_h = struct.unpack_from("<HH", body, header_offset)
        if cel_w <= 0 or cel_h <= 0:
            return None

        raw_stream = body[header_offset + 4 :]

        if cel_type == 2:
            try:
                pixel_data = zlib.decompress(raw_stream)
            except Exception as e:
                logger.warning(f"Aseprite cel ZLIB açma hatası: {e}")
                return None
        elif cel_type == 0:
            pixel_data = raw_stream
        else:
            # Desteklenmeyen veya Tilemap türü
            return None

        # Renk derinliğine göre pikselleri RGBA'ya dönüştür
        cel_img = self._decode_pixels_to_rgba(pixel_data, cel_w, cel_h)
        if cel_img is None:
            return None

        # Opaklık uygula (0-255)
        if opacity < 255:
            r, g, b, a = cel_img.split()
            factor = opacity / 255.0
            a = a.point(lambda p: int(p * factor))
            cel_img.putalpha(a)

        # Linked cels için önbelleğe al
        self.cels_by_frame_layer[(frame_idx, layer_idx)] = (cel_x, cel_y, opacity, cel_img)

        return (z_index, layer_idx, cel_x, cel_y, cel_img)

    def _decode_pixels_to_rgba(self, data: bytes, w: int, h: int) -> Image.Image | None:
        """Ham piksel verilerini RGBA PIL Image nesnesine dönüştürür."""
        total_pixels = w * h
        try:
            if self.color_depth == 32:
                expected_bytes = total_pixels * 4
                if len(data) >= expected_bytes:
                    return Image.frombytes("RGBA", (w, h), data[:expected_bytes])
                return None

            elif self.color_depth == 16:
                # 16 bpp: Grayscale (1 bayt) + Alpha (1 bayt) -> PIL 'LA' modu
                expected_bytes = total_pixels * 2
                if len(data) >= expected_bytes:
                    return Image.frombytes("LA", (w, h), data[:expected_bytes]).convert("RGBA")
                return None

            elif self.color_depth == 8:
                # 8 bpp: İndeksli palet
                if len(data) < total_pixels:
                    return None
                rgba_buf = bytearray(total_pixels * 4)
                pal = self.palette
                pal_len = len(pal)
                t_idx = self.transparent_index

                for i in range(total_pixels):
                    p_idx = data[i]
                    if p_idx == t_idx:
                        continue  # RGBA (0, 0, 0, 0)
                    if p_idx < pal_len:
                        r, g, b, a = pal[p_idx]
                        idx = i * 4
                        rgba_buf[idx] = r
                        rgba_buf[idx + 1] = g
                        rgba_buf[idx + 2] = b
                        rgba_buf[idx + 3] = a
                return Image.frombytes("RGBA", (w, h), bytes(rgba_buf))

        except Exception as e:
            logger.warning(f"Piksel çözme hatası ({w}x{h}, {self.color_depth} bpp): {e}")

        return None


class AsepriteFile:
    """Aseprite dosyasını temsil eden üst seviye sınıf."""

    def __init__(self, source: str | Path | bytes) -> None:
        self.source_path: Path | None = None
        if isinstance(source, (str, Path)):
            self.source_path = Path(source)
            if not self.source_path.is_file():
                raise FileNotFoundError(f"Aseprite dosyası bulunamadı: {self.source_path}")
            data = self.source_path.read_bytes()
        elif isinstance(source, (bytes, bytearray)):
            data = bytes(source)
        else:
            raise TypeError("source str, Path veya bytes olmalıdır.")

        parser = AsepriteParser(data, file_path=self.source_path)
        self.animation = parser.parse()

    @property
    def width(self) -> int:
        return self.animation.width

    @property
    def height(self) -> int:
        return self.animation.height

    @property
    def color_depth(self) -> int:
        return self.animation.color_depth

    @property
    def num_frames(self) -> int:
        return self.animation.num_frames

    @property
    def frames(self) -> list[Image.Image]:
        return self.animation.frames

    @property
    def durations(self) -> list[int]:
        return self.animation.durations


def parse_aseprite_file(source: str | Path | bytes) -> AsepriteAnimation:
    """Aseprite dosya yolunu veya ikili verisini ayrıştırır."""
    ase_file = AsepriteFile(source)
    return ase_file.animation


def create_minimal_aseprite(
    width: int,
    height: int,
    frames_rgba: list[tuple[bytes, int]],  # list of (raw_rgba_bytes, duration_ms)
    color_depth: int = 32,
    palette: list[tuple[int, int, int, int]] | None = None,
    compress: bool = True,
) -> bytes:
    """Birim testler ve sentetik dosya üretimi için geçerli bir Aseprite ikili akışı oluşturur."""
    num_frames = len(frames_rgba)
    frames_binary = bytearray()

    for frame_idx, (raw_pixels, dur_ms) in enumerate(frames_rgba):
        # Cel Chunk oluştur
        cel_type = 2 if compress else 0
        comp_data = zlib.compress(raw_pixels) if compress else raw_pixels

        # 16 bayt Cel başlığı + 4 bayt w,h
        cel_hdr = struct.pack("<HhhBHh5sHH", 0, 0, 0, 255, cel_type, 0, b"\x00" * 5, width, height)
        cel_chunk_size = 6 + len(cel_hdr) + len(comp_data)
        cel_chunk = struct.pack("<IH", cel_chunk_size, CHUNK_CEL) + cel_hdr + comp_data

        chunks_data = cel_chunk
        chunks_count = 1

        # İlk karede palet varsa Palet Chunk (0x2019) ekle
        if frame_idx == 0 and palette:
            pal_entries = bytearray()
            for r, g, b, a in palette:
                pal_entries.extend(struct.pack("<HBBBB", 0, r, g, b, a))
            pal_chunk_size = 6 + 12 + 8 + len(pal_entries)
            pal_hdr = struct.pack("<III8s", len(palette), 0, len(palette) - 1, b"\x00" * 8)
            pal_chunk = struct.pack("<IH", pal_chunk_size, CHUNK_PALETTE) + pal_hdr + bytes(pal_entries)
            chunks_data = pal_chunk + chunks_data
            chunks_count += 1

        # Kare başlığı (16 bayt)
        frame_bytes = 16 + len(chunks_data)
        frame_hdr = struct.pack("<IHHH2sI", frame_bytes, ASE_FRAME_MAGIC, chunks_count, dur_ms, b"\x00" * 2, chunks_count)
        frames_binary.extend(frame_hdr + chunks_data)

    # Dosya başlığı (128 bayt)
    total_size = 128 + len(frames_binary)
    hdr = bytearray(128)
    struct.pack_into("<IH", hdr, 0, total_size, ASE_HEADER_MAGIC)
    struct.pack_into("<H", hdr, 6, num_frames)
    struct.pack_into("<HH", hdr, 8, width, height)
    struct.pack_into("<H", hdr, 12, color_depth)
    struct.pack_into("<I", hdr, 14, 1)  # Bayraklar
    struct.pack_into("<H", hdr, 18, 100)  # Varsayılan hız

    return bytes(hdr) + bytes(frames_binary)
