"""End-to-end integration tests using real report examples."""

from __future__ import annotations

import io
import re
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
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

            stdout = io.StringIO()
            with redirect_stdout(stdout):
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
            self.assertEqual(stdout.getvalue(), "")
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

    def test_default_conversion_is_quiet_and_verbose_prints_validation(self) -> None:
        source_report = PROJECT_ROOT / "examples" / "report-minimal.md"
        self.assertTrue(
            source_report.is_file(), f"Minimal report missing: {source_report}"
        )

        with tempfile.TemporaryDirectory(prefix="md2dstu-e2e-min-") as temp_dir:
            output_docx = Path(temp_dir) / "minimal.docx"
            report_file = Path(temp_dir) / "minimal.validation.txt"

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main([str(source_report), "-o", str(output_docx)])

            self.assertEqual(exit_code, 0)
            self.assertTrue(output_docx.is_file())
            self.assertEqual(stdout.getvalue(), "")
            self.assertFalse(report_file.exists())

            verbose_output = Path(temp_dir) / "minimal-verbose.docx"
            verbose_stdout = io.StringIO()
            with redirect_stdout(verbose_stdout):
                verbose_exit_code = main(
                    [str(source_report), "-o", str(verbose_output), "-v"]
                )

            self.assertEqual(verbose_exit_code, 0)
            self.assertIn(
                "DSTU conversion validation: PASS WITH WARNINGS",
                verbose_stdout.getvalue(),
            )
            self.assertIn("Warnings:", verbose_stdout.getvalue())
            self.assertFalse(Path(str(verbose_output) + ".validation.txt").exists())

    def test_code_block_uses_courier_new_11_bold_single(self) -> None:
        with tempfile.TemporaryDirectory(prefix="md2dstu-e2e-code-") as temp_dir:
            source = Path(temp_dir) / "code.md"
            source.write_text(
                '---\ntitle: "T"\n---\n\n# РОЗДІЛ\n\n'
                "```python\ndef f(x):\n    return x + 1\n```\n\n"
                "# ВИСНОВКИ {-}\n\nТекст.\n",
                encoding="utf-8",
            )
            output_docx = Path(temp_dir) / "code.docx"

            self.assertEqual(
                main([str(source), "-o", str(output_docx), "--no-update-toc"]), 0
            )

            with zipfile.ZipFile(output_docx) as docx_zip:
                styles = docx_zip.read("word/styles.xml").decode("utf-8")
                document = docx_zip.read("word/document.xml").decode("utf-8")

            style = re.search(
                r'<w:style [^>]*w:styleId="SourceCode".*?</w:style>', styles
            )
            self.assertIsNotNone(style)
            self.assertIn('w:ascii="Courier New"', style.group(0))
            self.assertIn('<w:sz w:val="22"', style.group(0))
            self.assertIn("<w:b ", style.group(0))
            self.assertIn('w:line="240"', style.group(0))
            self.assertIn('<w:pStyle w:val="SourceCode"', document)
            spacer = (
                '<w:p><w:pPr><w:pStyle w:val="SourceCode" /></w:pPr>'
                '<w:r><w:t xml:space="preserve"> </w:t></w:r></w:p>'
            )
            self.assertEqual(document.count(spacer), 2)
            self.assertNotIn("KeywordTok", document)

    def test_no_spacer_between_figure_and_next_heading(self) -> None:
        image = PROJECT_ROOT / "examples" / "bombyx-mori.png"
        with tempfile.TemporaryDirectory(prefix="md2dstu-e2e-fig-") as temp_dir:
            source = Path(temp_dir) / "fig.md"
            source.write_text(
                '---\ntitle: "T"\n---\n\n# РОЗДІЛ\n\n'
                f"![Перший]({image})\n\nТекст.\n\n"
                f"![Другий]({image})\n\n## Підрозділ\n\nТекст.\n",
                encoding="utf-8",
            )
            output_docx = Path(temp_dir) / "fig.docx"

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    [str(source), "-o", str(output_docx), "--no-update-toc"]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")

            with zipfile.ZipFile(output_docx) as docx_zip:
                document = docx_zip.read("word/document.xml").decode("utf-8")

            self.assertEqual(document.count('w:val="FigureSpacer"'), 1)


if __name__ == "__main__":
    unittest.main()
