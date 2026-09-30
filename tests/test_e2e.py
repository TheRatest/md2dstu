"""End-to-end integration tests using real report examples."""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from md2dstu.cli import main
from md2dstu.constants import PROJECT_ROOT


class EndToEndIntegrationTestCase(unittest.TestCase):
    def test_full_report_conversion_e2e(self) -> None:
        source_report = PROJECT_ROOT / "examples" / "report.md"
        self.assertTrue(
            source_report.is_file(), f"Sample report missing: {source_report}"
        )

        with tempfile.TemporaryDirectory(prefix="md2dstu-e2e-") as temp_dir:
            output_docx = Path(temp_dir) / "output_report.docx"
            report_file = Path(temp_dir) / "output_report.validation.txt"

            exit_code = main(
                [
                    str(source_report),
                    "-o",
                    str(output_docx),
                    "--report",
                    str(report_file),
                    "--check",
                ]
            )

            self.assertEqual(exit_code, 0, "Conversion exited with non-zero status")
            self.assertTrue(output_docx.is_file(), "Generated DOCX does not exist")
            self.assertTrue(report_file.is_file(), "Validation report does not exist")

            # Check that validation report indicates PASS
            validation_text = report_file.read_text(encoding="utf-8")
            self.assertIn("DSTU conversion validation: PASS", validation_text)
            self.assertNotIn("Errors:\n- Required", validation_text)

            # Check that DOCX archive contains expected OpenXML parts
            with zipfile.ZipFile(output_docx) as docx_zip:
                namelist = docx_zip.namelist()
                self.assertIn("word/document.xml", namelist)
                self.assertIn("word/styles.xml", namelist)
                self.assertIn("word/numbering.xml", namelist)
                self.assertIn("word/header1.xml", namelist)

    def test_minimal_report_conversion_e2e(self) -> None:
        source_report = PROJECT_ROOT / "examples" / "report-minimal.md"
        self.assertTrue(
            source_report.is_file(), f"Minimal report missing: {source_report}"
        )

        with tempfile.TemporaryDirectory(prefix="md2dstu-e2e-min-") as temp_dir:
            output_docx = Path(temp_dir) / "minimal.docx"
            report_file = Path(temp_dir) / "minimal.validation.txt"

            exit_code = main(
                [
                    str(source_report),
                    "-o",
                    str(output_docx),
                    "--report",
                    str(report_file),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(output_docx.is_file())
            self.assertTrue(report_file.is_file())

            validation_text = report_file.read_text(encoding="utf-8")
            self.assertIn(
                "DSTU conversion validation: PASS WITH WARNINGS", validation_text
            )


if __name__ == "__main__":
    unittest.main()
