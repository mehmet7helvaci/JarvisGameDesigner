"""Jarvis Game Designer — Özel Fütüristik 3D Studio İkonu Üretici."""

import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter


def create_studio_icon(output_dir: Path | None = None) -> tuple[Path, Path]:
    """Fütüristik 3D oyun tasarım stüdyosu ikonu üretir (.ico ve .png)."""
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent.parent / "assets"
    output_dir.mkdir(parents=True, exist_ok=True)

    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Dış Yuvarlak Köşeli Çerçeve (Koyu Stüdyo Arka Planı)
    margin = 24
    bg_box = [margin, margin, size - margin, size - margin]
    draw.rounded_rectangle(bg_box, radius=80, fill=(15, 23, 42, 255), outline=(30, 41, 59, 255), width=4)

    # 2. Arka Plan İnce Izgara (Grid) Çizgileri - Unreal/Blender Hissi
    for i in range(80, size - 80, 44):
        draw.line([(80, i), (size - 80, i)], fill=(30, 41, 59, 120), width=1)
        draw.line([(i, 80), (i, size - 80)], fill=(30, 41, 59, 120), width=1)

    # 3. İzometrik 3D Küp / Kristal (Oyun Motoru & 3D Varlık Sembolü)
    cx, cy = size // 2, size // 2 - 10
    radius = 140

    def get_iso_point(angle_deg: float, r: float) -> tuple[float, float]:
        rad = math.radians(angle_deg)
        return (cx + r * math.cos(rad), cy + r * math.sin(rad))

    # Köşe noktaları (60'ar derece)
    p_top = get_iso_point(270, radius)          # (cx, cy - radius)
    p_top_right = get_iso_point(330, radius)    # Sağ üst
    p_bot_right = get_iso_point(30, radius)     # Sağ alt
    p_bot = get_iso_point(90, radius)           # En alt
    p_bot_left = get_iso_point(150, radius)     # Sol alt
    p_top_left = get_iso_point(210, radius)     # Sol üst
    p_center = (cx, cy)

    # Dış Işıma (Glow)
    glow_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_img)
    glow_draw.polygon([p_top, p_top_right, p_bot_right, p_bot, p_bot_left, p_top_left], fill=(6, 182, 212, 60))
    glow_img = glow_img.filter(ImageFilter.GaussianBlur(radius=20))
    img = Image.alpha_composite(img, glow_img)
    draw = ImageDraw.Draw(img)

    # 3D Yüzey 1: ÜST YÜZEY (Top Facet - Neon Cyan Gradient / Cyan Açık Mavi)
    draw.polygon([p_center, p_top_left, p_top, p_top_right], fill=(6, 182, 212, 240), outline=(56, 189, 248, 255), width=3)

    # 3D Yüzey 2: SOL YÜZEY (Left Facet - Koyu Royal Mavi)
    draw.polygon([p_center, p_bot_left, p_bot, (cx, cy)], fill=(29, 78, 216, 240), outline=(59, 130, 246, 255), width=3)

    # 3D Yüzey 3: SAĞ YÜZEY (Right Facet - Fütüristik Neon Mor)
    draw.polygon([p_center, p_bot_right, p_bot, (cx, cy)], fill=(139, 92, 246, 240), outline=(168, 85, 247, 255), width=3)

    # İç Tel Kafes & Eksen Çizgileri (Wireframe Gizmo)
    draw.line([p_center, p_top], fill=(255, 255, 255, 200), width=3)
    draw.line([p_center, p_bot_left], fill=(255, 255, 255, 160), width=3)
    draw.line([p_center, p_bot_right], fill=(255, 255, 255, 160), width=3)

    # Köşe Vertex Düğümleri (Noktalar)
    for pt in [p_top, p_top_right, p_bot_right, p_bot, p_bot_left, p_top_left, p_center]:
        px, py = int(pt[0]), int(pt[1])
        draw.ellipse([px - 5, py - 5, px + 5, py + 5], fill=(255, 255, 255, 255), outline=(6, 182, 212, 255), width=2)

    # 4. Merkezde "J" ve Oyun Kontrolcüsü / Crosshair Vurgusu
    # Modern ve şık geometrik Jarvis "J" harfi veya oyun d-pad'i
    j_color = (255, 255, 255, 250)
    # Üst bar
    draw.line([(cx - 30, cy + 180), (cx + 30, cy + 180)], fill=(6, 182, 212, 200), width=4)

    # Alt rozet: "JARVIS STUDIO" küçük yazı veya stilize rozet
    draw.rounded_rectangle([cx - 85, size - margin - 52, cx + 85, size - margin - 22], radius=8, fill=(30, 41, 59, 230), outline=(6, 182, 212, 180), width=2)
    # 3 adet minik durum LED'i (Yeşil, Cyan, Mor)
    draw.ellipse([cx - 50, size - margin - 40, cx - 42, size - margin - 32], fill=(16, 185, 129, 255))
    draw.ellipse([cx - 4, size - margin - 40, cx + 4, size - margin - 32], fill=(6, 182, 212, 255))
    draw.ellipse([cx + 42, size - margin - 40, cx + 50, size - margin - 32], fill=(139, 92, 246, 255))

    # Dosyaları kaydet
    png_path = output_dir / "icon.png"
    ico_path = output_dir / "icon.ico"

    # PNG olarak kaydet (256x256 pürüzsüz boyutlandırılmış)
    resized_png = img.resize((256, 256), Image.Resampling.LANCZOS)
    resized_png.save(png_path, format="PNG")

    # Windows çoklu çözünürlüklü ICO olarak kaydet (16, 24, 32, 48, 64, 128, 256)
    ico_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)]
    img.save(ico_path, format="ICO", sizes=ico_sizes)

    return ico_path, png_path


if __name__ == "__main__":
    ico, png = create_studio_icon()
    print(f"Ikonlar olusturuldu:\nICO: {ico}\nPNG: {png}")
