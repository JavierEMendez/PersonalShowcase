"""PDF primitives for the memo decks: page geometry, design tokens, fonts, tables and cells.

US Letter landscape. The site typefaces are used when their TTF files sit in app/static/fonts/;
otherwise the PDF core fonts stand in. Both tools' decks build on the Deck class here.
"""

from __future__ import annotations

import datetime
from collections.abc import Sequence
from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "app" / "static" / "fonts"
MARK = ROOT / "app" / "static" / "brand" / "icon-192.png"

# Design tokens from app/static/site.css, as RGB.
INK = (0x16, 0x19, 0x1D)
INK2 = (0x3A, 0x40, 0x48)
MUTED = (0x6C, 0x70, 0x78)
HAIRLINE = (0xE6, 0xE4, 0xDE)
RULE = (0xB8, 0xB5, 0xAC)
ACCENT = (0x0F, 0x2A, 0x44)
POS = (0x1E, 0x6B, 0x48)
NEG = (0x9E, 0x3A, 0x2B)
WARN = (0x8A, 0x6A, 0x1A)
BG = (0xFA, 0xFA, 0xF7)

PAGE_W, PAGE_H = 279.4, 215.9  # US Letter landscape, mm
MARGIN = 14.0
CONTENT_W = PAGE_W - 2 * MARGIN

FONT_FILES = {
    ("serif", ""): "SourceSerif4-Regular.ttf",
    ("serif", "B"): "SourceSerif4-Semibold.ttf",
    ("sans", ""): "IBMPlexSans-Regular.ttf",
    ("sans", "B"): "IBMPlexSans-Medium.ttf",
}

_LATIN = str.maketrans(
    {
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "•": "-",
        "…": "...",
        " ": " ",
    }
)


def _money_m(v: float, d: int = 1) -> str:
    return f"(${abs(v) / 1e6:,.{d}f}M)" if v < 0 else f"${v / 1e6:,.{d}f}M"


def _money(v: float) -> str:
    return f"(${abs(v):,.0f})" if v < 0 else f"${v:,.0f}"


def _pct(v: float | None, d: int = 1) -> str:
    return "n/a" if v is None else f"{v * 100:.{d}f}%"


def _mult(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.2f}x"


def _k(v: float) -> str:
    """Thousands, negatives in parentheses."""
    return f"({abs(v) / 1e3:,.0f})" if v < 0 else f"{v / 1e3:,.0f}"


