"""Unit tests for DSTU structural validation rules."""

from __future__ import annotations

import unittest
from pathlib import Path

from md2dstu.config import ConversionConfig
from md2dstu.metadata import DocumentMetadata
from md2dstu.validation.models import ValidationStatus
from md2dstu.validation.validator import DocumentValidator


class ValidatorTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.config = ConversionConfig(
            input_path=Path("dummy_report.md"),
            output_path=Path("dummy_report.docx"),
        )
        self.validator = DocumentValidator(self.config)

    def test_missing_title_produces_error(self) -> None:
        metadata = DocumentMetadata(title="")
        ast_data = {"blocks": []}

        report = self.validator.validate(ast_data, metadata)
        self.assertEqual(report.status, ValidationStatus.FAIL)
        self.assertIn(
            "No title page can be generated: metadata field 'title' is missing",
            report.errors,
        )

    def test_missing_conclusions_produces_error(self) -> None:
        metadata = DocumentMetadata(title="Звіт", student={"name": "Іванов"})
        ast_data = {
            "blocks": [
                {
                    "t": "Header",
                    "c": [1, ["vstup", [], []], [{"t": "Str", "c": "ВСТУП"}]],
                },
                {
                    "t": "Header",
                    "c": [1, ["sec1", [], []], [{"t": "Str", "c": "РОЗДІЛ 1"}]],
                },
            ]
        }

        report = self.validator.validate(ast_data, metadata)
        self.assertFalse(report.is_success)
        self.assertTrue(
            any(
                "Required structural heading is missing: conclusions/ВИСНОВКИ" in err
                for err in report.errors
            )
        )

    def test_heading_ending_with_period_produces_warning(self) -> None:
        metadata = DocumentMetadata(
            title="Звіт",
            institution="КПІ",
            city="Київ",
            year="2026",
            student={"name": "Іванов"},
            teacher={"name": "Шевченко"},
        )
        ast_data = {
            "blocks": [
                {
                    "t": "Header",
                    "c": [1, ["vstup", [], []], [{"t": "Str", "c": "ВСТУП."}]],
                },
                {
                    "t": "Header",
                    "c": [1, ["sec1", [], []], [{"t": "Str", "c": "ОСНОВНА ЧАСТИНА"}]],
                },
                {
                    "t": "Header",
                    "c": [1, ["visn", [], []], [{"t": "Str", "c": "ВИСНОВКИ"}]],
                },
            ]
        }

        report = self.validator.validate(ast_data, metadata)
        self.assertTrue(
            any("Heading ends with a period" in warning for warning in report.warnings)
        )

    def test_excluded_appendix_letter_produces_warning(self) -> None:
        metadata = DocumentMetadata(
            title="Звіт",
            institution="КПІ",
            city="Київ",
            year="2026",
            student={"name": "Іванов"},
            teacher={"name": "Шевченко"},
        )
        ast_data = {
            "blocks": [
                {
                    "t": "Header",
                    "c": [1, ["vstup", [], []], [{"t": "Str", "c": "ВСТУП"}]],
                },
                {
                    "t": "Header",
                    "c": [1, ["sec1", [], []], [{"t": "Str", "c": "РОЗДІЛ 1"}]],
                },
                {
                    "t": "Header",
                    "c": [1, ["visn", [], []], [{"t": "Str", "c": "ВИСНОВКИ"}]],
                },
                {
                    "t": "Header",
                    "c": [
                        1,
                        ["app", ["appendix"], []],
                        [{"t": "Str", "c": "ДОДАТОК З"}],
                    ],
                },
            ]
        }

        report = self.validator.validate(ast_data, metadata)
        self.assertTrue(
            any(
                "Appendix label uses an excluded Ukrainian letter: З" in w
                for w in report.warnings
            )
        )


if __name__ == "__main__":
    unittest.main()
