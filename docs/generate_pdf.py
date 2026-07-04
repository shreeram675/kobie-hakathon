"""
generate_pdf.py — Generates the Kobie Architecture & Design PDF using ReportLab 5.0.0
"""

import math
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.platypus.flowables import Flowable
from reportlab.graphics.shapes import (
    Drawing, Rect, String, Line, Polygon, Circle, Path, Group
)
from reportlab.graphics import renderPDF
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ─── COLOR PALETTE ───────────────────────────────────────────────────────────
PRIMARY     = HexColor('#1d4ed8')
PRIMARY_LT  = HexColor('#3b82f6')
PRIMARY_BG  = HexColor('#eff6ff')
PRIMARY_BD  = HexColor('#bfdbfe')
TEAL        = HexColor('#0d9488')
TEAL_BG     = HexColor('#f0fdfa')
AMBER       = HexColor('#d97706')
AMBER_BG    = HexColor('#fffbeb')
AMBER_BD    = HexColor('#fde68a')
RED         = HexColor('#dc2626')
RED_BG      = HexColor('#fef2f2')
RED_BD      = HexColor('#fecaca')
GREEN       = HexColor('#16a34a')
GREEN_BG    = HexColor('#f0fdf4')
GREEN_BD    = HexColor('#bbf7d0')
VIOLET      = HexColor('#7c3aed')
VIOLET_BG   = HexColor('#f5f3ff')
VIOLET_BD   = HexColor('#ddd6fe')
ORANGE      = HexColor('#f97316')
ORANGE_BG   = HexColor('#fff7ed')
PURPLE      = HexColor('#a855f7')
PURPLE_BG   = HexColor('#fdf4ff')
GRAY        = HexColor('#64748b')
GRAY_LT     = HexColor('#f1f5f9')
GRAY_BD     = HexColor('#e2e8f0')
TEXT        = HexColor('#0f172a')
TEXT_SEC    = HexColor('#475569')
DARK_BLUE   = HexColor('#1e3a8a')
ORANGE2     = HexColor('#ea580c')
COVER_DARK  = HexColor('#1e3a8a')
COVER_MID   = HexColor('#1d4ed8')
COVER_LT    = HexColor('#2563eb')

# ─── PAGE SETUP ──────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4   # 595.3 x 841.9 pts
MARGIN = 45
CONTENT_W = PAGE_W - 2 * MARGIN

# ─── STYLES ──────────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()

S_COVER_TITLE = ParagraphStyle('CoverTitle', fontSize=48, fontName='Helvetica-Bold',
    textColor=white, leading=52, spaceAfter=8)
S_COVER_SUB   = ParagraphStyle('CoverSub', fontSize=18, fontName='Helvetica-Bold',
    textColor=HexColor('#bfdbfe'), leading=24, spaceAfter=6)
S_COVER_TAG   = ParagraphStyle('CoverTag', fontSize=11, fontName='Helvetica',
    textColor=HexColor('#93c5fd'), leading=16, spaceAfter=4)
S_COVER_VER   = ParagraphStyle('CoverVer', fontSize=10, fontName='Helvetica',
    textColor=HexColor('#93c5fd'), leading=14, spaceAfter=20)

S_SEC_TITLE = ParagraphStyle('SecTitle', fontSize=16, fontName='Helvetica-Bold',
    textColor=PRIMARY, leading=20, spaceBefore=6, spaceAfter=8)
S_SUBSEC    = ParagraphStyle('SubSec', fontSize=12, fontName='Helvetica-Bold',
    textColor=DARK_BLUE, leading=16, spaceBefore=12, spaceAfter=6)
S_BODY      = ParagraphStyle('Body', fontSize=10, fontName='Helvetica',
    textColor=TEXT_SEC, leading=15, spaceAfter=6)
S_CARD_TITLE = ParagraphStyle('CardTitle', fontSize=11, fontName='Helvetica-Bold',
    textColor=TEXT, leading=14, spaceAfter=4)
S_CARD_BODY  = ParagraphStyle('CardBody', fontSize=9.5, fontName='Helvetica',
    textColor=TEXT_SEC, leading=13)
S_TH  = ParagraphStyle('TH', fontSize=9.5, fontName='Helvetica-Bold',
    textColor=white, leading=13)
S_TD  = ParagraphStyle('TD', fontSize=9, fontName='Helvetica',
    textColor=HexColor('#374151'), leading=13)
S_CODE = ParagraphStyle('Code', fontSize=8.5, fontName='Courier',
    textColor=TEXT, leading=12, backColor=GRAY_LT)
S_TL_TITLE = ParagraphStyle('TLTitle', fontSize=10.5, fontName='Helvetica-Bold',
    textColor=TEXT, leading=14)
S_TL_DESC  = ParagraphStyle('TLDesc', fontSize=9.5, fontName='Helvetica',
    textColor=TEXT_SEC, leading=13)
S_CALLOUT   = ParagraphStyle('Callout', fontSize=10, fontName='Helvetica',
    textColor=DARK_BLUE, leading=14, leftIndent=8)
S_CALLOUT_B = ParagraphStyle('CalloutB', fontSize=10, fontName='Helvetica-Bold',
    textColor=DARK_BLUE, leading=14, leftIndent=8)

# ─── HELPER FUNCTIONS ────────────────────────────────────────────────────────

def section_title(num, text):
    hr = HRFlowable(width=CONTENT_W, thickness=1, color=GRAY_BD, spaceAfter=6)
    p  = Paragraph(f'<font color="#94a3b8">{num}</font>  {text}', S_SEC_TITLE)
    return [hr, p]

def subsection_title(text):
    return Paragraph(text, S_SUBSEC)

def body(text):
    return Paragraph(text, S_BODY)

def spacer(h=8):
    return Spacer(1, h)

def callout(text, style='blue'):
    palette = {
        'blue':  (PRIMARY_BG,  PRIMARY),
        'amber': (AMBER_BG,    AMBER),
        'green': (GREEN_BG,    GREEN),
        'gray':  (GRAY_LT,     GRAY),
        'red':   (RED_BG,      RED),
    }
    bg, border = palette.get(style, (PRIMARY_BG, PRIMARY))
    inner = Paragraph(text, ParagraphStyle('co', fontSize=10, fontName='Helvetica',
        textColor=DARK_BLUE, leading=14))
    tbl = Table([[Paragraph('', ParagraphStyle('sp')), inner]],
                colWidths=[6, CONTENT_W - 6])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), border),
        ('BACKGROUND', (1,0), (1,0), bg),
        ('TOPPADDING',    (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING',   (0,0), (0,0),   0),
        ('RIGHTPADDING',  (0,0), (0,0),   0),
        ('LEFTPADDING',   (1,0), (1,0),   10),
        ('RIGHTPADDING',  (1,0), (1,0),   10),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    return tbl

def make_table(headers, rows, col_widths=None):
    header_row = [Paragraph(h, S_TH) for h in headers]
    data = [header_row]
    for i, row in enumerate(rows):
        data.append([Paragraph(str(c), S_TD) for c in row])

    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ('BACKGROUND', (0,0), (-1,0), PRIMARY),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, GRAY_LT]),
        ('TOPPADDING',    (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING',   (0,0), (-1,-1), 6),
        ('RIGHTPADDING',  (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, GRAY_BD),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]
    tbl.setStyle(TableStyle(style_cmds))
    return tbl

def draw_arrow(d, x1, y1, x2, y2, color=GRAY, width=1.2):
    d.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=width))
    angle = math.atan2(y2 - y1, x2 - x1)
    size = 5
    ax1 = x2 - size * math.cos(angle - 0.4)
    ay1 = y2 - size * math.sin(angle - 0.4)
    ax2 = x2 - size * math.cos(angle + 0.4)
    ay2 = y2 - size * math.sin(angle + 0.4)
    d.add(Polygon([x2, y2, ax1, ay1, ax2, ay2],
                  fillColor=color, strokeColor=color, strokeWidth=0))

def draw_label(d, text, x, y, font='Helvetica', size=9, color=GRAY, anchor='middle'):
    s = String(x, y, text, fontName=font, fontSize=size, fillColor=color, textAnchor=anchor)
    d.add(s)

# ─── COVER PAGE ──────────────────────────────────────────────────────────────

