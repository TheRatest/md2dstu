"""Coordinates post-processing of the generated DOCX package."""

from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from md2dstu.docx.document import DocumentModifier
from md2dstu.docx.headers import HeaderModifier
from md2dstu.docx.namespaces import register_openxml_namespaces, w_tag
from md2dstu.docx.numbering import NumberingModifier
from md2dstu.docx.styles import StyleModifier, normalize_code_styles
from md2dstu.docx.tables import TableModifier


class DocxPostProcessor:
    """Orchestrates XML post-processing steps on the unpacked DOCX package."""

    def __init__(
        self, bold_headings: bool = False, alt_heading_style: bool = False
    ) -> None:
        self.bold_headings = bold_headings
        self.alt_heading_style = alt_heading_style

    def process(self, docx_path: Path) -> None:
        """Unpack docx_path, apply all style and structural corrections, and repack."""
        register_openxml_namespaces()

        with tempfile.TemporaryDirectory(prefix="md2dstu-post-") as temporary_dir:
            unpacked = Path(temporary_dir)
            with zipfile.ZipFile(docx_path) as archive:
                archive.extractall(unpacked)

            word_dir = unpacked / "word"
            styles_path = word_dir / "styles.xml"
            numbering_path = word_dir / "numbering.xml"
            settings_path = word_dir / "settings.xml"
            document_path = word_dir / "document.xml"

            # 1. Styles adjustments
            styles_root: ET.Element | None = None
            if styles_path.is_file():
                StyleModifier.set_headings_bold(styles_path, self.bold_headings)
                StyleModifier.normalize_toc_styles(styles_path)
                styles_tree = ET.parse(styles_path)
                styles_root = styles_tree.getroot()
                normalize_code_styles(styles_root)
                StyleModifier.disable_proofing(styles_root)
                if self.alt_heading_style:
                    StyleModifier.apply_alternative_heading_style(styles_root)
                styles_tree.write(styles_path, encoding="UTF-8", xml_declaration=True)

            # 2. Numbering definitions
            if numbering_path.is_file():
                NumberingModifier.normalize_list_numbering(numbering_path)

            # 3. Header page numbers font
            HeaderModifier.set_page_number_font(unpacked)

            # 4. Settings (prevent Word from clearing TOC before update)
            if settings_path.is_file():
                DocumentModifier.disable_field_update_on_open(settings_path)

            # 5. Document body content adjustments
            if document_path.is_file():
                doc_tree = ET.parse(document_path)
                doc_root = doc_tree.getroot()

                StyleModifier.disable_proofing(doc_root)
                NumberingModifier.normalize_list_paragraphs(doc_root)
                if numbering_path.is_file():
                    NumberingModifier.apply_ukrainian_second_level_markers(
                        doc_root, numbering_path
                    )
                DocumentModifier.set_code_block_character_style(doc_root)
                if self.alt_heading_style:
                    DocumentModifier.apply_alternative_heading_style(
                        doc_root, styles_root
                    )
                DocumentModifier.collapse_adjacent_heading_spacing(doc_root)
                DocumentModifier.position_toc_after_title_page(doc_root)

                for table in doc_root.iter(w_tag("tbl")):
                    if TableModifier.is_title_details_table(table):
                        TableModifier.set_invisible_table_borders(table)
                    else:
                        TableModifier.set_table_borders(table)
                        TableModifier.stretch_to_page_width(table)
                    TableModifier.ensure_repeating_table_header(table)

                doc_tree.write(document_path, encoding="UTF-8", xml_declaration=True)

            # 6. Repack DOCX archive
            rebuilt_docx = docx_path.with_suffix(docx_path.suffix + ".rebuilt")
            with zipfile.ZipFile(rebuilt_docx, "w", zipfile.ZIP_DEFLATED) as archive:
                for item in sorted(unpacked.rglob("*")):
                    if item.is_file():
                        archive.write(item, item.relative_to(unpacked).as_posix())

            os.replace(rebuilt_docx, docx_path)
