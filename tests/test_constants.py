"""Unit tests for constants, unit conversions, and standard alphabets."""

from __future__ import annotations

import unittest

from md2dstu.constants import (
    EXCLUDED_APPENDIX_LETTERS,
    INDENT_FIRST_LINE_DXA,
    MARGIN_BOTTOM_DXA,
    MARGIN_LEFT_DXA,
    MARGIN_RIGHT_DXA,
    MARGIN_TOP_DXA,
    PAGE_A4_HEIGHT_DXA,
    PAGE_A4_WIDTH_DXA,
    PAGE_CONTENT_WIDTH_DXA,
    UKRAINIAN_ALPHABET_LOWER,
    cm_to_dxa,
    mm_to_dxa,
    points_to_eighths,
    points_to_half_points,
)


class ConstantsTestCase(unittest.TestCase):
    def test_unit_conversions(self) -> None:
        # 1 inch = 25.4 mm = 1440 dxa
        self.assertEqual(mm_to_dxa(25.4), 1440)
        # 1 cm = 10 mm
        self.assertEqual(cm_to_dxa(1.0), mm_to_dxa(10.0))
        # 1.25 cm standard indent ≈ 709 dxa
        self.assertEqual(cm_to_dxa(1.25), INDENT_FIRST_LINE_DXA)
        self.assertEqual(INDENT_FIRST_LINE_DXA, 709)

    def test_typographic_points(self) -> None:
        # 14 pt in half-points = 28
        self.assertEqual(points_to_half_points(14), 28)
        # 10 pt in half-points = 20
        self.assertEqual(points_to_half_points(10), 20)
        # 1 pt border in eighths = 8
        self.assertEqual(points_to_eighths(1), 8)

    def test_a4_page_dimensions(self) -> None:
        # A4: 210 x 297 mm
        self.assertEqual(PAGE_A4_WIDTH_DXA, 11906)
        self.assertEqual(PAGE_A4_HEIGHT_DXA, 16838)
        # Margins: Left 25mm, Right 10mm, Top 20mm, Bottom 20mm
        self.assertEqual(MARGIN_LEFT_DXA, 1417)
        self.assertEqual(MARGIN_RIGHT_DXA, 567)
        self.assertEqual(MARGIN_TOP_DXA, 1134)
        self.assertEqual(MARGIN_BOTTOM_DXA, 1134)
        # Content width = 11906 - 1417 - 567 = 9922 dxa
        self.assertEqual(
            PAGE_CONTENT_WIDTH_DXA,
            PAGE_A4_WIDTH_DXA - MARGIN_LEFT_DXA - MARGIN_RIGHT_DXA,
        )
        self.assertEqual(PAGE_CONTENT_WIDTH_DXA, 9922)

    def test_ukrainian_alphabet_and_exclusions(self) -> None:
        self.assertEqual(len(UKRAINIAN_ALPHABET_LOWER), 33)
        self.assertIn("а", UKRAINIAN_ALPHABET_LOWER)
        self.assertIn("я", UKRAINIAN_ALPHABET_LOWER)
        # Excluded letters in DSTU 3008:2015
        for letter in "ҐЄЗІЇЙОЧЬ":
            self.assertIn(letter, EXCLUDED_APPENDIX_LETTERS)


if __name__ == "__main__":
    unittest.main()