class CoverPage(Flowable):
    """Full-page cover rendered using absolute canvas coordinates.

    The flowable reports CONTENT_W x (PAGE_H - 2*MARGIN) so it fits in the
    default frame, then uses saveState/translate to paint the full page.
    """
    def __init__(self):
        super().__init__()
        self.width  = CONTENT_W
        # Use a height that fits within the frame (frame height = PAGE_H - 2*MARGIN - 12 for doc padding)
        self.height = PAGE_H - 2 * MARGIN - 14

    def draw(self):
        c = self.canv
        # Translate so we can paint the full page (frame starts at MARGIN,MARGIN)
        c.saveState()
        c.translate(-MARGIN, -MARGIN)
        w, h = PAGE_W, PAGE_H

        # Gradient bands (dark at top, lighter at bottom in page coords)
        bands = [
            (0.75, 1.00, HexColor('#172554')),
            (0.50, 0.75, COVER_DARK),
            (0.25, 0.50, COVER_MID),
            (0.00, 0.25, COVER_LT),
        ]
        for t0, t1, col in bands:
            y0 = t0 * h
            y1 = t1 * h
            c.setFillColor(col)
            c.rect(0, y0, w, y1 - y0, fill=1, stroke=0)

        # Decorative circles (bottom-right)
        c.setStrokeColor(HexColor('#ffffff'))
        c.setStrokeAlpha(0.08)
        c.setFillColor(HexColor('#1d4ed8'))
        for r in [120, 200, 300]:
            c.circle(w - 60, 80, r, stroke=1, fill=0)
        c.setStrokeAlpha(1.0)

        # Title: "Kobie"
        c.setFillColor(white)
        c.setFont('Helvetica-Bold', 52)
        c.drawString(MARGIN, 660, 'Kobie')

        # Subtitle
        c.setFont('Helvetica-Bold', 20)
        c.setFillColor(HexColor('#bfdbfe'))
        c.drawString(MARGIN, 618, 'Architecture & Design Document')

        # Tag line
        c.setFont('Helvetica-Oblique', 12)
        c.setFillColor(HexColor('#93c5fd'))
        c.drawString(MARGIN, 594, 'Autonomous Competitive Intelligence Agent for Loyalty Programs')

        # Version
        c.setFont('Helvetica', 10)
        c.setFillColor(HexColor('#93c5fd'))
        c.drawString(MARGIN, 572, 'Version 1.0')

        # Horizontal rule
        c.setStrokeColor(white)
        c.setLineWidth(0.5)
        c.line(MARGIN, 558, w - MARGIN, 558)

        # Tech pills row
        pills = ['FastAPI', 'LangGraph', 'Gemini 2.5 Flash', 'Groq',
                 'SQLite WAL', 'Next.js 14', 'Pydantic v2']
        px = MARGIN
        py = 530
        c.setFont('Helvetica', 8.5)
        for pill in pills:
            tw = c.stringWidth(pill, 'Helvetica', 8.5)
            pw = tw + 14
            ph = 18
            # pill background (semi-transparent white)
            c.setFillColor(HexColor('#ffffff'))
            c.setFillAlpha(0.15)
            c.roundRect(px, py - 4, pw, ph, 4, fill=1, stroke=0)
            c.setFillAlpha(1.0)
            # pill border
            c.setStrokeColor(HexColor('#ffffff'))
            c.setStrokeAlpha(0.3)
            c.setLineWidth(0.5)
            c.roundRect(px, py - 4, pw, ph, 4, fill=0, stroke=1)
            c.setStrokeAlpha(1.0)
            # pill text
            c.setFillColor(white)
            c.drawString(px + 7, py + 1, pill)
            px += pw + 8
            if px > w - MARGIN - 80:
                px = MARGIN
                py -= 24

        # Bottom accent line
        c.setStrokeColor(HexColor('#3b82f6'))
        c.setLineWidth(3)
        c.line(0, 20, w, 20)

        c.restoreState()

    def wrap(self, *args):
        return (self.width, self.height)


# ─── ARCHITECTURE DIAGRAM ────────────────────────────────────────────────────

class ArchitectureDiagram(Flowable):
    def __init__(self, width=CONTENT_W, height=320):
        super().__init__()
        self.width  = width
        self.height = height

    def draw(self):
        c = self.canv
        w = self.width

        layers = [
            # (y, h, fill, stroke, label, sublabel)
            (250, 55, PRIMARY_BG,         PRIMARY_LT,
             'Frontend — Next.js 14 / React 18',
             'PipelineGraph  ·  ClaimsTable  ·  ConflictCard  ·  DebateTimeline  ·  ComparisonTable  ·  PDF export  ·  TanStack Query'),
            (180, 55, GREEN_BG,           GREEN,
             'Backend — FastAPI (server.py)',
             'POST /api/run  ·  GET /api/run/{id}  ·  POST /clarify  ·  POST /converse  ·  GET /cache/check  ·  In-memory RunRecord'),
            (105, 60, HexColor('#fefce8'), AMBER,
             'LangGraph Pipeline — pipeline/graph.py',
             'input_validator · query_generator · app_ratings · retrieval · web_enrichment · firecrawl_scraper · ingest · adjudication · narration'),
            (55,  38, PURPLE_BG,          PURPLE,
             'Persistence — core/db.py (SQLite WAL)',
             'run_snapshots · runs · sources · pages · chunks · claims · conflicts · briefs · conversations'),
            (0,   44, ORANGE_BG,          ORANGE,
             'External Services',
             'Google Gemini 2.5 Flash  ·  Groq llama-3.3-70b  ·  Tavily Search  ·  Firecrawl  ·  Google Play/iTunes  ·  Wikipedia REST'),
        ]

        for (ly, lh, fill, stroke, label, sublabel) in layers:
            c.setFillColor(fill)
            c.setStrokeColor(stroke)
            c.setLineWidth(1.2)
            c.roundRect(0, ly, w, lh, 6, fill=1, stroke=1)

            c.setFillColor(DARK_BLUE)
            c.setFont('Helvetica-Bold', 10)
            c.drawString(10, ly + lh - 16, label)

            c.setFillColor(GRAY)
            c.setFont('Helvetica', 8.5)
            # Truncate sublabel if too wide
            max_w = w - 20
            while c.stringWidth(sublabel, 'Helvetica', 8.5) > max_w and len(sublabel) > 10:
                sublabel = sublabel[:-4] + '…'
            c.drawString(10, ly + 6, sublabel)

        # Vertical arrows between layers (from bottom of upper layer DOWN to top of lower layer)
        arrows_info = [
            (250, 235, 'REST polling'),
            (180, 165, 'node invocation'),
            (105,  93, 'SQLite r/w'),
            (55,   44, 'API calls'),
        ]
        arrow_x = w * 0.85
        for (y_top, y_bot, lbl) in arrows_info:
            # Draw arrow from bottom of upper layer to top of lower layer
            c.setStrokeColor(GRAY)
            c.setLineWidth(0.8)
            c.setDash([3, 3])
            c.line(arrow_x, y_top, arrow_x, y_bot)
            c.setDash([])
            # Arrowhead
            c.setFillColor(GRAY)
            p = c.beginPath()
            p.moveTo(arrow_x, y_bot)
            p.lineTo(arrow_x - 4, y_bot + 7)
            p.lineTo(arrow_x + 4, y_bot + 7)
            p.close()
            c.drawPath(p, fill=1, stroke=0)
            # Label
            c.setFillColor(TEXT_SEC)
            c.setFont('Helvetica', 7.5)
            c.drawString(arrow_x + 6, (y_top + y_bot) / 2, lbl)

    def wrap(self, *args):
        return (self.width, self.height)


# ─── PIPELINE FLOWCHART ──────────────────────────────────────────────────────

