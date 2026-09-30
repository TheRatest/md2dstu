"""Unit tests for command-line interface argument parsing."""

from __future__ import annotations

import unittest
from pathlib import Path

from md2dstu.cli import parse_arguments_to_config
from md2dstu.config import NumberingMode, OutputFormat


class CliTestCase(unittest.TestCase):
    def test_default_cli_arguments(self) -> None:
        config = parse_arguments_to_config(["report.md"])
        self.assertEqual(config.input_path, Path("report.md").resolve())
        self.assertEqual(config.output_path, Path("report.docx").resolve())
        self.assertEqual(config.output_format, OutputFormat.DOCX)
        self.assertEqual(config.numbering_mode, NumberingMode.SECTION)
        self.assertFalse(config.bold_heading2)
        self.assertTrue(config.update_toc)
        self.assertFalse(config.check_structural_errors)

    def test_custom_cli_arguments(self) -> None:
        config = parse_arguments_to_config(
            [
                "report.md",
                "-o",
                "custom.odt",
                "--numbering",
                "continuous",
                "--bold-heading2",
                "--no-update-toc",
                "--check",
                "--keep-docx",
            ]
        )
        self.assertEqual(config.output_path, Path("custom.odt").resolve())
        self.assertEqual(config.output_format, OutputFormat.ODT)
        self.assertEqual(config.numbering_mode, NumberingMode.CONTINUOUS)
        self.assertTrue(config.bold_heading2)
        self.assertFalse(config.update_toc)
        self.assertTrue(config.check_structural_errors)
        self.assertTrue(config.keep_intermediate_docx)


if __name__ == "__main__":
    unittest.main()
