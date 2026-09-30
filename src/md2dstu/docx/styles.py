"""WordprocessingML style manipulation and normalization."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from md2dstu.constants import (
    FONT_NAME_TIMES,
    FONT_SIZE_BODY_HALF_POINTS,
    INDENT_FIRST_LINE_DXA,
    LINE_SPACING_1_5,
    PAGE_CONTENT_WIDTH_DXA,
)
from md2dstu.docx.namespaces import (
    child_element,
    register_openxml_namespaces,
    replace_child_element,
    w_tag,
)


def apply_run_properties(
    owner: ET.Element,
    *,
    font_family: str = FONT_NAME_TIMES,
    size_half_points: int = FONT_SIZE_BODY_HALF_POINTS,
    bold: bool = False,
    italic: bool = False,
    color_hex: str = "000000",
) -> ET.Element:
    """Configure or replace a run property block (w:rPr)."""
    properties = replace_child_element(owner, "rPr")
    child_element(
        properties,
        "rFonts",
        ascii=font_family,
        hAnsi=font_family,
        eastAsia=font_family,
        cs=font_family,
    )
    child_element(properties, "color", val=color_hex)
    if bold:
        child_element(properties, "b")
        child_element(properties, "bCs")
    if italic:
        child_element(properties, "i")
        child_element(properties, "iCs")
    child_element(properties, "sz", val=str(size_half_points))
    child_element(properties, "szCs", val=str(size_half_points))
    return properties


def apply_paragraph_properties(
    owner: ET.Element,
    *,
    alignment: str = "both",
    spacing_before: int = 0,
    spacing_after: int = 0,
    line_spacing: int = LINE_SPACING_1_5,
    first_line_indent: int | None = INDENT_FIRST_LINE_DXA,
    left_indent: int | None = None,
    keep_with_next: bool = False,
    page_break_before: bool = False,
    outline_level: int | None = None,
) -> ET.Element:
    """Configure or replace a paragraph property block (w:pPr)."""
    properties = replace_child_element(owner, "pPr")
    if keep_with_next:
        child_element(properties, "keepNext")
    if page_break_before:
        child_element(properties, "pageBreakBefore")
    child_element(properties, "widowControl")
    child_element(
        properties,
        "spacing",
        before=str(spacing_before),
        after=str(spacing_after),
        line=str(line_spacing),
        lineRule="auto",
    )
    indent_kwargs: dict[str, str] = {}
    if first_line_indent is not None:
        indent_kwargs["firstLine"] = str(first_line_indent)
    if left_indent is not None:
        indent_kwargs["left"] = str(left_indent)
    if indent_kwargs:
        child_element(properties, "ind", **indent_kwargs)
    child_element(properties, "jc", val=alignment)
    if outline_level is not None:
        child_element(properties, "outlineLvl", val=str(outline_level))
    return properties


class StyleModifier:
    """Encapsulates style modifications for DOCX styles.xml."""

    @staticmethod
    def set_heading2_bold(styles_path: Path, enabled: bool) -> None:
        """Toggle bold weight for Heading 2 style in styles.xml."""
        register_openxml_namespaces()
        tree = ET.parse(styles_path)
        root = tree.getroot()
        heading_element = root.find(
            f".//{w_tag('style')}[@{w_tag('styleId')}='Heading2']"
        )
        if heading_element is None:
            return

        run_properties = heading_element.find(w_tag("rPr"))
        if run_properties is None:
            run_properties = ET.SubElement(heading_element, w_tag("rPr"))

        for tag_name in ("b", "bCs"):
            element = run_properties.find(w_tag(tag_name))
            if enabled:
                if element is None:
                    ET.SubElement(run_properties, w_tag(tag_name))
                else:
                    element.attrib.pop(w_tag("val"), None)
            elif element is not None:
                run_properties.remove(element)

        tree.write(styles_path, encoding="UTF-8", xml_declaration=True)

    @staticmethod
    def normalize_toc_styles(styles_path: Path) -> None:
        """Ensure TOC1..TOC3 have standard DSTU tab stops, line spacing, and fonts."""
        register_openxml_namespaces()
        tree = ET.parse(styles_path)
        root = tree.getroot()

        for level in range(1, 4):
            style_id = f"TOC{level}"
            toc_style = root.find(
                f".//{w_tag('style')}[@{w_tag('styleId')}='{style_id}']"
            )
            if toc_style is None:
                continue

            properties = toc_style.find(w_tag("pPr"))
            if properties is None:
                properties = ET.SubElement(toc_style, w_tag("pPr"))

            tabs = properties.find(w_tag("tabs"))
            if tabs is None:
                tabs = ET.SubElement(properties, w_tag("tabs"))
            for old_tab in list(tabs):
                tabs.remove(old_tab)

            # Dot leader aligned to right margin (9922 dxa)
            ET.SubElement(
                tabs,
                w_tag("tab"),
                {
                    w_tag("val"): "right",
                    w_tag("pos"): str(PAGE_CONTENT_WIDTH_DXA),
                    w_tag("leader"): "dot",
                },
            )

            spacing = properties.find(w_tag("spacing"))
            if spacing is None:
                spacing = ET.SubElement(properties, w_tag("spacing"))
            spacing.set(w_tag("before"), "0")
            spacing.set(w_tag("after"), "0")
            spacing.set(w_tag("line"), str(LINE_SPACING_1_5))
            spacing.set(w_tag("lineRule"), "auto")

            apply_run_properties(
                toc_style,
                font_family=FONT_NAME_TIMES,
                size_half_points=FONT_SIZE_BODY_HALF_POINTS,
            )

        tree.write(styles_path, encoding="UTF-8", xml_declaration=True)
