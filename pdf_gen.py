"""
The Daily Lemon — PDF Generator
Produces a one-page A4 report matching the established design.
Requires: reportlab
"""

from __future__ import annotations
import os
from datetime import datetime
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, black, white, Color
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

# ── Palette ───────────────────────────────────────────────────────────────────
DARK_BG      = HexColor("#1a1a1a")
YELLOW       = HexColor("#f5a623")
ORANGE_DARK  = HexColor("#d4840a")
PRIORITY_BG  = HexColor("#fff3cd")
PRIORITY_BORDER = HexColor("#f5a623")
TRADE_BG     = HexColor("#e8f4f8")
TRADE_BORDER = HexColor("#2196f3")
URGENT_BG    = HexColor("#fff0f0")
URGENT_BORDER= HexColor("#e53935")
CARD_BG      = HexColor("#ffffff")
CARD_BORDER  = HexColor("#e0e0e0")
TEXT_DARK    = HexColor("#1a1a1a")
TEXT_MED     = HexColor("#444444")
TEXT_LIGHT   = HexColor("#888888")
SECTION_BG   = HexColor("#f5f5f5")
QLD_COLOR    = HexColor("#d4380d")   # red-orange badge
NSW_COLOR    = HexColor("#1677ff")   # blue badge
VIC_COLOR    = HexColor("#52c41a")
TAS_COLOR    = HexColor("#722ed1")
STATE_COLORS = {"QLD": QLD_COLOR, "NSW": NSW_COLOR, "VIC": VIC_COLOR, "TAS": TAS_COLOR}
DEFAULT_STATE_COLOR = HexColor("#595959")

W, H = A4   # 595.28 x 841.89 pts
MARGIN = 14 * mm
COL_W = (W - 2 * MARGIN) / 2
INNER = W - 2 * MARGIN


# ── Drawing helpers ───────────────────────────────────────────────────────────

def draw_rect(c: rl_canvas.Canvas, x, y, w, h, fill=None, stroke=None, radius=3):
    if fill:
        c.setFillColor(fill)
    if stroke:
        c.setStrokeColor(stroke)
        c.setLineWidth(0.7)
    else:
        c.setLineWidth(0)
    if radius and (fill or stroke):
        c.roundRect(x, y, w, h, radius, fill=1 if fill else 0, stroke=1 if stroke else 0)
    elif fill or stroke:
        c.rect(x, y, w, h, fill=1 if fill else 0, stroke=1 if stroke else 0)


def text(c: rl_canvas.Canvas, s: str, x, y, font="Helvetica", size=8, color=TEXT_DARK, align="left"):
    c.setFont(font, size)
    c.setFillColor(color)
    if align == "center":
        c.drawCentredString(x, y, s)
    elif align == "right":
        c.drawRightString(x, y, s)
    else:
        c.drawString(x, y, s)


def badge(c: rl_canvas.Canvas, label: str, x, y, bg_color=None, text_color=white, size=6.5):
    if not label:
        return 0
    bg_color = bg_color or DEFAULT_STATE_COLOR
    pad_x, pad_y, h = 4 * mm, 1.5 * mm, 4.5 * mm
    w = c.stringWidth(label, "Helvetica-Bold", size) + 2 * pad_x
    draw_rect(c, x, y - pad_y, w, h, fill=bg_color, radius=2)
    text(c, label, x + pad_x, y + 0.8 * mm, "Helvetica-Bold", size, text_color)
    return w + 2 * mm  # consumed width


def wrap_text(c: rl_canvas.Canvas, s: str, x, y, max_w, font="Helvetica", size=7.5,
              color=TEXT_MED, line_h=3.8 * mm, max_lines=3) -> float:
    """Draw wrapped text; returns the y position after last line."""
    words = s.split()
    line = ""
    lines = []
    for word in words:
        test = (line + " " + word).strip()
        if c.stringWidth(test, font, size) <= max_w:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
        if len(lines) >= max_lines:
            break
    if line and len(lines) < max_lines:
        lines.append(line)

    for ln in lines:
        text(c, ln, x, y, font, size, color)
        y -= line_h
    return y


