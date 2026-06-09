"""Иконка EGTS Tracker — Вариант 3: GPS pin + long shadow + teal arcs."""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math, os

# ─── Цвета ────────────────────────────────────────────────────────────────────
BG_OUTER  = (30,  33,  48)   # тёмный фон вне иконки
BG_ICON   = (38,  42,  60)   # фон самой иконки (чуть светлее)
BG_ICON2  = (44,  49,  70)   # второй оттенок для лёгкого градиента
TEAL1     = (0,  200, 180)   # яркий бирюзовый (верх дуг)
TEAL2     = (0,  170, 155)   # чуть темнее (низ дуг)
WHITE     = (255, 255, 255)
SHADOW    = (28,  31,  46)   # цвет long shadow (почти как фон)
PIN_DOT   = (38,  42,  60)   # тёмное кольцо вокруг точки
TEAL_DOT  = (0,  200, 180)   # бирюзовая точка внутри пина
ACCENT    = (0,  200, 180)   # нижняя полоска


def make_icon(size: int) -> Image.Image:
    s  = size
    r  = s * 0.22   # радиус скругления

    # ── Маска формы иконки ────────────────────────────────────────────────────
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s - 1, s - 1], radius=r, fill=255)

    # ── Базовый фон ───────────────────────────────────────────────────────────
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    bg  = Image.new("RGBA", (s, s), BG_ICON)
    img.paste(bg, mask=mask)
    d   = ImageDraw.Draw(img)

    # ── Параметры GPS-пина ────────────────────────────────────────────────────
    cx  = s * 0.50
    cy  = s * 0.55           # центр круга булавки
    pr  = s * 0.200           # радиус круга
    tip = cy + pr + s * 0.24  # конец острия
    tw  = pr * 0.58           # полуширина основания острия

    # ── Long shadow — рисуем на отдельном слое, клипируем маской ──────────────
    shadow_steps = int(s * 0.22)
    sl = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sl)

    for i in range(shadow_steps, 0, -1):
        frac  = i / shadow_steps
        alpha = int(45 * frac)
        ox, oy = i * 0.65, i * 0.65
        # форма пина: полигон по контуру (нижняя дуга + острие)
        pts = []
        N = 24
        for k in range(N + 1):
            ang = math.radians(30 + (300 * k / N))
            pts.append((cx + pr * math.cos(ang) + ox,
                        cy + pr * math.sin(ang) + oy))
        pts.append((cx + ox, tip + oy))
        sd.polygon(pts, fill=SHADOW + (alpha,))

    # клипируем тень по форме иконки
    sl.putalpha(Image.fromarray(
        __import__('numpy').minimum(
            __import__('numpy').array(sl.getchannel('A')),
            __import__('numpy').array(mask)
        )
    ))
    img = Image.alpha_composite(img, sl)
    d   = ImageDraw.Draw(img)

    # ── GPS-пин: острие + круг ────────────────────────────────────────────────
    d.polygon([
        (cx - tw, cy + pr * 0.50),
        (cx + tw, cy + pr * 0.50),
        (cx,      tip),
    ], fill=WHITE)
    d.ellipse([cx - pr, cy - pr, cx + pr, cy + pr], fill=WHITE)

    # Полутень на правой половине (имитация объёма как в варианте 3)
    half = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    hd   = ImageDraw.Draw(half)
    hd.polygon([
        (cx,          cy - pr),
        (cx + pr + 2, cy - pr),
        (cx + pr + 2, cy + pr),
        (cx + tw,     cy + pr * 0.50),
        (cx,          tip),
    ], fill=(180, 185, 195, 55))
    img = Image.alpha_composite(img, half)
    d   = ImageDraw.Draw(img)

    # ── Тёмное кольцо и точка ─────────────────────────────────────────────────
    ring_r = pr * 0.40
    dot_r  = pr * 0.24
    d.ellipse([cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r], fill=PIN_DOT)
    d.ellipse([cx - dot_r,  cy - dot_r,  cx + dot_r,  cy + dot_r],  fill=TEAL_DOT)

    # ── Сигнальные дуги ───────────────────────────────────────────────────────
    arc_cy = cy - pr * 1.08
    lw     = max(3, int(s * 0.040))

    for arc_r, col in [(pr * 1.55, TEAL1), (pr * 1.08, TEAL2)]:
        d.arc(
            [cx - arc_r, arc_cy - arc_r * 0.58,
             cx + arc_r, arc_cy + arc_r * 0.58],
            start=207, end=333, fill=col, width=lw,
        )

    # ── Нижняя полоска ────────────────────────────────────────────────────────
    bh = max(2, int(s * 0.042))
    d.rounded_rectangle([0, s - bh, s, s], radius=r, fill=ACCENT)

    # Финальный клип по маске иконки
    out = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    out.paste(img, mask=mask)
    return out


# ─── Шрифты ───────────────────────────────────────────────────────────────────
def _font(size):
    for p in [r"C:\Windows\Fonts\arialbd.ttf",
              r"C:\Windows\Fonts\arial.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def _font_reg(size):
    for p in [r"C:\Windows\Fonts\arial.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


# ─── Полная карточка 512×680 (как у пользователя) ────────────────────────────
def make_card(icon_size=340) -> Image.Image:
    s    = icon_size
    cw   = int(s * 1.15)
    ch   = int(s * 1.55)
    card = Image.new("RGBA", (cw, ch), BG_OUTER + (255,))
    d    = ImageDraw.Draw(card)

    # иконка по центру сверху
    icon = make_icon(s)
    ox   = (cw - s) // 2
    oy   = int(ch * 0.07)
    card.paste(icon, (ox, oy), icon)

    # текст EGTS
    f1   = _font(int(s * 0.22))
    text = "EGTS"
    bb   = d.textbbox((0, 0), text, font=f1)
    tx   = (cw - (bb[2] - bb[0])) // 2 - bb[0]
    ty   = oy + s + int(s * 0.08)
    d.text((tx, ty), text, font=f1, fill=WHITE)

    # текст tracker
    f2   = _font_reg(int(s * 0.12))
    sub  = "tracker"
    bb2  = d.textbbox((0, 0), sub, font=f2)
    sx   = (cw - (bb2[2] - bb2[0])) // 2 - bb2[0]
    sy   = ty + (bb[3] - bb[1]) + int(s * 0.02)
    d.text((sx, sy), sub, font=f2, fill=TEAL1)

    # нижняя полоска
    bh = max(3, int(ch * 0.008))
    d.rectangle([0, ch - bh, cw, ch], fill=ACCENT)

    return card


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
    icon.convert("RGB").save(out, "PNG")
    print(f"  {folder:18s}  {px}x{px}  -> {out}")

# preview иконки 512
make_icon(512).save(r"C:\T1_GIT\egts_parser\icon_preview.png", "PNG")
print("  icon_preview.png saved")

# preview карточки (как присланные изображения)
make_card(380).save(r"C:\T1_GIT\egts_parser\icon_card_preview.png", "PNG")
print("  icon_card_preview.png saved")
print("Done.")
