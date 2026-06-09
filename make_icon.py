"""Генератор иконки EGTS Tracker для Android."""

from PIL import Image, ImageDraw, ImageFont
import math, os

# ─── Цвета ────────────────────────────────────────────────────────────────────
NAVY   = (31,  78, 121)
BLUE   = (46, 117, 182)
TEAL   = (0,  180, 160)
WHITE  = (255, 255, 255)
LIME   = (112, 173,  71)

def make_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    s   = size

    # ── Фон: скруглённый квадрат ──────────────────────────────────────────────
    pad = s * 0.0
    r   = s * 0.24
    d.rounded_rectangle([pad, pad, s - pad, s - pad],
                        radius=r, fill=NAVY)

    # ── Тонкая яркая полоска снизу (акцент) ───────────────────────────────────
    bh = max(2, int(s * 0.045))
    d.rounded_rectangle([pad, s - pad - bh, s - pad, s - pad],
                        radius=r, fill=TEAL)

    # ── Иконка: GPS-булавка (pin) ─────────────────────────────────────────────
    cx  = s * 0.5
    # центр круга булавки
    py  = s * 0.30
    pr  = s * 0.175   # радиус круга

    # внешний круг (белый контур)
    d.ellipse([cx - pr - s*0.015, py - pr - s*0.015,
               cx + pr + s*0.015, py + pr + s*0.015],
              fill=WHITE)
    # заливка круга
    d.ellipse([cx - pr, py - pr, cx + pr, py + pr], fill=BLUE)
    # внутренняя точка
    ir = s * 0.07
    d.ellipse([cx - ir, py - ir, cx + ir, py + ir], fill=WHITE)

    # «хвост» булавки — треугольник вниз
    tip_y = py + pr + s * 0.19
    tail_w = s * 0.11
    d.polygon([
        (cx - tail_w, py + pr * 0.7),
        (cx + tail_w, py + pr * 0.7),
        (cx,          tip_y),
    ], fill=WHITE)
    # перекрыть верхнюю часть хвоста чтобы слилась с кругом
    d.ellipse([cx - pr - s*0.015, py - pr - s*0.015,
               cx + pr + s*0.015, py + pr + s*0.015],
              fill=WHITE)
    d.ellipse([cx - pr, py - pr, cx + pr, py + pr], fill=BLUE)
    d.ellipse([cx - ir, py - ir, cx + ir, py + ir], fill=WHITE)

    # ── Сигнальные дуги вокруг булавки ────────────────────────────────────────
    for i, (arc_r, lw_k, alpha) in enumerate([
        (0.42, 0.030, 230),
        (0.32, 0.028, 170),
    ]):
        ar  = s * arc_r
        lw2 = max(2, int(s * lw_k))
        col = TEAL + (alpha,)
        d.arc([cx - ar, py - ar * 0.85,
               cx + ar, py + ar * 0.85],
              start=210, end=330, fill=col, width=lw2)

    # ── Текст «EGTS» ──────────────────────────────────────────────────────────
    font_size = int(s * 0.20)
    font = None
    for path in [r"C:\Windows\Fonts\arialbd.ttf",
                 r"C:\Windows\Fonts\arial.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, font_size)
                break
            except Exception:
                pass
    if font is None:
        font = ImageFont.load_default()

    text = "EGTS"
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (s - tw) / 2 - bbox[0]
    ty = s * 0.755 - th / 2 - bbox[1]

    d.text((tx, ty), text, font=font, fill=WHITE)

    # ── Маленький подзаголовок «tracker» ──────────────────────────────────────
    sub_size = max(8, int(s * 0.085))
    sub_font = None
    for path in [r"C:\Windows\Fonts\arial.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        if os.path.exists(path):
            try:
                sub_font = ImageFont.truetype(path, sub_size)
                break
            except Exception:
                pass
    if sub_font:
        sub = "tracker"
        sb = d.textbbox((0, 0), sub, font=sub_font)
        sw = sb[2] - sb[0]
        sx = (s - sw) / 2 - sb[0]
        sy = ty + th + s * 0.015
        d.text((sx, sy), sub, font=sub_font, fill=TEAL)

    return img


# ─── Размеры Android mipmap ────────────────────────────────────────────────────
SIZES = {
    "mipmap-mdpi":    48,
    "mipmap-hdpi":    72,
    "mipmap-xhdpi":   96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi":192,
}

BASE = r"C:\T1_GIT\egts_parser\MOBILE_APP\android\app\src\main\res"

for folder, px in SIZES.items():
    icon = make_icon(px)
    out  = os.path.join(BASE, folder, "ic_launcher.png")
    icon.save(out, "PNG")
    print(f"  {folder:18s}  {px}x{px}  -> {out}")

# preview 512
preview = make_icon(512)
preview.save(r"C:\T1_GIT\egts_parser\icon_preview.png", "PNG")
print("\nPreview: C:\\T1_GIT\\egts_parser\\icon_preview.png")
print("Done.")