class PipelineFlowchart(Flowable):
    SVG_W, SVG_H = 720, 840
    DRAW_W = CONTENT_W
    DRAW_H = 560

    def __init__(self):
        super().__init__()
        self.width  = self.DRAW_W
        self.height = self.DRAW_H

    def s(self, x, y):
        """Convert SVG coords to ReportLab coords."""
        sx = x * self.DRAW_W / self.SVG_W
        sy = self.DRAW_H - (y * self.DRAW_H / self.SVG_H)
        return sx, sy

    def arrow(self, c, x1, y1, x2, y2, color=GRAY, dashed=False):
        c.setStrokeColor(color)
        c.setLineWidth(1.0)
        if dashed:
            c.setDash([4, 3])
        else:
            c.setDash([])
        c.line(x1, y1, x2, y2)
        c.setDash([])
        # Arrowhead
        angle = math.atan2(y2 - y1, x2 - x1)
        size = 5
        ax1 = x2 - size * math.cos(angle - 0.4)
        ay1 = y2 - size * math.sin(angle - 0.4)
        ax2 = x2 - size * math.cos(angle + 0.4)
        ay2 = y2 - size * math.sin(angle + 0.4)
        c.setFillColor(color)
        p = c.beginPath()
        p.moveTo(x2, y2)
        p.lineTo(ax1, ay1)
        p.lineTo(ax2, ay2)
        p.close()
        c.drawPath(p, fill=1, stroke=0)

    def node_rect(self, c, svg_x, svg_y, svg_w, svg_h, fill, stroke, label, sublabel):
        x, y2 = self.s(svg_x, svg_y)
        x2, y1 = self.s(svg_x + svg_w, svg_y + svg_h)
        rw, rh = x2 - x, y2 - y1
        c.setFillColor(fill)
        c.setStrokeColor(stroke)
        c.setLineWidth(1.2)
        c.roundRect(x, y1, rw, rh, 5, fill=1, stroke=1)
        c.setFillColor(stroke)
        c.setFont('Helvetica-Bold', 9)
        lx = x + rw / 2
        c.drawCentredString(lx, y1 + rh * 0.6, label)
        if sublabel:
            c.setFillColor(GRAY)
            c.setFont('Helvetica', 7.5)
            c.drawCentredString(lx, y1 + rh * 0.25, sublabel)

    def draw(self):
        c = self.canv

        # START circle
        sx, sy = self.s(360, 28)
        c.setFillColor(PRIMARY)
        c.setStrokeColor(PRIMARY)
        c.circle(sx, sy, 14 * self.DRAW_W / self.SVG_W, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont('Helvetica-Bold', 7)
        c.drawCentredString(sx, sy - 2.5, 'START')

        # Arrow START -> input_validator
        x1, y1 = self.s(360, 48)
        x2, y2 = self.s(360, 66)
        self.arrow(c, x1, y1, x2, y2)

        # input_validator rect
        self.node_rect(c, 230, 66, 260, 50, PRIMARY_BG, PRIMARY,
                       'input_validator_node', 'Gemini · Identity Resolution')

        # Arrow to decision diamond
        x1, y1 = self.s(360, 116)
        x2, y2 = self.s(360, 134)
        self.arrow(c, x1, y1, x2, y2)

        # Decision diamond: 360,134 center; halfW=96, halfH=31
        pts = [360, 134, 456, 165, 360, 196, 264, 165]
        rpts = []
        for i in range(0, len(pts), 2):
            rx, ry = self.s(pts[i], pts[i+1])
            rpts.extend([rx, ry])
        c.setFillColor(HexColor('#fefce8'))
        c.setStrokeColor(AMBER)
        c.setLineWidth(1.2)
        p = c.beginPath()
        p.moveTo(rpts[0], rpts[1])
        for i in range(2, len(rpts), 2):
            p.lineTo(rpts[i], rpts[i+1])
        p.close()
        c.drawPath(p, fill=1, stroke=1)
        cx_d, cy_d = self.s(360, 165)
        c.setFillColor(AMBER)
        c.setFont('Helvetica-Bold', 8)
        c.drawCentredString(cx_d, cy_d + 2, 'Resolved?')
        c.setFont('Helvetica', 7)
        c.drawCentredString(cx_d, cy_d - 7, '(validation status)')

        # NO path -> red END circle
        x1, y1 = self.s(456, 165)
        x2, y2 = self.s(580, 165)
        self.arrow(c, x1, y1, x2, y2, RED)
        ex, ey = self.s(610, 165)
        c.setFillColor(RED)
        c.circle(ex, ey, 10 * self.DRAW_W / self.SVG_W, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont('Helvetica-Bold', 6)
        c.drawCentredString(ex, ey - 2, 'REJECT')
        # NO label
        lx, ly = self.s(490, 158)
        c.setFillColor(RED)
        c.setFont('Helvetica', 7)
        c.drawString(lx, ly, 'NO')

        # Clarification dashed loop back
        cx1, cy1 = self.s(264, 165)
        cx2, cy2 = self.s(230, 165)
        cx3, cy3 = self.s(200, 120)
        cx4, cy4 = self.s(230, 91)
        c.setStrokeColor(VIOLET)
        c.setLineWidth(0.8)
        c.setDash([4, 3])
        p = c.beginPath()
        p.moveTo(cx1, cy1)
        p.lineTo(cx2, cy2)
        p.lineTo(cx3, cy3)
        p.lineTo(cx4, cy4)
        c.drawPath(p, fill=0, stroke=1)
        c.setDash([])
        lx, ly = self.s(155, 130)
        c.setFillColor(VIOLET)
        c.setFont('Helvetica', 7)
        c.drawString(lx, ly, 'clarify (max 3)')

        # YES arrow down
        x1, y1 = self.s(360, 196)
        x2, y2 = self.s(360, 214)
        self.arrow(c, x1, y1, x2, y2)
        lx, ly = self.s(366, 205)
        c.setFillColor(GREEN)
        c.setFont('Helvetica', 7)
        c.drawString(lx, ly, 'YES')

        # query_generator
        self.node_rect(c, 230, 214, 260, 50, GREEN_BG, GREEN,
                       'query_generator_node', 'Gemini · Up to 15 queries')

        # arrow
        x1, y1 = self.s(360, 264)
        x2, y2 = self.s(360, 282)
        self.arrow(c, x1, y1, x2, y2)

        # app_ratings
        self.node_rect(c, 230, 282, 260, 50, PURPLE_BG, PURPLE,
                       'app_ratings_node', 'Google Play & iTunes API')

        x1, y1 = self.s(360, 332)
        x2, y2 = self.s(360, 350)
        self.arrow(c, x1, y1, x2, y2)

        # retrieval
        self.node_rect(c, 230, 350, 260, 50, GREEN_BG, GREEN,
                       'retrieval_node', 'Tavily Search · URL dedup')

        x1, y1 = self.s(360, 400)
        x2, y2 = self.s(360, 418)
        self.arrow(c, x1, y1, x2, y2)

        # web_enrichment
        self.node_rect(c, 230, 418, 260, 50, GREEN_BG, GREEN,
                       'web_enrichment_node', 'Direct URLs · Wikipedia')

        x1, y1 = self.s(360, 468)
        x2, y2 = self.s(360, 486)
        self.arrow(c, x1, y1, x2, y2)

        # firecrawl_scraper
        self.node_rect(c, 230, 486, 260, 50, PURPLE_BG, PURPLE,
                       'firecrawl_node', 'Firecrawl · Top 20 URLs')

        x1, y1 = self.s(360, 536)
        x2, y2 = self.s(360, 554)
        self.arrow(c, x1, y1, x2, y2)

        # ingest
        self.node_rect(c, 230, 554, 260, 50, PURPLE_BG, PURPLE,
                       'ingest_node', 'Chunk → Extract → Normalize')

        x1, y1 = self.s(360, 604)
        x2, y2 = self.s(360, 622)
        self.arrow(c, x1, y1, x2, y2)

        # adjudication
        self.node_rect(c, 230, 622, 260, 50, ORANGE_BG, ORANGE,
                       'adjudication_node', 'Conflict Detection & Debate')

        x1, y1 = self.s(360, 672)
        x2, y2 = self.s(360, 690)
        self.arrow(c, x1, y1, x2, y2)

        # narration
        self.node_rect(c, 230, 690, 260, 50, ORANGE_BG, ORANGE,
                       'narrator_node', 'Gemini · 600–900 word brief')

        x1, y1 = self.s(360, 740)
        x2, y2 = self.s(360, 758)
        self.arrow(c, x1, y1, x2, y2)

        # END circle
        ex, ey = self.s(360, 778)
        c.setFillColor(PRIMARY)
        c.circle(ex, ey, 14 * self.DRAW_W / self.SVG_W, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont('Helvetica-Bold', 7)
        c.drawCentredString(ex, ey - 2.5, 'END')

    def wrap(self, *args):
        return (self.width, self.height)


# ─── CONFLICT TREE ───────────────────────────────────────────────────────────

class ConflictTree(Flowable):
    SVG_W, SVG_H = 720, 560
    DRAW_W = CONTENT_W
    DRAW_H = 400

    def __init__(self):
        super().__init__()
        self.width  = self.DRAW_W
        self.height = self.DRAW_H

    def s(self, x, y):
        sx = x * self.DRAW_W / self.SVG_W
        sy = self.DRAW_H - (y * self.DRAW_H / self.SVG_H)
        return sx, sy

    def diamond(self, c, cx, cy, hw, hh, fill, stroke, text):
        rx, ry = self.s(cx, cy)
        rhw = hw * self.DRAW_W / self.SVG_W
        rhh = hh * self.DRAW_H / self.SVG_H
        c.setFillColor(fill)
        c.setStrokeColor(stroke)
        c.setLineWidth(1.2)
        p = c.beginPath()
        p.moveTo(rx, ry + rhh)
        p.lineTo(rx + rhw, ry)
        p.lineTo(rx, ry - rhh)
        p.lineTo(rx - rhw, ry)
        p.close()
        c.drawPath(p, fill=1, stroke=1)
        c.setFillColor(stroke)
        c.setFont('Helvetica-Bold', 8)
        c.drawCentredString(rx, ry - 3, text)

    def box(self, c, x, y, w, h, fill, stroke, text, subtext=None, bold=False):
        rx, ry2 = self.s(x, y)
        rx2, ry1 = self.s(x + w, y + h)
        rw, rh = rx2 - rx, ry2 - ry1
        c.setFillColor(fill)
        c.setStrokeColor(stroke)
        c.setLineWidth(1.2)
        c.roundRect(rx, ry1, rw, rh, 4, fill=1, stroke=1)
        c.setFillColor(stroke)
        fn = 'Helvetica-Bold' if bold else 'Helvetica'
        c.setFont(fn, 8)
        c.drawCentredString(rx + rw / 2, ry1 + rh * (0.65 if subtext else 0.35), text)
        if subtext:
            c.setFont('Helvetica', 7)
            c.setFillColor(GRAY)
            c.drawCentredString(rx + rw / 2, ry1 + rh * 0.2, subtext)

    def arr(self, c, x1, y1, x2, y2, color=GRAY):
        rx1, ry1 = self.s(x1, y1)
        rx2, ry2 = self.s(x2, y2)
        c.setStrokeColor(color)
        c.setLineWidth(0.8)
        c.line(rx1, ry1, rx2, ry2)
        angle = math.atan2(ry2 - ry1, rx2 - rx1)
        size = 4
        ax1 = rx2 - size * math.cos(angle - 0.4)
        ay1 = ry2 - size * math.sin(angle - 0.4)
        ax2 = rx2 - size * math.cos(angle + 0.4)
        ay2 = ry2 - size * math.sin(angle + 0.4)
        c.setFillColor(color)
        p = c.beginPath()
        p.moveTo(rx2, ry2)
        p.lineTo(ax1, ay1)
        p.lineTo(ax2, ay2)
        p.close()
        c.drawPath(p, fill=1, stroke=0)

    def draw(self):
        c = self.canv

        # Title
        tx, ty = self.s(360, 22)
        c.setFillColor(PRIMARY)
        c.setFont('Helvetica-Bold', 11)
        c.drawCentredString(tx, ty - 5, '5-Step Conflict Resolution Ladder')

        # Step 1
        self.diamond(c, 200, 65, 90, 25, GREEN_BG, GREEN, 'Identical values?')
        self.arr(c, 290, 65, 355, 65, GREEN)
        self.box(c, 360, 50, 190, 30, GREEN_BG, GREEN, 'Auto-resolve (no LLM call)', bold=True)
        lx, ly = self.s(296, 70)
        c.setFillColor(GREEN); c.setFont('Helvetica', 7); c.drawString(lx, ly, 'YES')

        self.arr(c, 200, 40, 200, 105)
        lx, ly = self.s(205, 75)
        c.setFillColor(GRAY); c.setFont('Helvetica', 7); c.drawString(lx, ly, 'NO')

        # Step 2
        self.diamond(c, 200, 155, 90, 25, GREEN_BG, GREEN, 'Confidence gap > 0.20?')
        self.arr(c, 290, 155, 355, 155, GREEN)
        self.box(c, 360, 140, 190, 30, GREEN_BG, GREEN, 'Auto-resolve to stronger claim', bold=True)
        lx, ly = self.s(296, 160)
        c.setFillColor(GREEN); c.setFont('Helvetica', 7); c.drawString(lx, ly, 'YES')

        self.arr(c, 200, 130, 200, 195)
        lx, ly = self.s(205, 165)
        c.setFillColor(GRAY); c.setFont('Helvetica', 7); c.drawString(lx, ly, 'NO')

        # Step 3
        self.diamond(c, 200, 245, 90, 25, AMBER_BG, AMBER, 'Field strategy set?')
        self.arr(c, 290, 245, 355, 245, AMBER)
        self.box(c, 360, 230, 190, 30, AMBER_BG, AMBER,
                 'Deterministic merge', 'range/union/recency/vote', bold=True)
        lx, ly = self.s(296, 250)
        c.setFillColor(AMBER); c.setFont('Helvetica', 7); c.drawString(lx, ly, 'YES')

        self.arr(c, 200, 220, 200, 290)
        lx, ly = self.s(205, 255)
        c.setFillColor(GRAY); c.setFont('Helvetica', 7); c.drawString(lx, ly, 'NO')

        # Step 4
        self.diamond(c, 200, 335, 90, 25, TEAL_BG, TEAL, 'Complementary?')
        self.arr(c, 290, 335, 355, 335, TEAL)
        self.box(c, 360, 320, 190, 30, TEAL_BG, TEAL, 'Synthesize MERGE (1 Groq call)', bold=True)
        lx, ly = self.s(296, 340)
        c.setFillColor(TEAL); c.setFont('Helvetica', 7); c.drawString(lx, ly, 'YES')

        self.arr(c, 200, 310, 200, 395)
        lx, ly = self.s(205, 350)
        c.setFillColor(GRAY); c.setFont('Helvetica', 7); c.drawString(lx, ly, 'NO')

        # Step 5 — Adversarial Debate
        self.box(c, 100, 415, 200, 60, PRIMARY_BG, PRIMARY,
                 'Adversarial Debate', 'Advocate A vs B · Judge', bold=True)
        self.arr(c, 300, 445, 355, 445, PRIMARY)
        self.box(c, 360, 430, 190, 30, PRIMARY_BG, PRIMARY, 'Verdict: A / B / MERGE')
        self.arr(c, 455, 430, 455, 510)
        self.box(c, 360, 510, 190, 30, RED_BG, RED, 'FLAG → human_review_queue')

    def wrap(self, *args):
        return (self.width, self.height)


# ─── SEQUENCE DIAGRAM ────────────────────────────────────────────────────────

class SequenceDiagram(Flowable):
    def __init__(self, width=CONTENT_W, height=480):
        super().__init__()
        self.width  = width
        self.height = height

    def draw(self):
        c = self.canv
        w = self.width
        h = self.height

        actors = ['User', 'Frontend', 'FastAPI', 'LangGraph', 'Gemini', 'Tavily', 'Firecrawl', 'SQLite']
        n = len(actors)
        step = w / n
        centers = [step * i + step / 2 for i in range(n)]
        box_h = 20
        box_w = min(step - 4, 62)

        actor_y = h - box_h - 2

        # Draw actor boxes
        for i, (name, cx) in enumerate(zip(actors, centers)):
            c.setFillColor(PRIMARY)
            c.setStrokeColor(PRIMARY)
            c.roundRect(cx - box_w/2, actor_y, box_w, box_h, 3, fill=1, stroke=0)
            c.setFillColor(white)
            c.setFont('Helvetica-Bold', 7)
            c.drawCentredString(cx, actor_y + 6, name)

        # Lifelines
        ll_top = actor_y - 1
        ll_bot = 5
        for cx in centers:
            c.setStrokeColor(GRAY_BD)
            c.setLineWidth(0.5)
            c.setDash([3, 3])
            c.line(cx, ll_top, cx, ll_bot)
        c.setDash([])

        def msg_arrow(from_i, to_i, y, label, color=GRAY, dashed=False, self_loop=False):
            x1 = centers[from_i]
            x2 = centers[to_i]
            c.setStrokeColor(color)
            c.setLineWidth(0.8)
            if dashed:
                c.setDash([3, 3])
            if self_loop:
                lp_w = step * 0.4
                c.line(x1, y, x1 + lp_w, y)
                c.line(x1 + lp_w, y, x1 + lp_w, y - 10)
                c.line(x1 + lp_w, y - 10, x1, y - 10)
                c.setDash([])
                # arrowhead
                c.setFillColor(color)
                p = c.beginPath()
                p.moveTo(x1, y - 10)
                p.lineTo(x1 + 5, y - 7)
                p.lineTo(x1 + 5, y - 13)
                p.close()
                c.drawPath(p, fill=1, stroke=0)
                c.setFillColor(TEXT_SEC)
                c.setFont('Helvetica', 7)
                c.drawString(x1 + 3, y + 2, label)
                return
            c.line(x1, y, x2, y)
            c.setDash([])
            # arrowhead
            angle = math.atan2(0, x2 - x1)
            size = 4
            ax1 = x2 - size * math.cos(angle - 0.4)
            ay1 = y - size * math.sin(angle - 0.4)
            ax2 = x2 - size * math.cos(angle + 0.4)
            ay2 = y - size * math.sin(angle + 0.4)
            c.setFillColor(color)
            p = c.beginPath()
            p.moveTo(x2, y)
            p.lineTo(ax1, ay1)
            p.lineTo(ax2, ay2)
            p.close()
            c.drawPath(p, fill=1, stroke=0)
            # label
            mid_x = (x1 + x2) / 2
            c.setFillColor(TEXT_SEC)
            c.setFont('Helvetica', 7)
            c.drawCentredString(mid_x, y + 2, label)

        def alt_box(y_top, y_bot, label):
            c.setStrokeColor(GRAY_BD)
            c.setLineWidth(0.6)
            c.setDash([4, 2])
            c.rect(4, y_bot, w - 8, y_top - y_bot, fill=0, stroke=1)
            c.setDash([])
            c.setFillColor(GRAY)
            c.setFont('Helvetica', 7)
            c.drawString(8, y_top - 9, label)

        # Messages — y positions from top (high y_rl)
        msgs = [
            (0, 1, h - 30,  'Enter program name'),
            (1, 2, h - 50,  'POST /api/run'),
            (2, 3, h - 70,  'start thread'),
            (3, 4, h - 90,  'validate identity'),
            (4, 3, h - 110, 'ValidationResult'),
        ]
        for f, t, y, lbl in msgs:
            msg_arrow(f, t, y, lbl)

        # alt[needs_clarification]
        alt_box(h - 120, h - 160, '[needs_clarification]')
        msg_arrow(3, 1, h - 135, 'clarification_needed')
        msg_arrow(1, 2, h - 150, 'POST /clarify')

        # alt[cache hit]
        alt_box(h - 165, h - 200, '[cache hit]')
        msg_arrow(3, 7, h - 178, 'find_program_snapshot')
        msg_arrow(7, 3, h - 193, 'snapshot', dashed=True)

        # Main fresh run
        alt_box(h - 205, h - 355, '[fresh run]')
        msg_arrow(3, 4, h - 215, 'generate queries')
        msg_arrow(3, 5, h - 232, 'retrieve URLs')
        msg_arrow(3, 6, h - 249, 'scrape pages')
        msg_arrow(3, 4, h - 266, 'extract fields')
        msg_arrow(3, 3, h - 283, 'adjudicate + debate (Groq)', self_loop=True)
        msg_arrow(3, 4, h - 305, 'narrate brief')
        msg_arrow(3, 7, h - 322, 'save snapshot')

        # Polling
        msg_arrow(1, 2, h - 360, 'GET /api/run/{id} (poll)')
        msg_arrow(2, 1, h - 377, 'status=done, brief', dashed=True)

        # Converse
        msg_arrow(0, 1, h - 400, 'question via POST /converse')
        msg_arrow(3, 3, h - 417, 'answer from field_report', self_loop=True)
        msg_arrow(1, 0, h - 440, 'ConverseAnswer', dashed=True)

    def wrap(self, *args):
        return (self.width, self.height)


# ─── DOCUMENT BUILDER ────────────────────────────────────────────────────────

def build_document():
    doc = SimpleDocTemplate(
        r'C:\Users\shreeram\Documents\kobi\docs\ARCHITECTURE_AND_DESIGN.pdf',
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title='Kobie — Architecture & Design Document',
        author='Kobie',
        subject='Autonomous Competitive Intelligence Agent for Loyalty Programs',
    )
    story = []

    # ── COVER ────────────────────────────────────────────────────────────────
    story.append(CoverPage())
    story.append(PageBreak())

    # ── SECTION 1: PROJECT OVERVIEW ──────────────────────────────────────────
    story.append(KeepTogether([
        *section_title('01', 'Project Overview'),
        body(
            'Kobie is an autonomous competitive-intelligence agent that researches customer loyalty programs '
            '(airline, hotel, retail, etc.) and produces analyst-grade, evidence-grounded briefs.'
        ),
    ]))
    story.append(spacer(10))

    # Capability cards: 3×2 grid
    def cap_card(num, title, desc, bg=PRIMARY_BG, border=PRIMARY):
        return Table(
            [[Paragraph(f'<font color="white"><b>{num}</b></font>',
                        ParagraphStyle('num', fontSize=10, fontName='Helvetica-Bold', textColor=white,
                                       backColor=border, leading=14, alignment=TA_CENTER)),
              [Paragraph(title, S_CARD_TITLE), Paragraph(desc, S_CARD_BODY)]]],
            colWidths=[22, CONTENT_W / 2 - 28],
        )

    cap_data = [
        ('1', 'Input Resolution',
         'LLM-backed identity validator resolves ambiguous program names via Gemini; max 3 clarification rounds.'),
        ('2', 'Research Planning',
         'Up to 15 targeted search queries planned across 10 source types (official, financial, review, forum, app_reviews, etc.).'),
        ('3', 'Evidence Extraction',
         'Schema-grounded facts per SCHEMA_FIELD_PATHS; per-field confidence, source URL, and EXTRACTED/NOT_FOUND/AMBIGUOUS status.'),
        ('4', 'Conflict Adjudication',
         '5-step ladder: identical-value short-circuit → confidence gap → field-type deterministic merge → adversarial debate.'),
        ('5', 'Narrative Synthesis',
         '600–900 word analyst brief from adjudicated FieldReport entries, organized by 8 schema categories.'),
        ('6', 'Grounded Q&A',
         'Conversational interface strictly from final_brief + field_report; all answers traceable to extracted evidence.'),
    ]

    def make_card_cell(num, title, desc):
        inner = Table(
            [[Paragraph(f'<b>{num}</b>',
                        ParagraphStyle('cn', fontSize=10, fontName='Helvetica-Bold',
                                       textColor=white, alignment=TA_CENTER)),
              [Paragraph(title, S_CARD_TITLE), Paragraph(desc, S_CARD_BODY)]]],
            colWidths=[20, CONTENT_W/2 - 32],
        )
        inner.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (0, 0), PRIMARY),
            ('BACKGROUND',    (1, 0), (1, 0), white),
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING',    (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING',   (0, 0), (0, 0), 0),
            ('RIGHTPADDING',  (0, 0), (0, 0), 4),
            ('LEFTPADDING',   (1, 0), (1, 0), 6),
        ]))
        outer = Table([[inner]], colWidths=[CONTENT_W/2 - 8])
        outer.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), PRIMARY_BG),
            ('LEFTBORDER',    (0, 0), (0, 0),   3, PRIMARY),
            ('BOX',           (0, 0), (-1, -1), 0.5, PRIMARY_BD),
            ('TOPPADDING',    (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('LEFTPADDING',   (0, 0), (-1, -1), 0),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
        ]))
        return outer

    card_rows = []
    for i in range(0, len(cap_data), 2):
        row = []
        for j in range(2):
            if i + j < len(cap_data):
                num, title, desc = cap_data[i + j]
                row.append(make_card_cell(num, title, desc))
            else:
                row.append('')
        card_rows.append(row)

    cap_tbl = Table(card_rows, colWidths=[CONTENT_W/2 - 4, CONTENT_W/2 - 4], hAlign='LEFT')
    cap_tbl.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 2),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 2),
    ]))
    story.append(cap_tbl)
    story.append(spacer(10))
    story.append(callout(
        '<b>Implementation:</b> FastAPI backend (server.py) · LangGraph pipeline (pipeline/graph.py) '
        '· SQLite persistence (core/db.py) · Next.js 14 frontend (frontend/)', 'gray'))
    story.append(spacer(12))

    # ── SECTION 2: PROBLEM STATEMENT ─────────────────────────────────────────
    story.append(KeepTogether([
        *section_title('02', 'Problem Statement'),
        body(
            'Customer loyalty programs present a unique data challenge for competitive analysts. '
            'Information is distributed across official program pages, financial disclosures, travel blogs, '
            'forum threads, and app stores — each with varying accuracy and recency. Four core problems compound this difficulty:'
        ),
        spacer(8),
    ]))

    problems = [
        ('Fragmented', RED, RED_BG,
         'No single authoritative source covers all program mechanics. Data spans official pages, '
         'app stores, financial filings, and user forums.'),
        ('Volatile', AMBER, AMBER_BG,
         'Earn rates, tier thresholds, and point valuations change frequently. '
         'HIGH_VOLATILITY_FIELDS in core/schemas.py require recency-aware adjudication.'),
        ('Contradictory', ORANGE, ORANGE_BG,
         'Official pages vs. blogs vs. forums frequently disagree on the same fact, '
         'requiring systematic conflict detection and resolution.'),
        ('Expensive to Verify', VIOLET, VIOLET_BG,
         'Analysts must cross-reference many pages per program and adjudicate disagreements by hand — '
         'a process Kobie automates end-to-end.'),
    ]

    def prob_cell(title, color, bg, desc):
        # Stacked: title row, then description row (1 column each)
        t = Table(
            [[Paragraph(f'<b>{title}</b>',
                        ParagraphStyle('ph', fontSize=11, fontName='Helvetica-Bold',
                                       textColor=color, leading=14))],
             [Paragraph(desc, S_CARD_BODY)]],
            colWidths=[CONTENT_W/2 - 24],
        )
        t.setStyle(TableStyle([
            ('TOPPADDING',    (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ('LEFTPADDING',   (0,0), (-1,-1), 0),
            ('RIGHTPADDING',  (0,0), (-1,-1), 0),
        ]))
        outer = Table([[t]], colWidths=[CONTENT_W/2 - 8])
        outer.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,-1), bg),
            ('BOX',           (0,0), (-1,-1), 0.5, color),
            ('LINEBEFORE',    (0,0), (0,-1),  3, color),
            ('TOPPADDING',    (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING',   (0,0), (-1,-1), 8),
            ('RIGHTPADDING',  (0,0), (-1,-1), 8),
        ]))
        return outer

    prob_rows = [
        [prob_cell(*problems[0]), prob_cell(*problems[1])],
        [prob_cell(*problems[2]), prob_cell(*problems[3])],
    ]
    prob_tbl = Table(prob_rows, colWidths=[CONTENT_W/2 - 4, CONTENT_W/2 - 4])
    prob_tbl.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 2),
        ('RIGHTPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(prob_tbl)
    story.append(spacer(10))
    story.append(callout(
        '<b>Design constraint (README.md):</b> Never use LLM training memory as a source of loyalty-program facts. '
        'Every supported claim must carry a source_url and be traceable to scraped content.', 'red'))
    story.append(spacer(12))

    # ── SECTION 3: OBJECTIVES ─────────────────────────────────────────────────
    story.append(KeepTogether(section_title('03', 'Objectives')))

    objectives = [
        ('1', 'Input Resolution',
         'Resolve ambiguous/partial input to one canonical identity; max 3 clarification rounds, 5-min timeout each.'),
        ('2', 'Research Planning',
         'Plan and execute up to 15 targeted queries per program across 10 source types.'),
        ('3', 'Evidence Extraction',
         'Extract EXTRACTED/NOT_FOUND/AMBIGUOUS facts with per-field confidence and source attribution.'),
        ('4', 'Conflict Resolution',
         'Detect and resolve conflicts via cheapest-sufficient strategy ladder.'),
        ('5', 'Brief + Q&A',
         '600–900 word analyst brief; grounded Q&A traceable to field_report entries.'),
        ('6', 'Comparison Mode',
         'Side-by-side comparison with category-level verdicts and comparison brief.'),
        ('7', 'Reliability & Caching',
         'Track per-stage cost (tokens/USD), cache completed runs, survive process restarts.'),
    ]

    def obj_cell(num, title, desc):
        inner = Table(
            [[Paragraph(f'<b>{num}</b>',
                        ParagraphStyle('on', fontSize=10, fontName='Helvetica-Bold',
                                       textColor=white, alignment=TA_CENTER)),
              [Paragraph(title, S_CARD_TITLE), Paragraph(desc, S_CARD_BODY)]]],
            colWidths=[20, CONTENT_W/2 - 32],
        )
        inner.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (0,0), PRIMARY),
            ('VALIGN',        (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING',    (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING',   (0,0), (0,0), 0),
            ('RIGHTPADDING',  (0,0), (0,0), 4),
            ('LEFTPADDING',   (1,0), (1,0), 6),
        ]))
        return inner

    obj_rows = []
    for i in range(0, len(objectives), 2):
        row = []
        for j in range(2):
            if i + j < len(objectives):
                row.append(obj_cell(*objectives[i+j]))
            else:
                row.append('')
        obj_rows.append(row)

    obj_tbl = Table(obj_rows, colWidths=[CONTENT_W/2, CONTENT_W/2])
    obj_tbl.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [white, GRAY_LT]),
    ]))
    story.append(obj_tbl)
    story.append(spacer(12))

    # ── SECTION 4: HIGH-LEVEL ARCHITECTURE ───────────────────────────────────
    story.append(KeepTogether([
        *section_title('04', 'High-Level Architecture'),
        subsection_title('Architecture Layers'),
        spacer(6),
        ArchitectureDiagram(),
    ]))
    story.append(spacer(12))

    # ── SECTION 5: END-TO-END DATA FLOW ──────────────────────────────────────
    story.append(KeepTogether(section_title('05', 'End-to-End Data Flow')))

    steps = [
        ('1',  'Submission',         'User submits a loyalty program name via the Next.js frontend. POST /api/run creates a RunRecord in STORE with status=pending.'),
        ('2',  'Validation',         'input_validator_node calls Gemini to resolve the program identity. Returns ValidationResult with status (resolved/ambiguous/rejected).'),
        ('3',  'Cache Check',        'After validation, the pipeline checks run_snapshots for a prior completed run for the same canonical program. If found, the snapshot is replayed.'),
        ('4',  'Query Generation',   'query_generator_node calls Gemini to plan up to 15 targeted search queries across 10 source types.'),
        ('5',  'App Ratings Prefetch','app_ratings_node fetches Google Play Store and Apple iTunes ratings for the program app in parallel.'),
        ('6',  'Retrieval',          'retrieval_node submits queries to Tavily Search, deduplicates URLs, and stores SourceRecord rows in the database.'),
        ('7',  'Web Enrichment',     'web_enrichment_node fetches direct URLs and Wikipedia pages identified during query planning.'),
        ('8',  'Firecrawl Scraping', 'firecrawl_node passes the top 20 URLs (by Tavily score) to the Firecrawl API for full-page markdown extraction.'),
        ('9',  'Ingestion',          'ingest_node chunks all page content, calls Gemini to extract schema fields per chunk, and normalises raw claims into the claims table.'),
        ('10', 'Adjudication',       'adjudication_node groups claims by field, detects conflicts, and resolves them via the 5-step cheapest-sufficient ladder.'),
        ('11', 'Narration',          'narrator_node calls Gemini to produce a 600–900 word analyst brief from adjudicated FieldReport entries.'),
        ('12', 'Persistence & Caching','All data is saved to SQLite. A run_snapshot is written for future cache hits.'),
        ('13', 'Conversation',       'The user can ask questions via POST /converse. Answers are grounded strictly in final_brief + field_report.'),
        ('14', 'Comparison Mode',    'POST /api/run with two programs triggers sequential pipeline runs, then a comparison brief with category-level verdicts.'),
    ]

    def step_row(num, title, desc, bg=white):
        circle = Table(
            [[Paragraph(f'<b>{num}</b>',
                        ParagraphStyle('sn', fontSize=9, fontName='Helvetica-Bold',
                                       textColor=white, alignment=TA_CENTER))]],
            colWidths=[22], rowHeights=[22],
        )
        circle.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), PRIMARY),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        content = [Paragraph(f'<b>{title}</b>', S_TL_TITLE), Paragraph(desc, S_TL_DESC)]
        row_tbl = Table([[circle, content]], colWidths=[28, CONTENT_W - 28])
        row_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), bg),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ]))
        return row_tbl

    for i, (num, title, desc) in enumerate(steps):
        bg = white if i % 2 == 0 else GRAY_LT
        story.append(step_row(num, title, desc, bg))
    story.append(spacer(12))

    # ── SECTION 6: SYSTEM COMPONENTS ─────────────────────────────────────────
    story.append(KeepTogether(section_title('06', 'System Components')))

    comp_headers = ['Component', 'File(s)', 'Responsibility']
    comp_rows = [
        ('FastAPI Server',        'server.py',                                      'HTTP API, RunRecord management, STORE dict, clarification/cache threading events'),
        ('LangGraph Graph',       'pipeline/graph.py',                              'Node registration, conditional edges, graph compilation; also direct node invocation for server.py'),
        ('Input Validator',       'pipeline/stages/validation.py',                  'Gemini-backed program identity resolution; clarification loop up to 3 rounds, 5-min timeout'),
        ('Query Generator',       'pipeline/stages/query_generator.py',             'Gemini query planning; up to 15 queries across 10 source types with field_query_map'),
        ('App Ratings',           'pipeline/stages/app_ratings_fetcher.py',         'Google Play Scraper + iTunes Search API; prefetch before Tavily to save budget'),
        ('Retrieval',             'pipeline/stages/retrieval.py',                   'Tavily Search; URL canonicalisation and deduplication into SourceRecord list'),
        ('Web Enrichment',        'pipeline/stages/direct_url_seeder.py\n+ wikipedia_fetcher.py', 'Seeds high-confidence direct URLs; Wikipedia summary — both non-fatal, zero Tavily budget'),
        ('Firecrawl Scraper',     'pipeline/stages/firecrawl_scraper.py',           'Firecrawl API; round-robin top-20 URL selection; partial failure tolerant'),
        ('Ingest Node',           'pipeline/nodes/ingest_node.py\n+ chunker.py, extractor.py, normalizer.py', 'Raw store → chunk → Gemini extraction → normalise → FieldReport'),
        ('Conflict Adjudicator',  'pipeline/adjudication/conflict_adjudicator.py',  '5-step resolution ladder; FIELD_STRATEGY_MAP; debate dispatch; FLAG → human_review_queue'),
        ('Debate Engine',         'pipeline/adjudication/debate_engine.py',         'Groq advocate/judge calls; cosine similarity gate; key pool; 401 eviction'),
        ('Narrator',              'pipeline/stages/narration.py',                   'Gemini brief synthesis (600–900 words) from adjudicated FieldReport'),
        ('Database Layer',        'core/db.py',                                     'SQLite WAL DDL (12 tables); connect/checkpoint; WAL-safe write lock'),
        ('Schemas',               'core/schemas.py',                                'AgentState TypedDict, Pydantic models, SCHEMA_FIELD_PATHS, HIGH_VOLATILITY_FIELDS'),
        ('Cost Tracker',          'core/cost_tracker.py',                           'Per-provider/stage token counts and USD pricing constants'),
        ('Extractor',             'pipeline/stages/extractor.py',                   'Active runtime; heuristic chunk scoring; supersedes legacy extraction.py'),
        ('Frontend',              'frontend/',                                       'Next.js 14 / React 18; TanStack Query polling; PDF export via @react-pdf/renderer'),
        ('Verification',          'pipeline/stages/verification.py',                'Standalone confidence scoring; candidate for merge with conflict_adjudicator.py'),
    ]
    story.append(make_table(comp_headers, comp_rows, col_widths=[90, 140, 285]))
    story.append(spacer(12))

    # ── SECTION 7: TECHNOLOGY STACK ───────────────────────────────────────────
    story.append(KeepTogether(section_title('07', 'Technology Stack')))

    tech_headers = ['Layer', 'Technology', 'Justification']
    tech_rows = [
        ('Backend API',      'FastAPI 0.111',          'Async-first; native background tasks; automatic OpenAPI docs'),
        ('Agent Orchestration','LangGraph',             'Node-based graph with typed state; supports conditional edges and mid-graph pause/resume'),
        ('AI — Extraction',  'Google Gemini 2.5 Flash','Large context window (1M tokens); low cost per token for high-volume chunk extraction'),
        ('AI — Debate',      'Groq llama-3.3-70b',    'Low-latency inference; free-tier key pool spreads rate limits across burst periods'),
        ('Web Search',       'Tavily Search API',      'Purpose-built for LLM agents; returns pre-filtered results with source scores'),
        ('Web Scraping',     'Firecrawl',              'Handles JS-rendered pages; returns clean markdown; async batch support'),
        ('App Ratings',      'Google Play + iTunes',   'Official store APIs for live app rating data; no scraping required'),
        ('Database',         'SQLite 3 + WAL',         'Zero-ops deployment; WAL journal mode gives adequate read/write concurrency'),
        ('Data Validation',  'Pydantic v2',            'Runtime type validation for all agent state, API request/response, and schema models'),
        ('Frontend',         'Next.js 14 / React 18',  'App Router; server components; TanStack Query for polling; Tailwind CSS'),
        ('HTTP Client',      'httpx + aiohttp',        'Async HTTP for enrichment and app rating fetches'),
        ('Process Comms',    'threading.Event + Lock', 'Clarification and cache-hit pauses; STORE guarded by STORE_LOCK'),
        ('Environment',      'python-dotenv',          'API key injection with reject_placeholders=True guard'),
        ('Logging',          'Python logging + FileHandler','Per-component log files: backend.log, debate_debug.log, frontend.log'),
    ]
    story.append(make_table(tech_headers, tech_rows, col_widths=[90, 110, 315]))
    story.append(spacer(12))

    # ── SECTION 8: DATABASE & DATA MODELS ─────────────────────────────────────
    story.append(KeepTogether([
        *section_title('08', 'Database & Data Models'),
        subsection_title('8.1 Persistence Layer'),
    ]))

    db_headers = ['Table', 'Purpose']
    db_rows = [
        ('run_snapshots',      'Cache of completed runs keyed by program_name_normalized; stores full AgentState as JSON for instant replay'),
        ('runs',               'Run history index: run_id, mode, status, data_quality, run_state_json — survives process restarts'),
        ('program_identities', 'Resolved ProgramIdentity records: name, brand, domain, country, confidence, status'),
        ('sources',            'URL-level metadata: canonical_url, source_type, authority_score, fetched_at, http_status'),
        ('pages',              'Cleaned page text per URL: title, cleaned_text, token_count, sanitizer_flags'),
        ('chunks',             'Text chunks from pages: chunk_index, text, token_count, embedding_hash (forward-compatible)'),
        ('claims',             'Extracted field claims: field_path, value_json, status, confidence, source_url, access_date'),
        ('conflicts',          'Conflict records: field_path, strategy used, resolution status, judge reasoning, confidence'),
        ('briefs',             'Final brief output per run: text, word_count, cited claim IDs, entailment flag'),
        ('conversations',      'Q&A turn log per run: question, answer, citations, timestamp'),
        ('raw_documents',      'Post-Firecrawl documents keyed by url_hash: markdown content, source_authority, metadata'),
        ('normalized_packets', 'Normalised extraction packets: identity_hash × source_url × chunk_id → structured fields'),
    ]
    story.append(make_table(db_headers, db_rows, col_widths=[120, 395]))
    story.append(spacer(8))
    story.append(callout(
        '<b>connect()</b> opens with PRAGMA journal_mode=WAL and 5s busy timeout. '
        '<b>checkpoint()</b> runs PRAGMA wal_checkpoint(TRUNCATE) on FastAPI shutdown so committed data '
        'survives even if the -wal/-shm files are lost.', 'blue'))
    story.append(spacer(10))

    story.append(subsection_title('8.2 Schema Field Categories'))

    field_cats = [
        ('program_basics',
         'program_name · brand · industry · program_type · geography · membership_count · ownership_or_parent_company · launch_or_rebrand_history'),
        ('earn_mechanics',
         'base_earn_rate · earn_rate_unit · bonus_categories · co_brand_card_earn · partner_earn · non_transactional_earn · earning_exclusions'),
        ('burn_mechanics',
         'redemption_options · redemption_thresholds · point_value_cpp · cash_equivalent_value · expiry_policy · blackout_or_capacity_rules · transfer_options'),
        ('tier_system',
         'tier_names · qualification_criteria · tier_thresholds · qualification_period · tier_benefits · soft_landing_or_status_match · elite_bonus'),
        ('partnerships',
         'partner_names · partnership_type · details · partner_category · earn_details · burn_details · transfer_ratios · discontinued_partners'),
        ('digital_experience',
         'mobile_app_available · app_ratings · app_store_rating · play_store_rating · personalization_features · gamification_features · digital_wallet_or_card_linking · app_pain_points'),
        ('member_sentiment',
         'ratings · common_praise · common_complaints · complaint_frequency · sources_checked · review_sources_checked · forum_sources_checked · sentiment_summary'),
        ('competitive_position',
         'key_differentiators · weaknesses · closest_competitors'),
    ]

    def field_cat_cell(name, fields):
        t = Table(
            [[Paragraph(f'<b>{name}</b>',
                        ParagraphStyle('fc', fontSize=9.5, fontName='Helvetica-Bold',
                                       textColor=PRIMARY, leading=13))],
             [Paragraph(fields,
                        ParagraphStyle('ff', fontSize=8, fontName='Helvetica',
                                       textColor=TEXT_SEC, leading=12))]],
            colWidths=[CONTENT_W/2 - 12],
        )
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), PRIMARY_BG),
            ('BOX', (0,0), (-1,-1), 0.5, PRIMARY_BD),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        return t

    fc_rows = []
    for i in range(0, len(field_cats), 2):
        row = []
        for j in range(2):
            if i + j < len(field_cats):
                row.append(field_cat_cell(*field_cats[i+j]))
            else:
                row.append('')
        fc_rows.append(row)

    fc_tbl = Table(fc_rows, colWidths=[CONTENT_W/2, CONTENT_W/2])
    fc_tbl.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 2),
        ('RIGHTPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(fc_tbl)
    story.append(spacer(8))
    story.append(callout(
        '<b>High-volatility fields</b> (recency-aware adjudication): base_earn_rate · tier_thresholds · '
        'redemption_thresholds · point_value_cpp · app_ratings · recent_changes_last_6_months', 'amber'))
    story.append(spacer(12))

    # ── SECTION 9: AI AGENT PIPELINE ──────────────────────────────────────────
    story.append(KeepTogether([
        *section_title('09', 'AI Agent Pipeline'),
        subsection_title('9.1 Pipeline Flowchart'),
        spacer(6),
        PipelineFlowchart(),
    ]))
    story.append(spacer(12))

    story.append(KeepTogether([
        subsection_title('9.2 Conflict Resolution Decision Tree'),
        spacer(6),
        ConflictTree(),
    ]))
    story.append(spacer(12))

    # ── SECTION 10: EXTERNAL INTEGRATIONS ─────────────────────────────────────
    story.append(KeepTogether(section_title('10', 'External Integrations')))

    services = [
        ('Google Gemini 2.5 Flash', PRIMARY,
         'validation.py · query_generator.py · extractor.py · narration.py',
         'Identity resolution, query planning, field extraction, brief narration. Large context window (1M tokens).',
         'GEMINI_API_KEY (overridable per stage: INPUT_VERIFIER_*, QUERY_GENERATOR_*, EXTRACTION_*, NARRATION_*)'),
        ('Groq (llama-3.3-70b-versatile)', VIOLET,
         'pipeline/adjudication/debate_engine.py + converse.py',
         'Low-latency adversarial debate (advocate A, B, judge) and interactive grounded Q&A.',
         'GROQ_API_KEYS (round-robin pool); 401 auto-eviction via _remove_client_from_pool'),
        ('Tavily Search API', TEAL,
         'pipeline/stages/retrieval.py',
         'Query-driven URL discovery. 5 results/query, scored and typed. Purpose-built for LLM agents.',
         'TAVILY_API_KEY / TAVILY_API_BASE'),
        ('Firecrawl', ORANGE,
         'pipeline/stages/firecrawl_scraper.py',
         'Full-page markdown/PDF extraction of JS-rendered pages. Top 20 URLs per run. Partial failure tolerant.',
         'FIRECRAWL_API_KEY / FIRECRAWL_API_BASE'),
        ('Google Play Scraper + iTunes', GREEN,
         'pipeline/stages/app_ratings_fetcher.py',
         'Live app ratings prefetched before Tavily retrieval begins. Bypasses scrape budget. Structured data.',
         '(no key required — public APIs)'),
        ('Wikipedia REST API', GRAY,
         'pipeline/stages/wikipedia_fetcher.py',
         'Free company/brand summary injected as synthetic evidence block. Zero search or scrape budget.',
         '(no key required — public API)'),
    ]

    def svc_cell(name, color, files, purpose, config):
        content = [
            Paragraph(f'<b>{name}</b>',
                      ParagraphStyle('sn', fontSize=10, fontName='Helvetica-Bold',
                                     textColor=color, leading=14)),
            Paragraph(f'<b>Used by:</b> {files}',
                      ParagraphStyle('sf', fontSize=8.5, fontName='Helvetica',
                                     textColor=TEXT_SEC, leading=12)),
            Paragraph(f'<b>Purpose:</b> {purpose}',
                      ParagraphStyle('sp', fontSize=8.5, fontName='Helvetica',
                                     textColor=TEXT_SEC, leading=12)),
            Paragraph(f'<b>Config:</b> <font name="Courier">{config}</font>',
                      ParagraphStyle('sc', fontSize=8.5, fontName='Helvetica',
                                     textColor=GRAY, leading=12)),
        ]
        t = Table([[c] for c in content], colWidths=[CONTENT_W/2 - 20])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), white),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))
        outer = Table([[t]], colWidths=[CONTENT_W/2 - 8])
        outer.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), white),
            ('LINEBEFORE', (0,0), (0,-1), 3, color),
            ('BOX', (0,0), (-1,-1), 0.5, GRAY_BD),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        return outer

    svc_rows = []
    for i in range(0, len(services), 2):
        row = []
        for j in range(2):
            if i + j < len(services):
                row.append(svc_cell(*services[i+j]))
            else:
                row.append('')
        svc_rows.append(row)

    svc_tbl = Table(svc_rows, colWidths=[CONTENT_W/2 - 4, CONTENT_W/2 - 4])
    svc_tbl.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 2),
        ('RIGHTPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(svc_tbl)
    story.append(spacer(8))
    story.append(callout(
        '<b>No vector database</b> — chunk selection uses heuristic scoring (extractor.py). '
        'ChunkRef.embedding_hash exists in schema/DDL as a forward-compatible migration path.', 'gray'))
    story.append(spacer(12))

    # ── SECTION 11: SEQUENCE DIAGRAM ──────────────────────────────────────────
    story.append(KeepTogether([
        *section_title('11', 'Sequence Diagram'),
        spacer(6),
        SequenceDiagram(),
    ]))
    story.append(spacer(12))

    # ── SECTION 12: DESIGN DECISIONS & TRADE-OFFS ─────────────────────────────
    story.append(KeepTogether(section_title('12', 'Design Decisions & Trade-offs')))

    dd_headers = ['Decision', 'Rationale', 'Trade-off']
    dd_rows = [
        ('LangGraph invoked directly by server.py',
         'Enables per-stage UI updates, clarification/cache pause, cancellation support',
         'Two execution paths must stay behaviourally consistent'),
        ('Thread-per-run',
         'Simple to reason about; each RunRecord owns its own Lock, Events, stop_event',
         'Does not scale horizontally beyond a single process'),
        ('In-memory STORE + SQLite snapshot',
         'Low-latency polling from memory; completed runs persist across restarts',
         'Any run still running when the process restarts is lost'),
        ('Cheapest-sufficient conflict ladder',
         'Full debate costs 3–5 LLM calls/conflict; most conflicts resolve deterministically',
         'Requires maintaining FIELD_STRATEGY_MAP by hand; wrong strategy suppresses a real debate'),
        ('Debate advocates see only structured metadata',
         'Prevents re-hallucination of training-data facts; keeps arguments auditable',
         'Quality bounded by how well metadata captures the actual disagreement'),
        ('Gemini for extraction, Groq for debate',
         'Splits cost/latency profiles: Gemini cheap for per-chunk extraction; Groq fast for debate',
         'Two provider integrations; two sets of rate limits and keys'),
        ('Round-robin Groq key pool with 401 eviction',
         'Free-tier limits crash under concurrent debate bursts; spreading across keys prevents stalling',
         'Pool management complexity; pool must be reset per run to avoid stale event-loop binding'),
        ('No vector DB',
         'Query-plan-driven Tavily + heuristic scoring sufficient for the fixed schema; kept system dependency-light',
         'Can miss relevant text that semantic search would surface; embedding_hash unused'),
        ('SQLite over client-server DB',
         'Zero-ops single-node deployment; WAL gives adequate concurrency',
         'Not suitable for multi-instance deployment; WAL journal files are a known failure point'),
    ]
    story.append(make_table(dd_headers, dd_rows, col_widths=[120, 190, 205]))
    story.append(spacer(12))

    # ── SECTION 13: SCALABILITY, RELIABILITY, SECURITY & OBSERVABILITY ────────
    story.append(KeepTogether(section_title('13', 'Scalability, Reliability, Security & Observability')))

    def obs_card(title, color, items):
        bullets = ''.join(f'• {item}<br/>' for item in items)
        content = [
            Paragraph(f'<b>{title}</b>',
                      ParagraphStyle('oh', fontSize=11, fontName='Helvetica-Bold',
                                     textColor=color, leading=14)),
            Paragraph(bullets,
                      ParagraphStyle('ob', fontSize=9, fontName='Helvetica',
                                     textColor=TEXT_SEC, leading=13)),
        ]
        t = Table([[c] for c in content], colWidths=[CONTENT_W/2 - 20])
        t.setStyle(TableStyle([
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ]))
        outer = Table([[t]], colWidths=[CONTENT_W/2 - 8])
        outer.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 0.8, color),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        return outer

    cards_13 = [
        obs_card('Scalability', PRIMARY, [
            'Single-process / single-node: STORE is an in-memory dict guarded by STORE_LOCK',
            'Thread-per-run; compare-mode runs programs sequentially',
            'Horizontal scaling path: externalize STORE to Redis, move execution to Celery/RQ',
        ]),
        obs_card('Reliability', GREEN, [
            'checkpoint() runs PRAGMA wal_checkpoint(TRUNCATE) on FastAPI shutdown',
            'server.sh integrity check on startup; corrupt DB moved to db_corrupted_backup/',
            'Per-program caching via run_snapshots survives process restarts',
            'All nodes catch exceptions → PipelineError → UI error (no run crash)',
            'Clarification/cache waits bounded to 300s via threading.Event.wait',
        ]),
        obs_card('Security', AMBER, [
            'API keys from .env via python-dotenv; reject_placeholders=True rejects "your_..." values',
            'CORS restricted to localhost:3000/3001 and 127.0.0.1 only',
            'No authentication layer on the API (gap before non-local deployment)',
            'Extraction and debate prompts include "hallucination fence" grounding instructions',
        ]),
        obs_card('Observability', VIOLET, [
            'CostLedger: per-provider/stage token counts → USD via hard-coded pricing constants',
            'UI_STAGES tracked per run; surfaced to frontend via polling response',
            'logs/backend.log, logs/frontend.log, logs/debate_debug.log (FileHandler in debate_engine.py)',
            'Per-stage cost breakdown visible in the frontend cost panel',
        ]),
    ]

    obs_rows = [
        [cards_13[0], cards_13[1]],
        [cards_13[2], cards_13[3]],
    ]
    obs_tbl = Table(obs_rows, colWidths=[CONTENT_W/2, CONTENT_W/2])
    obs_tbl.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 2),
        ('RIGHTPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(obs_tbl)
    story.append(spacer(12))

    # ── SECTION 14: ERROR HANDLING & RETRY STRATEGY ───────────────────────────
    story.append(KeepTogether(section_title('14', 'Error Handling & Retry Strategy')))

    err_items = [
        (PRIMARY, 'Node-level isolation',
         'Every graph node catches exceptions internally and writes a PipelineError delta. '
         'The background thread continues without crashing; the UI reflects an error state for that stage.'),
        (AMBER, 'Firecrawl partial failure',
         'The scraper continues if individual URL fetches fail; the node only raises if zero URLs succeed overall.'),
        (VIOLET, 'Groq rate limiting',
         'debate_engine.py::call_groq retries up to pool_size × 2 attempts, rotates keys on HTTP 429, '
         'permanently evicts keys on HTTP 401 via _remove_client_from_pool.'),
        (TEAL, 'Judge output parsing',
         'parse_judge_output tolerates malformed or partial JSON, falling back to FLAG_FALLBACK_REASONING '
         'so the conflict always has a recorded outcome.'),
        (GREEN, 'Non-fatal enrichment failures',
         'web_enrichment_node treats URL-seeding and Wikipedia fetch errors as non-fatal; '
         'logging warnings and continuing with available evidence.'),
        (RED, 'User-triggered cancellation',
         'record.stop_event checked before every stage transition; in-flight stages marked error, '
         'run_status set to cancelled.'),
        (GRAY, 'Debate engine fallback',
         'Unhandled exceptions from the debate engine produce a FLAG with deciding_factor: "unresolvable" '
         'and confidence 0.40.'),
    ]

    for color, title, desc in err_items:
        row = Table(
            [[Paragraph('', ParagraphStyle('s')),
              [Paragraph(f'<b>{title}</b>',
                         ParagraphStyle('et', fontSize=10, fontName='Helvetica-Bold',
                                        textColor=TEXT, leading=14)),
               Paragraph(desc, S_CARD_BODY)]]],
            colWidths=[6, CONTENT_W - 6],
        )
        row.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,0), color),
            ('BACKGROUND', (1,0), (1,0), white),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING',  (0,0), (0,0), 0),
            ('RIGHTPADDING', (0,0), (0,0), 0),
            ('LEFTPADDING',  (1,0), (1,0), 10),
            ('RIGHTPADDING', (1,0), (1,0), 10),
            ('BOX', (0,0), (-1,-1), 0.5, GRAY_BD),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        story.append(row)
        story.append(spacer(4))
    story.append(spacer(8))

    # ── SECTION 15: FUTURE ENHANCEMENTS ──────────────────────────────────────
    story.append(KeepTogether(section_title('15', 'Future Enhancements')))

    future = [
        ('1', 'Embedding-based Retrieval',
         'ChunkRef.embedding_hash and chunks table schema are forward-compatible; moving from '
         'heuristic scoring to semantic vector search improves extraction recall.'),
        ('2', 'Multi-instance Scaling',
         'Externalise STORE to Redis and move run execution to Celery or RQ.'),
        ('3', 'Authentication & Authorisation',
         'No auth layer on the API; required before non-local deployment. '
         'Candidate: OAuth2/OIDC middleware on FastAPI.'),
        ('4', 'Streaming Updates via WebSocket / SSE',
         'Replace polling (GET /api/run/{id}) with WebSocket or SSE channel '
         'for lower-latency stage-progress updates.'),
        ('5', 'Crash-resumable Runs',
         'Persist AgentState to the database after each completed node '
         'to enable mid-run restart recovery.'),
        ('6', 'verification.py Consolidation',
         'Standalone confidence-scoring module is a candidate for merge with '
         'conflict_adjudicator.py to reduce overlapping scoring paths.'),
        ('7', 'extraction.py Retirement',
         'Superseded by extractor.py as the active runtime path; '
         'should be formally deprecated or removed.'),
    ]

    for num, title, desc in future:
        row = Table(
            [[Paragraph(f'<b>{num}</b>',
                        ParagraphStyle('fn', fontSize=10, fontName='Helvetica-Bold',
                                       textColor=white, alignment=TA_CENTER)),
              [Paragraph(f'<b>{title}</b>', S_TL_TITLE), Paragraph(desc, S_TL_DESC)]]],
            colWidths=[22, CONTENT_W - 22],
        )
        row.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,0), PRIMARY),
            ('BACKGROUND', (1,0), (1,0), white),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (0,0), 0),
            ('RIGHTPADDING', (0,0), (0,0), 4),
            ('LEFTPADDING', (1,0), (1,0), 8),
            ('ROWBACKGROUNDS', (1,0), (1,0), [GRAY_LT if int(num) % 2 == 0 else white]),
        ]))
        story.append(row)
        story.append(spacer(3))
    story.append(spacer(12))

    # ── SECTION 16: CONCLUSION ────────────────────────────────────────────────
    story.append(KeepTogether(section_title('16', 'Conclusion')))

    conclusion_text = (
        '<b>Kobie demonstrates that a rigorous, source-grounded intelligence pipeline can be built '
        'from commodity LLM APIs and open-source tooling without a vector database or bespoke model. '
        'Its design is governed by a single architectural constraint: "Never hallucinate a fact."</b>'
        '<br/><br/>'
        'Every extracted value carries a source_url. Conflicts between sources are resolved through '
        'an auditable ladder of deterministic strategies — using the cheapest sufficient method — '
        'before falling back to metadata-only adversarial debate. The narrative brief and the '
        'grounded Q&A interface are both constrained to adjudicated evidence only; the LLM is '
        'used as a synthesiser and writer, not as a knowledge store.'
        '<br/><br/>'
        'The result is an agent whose outputs can be independently verified: every claim traces '
        'back to a retrieved page, and every conflict resolution decision is recorded with its '
        'strategy, judge reasoning, and confidence score. This auditability is the architectural '
        'property that distinguishes Kobie from a simple chatbot wrapper over a search API.'
    )

    conc_inner = Paragraph(conclusion_text,
                           ParagraphStyle('conc', fontSize=10, fontName='Helvetica',
                                          textColor=DARK_BLUE, leading=15, leftIndent=8))
    conc_tbl = Table([[Paragraph('', ParagraphStyle('sp')), conc_inner]],
                     colWidths=[6, CONTENT_W - 6])
    conc_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), PRIMARY),
        ('BACKGROUND', (1,0), (1,0), PRIMARY_BG),
        ('TOPPADDING', (0,0), (-1,-1), 14),
        ('BOTTOMPADDING', (0,0), (-1,-1), 14),
        ('LEFTPADDING',  (0,0), (0,0), 0),
        ('RIGHTPADDING', (0,0), (0,0), 0),
        ('LEFTPADDING', (1,0), (1,0), 14),
        ('RIGHTPADDING', (1,0), (1,0), 14),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(conc_tbl)
    story.append(spacer(16))

    # Technology pills footer
    pill_labels = [
        'FastAPI', 'LangGraph', 'Gemini 2.5 Flash', 'Groq', 'Tavily',
        'Firecrawl', 'SQLite WAL', 'Next.js 14', 'TanStack Query', 'Pydantic v2'
    ]
    pill_colors = [GREEN, TEAL, PRIMARY, VIOLET, TEAL, ORANGE, AMBER, PRIMARY_LT, PRIMARY, TEAL]

    pill_cells = []
    for label, color in zip(pill_labels, pill_colors):
        p = Paragraph(
            f'<b>{label}</b>',
            ParagraphStyle('pill', fontSize=8.5, fontName='Helvetica-Bold',
                           textColor=white, alignment=TA_CENTER, leading=12)
        )
        cell_t = Table([[p]])
        cell_t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), color),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('ROUNDEDCORNERS', [4]),
        ]))
        pill_cells.append(cell_t)

    # Layout pills in rows of 5
    pill_rows = []
    for i in range(0, len(pill_cells), 5):
        row = pill_cells[i:i+5]
        while len(row) < 5:
            row.append('')
        pill_rows.append(row)

    pill_tbl = Table(pill_rows, colWidths=[CONTENT_W/5]*5)
    pill_tbl.setStyle(TableStyle([
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 3),
        ('RIGHTPADDING', (0,0), (-1,-1), 3),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(pill_tbl)

    doc.build(story)


if __name__ == '__main__':
    build_document()
    print('PDF generated: docs/ARCHITECTURE_AND_DESIGN.pdf')