# ── Section renderers ─────────────────────────────────────────────────────────

def draw_header(c: rl_canvas.Canvas, date_str: str, time_str: str, stats: dict) -> float:
    """Returns y position after header."""
    HEADER_H = 30 * mm
    draw_rect(c, 0, H - HEADER_H, W, HEADER_H, fill=DARK_BG)

    # Title
    c.setFont("Helvetica-Bold", 26)
    c.setFillColor(YELLOW)
    c.drawString(MARGIN, H - 12 * mm, "THE DAILY LEMON")

    # Subtitle
    c.setFont("Helvetica", 8)
    c.setFillColor(HexColor("#aaaaaa"))
    c.drawString(MARGIN, H - 17 * mm, "AI Data Centre Fitout Jobs & Tenders — Australia")

    # Date / source right-aligned
    c.setFont("Helvetica", 7.5)
    c.setFillColor(HexColor("#cccccc"))
    c.drawRightString(W - MARGIN, H - 11 * mm, date_str)
    c.drawRightString(W - MARGIN, H - 16 * mm, f"{time_str}  ·  The Daily Lemon Agent")

    # Stats bar
    STATS_Y = H - HEADER_H - 12 * mm
    STATS_H = 11 * mm
    draw_rect(c, MARGIN, STATS_Y, INNER, STATS_H, fill=DARK_BG, radius=4)

    stat_items = [
        (str(stats.get("leads", 0)), "SPECIFIC LEADS"),
        (str(stats.get("priority", 0)), "PRIORITY HITS"),
        (str(stats.get("trade", 0)), "TRADE MATCHES"),
        (str(stats.get("urgent", 0)), "URGENT"),
    ]
    col_w = INNER / len(stat_items)
    for i, (val, label) in enumerate(stat_items):
        cx = MARGIN + i * col_w + col_w / 2
        c.setFont("Helvetica-Bold", 16)
        c.setFillColor(YELLOW)
        c.drawCentredString(cx, STATS_Y + 5.5 * mm, val)
        c.setFont("Helvetica", 6)
        c.setFillColor(HexColor("#aaaaaa"))
        c.drawCentredString(cx, STATS_Y + 2 * mm, label)

    # Divider lines between stats
    c.setStrokeColor(HexColor("#333333"))
    c.setLineWidth(0.5)
    for i in range(1, len(stat_items)):
        lx = MARGIN + i * col_w
        c.line(lx, STATS_Y + 2 * mm, lx, STATS_Y + STATS_H - 2 * mm)

    return STATS_Y - 3 * mm


def draw_urgent_banner(c: rl_canvas.Canvas, lead: dict, y: float) -> float:
    H_BANNER = 7.5 * mm
    draw_rect(c, MARGIN, y - H_BANNER, INNER, H_BANNER, fill=HexColor("#c0392b"), radius=3)
    msg = f"URGENT: {lead['title'][:80]} — Closes {lead.get('close_date','')} ({lead.get('urgency','')})  → {lead.get('source','')}"
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(white)
    c.drawString(MARGIN + 3 * mm, y - 5 * mm, msg[:110])
    return y - H_BANNER - 2 * mm


def draw_priority_banner(c: rl_canvas.Canvas, y: float) -> float:
    H_B = 6 * mm
    draw_rect(c, MARGIN, y - H_B, INNER, H_B, fill=YELLOW, radius=3)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(DARK_BG)
    c.drawString(MARGIN + 3 * mm, y - 4 * mm, "★  PRIORITY FOCUS — CENTRAL QUEENSLAND & CASINO NSW")
    return y - H_B - 2 * mm


