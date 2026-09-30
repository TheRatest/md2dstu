"""List numbering adjustments and Ukrainian Cyrillic sub-list markers."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from md2dstu.constants import (
    FONT_NAME_TIMES,
    FONT_SIZE_BODY_HALF_POINTS,
    INDENT_FIRST_LINE_DXA,
    INDENT_LIST_HANGING_DXA,
    LINE_SPACING_1_5,
    UKRAINIAN_ALPHABET_LOWER,
)
from md2dstu.docx.namespaces import register_openxml_namespaces, w_tag


class NumberingModifier:
    """Handles list indentation, standard markers, and Ukrainian Cyrillic level-2 markers."""

    @staticmethod
    def normalize_list_numbering(numbering_path: Path) -> None:
        """Enforce Times New Roman 14 pt, 1.5 line spacing, and DSTU list indents."""
        register_openxml_namespaces()
        tree = ET.parse(numbering_path)
        root = tree.getroot()

        for level_elem in root.iter(w_tag("lvl")):
            level_index = int(level_elem.get(w_tag("ilvl"), "0"))
            number_format = level_elem.find(w_tag("numFmt"))
            level_text = level_elem.find(w_tag("lvlText"))

            if number_format is not None and level_text is not None:
                format_name = number_format.get(w_tag("val"), "")
                if format_name == "bullet":
                    # DSTU standard dash bullet
                    level_text.set(w_tag("val"), "–")
                else:
                    # DSTU hierarchy: 1., a), i.
                    if level_index == 0:
                        number_format.set(w_tag("val"), "decimal")
                        level_text.set(w_tag("val"), "%1.")
                    elif level_index == 1:
                        number_format.set(w_tag("val"), "lowerLetter")
                        level_text.set(w_tag("val"), "%2)")
                    elif level_index == 2:
                        number_format.set(w_tag("val"), "lowerRoman")
                        level_text.set(w_tag("val"), "%3.")

            properties = level_elem.find(w_tag("pPr"))
            if properties is None:
                properties = ET.SubElement(level_elem, w_tag("pPr"))

            indent = properties.find(w_tag("ind"))
            if indent is None:
                indent = ET.SubElement(properties, w_tag("ind"))

            marker_position = (level_index + 1) * INDENT_FIRST_LINE_DXA
            hanging_indent = INDENT_LIST_HANGING_DXA
            left_indent = marker_position + hanging_indent

            indent.set(w_tag("left"), str(left_indent))
            indent.attrib.pop(w_tag("firstLine"), None)
            indent.set(w_tag("hanging"), str(hanging_indent))

            tabs = properties.find(w_tag("tabs"))
            if tabs is not None:
                properties.remove(tabs)

            spacing = properties.find(w_tag("spacing"))
            if spacing is None:
                spacing = ET.SubElement(properties, w_tag("spacing"))
            spacing.set(w_tag("before"), "0")
            spacing.set(w_tag("after"), "0")
            spacing.set(w_tag("line"), str(LINE_SPACING_1_5))
            spacing.set(w_tag("lineRule"), "auto")

            run_properties = level_elem.find(w_tag("rPr"))
            if run_properties is None:
                run_properties = ET.SubElement(level_elem, w_tag("rPr"))

            fonts = run_properties.find(w_tag("rFonts"))
            if fonts is None:
                fonts = ET.SubElement(run_properties, w_tag("rFonts"))
            for font_attr in ("ascii", "hAnsi", "eastAsia", "cs"):
                fonts.set(w_tag(font_attr), FONT_NAME_TIMES)

            for size_attr in ("sz", "szCs"):
                size_elem = run_properties.find(w_tag(size_attr))
                if size_elem is None:
                    size_elem = ET.SubElement(run_properties, w_tag(size_attr))
                size_elem.set(w_tag("val"), str(FONT_SIZE_BODY_HALF_POINTS))

        tree.write(numbering_path, encoding="UTF-8", xml_declaration=True)

    @staticmethod
    def normalize_list_paragraphs(document_root: ET.Element) -> None:
        """Align paragraph indents of list items to match the numbering definition."""
        for paragraph in document_root.iter(w_tag("p")):
            properties = paragraph.find(w_tag("pPr"))
            if properties is None:
                continue

            num_properties = properties.find(w_tag("numPr"))
            if num_properties is None:
                continue

            level = num_properties.find(w_tag("ilvl"))
            level_index = int(level.get(w_tag("val"), "0")) if level is not None else 0

            indent = properties.find(w_tag("ind"))
            if indent is None:
                indent = ET.SubElement(properties, w_tag("ind"))

            marker_position = (level_index + 1) * INDENT_FIRST_LINE_DXA
            hanging_indent = INDENT_LIST_HANGING_DXA
            left_indent = marker_position + hanging_indent

            indent.set(w_tag("left"), str(left_indent))
            indent.attrib.pop(w_tag("firstLine"), None)
            indent.set(w_tag("hanging"), str(hanging_indent))

    @staticmethod
    def apply_ukrainian_second_level_markers(
        document_root: ET.Element,
        numbering_path: Path,
    ) -> None:
        """Replace ordered-list level 2 counters with explicit Cyrillic markers (а, б, в…)."""
        register_openxml_namespaces()
        numbering_root = ET.parse(numbering_path).getroot()

        # Map abstractNumId to format of level 0
        abstract_kind: dict[str, str] = {}
        for abstract in numbering_root.findall(w_tag("abstractNum")):
            first_format = abstract.find(
                f"./{w_tag('lvl')}[@{w_tag('ilvl')}='0']/{w_tag('numFmt')}"
            )
            abstract_id = abstract.get(w_tag("abstractNumId"), "")
            abstract_kind[abstract_id] = (
                first_format.get(w_tag("val"), "") if first_format is not None else ""
            )

        # Collect numIds of ordered lists
        ordered_num_ids: set[str] = set()
        for number_def in numbering_root.findall(w_tag("num")):
            abstract_ref = number_def.find(w_tag("abstractNumId"))
            if abstract_ref is not None:
                abs_id = abstract_ref.get(w_tag("val"), "")
                if abstract_kind.get(abs_id) != "bullet":
                    ordered_num_ids.add(number_def.get(w_tag("numId"), ""))

        counters: dict[str, int] = {}
        for paragraph in document_root.iter(w_tag("p")):
            num_properties = paragraph.find(f"./{w_tag('pPr')}/{w_tag('numPr')}")
            if num_properties is None:
                continue

            level = num_properties.find(w_tag("ilvl"))
            num_id_elem = num_properties.find(w_tag("numId"))
            if level is None or num_id_elem is None or level.get(w_tag("val")) != "1":
                continue

            num_id = num_id_elem.get(w_tag("val"), "")
            if num_id not in ordered_num_ids:
                continue

            counter_index = counters.get(num_id, 0)
            counters[num_id] = counter_index + 1

            if counter_index < len(UKRAINIAN_ALPHABET_LOWER):
                marker_letter = UKRAINIAN_ALPHABET_LOWER[counter_index]
            else:
                marker_letter = str(counter_index + 1)

            # Strip Word automatic numbering from this paragraph
            paragraph_props = paragraph.find(w_tag("pPr"))
            if paragraph_props is not None:
                paragraph_props.remove(num_properties)

            # Insert an explicit editable text run with Ukrainian Cyrillic marker
            run = ET.Element(w_tag("r"))
            run_props = ET.SubElement(run, w_tag("rPr"))
            fonts = ET.SubElement(run_props, w_tag("rFonts"))
            for font_attr in ("ascii", "hAnsi", "eastAsia", "cs"):
                fonts.set(w_tag(font_attr), FONT_NAME_TIMES)

            ET.SubElement(
                run_props, w_tag("sz"), {w_tag("val"): str(FONT_SIZE_BODY_HALF_POINTS)}
            )
            ET.SubElement(
                run_props,
                w_tag("szCs"),
                {w_tag("val"): str(FONT_SIZE_BODY_HALF_POINTS)},
            )

            text_node = ET.SubElement(
                run,
                w_tag("t"),
                {"{http://www.w3.org/XML/1998/namespace}space": "preserve"},
            )
            text_node.text = f"{marker_letter}) "

            first_content_index = next(
                (
                    i
                    for i, child in enumerate(list(paragraph))
                    if child.tag != w_tag("pPr")
                ),
                len(paragraph),
            )
            paragraph.insert(first_content_index, run)
