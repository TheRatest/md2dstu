"""Unit tests for DOCX postprocessor and XML modifiers."""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from md2dstu.docx.document import DocumentModifier
from md2dstu.docx.namespaces import w_tag
from md2dstu.docx.styles import StyleModifier
from md2dstu.docx.tables import TableModifier, split_table
from md2dstu.docx.toc_casing import toc_sentence_case


class DocxModifiersTestCase(unittest.TestCase):
    def test_toc_sentence_case(self) -> None:
        self.assertEqual(toc_sentence_case("ВСТУП"), "Вступ")
        self.assertEqual(
            toc_sentence_case("РОЗДІЛ 1. АНАЛІЗ ПРЕДМЕТНОЇ ОБЛАСТІ"),
            "Розділ 1. аналіз предметної області",
        )
        self.assertEqual(
            toc_sentence_case("ДОДАТОК А. ТЕКСТ ПРОГРАМИ"), "Додаток А. текст програми"
        )
        self.assertEqual(
            toc_sentence_case("APPENDIX B. RAW DATA"), "Appendix B. raw data"
        )

    def test_is_title_details_table(self) -> None:
        table_xml = (
            '<w:tbl xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '  <w:tblPr><w:tblCaption w:val="md2dstu-title-details"/></w:tblPr>'
            "</w:tbl>"
        )
        table = ET.fromstring(table_xml)
        self.assertTrue(TableModifier.is_title_details_table(table))

        regular_table_xml = (
            '<w:tbl xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '  <w:tblPr><w:tblCaption w:val="Regular Table"/></w:tblPr>'
            "</w:tbl>"
        )
        regular_table = ET.fromstring(regular_table_xml)
        self.assertFalse(TableModifier.is_title_details_table(regular_table))

    def test_split_table_repeats_header_and_relabels_previous_end(self) -> None:
        namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

        def row(text: str) -> str:
            return f"<w:tr><w:tc><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:tc></w:tr>"

        document = (
            f'<w:document xmlns:w="{namespace}"><w:body>'
            '<w:p><w:pPr><w:pStyle w:val="TableCaption"/></w:pPr>'
            "<w:r><w:t>Таблиця 2.1 – Дані</w:t></w:r></w:p>"
            f"<w:tbl>{row('H')}{row('1')}{row('2')}{row('3')}{row('4')}</w:tbl>"
            "</w:body></w:document>"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            docx_path = Path(temp_dir) / "t.docx"
            with zipfile.ZipFile(docx_path, "w") as archive:
                archive.writestr("word/document.xml", document)

            self.assertTrue(split_table(docx_path, 0, 3))
            self.assertTrue(split_table(docx_path, 1, 2))
            self.assertFalse(split_table(docx_path, 2, 1))

            with zipfile.ZipFile(docx_path) as archive:
                body = ET.fromstring(archive.read("word/document.xml")).find(
                    w_tag("body")
                )

        def text_of(element: ET.Element) -> str:
            return "".join(t.text or "" for t in element.iter(w_tag("t")))

        self.assertEqual(
            [text_of(child) for child in body],
            [
                "Таблиця 2.1 – Дані",
                "H12",
                "Продовження таблиці 2.1",
                "H3",
                "Кінець таблиці 2.1",
                "H4",
            ],
        )
        labels = [child for child in body if child.tag == w_tag("p")][1:]
        for label in labels:
            self.assertIsNotNone(label.find(f"./{w_tag('pPr')}/{w_tag('pageBreakBefore')}"))
            self.assertEqual(
                label.find(f"./{w_tag('pPr')}/{w_tag('pStyle')}").get(w_tag("val")),
                "TableCaption",
            )

    def test_stretch_to_page_width(self) -> None:
        table = ET.fromstring(
            '<w:tbl xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:tblPr><w:tblW w:type="auto" w:w="0"/></w:tblPr>'
            '<w:tblGrid><w:gridCol w:w="2640"/><w:gridCol w:w="5280"/></w:tblGrid>'
            '<w:tr><w:tc><w:tcPr><w:tcW w:type="dxa" w:w="2640"/></w:tcPr></w:tc></w:tr>'
            "</w:tbl>"
        )
        TableModifier.stretch_to_page_width(table)

        widths = [int(c.get(w_tag("w"))) for c in table.iter(w_tag("gridCol"))]
        self.assertAlmostEqual(sum(widths), 9922, delta=1)
        self.assertAlmostEqual(widths[1], 2 * widths[0], delta=1)
        self.assertEqual(table.find(f".//{w_tag('tcW')}").get(w_tag("w")), str(widths[0]))
        table_width = table.find(f".//{w_tag('tblW')}")
        self.assertEqual(table_width.get(w_tag("type")), "dxa")
        self.assertEqual(table_width.get(w_tag("w")), "9922")

    def test_collapse_adjacent_heading_spacing(self) -> None:
        doc_xml = (
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "  <w:body>"
            '    <w:p><w:pPr><w:pStyle w:val="Heading1"/><w:spacing w:after="360"/></w:pPr></w:p>'
            '    <w:p><w:pPr><w:pStyle w:val="Heading2"/><w:spacing w:before="360"/></w:pPr></w:p>'
            "  </w:body>"
            "</w:document>"
        )
        doc = ET.fromstring(doc_xml)
        DocumentModifier.collapse_adjacent_heading_spacing(doc)

        body = doc.find(w_tag("body"))
        self.assertIsNotNone(body)
        paragraphs = body.findall(w_tag("p"))
        first_spacing = paragraphs[0].find(f"./{w_tag('pPr')}/{w_tag('spacing')}")
        second_spacing = paragraphs[1].find(f"./{w_tag('pPr')}/{w_tag('spacing')}")

        self.assertEqual(first_spacing.get(w_tag("after")), "0")
        self.assertEqual(second_spacing.get(w_tag("before")), "0")

    def test_alternative_heading_style_does_not_add_spacing_after_page_break(self) -> None:
        document = ET.fromstring(
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body>"
            '<w:p><w:r><w:t>Previous page content.</w:t></w:r></w:p>'
            '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
            '<w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr>'
            '<w:r><w:t>Next page heading</w:t></w:r></w:p>'
            "</w:body></w:document>"
        )

        DocumentModifier.apply_alternative_heading_style(document)

        body = document.find(w_tag("body"))
        self.assertIsNotNone(body)
        paragraphs = body.findall(w_tag("p"))
        self.assertEqual(len(paragraphs), 3)

    def test_alternative_heading_style_does_not_separate_adjacent_headings(self) -> None:
        document = ET.fromstring(
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body>"
            '<w:p><w:r><w:t>Text before headings.</w:t></w:r></w:p>'
            '<w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr>'
            '<w:r><w:t>Second level</w:t></w:r></w:p>'
            '<w:p><w:pPr><w:pStyle w:val="Heading3"/></w:pPr>'
            '<w:r><w:t>Third level</w:t></w:r></w:p>'
            "</w:body></w:document>"
        )

        DocumentModifier.apply_alternative_heading_style(document)

        body = document.find(w_tag("body"))
        self.assertIsNotNone(body)
        paragraphs = body.findall(w_tag("p"))
        self.assertEqual(len(paragraphs), 4)
        self.assertEqual(
            paragraphs[1].find(f"./{w_tag('pPr')}/{w_tag('pStyle')}").get(
                w_tag("val")
            ),
            "Normal",
        )
        self.assertEqual(
            paragraphs[2].find(f"./{w_tag('pPr')}/{w_tag('pStyle')}").get(
                w_tag("val")
            ),
            "Heading2",
        )
        self.assertEqual(
            paragraphs[3].find(f"./{w_tag('pPr')}/{w_tag('pStyle')}").get(
                w_tag("val")
            ),
            "Heading3",
        )

    def test_alternative_heading_style_zeroes_spacing_and_inserts_one_blank_line(self) -> None:
        document = ET.fromstring(
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body>"
            '<w:p><w:r><w:t>Text before heading.</w:t></w:r></w:p>'
            '<w:p><w:pPr><w:pStyle w:val="Heading1"/><w:pageBreakBefore/></w:pPr>'
            '<w:r><w:t>First level</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>Text before second level.</w:t></w:r></w:p>'
            '<w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr>'
            '<w:r><w:t>Second level</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>More text.</w:t></w:r></w:p>'
            '<w:p><w:pPr><w:pStyle w:val="Heading3"/></w:pPr>'
            '<w:r><w:t>Third level</w:t></w:r></w:p>'
            "</w:body></w:document>"
        )
        styles = ET.fromstring(
            '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:style w:type="paragraph" w:styleId="Heading1"><w:pPr>'
            '<w:pageBreakBefore/></w:pPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Heading2"><w:pPr>'
            '<w:spacing w:before="360" w:after="360"/></w:pPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Heading3"><w:pPr>'
            '<w:spacing w:before="360" w:after="360"/></w:pPr></w:style>'
            "</w:styles>"
        )

        DocumentModifier.apply_alternative_heading_style(document, styles)

        body = document.find(w_tag("body"))
        self.assertIsNotNone(body)
        paragraphs = body.findall(w_tag("p"))
        self.assertEqual(len(paragraphs), 8)
        for index in (3, 6):
            self.assertEqual(
                "".join(text.text or "" for text in paragraphs[index].iter(w_tag("t"))),
                "",
            )
        for paragraph in (paragraphs[4], paragraphs[7]):
            spacing = paragraph.find(f"./{w_tag('pPr')}/{w_tag('spacing')}")
            self.assertEqual(spacing.get(w_tag("before")), "0")
            self.assertEqual(spacing.get(w_tag("after")), "0")

        DocumentModifier.apply_alternative_heading_style(document, styles)
        self.assertEqual(len(body.findall(w_tag("p"))), 8)

    def test_alternative_heading_style_zeroes_style_spacing(self) -> None:
        styles = ET.fromstring(
            '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            + "".join(
                f'<w:style w:type="paragraph" w:styleId="Heading{level}"><w:pPr>'
                '<w:spacing w:before="360" w:after="240" w:line="360"/>'
                "</w:pPr></w:style>"
                for level in range(1, 10)
            )
            + "</w:styles>"
        )

        StyleModifier.apply_alternative_heading_style(styles)

        for style in styles.findall(w_tag("style")):
            spacing = style.find(f"./{w_tag('pPr')}/{w_tag('spacing')}")
            self.assertEqual(spacing.get(w_tag("before")), "0")
            self.assertEqual(spacing.get(w_tag("after")), "0")
            self.assertEqual(spacing.get(w_tag("line")), "360")

    def test_bold_headings_flag_covers_heading_levels_one_through_nine(self) -> None:
        with tempfile.TemporaryDirectory(prefix="md2dstu-heading-styles-") as temp_dir:
            styles_path = Path(temp_dir) / "styles.xml"
            styles_path.write_text(
                '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                + "".join(
                    f'<w:style w:type="paragraph" w:styleId="Heading{level}">'
                    "<w:rPr/>"
                    "</w:style>"
                    for level in range(1, 10)
                )
                + "</w:styles>",
                encoding="utf-8",
            )

            StyleModifier.set_headings_bold(styles_path, enabled=True)
            styles = ET.parse(styles_path).getroot()
            for level in range(1, 10):
                heading = styles.find(
                    f".//{w_tag('style')}[@{w_tag('styleId')}='Heading{level}']"
                )
                properties = heading.find(w_tag("rPr"))
                self.assertIsNotNone(properties.find(w_tag("b")))
                self.assertIsNotNone(properties.find(w_tag("bCs")))

            for level in range(1, 10):
                heading = styles.find(
                    f".//{w_tag('style')}[@{w_tag('styleId')}='Heading{level}']"
                )
                properties = heading.find(w_tag("rPr"))
                properties.find(w_tag("b")).set(w_tag("val"), "0")
                properties.find(w_tag("bCs")).set(w_tag("val"), "0")
            ET.ElementTree(styles).write(styles_path, encoding="utf-8")

            StyleModifier.set_headings_bold(styles_path, enabled=False)
            styles = ET.parse(styles_path).getroot()
            first_heading = styles.find(
                f".//{w_tag('style')}[@{w_tag('styleId')}='Heading1']"
            )
            self.assertIsNotNone(first_heading.find(f"./{w_tag('rPr')}/{w_tag('b')}"))
            for level in range(2, 10):
                heading = styles.find(
                    f".//{w_tag('style')}[@{w_tag('styleId')}='Heading{level}']"
                )
                properties = heading.find(w_tag("rPr"))
                if level == 2:
                    self.assertIsNone(properties.find(w_tag("b")))
                    self.assertIsNone(properties.find(w_tag("bCs")))
                else:
                    self.assertEqual(
                        properties.find(w_tag("b")).get(w_tag("val")), "0"
                    )
                    self.assertEqual(
                        properties.find(w_tag("bCs")).get(w_tag("val")), "0"
                    )


if __name__ == "__main__":
    unittest.main()