def draw_lead_card(c: rl_canvas.Canvas, lead: dict, x: float, y: float, w: float) -> float:
    """Draw a single lead card. Returns y position after card."""
    CARD_H = 24 * mm
    PAD = 3 * mm

    # Card background
    is_priority = bool(lead.get("priority"))
    is_trade = bool(lead.get("trade_match"))
    is_urgent = lead.get("urgency", "").startswith("URGENT")

    if is_urgent:
        bg, border = HexColor("#fff5f5"), URGENT_BORDER
    elif is_priority:
        bg, border = PRIORITY_BG, PRIORITY_BORDER
    elif is_trade:
        bg, border = TRADE_BG, TRADE_BORDER
    else:
        bg, border = CARD_BG, CARD_BORDER

    draw_rect(c, x, y - CARD_H, w, CARD_H, fill=bg, stroke=border, radius=3)

    # Title line
    title = lead.get("title", "Untitled")[:70]
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(TEXT_DARK)
    c.drawString(x + PAD, y - 6 * mm, title)

    # Badges row (right side)
    badge_x = x + w - PAD
    bx = badge_x
    state = lead.get("state", "")
    status = lead.get("status", "")
    urgency = lead.get("urgency", "")

    if urgency:
        ug_col = URGENT_BORDER if "URGENT" in urgency else HexColor("#e67e22")
        uw = c.stringWidth(urgency, "Helvetica-Bold", 6.5) + 8 * mm
        draw_rect(c, bx - uw, y - 7 * mm, uw, 4.5 * mm, fill=ug_col, radius=2)
        text(c, urgency, bx - uw + 4 * mm, y - 5.3 * mm, "Helvetica-Bold", 6.5, white)
        bx -= uw + 2 * mm

    if state:
        sc = STATE_COLORS.get(state, DEFAULT_STATE_COLOR)
        sw = c.stringWidth(state, "Helvetica-Bold", 6.5) + 6 * mm
        draw_rect(c, bx - sw, y - 7 * mm, sw, 4.5 * mm, fill=sc, radius=2)
        text(c, state, bx - sw + 3 * mm, y - 5.3 * mm, "Helvetica-Bold", 6.5, white)

    # Value + region line
    meta_parts = []
    if lead.get("value"):
        meta_parts.append(lead["value"])
    if lead.get("region") and lead["region"] not in ("General", "AU"):
        meta_parts.append(lead["region"])
    if lead.get("agency") and lead["agency"] not in (lead.get("source", ""), ""):
        meta_parts.append(lead["agency"])
    if lead.get("close_date"):
        meta_parts.append(f"Close: {lead['close_date']}")
    meta_str = "  |  ".join(meta_parts)
    c.setFont("Helvetica", 7)
    c.setFillColor(TEXT_LIGHT)
    c.drawString(x + PAD, y - 10 * mm, meta_str[:90])

    # Trade keywords highlight
    if is_trade:
        from scrapers import TRADE_KEYWORDS
        combined = (lead.get("title", "") + " " + lead.get("summary", "")).lower()
        matched = [kw for kw in TRADE_KEYWORDS if kw in combined][:5]
        if matched:
            kw_str = "◆  " + " · ".join(matched)
            c.setFont("Helvetica-Oblique", 7)
            c.setFillColor(HexColor("#1677ff"))
            c.drawString(x + PAD, y - 14 * mm, kw_str[:80])

    # Summary
    summary = lead.get("summary", "")
    if summary:
        wrap_text(c, summary, x + PAD, y - 17.5 * mm, w - 2 * PAD,
                  font="Helvetica", size=7, color=TEXT_MED, max_lines=2)

    # View link
    url = lead.get("url", "")
    if url:
        c.setFont("Helvetica", 7)
        c.setFillColor(HexColor("#1677ff"))
        c.drawRightString(x + w - PAD, y - CARD_H + 3 * mm, "View →")

    return y - CARD_H - 2 * mm


def draw_section_header(c: rl_canvas.Canvas, label: str, x, y, w) -> float:
    H_S = 5.5 * mm
    col = STATE_COLORS.get(label, HexColor("#333333"))
    draw_rect(c, x, y - H_S, w, H_S, fill=col, radius=2)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(white)
    c.drawString(x + 3 * mm, y - 4 * mm, label)
    return y - H_S - 1.5 * mm


