"""Генератор лендинг-страницы EGTS Tracker в PDF."""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import Image
from reportlab.lib.colors import HexColor
import io, os

W, H = A4

# ─── Palette ─────────────────────────────────────────────────────────────────
NAVY    = HexColor("#1F4E79")
BLUE    = HexColor("#2E75B6")
GREEN   = HexColor("#375623")
LIME    = HexColor("#70AD47")
ORANGE  = HexColor("#ED7D31")
PURPLE  = HexColor("#6F31A5")
GRAY    = HexColor("#F2F2F2")
DGRAY   = HexColor("#595959")
WHITE   = colors.white
BLACK   = colors.black


def make_pdf(out_path: str) -> None:
    doc = SimpleDocTemplate(
        out_path,
        pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=15*mm, bottomMargin=15*mm,
    )

    SS = getSampleStyleSheet()

    def S(name, **kw):
        base = SS["Normal"]
        return ParagraphStyle(name, parent=base, **kw)

    sHero   = S("hero",   fontSize=28, leading=34, textColor=WHITE,
                 alignment=TA_CENTER, fontName="Helvetica-Bold")
    sSub    = S("sub",    fontSize=13, leading=18, textColor=WHITE,
                 alignment=TA_CENTER, fontName="Helvetica")
    sH2     = S("h2",    fontSize=16, leading=20, textColor=NAVY,
                 fontName="Helvetica-Bold", spaceAfter=4)
    sH3     = S("h3",    fontSize=12, leading=16, textColor=GREEN,
                 fontName="Helvetica-Bold", spaceAfter=2)
    sBody   = S("body",  fontSize=10, leading=14, textColor=DGRAY,
                 alignment=TA_JUSTIFY)
    sCaption= S("cap",   fontSize=8,  leading=11, textColor=DGRAY,
                 alignment=TA_CENTER)
    sMono   = S("mono",  fontSize=9,  leading=13, textColor=NAVY,
                 fontName="Courier", backColor=GRAY, leftIndent=6, rightIndent=6,
                 spaceBefore=2, spaceAfter=2)
    sBadge  = S("badge", fontSize=9,  leading=12, textColor=WHITE,
                 fontName="Helvetica-Bold", alignment=TA_CENTER)
    sFooter = S("footer",fontSize=8,  leading=11, textColor=DGRAY,
                 alignment=TA_CENTER)

    story = []

    # ═══════════════════════════════════════════════════════════════════════════
    # HERO BANNER
    # ═══════════════════════════════════════════════════════════════════════════

    hero_table = Table(
        [[
            Paragraph("EGTS Tracker", sHero),
        ]],
        colWidths=[W - 36*mm],
    )
    hero_table.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), NAVY),
        ("TOPPADDING",   (0,0), (-1,-1), 22),
        ("BOTTOMPADDING",(0,0), (-1,-1), 8),
    ]))
    story.append(hero_table)
    story.append(Spacer(1, 4))

    sub_table = Table(
        [[Paragraph(
            "Мобильная система мониторинга iBeacon · NFC/RFID · WiFi · GPS/ГЛОНАСС<br/>"
            "с мгновенной отправкой EGTS-пакетов на сервер",
            sSub,
        )]],
        colWidths=[W - 36*mm],
    )
    sub_table.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), BLUE),
        ("TOPPADDING",   (0,0), (-1,-1), 10),
        ("BOTTOMPADDING",(0,0), (-1,-1), 14),
    ]))
    story.append(sub_table)
    story.append(Spacer(1, 10*mm))

    # ═══════════════════════════════════════════════════════════════════════════
    # ЧТО ЭТО?
    # ═══════════════════════════════════════════════════════════════════════════

    story.append(Paragraph("Что такое EGTS Tracker?", sH2))
    story.append(HRFlowable(width="100%", thickness=1, color=NAVY, spaceAfter=6))
    story.append(Paragraph(
        "EGTS Tracker — это Flutter-приложение для Android, которое в реальном времени сканирует "
        "окружающие устройства позиционирования и формирует стандартные пакеты протокола "
        "<b>EGTS (ГОСТ Р 54619-2011)</b>, отправляя их непосредственно в облачный сервис.",
        sBody,
    ))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Приложение предназначено для систем <b>RTLS</b> (Real-Time Location System), "
        "мониторинга транспортных средств, контроля доступа и отслеживания активов на предприятии.",
        sBody,
    ))
    story.append(Spacer(1, 8*mm))

    # ═══════════════════════════════════════════════════════════════════════════
    # ТЕХНОЛОГИИ ПОЗИЦИОНИРОВАНИЯ
    # ═══════════════════════════════════════════════════════════════════════════

    story.append(Paragraph("Поддерживаемые технологии", sH2))
    story.append(HRFlowable(width="100%", thickness=1, color=NAVY, spaceAfter=6))

    tech_data = [
        ["Технология", "Стандарт", "Точность", "Применение"],
        ["iBeacon / BLE", "Bluetooth 4.0+", "0.5 – 10 м", "Навигация внутри зданий"],
        ["NFC / RFID",    "ISO 14443 / 15693", "< 10 см", "Контроль доступа, активы"],
        ["WiFi BSSID",    "IEEE 802.11",  "2 – 15 м", "Зональное позиционирование"],
        ["GPS / ГЛОНАСС", "ГОСТ Р 54619", "3 – 10 м", "Навигация на открытых пространствах"],
        ["LBS",           "GSM / LTE", "50 – 500 м", "Грубое определение зоны"],
    ]
    tech_table = Table(
        [[Paragraph(str(c), S("th" if i == 0 else "td",
                              fontSize=9,
                              fontName="Helvetica-Bold" if i == 0 else "Helvetica",
                              textColor=WHITE if i == 0 else DGRAY,
                              alignment=TA_CENTER if j == 0 else TA_LEFT))
          for j, c in enumerate(row)]
         for i, row in enumerate(tech_data)],
        colWidths=[40*mm, 42*mm, 32*mm, 52*mm],
    )
    tech_table.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1, 0), NAVY),
        ("BACKGROUND",   (0,1), (-1,-1), GRAY),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [WHITE, GRAY]),
        ("GRID",         (0,0), (-1,-1), 0.3, colors.lightgrey),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0), (-1,-1), 5),
        ("LEFTPADDING",  (0,0), (-1,-1), 5),
    ]))
    story.append(tech_table)
    story.append(Spacer(1, 8*mm))

    # ═══════════════════════════════════════════════════════════════════════════
    # КАК РАБОТАЕТ
    # ═══════════════════════════════════════════════════════════════════════════

    story.append(Paragraph("Как это работает", sH2))
    story.append(HRFlowable(width="100%", thickness=1, color=NAVY, spaceAfter=6))

    steps = [
        (BLUE,   "1", "Обнаружение",
         "Приложение непрерывно сканирует iBeacon, WiFi, NFC/RFID в фоновом режиме."),
        (GREEN,  "2", "Проверка белого списка",
         "UUID/MAC/UID сравнивается с настроенным белым списком. Неизвестные устройства игнорируются."),
        (ORANGE, "3", "Формирование пакета",
         "При совпадении мгновенно строится EGTS-пакет (SRT 16 GPS + SRT 17 DOP + "
         "SRT 21 State + SRT 202 TagID + SRT 203 Event) с текущими координатами."),
        (PURPLE, "4", "Отправка на сервер",
         "POST запрос с HEX-пакетом отправляется в Yandex Cloud Function. "
         "Ответ декодируется и отображается в ленте событий."),
    ]

    step_rows = []
    for color, num, title, desc in steps:
        num_cell = Table([[Paragraph(num, sBadge)]], colWidths=[8*mm])
        num_cell.setStyle(TableStyle([
            ("BACKGROUND",   (0,0), (-1,-1), color),
            ("TOPPADDING",   (0,0), (-1,-1), 3),
            ("BOTTOMPADDING",(0,0), (-1,-1), 3),
        ]))
        step_rows.append([
            num_cell,
            Paragraph(f"<b>{title}</b><br/>{desc}", sBody),
        ])

    step_table = Table(step_rows, colWidths=[12*mm, W - 48*mm])
    step_table.setStyle(TableStyle([
        ("VALIGN",       (0,0), (-1,-1), "TOP"),
        ("TOPPADDING",   (0,0), (-1,-1), 6),
        ("BOTTOMPADDING",(0,0), (-1,-1), 6),
    ]))
    story.append(step_table)
    story.append(Spacer(1, 8*mm))

    # ═══════════════════════════════════════════════════════════════════════════
    # СТРУКТУРА EGTS ПАКЕТА
    # ═══════════════════════════════════════════════════════════════════════════

    story.append(Paragraph("Структура EGTS-пакета от приложения", sH2))
    story.append(HRFlowable(width="100%", thickness=1, color=NAVY, spaceAfter=6))

    packet_text = (
        "PT_APPDATA (тип 1)\n"
        "└── SDR  SST=TELEDATA  RST=TELEDATA  OID=terminalId\n"
        "    ├── SRT=16  EGTS_SR_POS_DATA       LAT, LON, SPD, DIR\n"
        "    ├── SRT=17  EGTS_SR_EXT_POS_DATA   HDOP, SAT count\n"
        "    ├── SRT=21  EGTS_SR_STATE_DATA      Напряжение 12V, state=active\n"
        "    ├── SRT=202 CUSTOM_SRT202 (TagID)   tag_id, zone_id, rssi\n"
        "    └── SRT=203 CUSTOM_SRT203 (Event)   event=enter, zone_id, time"
    )
    story.append(Paragraph(packet_text.replace("\n", "<br/>"), sMono))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Все длины (RL, FDL), CRC-8 заголовка и CRC-16 тела пересчитываются автоматически "
        "при каждом формировании пакета согласно ГОСТ Р 54619-2011.",
        sBody,
    ))
    story.append(Spacer(1, 8*mm))

    # ═══════════════════════════════════════════════════════════════════════════
    # ЭКРАНЫ ПРИЛОЖЕНИЯ
    # ═══════════════════════════════════════════════════════════════════════════

    story.append(Paragraph("Экраны приложения", sH2))
    story.append(HRFlowable(width="100%", thickness=1, color=NAVY, spaceAfter=6))

    screens_data = [
        [
            _screen_block("Мониторинг", NAVY,
                "4 вкладки:\n• События — лента EGTS-пакетов\n"
                "• NFC — считанные метки\n"
                "• iBeacon — маяки + RSSI\n"
                "• WiFi — точки доступа\n\n"
                "GPS-статус в строке состояния.\n"
                "Раскрываемая структура каждого пакета.\n"
                "Копирование HEX в буфер.", sBody),
            _screen_block("Настройки", GREEN,
                "• URL Yandex Cloud Function\n"
                "• IAM-токен авторизации\n"
                "• Terminal ID устройства\n\n"
                "Белые списки:\n"
                "• NFC — по UID тега\n"
                "• iBeacon — UUID + Major + Minor\n"
                "• WiFi — SSID и/или BSSID\n\n"
                "Свайп влево для удаления записи.", sBody),
        ]
    ]
    screens_table = Table(screens_data, colWidths=[(W-36*mm)/2, (W-36*mm)/2])
    screens_table.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING",  (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(screens_table)
    story.append(Spacer(1, 8*mm))

    # ═══════════════════════════════════════════════════════════════════════════
    # СЕРВЕРНАЯ ЧАСТЬ
    # ═══════════════════════════════════════════════════════════════════════════

    story.append(Paragraph("Серверная часть — Yandex Cloud Function", sH2))
    story.append(HRFlowable(width="100%", thickness=1, color=NAVY, spaceAfter=6))

    server_data = [
        ["Компонент", "Описание"],
        ["handler.py",    "Точка входа Cloud Function. Принимает hex-пакет, возвращает JSON."],
        ["egts/codec.py", "Полный декодер/энкодер EGTS: parse_packet() / build_packet()"],
        ["egts/models.py","Dataclasses для всех SRT-типов с encode() и decode()"],
        ["egts/crc.py",   "CRC-8 (заголовок) и CRC-16 (тело) с lookup-таблицами"],
        ["egts/log.py",   "ANSI-цветной терминальный лог + JSON-лог файл"],
        ["PARSER/",       "Двунаправленный Excel-парсер: decode CSV→xlsx, encode xlsx→binary"],
    ]
    srv_table = Table(
        [[Paragraph(str(c), S("shdr" if i == 0 else "scell",
                              fontSize=9,
                              fontName="Helvetica-Bold" if i == 0 else "Courier" if j == 0 else "Helvetica",
                              textColor=WHITE if i == 0 else (NAVY if j == 0 else DGRAY)))
          for j, c in enumerate(row)]
         for i, row in enumerate(server_data)],
        colWidths=[42*mm, W - 36*mm - 42*mm],
    )
    srv_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [WHITE, GRAY]),
        ("GRID",          (0,0), (-1,-1), 0.3, colors.lightgrey),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 5),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
    ]))
    story.append(srv_table)
    story.append(Spacer(1, 8*mm))

    # ═══════════════════════════════════════════════════════════════════════════
    # БЫСТРЫЙ СТАРТ
    # ═══════════════════════════════════════════════════════════════════════════

    story.append(Paragraph("Быстрый старт", sH2))
    story.append(HRFlowable(width="100%", thickness=1, color=NAVY, spaceAfter=6))

    qs_steps = [
        ("Установить Cloud Function",
         "cd SERVICE && zip -r fn.zip egts/ handler.py\n"
         "yc serverless function version create --runtime python311 --entrypoint handler.handler --source-path fn.zip"),
        ("Настроить приложение",
         "Настройки → URL: https://functions.yandexcloud.net/<id>\n"
         "Настройки → Terminal ID: 1"),
        ("Добавить в белый список",
         "NFC: поднесите карту → UID появится в списке → нажмите «Добавить»\n"
         "iBeacon: введите UUID маяка + Major/Minor (* = любой)\n"
         "WiFi: введите SSID и/или BSSID точки доступа"),
        ("Начать мониторинг",
         "Мониторинг → Старт → при совпадении в ленте появляется EGTS-пакет\n"
         "Нажмите на пакет для раскрытия структуры и копирования HEX"),
    ]

    for i, (title, code) in enumerate(qs_steps, 1):
        row = Table([[
            Table([[Paragraph(str(i), sBadge)]], colWidths=[7*mm],
                  style=TableStyle([("BACKGROUND",(0,0),(-1,-1),NAVY),
                                    ("TOPPADDING",(0,0),(-1,-1),2),
                                    ("BOTTOMPADDING",(0,0),(-1,-1),2)])),
            Paragraph(f"<b>{title}</b>", sH3),
        ]], colWidths=[10*mm, W-46*mm])
        story.append(row)
        story.append(Paragraph(code.replace("\n", "<br/>"), sMono))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 8*mm))

    # ═══════════════════════════════════════════════════════════════════════════
    # ЗАВИСИМОСТИ / СТЕК
    # ═══════════════════════════════════════════════════════════════════════════

    story.append(Paragraph("Технический стек", sH2))
    story.append(HRFlowable(width="100%", thickness=1, color=NAVY, spaceAfter=6))

    cols_data = [
        [
            _tech_col("Мобильное приложение", BLUE, [
                "Flutter 3.41 / Dart 3",
                "flutter_nfc_kit — NFC/RFID",
                "flutter_blue_plus — BLE iBeacon",
                "wifi_scan — WiFi AP",
                "geolocator — GPS/ГЛОНАСС",
                "provider — state management",
                "shared_preferences — whitelist",
                "http — HTTP POST",
            ]),
            _tech_col("Серверная часть", GREEN, [
                "Python 3.11 (stdlib only)",
                "Yandex Cloud Functions",
                "EGTS codec (ГОСТ Р 54619-2011)",
                "CRC-8 / CRC-16 (lookup tables)",
                "JSON log + TXT log",
                "Re-encode (attrs → binary)",
                "openpyxl — Excel parser",
                "Bidirectional Excel ↔ binary",
            ]),
        ]
    ]
    tech_col_table = Table(cols_data, colWidths=[(W-36*mm)/2 - 2, (W-36*mm)/2 - 2])
    tech_col_table.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING",  (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (0,-1), 6),
    ]))
    story.append(tech_col_table)
    story.append(Spacer(1, 10*mm))

    # ═══════════════════════════════════════════════════════════════════════════
    # НОРМАТИВНАЯ БАЗА
    # ═══════════════════════════════════════════════════════════════════════════

    story.append(Paragraph("Нормативная база", sH2))
    story.append(HRFlowable(width="100%", thickness=1, color=NAVY, spaceAfter=6))

    norms = [
        ("ГОСТ Р 54619-2011",  "Структура обмена навигационными данными в системах мониторинга транспортных средств"),
        ("ГОСТ Р 33472-2015",  "Прикладное программное обеспечение. Обмен данными между диспетчерскими центрами"),
        ("Приказ МинТранс №285", "О порядке передачи телематических данных в систему ЭРА-ГЛОНАСС"),
    ]
    for norm_doc, desc in norms:
        story.append(Paragraph(
            f"<b>{norm_doc}</b> — {desc}", sBody))
        story.append(Spacer(1, 3))
    story.append(Spacer(1, 8*mm))

    # ═══════════════════════════════════════════════════════════════════════════
    # FOOTER
    # ═══════════════════════════════════════════════════════════════════════════

    story.append(HRFlowable(width="100%", thickness=0.5, color=DGRAY, spaceAfter=6))

    footer_table = Table([[
        Paragraph("EGTS Tracker v1.0", sFooter),
        Paragraph("Python 3.11 · Flutter 3.41 · ГОСТ Р 54619-2011", sFooter),
        Paragraph("Yandex Cloud Functions", sFooter),
    ]], colWidths=[(W-36*mm)/3]*3)
    story.append(footer_table)

    doc.build(story)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _screen_block(title: str, color, body_text: str, body_style) -> Table:
    SS = getSampleStyleSheet()
    title_s = ParagraphStyle("st", parent=SS["Normal"],
                              fontSize=11, fontName="Helvetica-Bold",
                              textColor=WHITE, alignment=TA_CENTER)
    t = Table([
        [Paragraph(title, title_s)],
        [Paragraph(body_text.replace("\n", "<br/>"), body_style)],
    ], colWidths=[(A4[0]-36*mm)/2 - 4])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1, 0), color),
        ("BACKGROUND",   (0,1), (-1,-1), HexColor("#F5F8FC")),
        ("TOPPADDING",   (0,0), (-1,-1), 7),
        ("BOTTOMPADDING",(0,0), (-1,-1), 7),
        ("LEFTPADDING",  (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("BOX",          (0,0), (-1,-1), 0.5, HexColor("#CCCCCC")),
    ]))
    return t


def _tech_col(title: str, color, items: list) -> Table:
    SS = getSampleStyleSheet()
    title_s = ParagraphStyle("tc", parent=SS["Normal"],
                              fontSize=10, fontName="Helvetica-Bold",
                              textColor=WHITE, alignment=TA_CENTER)
    item_s  = ParagraphStyle("ti", parent=SS["Normal"],
                              fontSize=9, leading=13, textColor=HexColor("#595959"))
    rows = [[Paragraph(title, title_s)]] + [[Paragraph(f"• {i}", item_s)] for i in items]
    t = Table(rows, colWidths=[(A4[0]-36*mm)/2 - 6])
    style = [
        ("BACKGROUND",   (0,0), (-1, 0), color),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0), (-1,-1), 4),
        ("LEFTPADDING",  (0,0), (-1,-1), 7),
        ("BOX",          (0,0), (-1,-1), 0.5, HexColor("#CCCCCC")),
    ]
    for i in range(1, len(rows)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), HexColor("#F2F2F2")))
    t.setStyle(TableStyle(style))
    return t


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "egts_tracker_landing.pdf"
    make_pdf(out)
    print(f"PDF создан: {out}")
