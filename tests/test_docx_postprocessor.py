"""Unit tests for DOCX postprocessor and XML modifiers."""

from __future__ import annotations

import unittest
from xml.etree import ElementTree as ET

from md2dstu.docx.document import DocumentModifier
from md2dstu.docx.namespaces import w_tag
from md2dstu.docx.tables import TableModifier
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


if __name__ == "__main__":
    unittest.main()
