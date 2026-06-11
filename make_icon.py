"""EGTS Tracker icon — по референсу Grok."""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math, os, numpy as np

BG       = (33,  36,  55)    # тёмный navy фон
WHITE    = (255, 255, 255)
BLUE_DOT = ( 50, 120, 200)   # синяя точка внутри пина
# Три дуги: градиент бирюза→синий (снаружи внутрь)
ARC_C = [
    (  0, 200, 185),   # внешняя — бирюзовая
    (  0, 165, 200),   # средняя — голубая
    ( 30, 120, 200),   # внутренняя — синяя
]
BG_CARD  = (24,  27,  44)


def make_icon(size: int) -> Image.Image:
    s      = size
    corner = s * 0.20

    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s-1, s-1], radius=corner, fill=255)

    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    img.paste(Image.new("RGBA", (s, s), BG), mask=mask)
    d = ImageDraw.Draw(img)

    # ── Параметры ─────────────────────────────────────────────────────────────
    cx  = s * 0.500
    # Дуги центрированы в верхней трети
    ax  = cx
    ay  = s * 0.420     # центр дуг

    # Пин: ниже центра
    cy  = s * 0.620     # центр круга пина
    pr  = s * 0.185     # радиус круга пина
    tip = cy + pr + s * 0.160  # острие

    # ── Три WiFi-дуги ─────────────────────────────────────────────────────────
    # Радиусы и толщины
    lw   = max(4, int(s * 0.058))
    gap  = max(2, int(s * 0.028))
    # от внешней к внутренней
    radii = [s * 0.400, s * 0.400 - lw - gap, s * 0.400 - 2*(lw + gap)]

    for R, col in zip(radii, ARC_C):
        d.arc([ax-R, ay-R, ax+R, ay+R],
              start=213, end=327, fill=col, width=lw)

    # ── Белый овал-тень под пином ─────────────────────────────────────────────
    ew = pr * 1.10
    eh = pr * 0.28
    ey = tip + eh * 0.3
    shadow_layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_layer)
    sd.ellipse([cx-ew, ey-eh, cx+ew, ey+eh], fill=(255, 255, 255, 80))
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(max(1, int(s*0.018))))
    img = Image.alpha_composite(img, shadow_layer)
    d = ImageDraw.Draw(img)

    # ── Пин: острие ───────────────────────────────────────────────────────────
    tw = pr * 0.40
    d.polygon([
        (cx - tw, cy + pr * 0.45),
        (cx + tw, cy + pr * 0.45),
        (cx,      tip),
    ], fill=WHITE)

    # ── Пин: круг ─────────────────────────────────────────────────────────────
    d.ellipse([cx-pr, cy-pr, cx+pr, cy+pr], fill=WHITE)

    # ── Синяя точка (без кольца) ──────────────────────────────────────────────
    dr = pr * 0.38
    d.ellipse([cx-dr, cy-dr, cx+dr, cy+dr], fill=BLUE_DOT)

    # Финальный клип
    out = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    out.paste(img, mask=mask)
    return out


def _font(size, bold=True):
    for p in ([r"C:\Windows\Fonts\arialbd.ttf"] if bold else []) + \
             [r"C:\Windows\Fonts\arial.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def make_card(icon_size=340) -> Image.Image:
    s  = icon_size
    cw = int(s * 1.15)
    ch = int(s * 1.55)
    c  = Image.new("RGBA", (cw, ch), BG_CARD+(255,))
    d  = ImageDraw.Draw(c)
    icon = make_icon(s)
    ox = (cw - s) // 2
    oy = int(ch * 0.07)
    c.paste(icon, (ox, oy), icon)
    f1  = _font(int(s * 0.22))
    bb  = d.textbbox((0,0), "EGTS", font=f1)
    d.text(((cw-(bb[2]-bb[0]))//2-bb[0], oy+s+int(s*0.08)), "EGTS", font=f1, fill=WHITE)
    f2  = _font(int(s * 0.12), bold=False)
    bb2 = d.textbbox((0,0), "tracker", font=f2)
    d.text(((cw-(bb2[2]-bb2[0]))//2-bb2[0],
            oy+s+int(s*0.08)+(bb[3]-bb[1])+int(s*0.02)),
           "tracker", font=f2, fill=ARC_C[0])
    return c


SIZES = {"mipmap-mdpi":48,"mipmap-hdpi":72,"mipmap-xhdpi":96,
         "mipmap-xxhdpi":144,"mipmap-xxxhdpi":192}
BASE  = r"C:\T1_GIT\egts_parser\MOBILE_APP\android\app\src\main\res"

for folder, px in SIZES.items():
    make_icon(px).convert("RGB").save(
        os.path.join(BASE, folder, "ic_launcher.png"), "PNG")
    print(f"  {folder:18s}  {px}x{px}")

make_icon(512).save(r"C:\T1_GIT\egts_parser\icon_preview.png", "PNG")
make_card(380).save(r"C:\T1_GIT\egts_parser\icon_card_preview.png", "PNG")
print("Done.")