def draw_market_intel(c: rl_canvas.Canvas, bullets: list[str], y: float) -> float:
    H_HDR = 5.5 * mm
    draw_rect(c, MARGIN, y - H_HDR, INNER, H_HDR, fill=HexColor("#2c2c2c"), radius=2)
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(YELLOW)
    c.drawString(MARGIN + 3 * mm, y - 4 * mm, "CHART  MARKET INTEL")
    y -= H_HDR + 2 * mm

    for b in bullets:
        c.setFont("Helvetica", 7)
        c.setFillColor(TEXT_MED)
        c.drawString(MARGIN + 2 * mm, y, "→")
        wrap_text(c, b, MARGIN + 6 * mm, y, INNER - 8 * mm,
                  font="Helvetica", size=7, color=TEXT_MED, max_lines=2)
        y -= 4.5 * mm

    return y - 1 * mm


def draw_action_items(c: rl_canvas.Canvas, items: list[str], y: float) -> float:
    H_HDR = 5.5 * mm
    draw_rect(c, MARGIN, y - H_HDR, INNER, H_HDR, fill=YELLOW, radius=2)
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(DARK_BG)
    c.drawString(MARGIN + 3 * mm, y - 4 * mm, "TICK  DO THESE 3 THINGS THIS WEEK")
    y -= H_HDR + 2 * mm

    for i, item in enumerate(items, 1):
        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(YELLOW)
        c.drawString(MARGIN + 2 * mm, y, f"{i}.")
        wrap_text(c, item, MARGIN + 8 * mm, y, INNER - 10 * mm,
                  font="Helvetica", size=7.5, color=TEXT_DARK, max_lines=2)
        y -= 9 * mm

    return y


def draw_footer(c: rl_canvas.Canvas, date_str: str):
    FOOTER_H = 6 * mm
    draw_rect(c, 0, 0, W, FOOTER_H, fill=DARK_BG)
    sources = "EstimateOne · ICN Gateway · NSW eTendering · AusTender · QTenders · TenderLink · DCD · iTnews"
    c.setFont("Helvetica", 5.5)
    c.setFillColor(HexColor("#888888"))
    c.drawString(MARGIN, 2.5 * mm, sources)
    c.drawRightString(W - MARGIN, 2.5 * mm, f"The Daily Lemon · {date_str}")


# ── Main entry ────────────────────────────────────────────────────────────────

def generate_daily_lemon_pdf(
    leads: list[dict],
    stats: dict,
    out_path: str,
    date_str: str,
    time_str: str,
    action_items: list[str],
    market_intel: list[str],
):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    c = rl_canvas.Canvas(out_path, pagesize=A4, pageCompression=0)
    c.setTitle(f"The Daily Lemon — {date_str}")

    y = H  # current Y cursor (top of page)

    # Header
    y = draw_header(c, date_str, time_str, stats)

    # Urgent banner (first urgent lead)
    urgent_leads = [l for l in leads if l.get("urgency", "").startswith("URGENT")]
    if urgent_leads:
        y = draw_urgent_banner(c, urgent_leads[0], y)

    # Priority banner
    y = draw_priority_banner(c, y)
    y -= 1 * mm

    # ── Leads in two columns ──────────────────────────────────────────────────
    # Show up to 6 leads (3 per column) to stay on one page
    display_leads = leads[:6]

    if display_leads:
        col_y = [y, y]   # current y for each column
        for i, lead in enumerate(display_leads):
            col = i % 2
            cx = MARGIN + col * (COL_W + 2 * mm)
            col_y[col] = draw_lead_card(c, lead, cx, col_y[col], COL_W - 1 * mm)

        y = min(col_y) - 2 * mm
    else:
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(TEXT_LIGHT)
        c.drawCentredString(W / 2, y - 10 * mm, "No new leads found today — check sources manually.")
        y -= 20 * mm

    # ── Market Intel ──────────────────────────────────────────────────────────
    if y > 55 * mm:
        y = draw_market_intel(c, market_intel, y)

    # ── Action Items ──────────────────────────────────────────────────────────
    if y > 35 * mm:
        y = draw_action_items(c, action_items, y)

    # Footer
    draw_footer(c, date_str)

    c.save()