class Deck(FPDF):
    def __init__(self) -> None:
        super().__init__(orientation="L", unit="mm", format="Letter")
        self.set_margins(MARGIN, MARGIN, MARGIN)
        self.set_auto_page_break(auto=False)
        self.set_title("Investment committee memo")
        self._site_fonts = self._load_fonts()
        self.footer_text = ""
        self.product = "Multifamily Copilot"

    # -- fonts ---------------------------------------------------------------------------------
    def _load_fonts(self) -> bool:
        if not all((FONT_DIR / name).exists() for name in FONT_FILES.values()):
            return False
        for (family, style), name in FONT_FILES.items():
            self.add_font(family, style, str(FONT_DIR / name))
        return True

    def font(
        self, family: str, size: float, bold: bool = False, color: tuple[int, int, int] = INK
    ) -> None:
        style = "B" if bold else ""
        if self._site_fonts:
            self.set_font(family, style, size)
        else:
            self.set_font("times" if family == "serif" else "helvetica", style, size)
        self.set_text_color(*color)

    def text_safe(self, text: str) -> str:
        text = text.translate(_LATIN)
        if self._site_fonts:
            return text
        return text.encode("latin-1", "replace").decode("latin-1")

    # -- primitives ----------------------------------------------------------------------------
    def eyebrow(
        self, x: float, y: float, text: str, w: float | None = None, align: str = "L"
    ) -> None:
        self.font("sans", 6.6, bold=True, color=MUTED)
        self.set_xy(x, y)
        self.cell(
            w or self.get_string_width(text.upper()) + 1,
            3.6,
            self.text_safe(text.upper()),
            align=align,
        )

    def rule(
        self, x: float, y: float, w: float, color: tuple[int, int, int] = RULE, width: float = 0.25
    ) -> None:
        self.set_draw_color(*color)
        self.set_line_width(width)
        self.line(x, y, x + w, y)

    def para(
        self,
        x: float,
        y: float,
        w: float,
        text: str,
        family: str,
        size: float,
        lh: float,
        color: tuple[int, int, int] = INK,
        bold: bool = False,
    ) -> float:
        """Wrapped text; returns the y below it."""
        self.font(family, size, bold=bold, color=color)
        self.set_xy(x, y)
        self.multi_cell(w, lh, self.text_safe(text), align="L")
        return self.get_y()

    def grid(
        self,
        x: float,
        y: float,
        widths: Sequence[float],
        header: Sequence[str],
        rows: Sequence[Sequence[str]],
        aligns: Sequence[str],
        total_rows: Sequence[int] = (),
        size: float = 7.4,
        lh: float = 4.6,
        colors: dict[tuple[int, int], tuple[int, int, int]] | None = None,
    ) -> float:
        """A compact table with an eyebrow header row and hairline rules; returns the y below."""
        colors = colors or {}
        if header:
            self.font("sans", 6.2, bold=True, color=MUTED)
            cx = x
            for h, w, a in zip(header, widths, aligns, strict=True):
                self.set_xy(cx, y)
                self.cell(w, lh, self.text_safe(h.upper()), align=a)
                cx += w
            y += lh
            self.rule(x, y, sum(widths), RULE)
        for i, row in enumerate(rows):
            bold = i in total_rows
            cx = x
            for j, (cell, w, a) in enumerate(zip(row, widths, aligns, strict=True)):
                self.font("sans", size, bold=bold, color=colors.get((i, j), INK if bold else INK2))
                self.set_xy(cx, y)
                self.cell(w, lh, self.text_safe(cell), align=a)
                cx += w
            y += lh
            self.rule(x, y, sum(widths), INK if bold else HAIRLINE, 0.3 if bold else 0.18)
        return y

    def kv(
        self,
        x: float,
        y: float,
        w: float,
        pairs: Sequence[tuple[str, str]],
        size: float = 7.6,
        lh: float = 4.8,
    ) -> float:
        for k, v in pairs:
            self.font("sans", size, color=INK2)
            self.set_xy(x, y)
            self.cell(w * 0.55, lh, self.text_safe(k))
            self.font("sans", size, color=INK)
            self.set_xy(x + w * 0.55, y)
            self.cell(w * 0.45, lh, self.text_safe(v), align="R")
            y += lh
            self.rule(x, y, w, HAIRLINE, 0.18)
        return y

    def kpi(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        label: str,
        figure: str,
        note: str,
        color: tuple[int, int, int] = INK,
    ) -> None:
        self.eyebrow(x, y + 1.5, label)
        self.font("serif", 14, color=color)
        self.set_xy(x, y + 5.5)
        self.cell(w, 7, self.text_safe(figure))
        self.font("sans", 6.6, color=MUTED)
        self.set_xy(x, y + 12.6)
        self.cell(w, 3.4, self.text_safe(note))

    # -- page furniture ------------------------------------------------------------------------
    def header(self) -> None:  # fpdf hook, drawn on add_page
        pass

    def footer(self) -> None:  # fpdf hook
        self.rule(MARGIN, PAGE_H - 11, CONTENT_W, HAIRLINE, 0.18)
        self.font("sans", 6.4, color=MUTED)
        self.set_xy(MARGIN, PAGE_H - 10)
        self.cell(CONTENT_W * 0.8, 4, self.text_safe(self.footer_text))
        self.set_xy(MARGIN, PAGE_H - 10)
        self.cell(CONTENT_W, 4, f"Page {self.page_no()}", align="R")

    def page_head(self, deal: str, case: str, section: str, date: datetime.date) -> float:
        if MARK.exists():
            self.image(str(MARK), x=MARGIN, y=MARGIN, w=6, h=6)
        self.font("sans", 8, bold=True, color=INK)
        self.set_xy(MARGIN + 8, MARGIN + 0.6)
        self.cell(60, 5, "Javier Mendez")
        self.font("sans", 8, color=MUTED)
        self.set_xy(MARGIN + 8 + self.get_string_width("Javier Mendez") + 2, MARGIN + 0.6)
        self.cell(60, 5, self.text_safe(f"/  {self.product}"))
        self.eyebrow(
            MARGIN,
            MARGIN,
            f"Investment committee memo  ·  {section}  ·  {date:%B %d, %Y}",
            CONTENT_W,
            "R",
        )
        self.font("serif", 19, color=INK)
        self.set_xy(MARGIN, MARGIN + 9)
        self.cell(CONTENT_W * 0.6, 9, self.text_safe(deal))
        self.font("sans", 8, color=MUTED)
        self.set_xy(MARGIN, MARGIN + 9)
        self.cell(CONTENT_W, 9, self.text_safe(f"{case} case"), align="R")
        y = MARGIN + 19.5
        self.rule(MARGIN, y, CONTENT_W, INK, 0.4)
        return y + 4
