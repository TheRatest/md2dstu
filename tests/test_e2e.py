"""End-to-end integration tests using real report examples."""

from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from xml.etree import ElementTree as ET

from md2dstu.cli import main
from md2dstu.constants import PROJECT_ROOT
from md2dstu.docx.namespaces import w_tag


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

    def test_yaml_metadata_line_feeds_render_as_title_page_breaks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="md2dstu-e2e-meta-linefeed-") as temp_dir:
            source = Path(temp_dir) / "line-feeds.md"
            source.write_text(
                '---\n'
                'title: "з дисципліни «Паралельне програмування»\\n'
                'на тему «Технології виміру часу та їх практичне використання»"\n'
                'approval: "ЗАТВЕРДЖУЮ\\nКерівник практики"\n'
                'student:\n'
                '  label: "Виконав:"\n'
                '  title: "студент групи ПІ-22\\nденна форма навчання"\n'
                '  name: "Іваненко І. І."\n'
                'teacher:\n'
                '  name: "Петренко П. П."\n'
                'city: "Київ\\nУкраїна"\n'
                'year: "2026"\n'
                'toc: false\n'
                '---\n\n'
                '# РОЗДІЛ\n\nТекст.\n\n'
                '# ВИСНОВКИ {-}\n\nВисновок.\n',
                encoding="utf-8",
            )
            output_docx = Path(temp_dir) / "line-feeds.docx"

            self.assertEqual(
                main([str(source), "-o", str(output_docx), "--no-update-toc"]), 0
            )

            with zipfile.ZipFile(output_docx) as docx_zip:
                document = ET.fromstring(docx_zip.read("word/document.xml"))

            expected_by_style = {
                "TitleDocumentTitle": [
                    "з дисципліни «Паралельне програмування»",
                    "на тему «Технології виміру часу та їх практичне використання»",
                ],
                "TitleApproval": ["ЗАТВЕРДЖУЮ", "Керівник практики"],
                "TitleDetailsCell": ["студент групи ПІ-22", "денна форма навчання"],
                "TitlePlace": ["Київ", "Україна – 2026"],
            }
            for style_id, expected_lines in expected_by_style.items():
                with self.subTest(style=style_id):
                    paragraph = next(
                        paragraph
                        for paragraph in document.iter(w_tag("p"))
                        if (
                            (style := paragraph.find(
                                f"./{w_tag('pPr')}/{w_tag('pStyle')}"
                            ))
                            is not None
                            and style.get(w_tag("val")) == style_id
                            and "".join(
                                text.text or ""
                                for text in paragraph.iter(w_tag("t"))
                            )
                            == "".join(expected_lines)
                        )
                    )
                    self.assertEqual(
                        [
                            text.text or ""
                            for text in paragraph.iter(w_tag("t"))
                        ],
                        expected_lines,
                    )
                    self.assertEqual(
                        len(
                            [
                                line_break
                                for line_break in paragraph.iter(w_tag("br"))
                                if line_break.get(w_tag("type")) != "page"
                            ]
                        ),
                        len(expected_lines) - 1,
                    )

    def test_code_uses_courier_new_11_bold_single(self) -> None:
        with tempfile.TemporaryDirectory(prefix="md2dstu-e2e-code-") as temp_dir:
            source = Path(temp_dir) / "code.md"
            source.write_text(
                '---\ntitle: "T"\n---\n\n# РОЗДІЛ\n\n'
                "```python\ndef f(x):\n    return x + 1\n```\n\n"
                "Inline `code` example.\n\n# ВИСНОВКИ {-}\n\nТекст.\n",
                encoding="utf-8",
            )
            output_docx = Path(temp_dir) / "code.docx"

            self.assertEqual(
                main([str(source), "-o", str(output_docx), "--no-update-toc"]), 0
            )

            with zipfile.ZipFile(output_docx) as docx_zip:
                styles_xml = docx_zip.read("word/styles.xml")
                document_xml = docx_zip.read("word/document.xml")
                document = document_xml.decode("utf-8")
                package_xml = b"\n".join(
                    docx_zip.read(name)
                    for name in docx_zip.namelist()
                    if name.endswith(".xml")
                )

            styles_root = ET.fromstring(styles_xml)
            style_by_id = {
                style.get(w_tag("styleId")): style
                for style in styles_root.findall(w_tag("style"))
            }
            for style_id in ("SourceCode", "CodeBlockChar", "VerbatimChar"):
                with self.subTest(style=style_id):
                    style = style_by_id[style_id]
                    run_properties = style.find(w_tag("rPr"))
                    self.assertIsNotNone(run_properties)
                    fonts = run_properties.find(w_tag("rFonts"))
                    self.assertIsNotNone(fonts)
                    self.assertEqual(
                        fonts.attrib,
                        {
                            w_tag("ascii"): "Courier New",
                            w_tag("hAnsi"): "Courier New",
                            w_tag("eastAsia"): "Courier New",
                            w_tag("cs"): "Courier New",
                        },
                    )
                    self.assertEqual(
                        run_properties.find(w_tag("sz")).get(w_tag("val")), "22"
                    )
                    if style_id == "VerbatimChar":
                        self.assertIsNone(run_properties.find(w_tag("b")))
                    else:
                        self.assertIsNotNone(run_properties.find(w_tag("b")))

            self.assertNotIn(b"Consolas", package_xml)
            source_code_paragraph = style_by_id["SourceCode"].find(w_tag("pPr"))
            self.assertEqual(
                source_code_paragraph.find(w_tag("spacing")).get(w_tag("line")),
                "240",
            )
            self.assertIn('<w:pStyle w:val="SourceCode"', document)
            document_root = ET.fromstring(document_xml)
            code_block_paragraphs = [
                paragraph
                for paragraph in document_root.iter(w_tag("p"))
                if (
                    (paragraph_style := paragraph.find(
                        f"./{w_tag('pPr')}/{w_tag('pStyle')}"
                    ))
                    is not None
                    and paragraph_style.get(w_tag("val")) == "SourceCode"
                )
            ]
            code_block_styles = [
                run_style.get(w_tag("val"))
                for paragraph in code_block_paragraphs
                for run_style in paragraph.iter(w_tag("rStyle"))
            ]
            self.assertIn("CodeBlockChar", code_block_styles)
            self.assertNotIn("VerbatimChar", code_block_styles)
            code_text_runs = [
                run
                for paragraph in code_block_paragraphs
                for run in paragraph.findall(w_tag("r"))
                if any(
                    (text.text or "").strip()
                    for text in run.iter(w_tag("t"))
                )
            ]
            self.assertTrue(code_text_runs)
            for run in code_text_runs:
                run_properties = run.find(w_tag("rPr"))
                self.assertIsNotNone(run_properties)
                self.assertIsNotNone(run_properties.find(w_tag("b")))
                self.assertEqual(
                    run_properties.find(w_tag("sz")).get(w_tag("val")), "22"
                )
            inline_code_styles = [
                run_style.get(w_tag("val"))
                for paragraph in document_root.iter(w_tag("p"))
                if not any(
                    style.get(w_tag("val")) == "SourceCode"
                    for style in paragraph.findall(
                        f"./{w_tag('pPr')}/{w_tag('pStyle')}"
                    )
                )
                for run_style in paragraph.iter(w_tag("rStyle"))
            ]
            self.assertIn("VerbatimChar", inline_code_styles)
            spacer_paragraphs = [
                paragraph
                for paragraph in code_block_paragraphs
                if "".join(
                    text.text or "" for text in paragraph.iter(w_tag("t"))
                )
                == " "
            ]
            self.assertEqual(len(spacer_paragraphs), 2)
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
