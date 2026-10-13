"""Document-level paragraph structure, heading spacing, and TOC positioning."""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path
from xml.etree import ElementTree as ET

from md2dstu.constants import FONT_NAME_CODE, FONT_SIZE_CODE_HALF_POINTS
from md2dstu.docx.namespaces import register_openxml_namespaces, w_tag


class DocumentModifier:
    """Modifies document.xml paragraph flow and settings.xml field settings."""

    @staticmethod
    def set_code_block_character_style(document_root: ET.Element) -> None:
        """Apply the bold code character style inside fenced-code paragraphs."""
        for paragraph in document_root.iter(w_tag("p")):
            paragraph_style = paragraph.find(
                f"./{w_tag('pPr')}/{w_tag('pStyle')}"
            )
            if (
                paragraph_style is None
                or paragraph_style.get(w_tag("val")) != "SourceCode"
            ):
                continue

            for run in paragraph.findall(w_tag("r")):
                run_properties = run.find(w_tag("rPr"))
                if run_properties is None:
                    run_properties = ET.Element(w_tag("rPr"))
                    run.insert(0, run_properties)

                character_style = run_properties.find(w_tag("rStyle"))
                if character_style is None:
                    character_style = ET.Element(w_tag("rStyle"))
                    run_properties.insert(0, character_style)
                character_style.set(w_tag("val"), "CodeBlockChar")

                fonts = run_properties.find(w_tag("rFonts"))
                if fonts is None:
                    fonts = ET.SubElement(run_properties, w_tag("rFonts"))
                for font_attribute in ("ascii", "hAnsi", "eastAsia", "cs"):
                    fonts.set(w_tag(font_attribute), FONT_NAME_CODE)

                for property_name in ("b", "bCs"):
                    bold = run_properties.find(w_tag(property_name))
                    if bold is None:
                        ET.SubElement(run_properties, w_tag(property_name))
                    else:
                        bold.attrib.pop(w_tag("val"), None)

                for property_name in ("sz", "szCs"):
                    size = run_properties.find(w_tag(property_name))
                    if size is None:
                        size = ET.SubElement(run_properties, w_tag(property_name))
                    size.set(w_tag("val"), str(FONT_SIZE_CODE_HALF_POINTS))

    @staticmethod
    def collapse_adjacent_heading_spacing(document_root: ET.Element) -> None:
        """Eliminate gap when Heading 1 is immediately followed by Heading 2."""
        body = document_root.find(w_tag("body"))
        if body is None:
            return

        paragraphs = [child for child in body if child.tag == w_tag("p")]
        for first, second in pairwise(paragraphs):
            first_style = first.find(f"./{w_tag('pPr')}/{w_tag('pStyle')}")
            second_style = second.find(f"./{w_tag('pPr')}/{w_tag('pStyle')}")

            if (
                first_style is None
                or second_style is None
                or first_style.get(w_tag("val")) != "Heading1"
                or second_style.get(w_tag("val")) != "Heading2"
            ):
                continue

            for paragraph, attribute in ((first, "after"), (second, "before")):
                properties = paragraph.find(w_tag("pPr"))
                if properties is None:
                    properties = ET.SubElement(paragraph, w_tag("pPr"))
                spacing = properties.find(w_tag("spacing"))
                if spacing is None:
                    spacing = ET.SubElement(properties, w_tag("spacing"))
                spacing.set(w_tag(attribute), "0")

    @staticmethod
    def position_toc_after_title_page(document_root: ET.Element) -> None:
        """Ensure Pandoc's TOC block is positioned after the title-page page break."""
        body = document_root.find(w_tag("body"))
        if body is None:
            return

        body_children = list(body)
        toc_element = next(
            (
                item
                for item in body_children
                if any(
                    (instr.text or "").lstrip().startswith("TOC ")
                    for instr in item.iter(w_tag("instrText"))
                )
            ),
            None,
        )

        if toc_element is not None:
            toc_index = body_children.index(toc_element)
            first_page_break_index = next(
                (
                    idx
                    for idx, item in enumerate(body_children)
                    if any(
                        br.get(w_tag("type")) == "page" for br in item.iter(w_tag("br"))
                    )
                ),
                None,
            )

            if (
                first_page_break_index is not None
                and toc_index < first_page_break_index
            ):
                body.remove(toc_element)
                body.insert(first_page_break_index, toc_element)

    @staticmethod
    def disable_field_update_on_open(settings_path: Path) -> None:
        """Prevent Word/Writer from clearing unpopulated TOC on open."""
        register_openxml_namespaces()
        tree = ET.parse(settings_path)
        root = tree.getroot()

        update_element = root.find(w_tag("updateFields"))
        if update_element is None:
            update_element = ET.SubElement(root, w_tag("updateFields"))
        update_element.set(w_tag("val"), "false")

        tree.write(settings_path, encoding="UTF-8", xml_declaration=True)
