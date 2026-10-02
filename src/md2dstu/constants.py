"""Constants and unit conversions for DSTU formatting and OpenXML structures."""

from __future__ import annotations

from pathlib import Path

# OpenXML Namespaces
W_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/math"
R_NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
O_NAMESPACE = "urn:schemas-microsoft-com:office:office"
V_NAMESPACE = "urn:schemas-microsoft-com:vml"
W10_NAMESPACE = "urn:schemas-microsoft-com:office:word"
SL_NAMESPACE = "http://schemas.openxmlformats.org/schemaLibrary/2006/main"
PKG_REL_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/content-types"

# Standard namespace dictionary for OpenXML element manipulation
OPENXML_NAMESPACES: dict[str, str] = {
    "w": W_NAMESPACE,
    "m": M_NAMESPACE,
    "r": R_NAMESPACE,
    "o": O_NAMESPACE,
    "v": V_NAMESPACE,
    "w10": W10_NAMESPACE,
    "sl": SL_NAMESPACE,
    "": PKG_REL_NAMESPACE,
}

# Unit conversion factors:
# dxa (twip, twentieth of a point): 1 pt = 20 dxa; 1 inch = 72 pt = 1440 dxa; 1 mm ≈ 56.6929 dxa.
DXA_PER_INCH = 1440
DXA_PER_POINT = 20
DXA_PER_MM = DXA_PER_INCH / 25.4  # ≈ 56.692913


def mm_to_dxa(millimeters: float) -> int:
    """Convert millimeters to Word dxa (twips)."""
    return round(millimeters * DXA_PER_MM)


def cm_to_dxa(centimeters: float) -> int:
    """Convert centimeters to Word dxa (twips)."""
    return mm_to_dxa(centimeters * 10)


def points_to_dxa(points: float) -> int:
    """Convert typographic points to Word dxa (twips)."""
    return round(points * DXA_PER_POINT)


def points_to_half_points(points: float) -> int:
    """Convert typographic points to Word half-points (used in w:sz)."""
    return round(points * 2)


def points_to_eighths(points: float) -> int:
    """Convert typographic points to border eighths (used in w:sz for borders)."""
    return round(points * 8)


# DSTU 3008:2015 Layout dimensions
PAGE_A4_WIDTH_DXA = mm_to_dxa(210)  # 11906 dxa (210 mm)
PAGE_A4_HEIGHT_DXA = mm_to_dxa(297)  # 16838 dxa (297 mm)

MARGIN_LEFT_DXA = mm_to_dxa(25)  # 1417 dxa (25 mm)
MARGIN_RIGHT_DXA = mm_to_dxa(10)  # 567 dxa (10 mm)
MARGIN_TOP_DXA = mm_to_dxa(20)  # 1134 dxa (20 mm)
MARGIN_BOTTOM_DXA = mm_to_dxa(20)  # 1134 dxa (20 mm)
MARGIN_HEADER_DXA = mm_to_dxa(10)  # 567 dxa (10 mm)
MARGIN_FOOTER_DXA = mm_to_dxa(10)  # 567 dxa (10 mm)

# Printable area width: 11906 - 1417 - 567 = 9922 dxa
PAGE_CONTENT_WIDTH_DXA = (
    PAGE_A4_WIDTH_DXA - MARGIN_LEFT_DXA - MARGIN_RIGHT_DXA
)  # 9922 dxa
# Printable center tab stop: 9922 // 2 = 4961 dxa
PAGE_CONTENT_CENTER_DXA = PAGE_CONTENT_WIDTH_DXA // 2  # 4961 dxa

# Indentation
# DSTU standard first-line indent is 1.25 cm (~5 standard characters)
INDENT_FIRST_LINE_DXA = cm_to_dxa(1.25)  # 709 dxa
# Hanging indent for list items wrapped across lines (~0.75 cm)
INDENT_LIST_HANGING_DXA = 425

# Typography
FONT_NAME_TIMES = "Times New Roman"
FONT_SIZE_BODY_HALF_POINTS = points_to_half_points(14)  # 28 (14 pt)
FONT_SIZE_FOOTNOTE_HALF_POINTS = points_to_half_points(12)  # 24 (12 pt)
FONT_SIZE_PAGE_NUMBER_HALF_POINTS = points_to_half_points(10)  # 20 (10 pt)
FONT_NAME_CODE = "Courier New"
FONT_SIZE_CODE_HALF_POINTS = points_to_half_points(11)  # 22 (11 pt)

# Line spacing in Word (240 units = 1.0 single spacing; 360 units = 1.5 line spacing)
LINE_SPACING_1_5 = 360
LINE_SPACING_SINGLE = 240

# Table border size (1 pt = 8 eighths of a point)
BORDER_SIZE_ONE_POINT = points_to_eighths(1)  # 8

# Title-page vertical spacers (in dxa)
TITLE_SPACER_TOP_DXA = 3000
TITLE_SPACER_MIDDLE_DXA = 2000
TITLE_SPACER_BOTTOM_DXA = 2900

# Ukrainian alphabet and exclusions for DSTU compliance
# Standard lower-case Ukrainian alphabet for ordered sub-lists
UKRAINIAN_ALPHABET_LOWER: list[str] = list("абвгґдеєжзиіїйклмнопрстуфхцчшщьюя")

# Letters excluded in DSTU for appendix numbering (DSTU 3008:2015 item 7.1.3)
EXCLUDED_APPENDIX_LETTERS: frozenset[str] = frozenset("ҐЄЗІЇЙОЧЬ")

# Known structural heading aliases in Ukrainian and English
STRUCTURAL_HEADINGS: frozenset[str] = frozenset(
    {
        "реферат",
        "abstract",
        "зміст",
        "contents",
        "вступ",
        "introduction",
        "висновки",
        "conclusions",
        "рекомендації",
        "recommendations",
        "перелік джерел посилання",
        "список використаних джерел",
        "references",
    }
)

# Default package resources paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FILTER_PATH = PROJECT_ROOT / "filters" / "dstu.lua"
DEFAULT_CSL_PATH = PROJECT_ROOT / "resources" / "dstu-numeric.csl"
DEFAULT_REFERENCE_DOCX_PATH = PROJECT_ROOT / "templates" / "dstu-reference.docx"
