"""Document-level paragraph structure, heading spacing, and TOC positioning."""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path
from xml.etree import ElementTree as ET

from md2dstu.constants import (
    APPENDIX_TITLE_SPACING_AFTER_DXA,
    FONT_NAME_CODE,
    FONT_SIZE_CODE_HALF_POINTS,
)
from md2dstu.docx.namespaces import register_openxml_namespaces, w_tag


class DocumentModifier:
    """Modifies document.xml paragraph flow and settings.xml field settings."""

    @staticmethod
    def apply_alternative_heading_style(
        document_root: ET.Element,
        styles_root: ET.Element | None = None,
    ) -> None:
        """Zero heading paragraph spacing and add one empty paragraph before headings."""
        body = document_root.find(w_tag("body"))
        if body is None:
            return

        heading_styles = {f"Heading{level}" for level in range(1, 10)}
        styles_by_id = (
            {
                style.get(w_tag("styleId")): style
                for style in styles_root.findall(w_tag("style"))
                if style.get(w_tag("styleId"))
            }
            if styles_root is not None
            else {}
        )

        def has_page_break_before(style_id: str, seen: set[str] | None = None) -> bool:
            seen = seen or set()
            if style_id in seen:
                return False
            seen.add(style_id)
            style = styles_by_id.get(style_id)
            if style is None:
                return False
            paragraph_properties = style.find(w_tag("pPr"))
            page_break = (
                paragraph_properties.find(w_tag("pageBreakBefore"))
                if paragraph_properties is not None
                else None
            )
            if (
                page_break is not None
                and page_break.get(w_tag("val"), "true").lower()
                not in {"0", "false", "off"}
            ):
                return True
            based_on = style.find(w_tag("basedOn"))
            return (
                has_page_break_before(based_on.get(w_tag("val")), seen)
                if based_on is not None
                else False
            )

        def has_text(element: ET.Element) -> bool:
            return any((text.text or "").strip() for text in element.iter(w_tag("t")))

        def is_heading(element: ET.Element) -> bool:
            if element.tag != w_tag("p"):
                return False
            paragraph_properties = element.find(w_tag("pPr"))
            style = (
                paragraph_properties.find(w_tag("pStyle"))
                if paragraph_properties is not None
                else None
            )
            return style is not None and style.get(w_tag("val")) in heading_styles

        def has_page_break(element: ET.Element) -> bool:
            return any(
                line_break.get(w_tag("type")) == "page"
                for line_break in element.iter(w_tag("br"))
            )

        def ensure_spacing(paragraph_properties: ET.Element) -> ET.Element:
            spacing = paragraph_properties.find(w_tag("spacing"))
            if spacing is not None:
                return spacing

            spacing = ET.Element(w_tag("spacing"))
            later_properties = {
                w_tag(name)
                for name in (
                    "ind",
                    "contextualSpacing",
                    "mirrorIndents",
                    "suppressOverlap",
                    "jc",
                    "textDirection",
                    "textAlignment",
                    "outlineLvl",
                    "divId",
                    "cnfStyle",
                    "rPr",
                    "sectPr",
                    "pPrChange",
                )
            }
            position = next(
                (
                    index
                    for index, child in enumerate(paragraph_properties)
                    if child.tag in later_properties
                ),
                len(paragraph_properties),
            )
            paragraph_properties.insert(position, spacing)
            return spacing

        body_children = list(body)
        normalized: list[ET.Element] = []
        text_before = False
        for element in body_children:
            heading_style = None
            if element.tag == w_tag("p"):
                paragraph_properties = element.find(w_tag("pPr"))
                style = (
                    paragraph_properties.find(w_tag("pStyle"))
                    if paragraph_properties is not None
                    else None
                )
                if style is not None and style.get(w_tag("val")) in heading_styles:
                    heading_style = style.get(w_tag("val"))
                    if paragraph_properties is None:
                        paragraph_properties = ET.Element(w_tag("pPr"))
                        element.insert(0, paragraph_properties)

                    spacing = ensure_spacing(paragraph_properties)
                    spacing.set(w_tag("before"), "0")
                    spacing.set(w_tag("after"), "0")

            starts_new_page = False
            if heading_style is not None:
                paragraph_properties = element.find(w_tag("pPr"))
                page_break = (
                    paragraph_properties.find(w_tag("pageBreakBefore"))
                    if paragraph_properties is not None
                    else None
                )
                if page_break is not None:
                    starts_new_page = page_break.get(
                        w_tag("val"), "true"
                    ).lower() not in {"0", "false", "off"}
                else:
                    starts_new_page = has_page_break_before(heading_style)

                previous_content_is_heading = False
                for previous in reversed(normalized):
                    if has_page_break(previous):
                        break
                    if has_text(previous):
                        previous_content_is_heading = is_heading(previous)
                        break

                if previous_content_is_heading:
                    while (
                        normalized
                        and normalized[-1].tag == w_tag("p")
                        and not has_text(normalized[-1])
                        and not has_page_break(normalized[-1])
                    ):
                        normalized.pop()

                while (
                    len(normalized) >= 2
                    and all(
                        paragraph.tag == w_tag("p")
                        and not has_text(paragraph)
                        and not has_page_break(paragraph)
                        for paragraph in normalized[-2:]
                    )
                ):
                    normalized.pop()
                previous_is_blank = bool(
                    normalized
                    and normalized[-1].tag == w_tag("p")
                    and not has_text(normalized[-1])
                    and not has_page_break(normalized[-1])
                )
                if (
                    text_before
                    and not starts_new_page
                    and not previous_is_blank
                    and not previous_content_is_heading
                ):
                    spacer = ET.Element(w_tag("p"))
                    spacer_properties = ET.SubElement(spacer, w_tag("pPr"))
                    ET.SubElement(
                        spacer_properties,
                        w_tag("pStyle"),
                        {w_tag("val"): "Normal"},
                    )
                    ET.SubElement(
                        spacer_properties,
                        w_tag("spacing"),
                        {w_tag("before"): "0", w_tag("after"): "0"},
                    )
                    normalized.append(spacer)

                if starts_new_page:
                    text_before = False

            normalized.append(element)
            if has_page_break(element):
                text_before = False
            elif has_text(element):
                text_before = True

        body[:] = normalized

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
    def set_appendix_title_spacing(document_root: ET.Element) -> None:
        """Keep the DSTU gap after "ДОДАТОК А" + title, whatever follows it."""
        body = document_root.find(w_tag("body"))
        if body is None:
            return

        for paragraph in body.findall(w_tag("p")):
            style = paragraph.find(f"./{w_tag('pPr')}/{w_tag('pStyle')}")
            if style is None or style.get(w_tag("val")) != "Heading1":
                continue
            text = "".join(t.text or "" for t in paragraph.iter(w_tag("t")))
            if not text.strip().upper().startswith(("ДОДАТОК", "APPENDIX")):
                continue

            properties = paragraph.find(w_tag("pPr"))
            spacing = properties.find(w_tag("spacing"))
            if spacing is None:
                spacing = ET.SubElement(properties, w_tag("spacing"))
            spacing.set(w_tag("after"), str(APPENDIX_TITLE_SPACING_AFTER_DXA))

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
