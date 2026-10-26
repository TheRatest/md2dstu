"""WordprocessingML style manipulation and normalization."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from md2dstu.constants import (
    FONT_NAME_CODE,
    FONT_NAME_TIMES,
    FONT_SIZE_BODY_HALF_POINTS,
    FONT_SIZE_CODE_HALF_POINTS,
    INDENT_FIRST_LINE_DXA,
    LINE_SPACING_1_5,
    LINE_SPACING_SINGLE,
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


def normalize_code_styles(styles_root: ET.Element) -> None:
    """Use Courier New 11 pt for inline code and bold fenced-code styles."""
    code_styles = (
        ("VerbatimChar", "Verbatim Char", "character", False),
        ("CodeBlockChar", "Code Block Char", "character", True),
        ("SourceCode", "Source Code", "paragraph", True),
    )
    for style_id, name, style_type, bold in code_styles:
        style = styles_root.find(
            f".//{w_tag('style')}[@{w_tag('styleId')}='{style_id}']"
        )
        if style is None:
            style = ET.Element(
                w_tag("style"),
                {
                    w_tag("type"): style_type,
                    w_tag("customStyle"): "1",
                    w_tag("styleId"): style_id,
                },
            )
            child_element(style, "name", val=name)
            if style_type == "paragraph":
                child_element(style, "basedOn", val="Normal")
                child_element(style, "next", val="BodyText")
                child_element(style, "qFormat")
                apply_paragraph_properties(
                    style,
                    alignment="left",
                    line_spacing=LINE_SPACING_SINGLE,
                    first_line_indent=0,
                )

            extension_list = styles_root.find(w_tag("extLst"))
            if extension_list is None:
                styles_root.append(style)
            else:
                styles_root.insert(list(styles_root).index(extension_list), style)

        apply_run_properties(
            style,
            font_family=FONT_NAME_CODE,
            size_half_points=FONT_SIZE_CODE_HALF_POINTS,
            bold=bold,
        )


class StyleModifier:
    """Encapsulates style modifications for DOCX styles.xml."""

    @staticmethod
    def set_headings_bold(styles_path: Path, enabled: bool) -> None:
        """Apply bold weight to all heading styles, preserving the default otherwise."""
        register_openxml_namespaces()
        tree = ET.parse(styles_path)
        root = tree.getroot()
        for level in range(1, 10):
            heading = root.find(
                f".//{w_tag('style')}[@{w_tag('styleId')}='Heading{level}']"
            )
            if heading is None:
                continue

            run_properties = heading.find(w_tag("rPr"))
            if run_properties is None:
                if not enabled:
                    continue
                run_properties = ET.SubElement(heading, w_tag("rPr"))

            for tag_name in ("b", "bCs"):
                element = run_properties.find(w_tag(tag_name))
                if enabled:
                    if element is None:
                        ET.SubElement(run_properties, w_tag(tag_name))
                    else:
                        element.attrib.pop(w_tag("val"), None)
                elif level == 2 and element is not None:
                    run_properties.remove(element)

        tree.write(styles_path, encoding="UTF-8", xml_declaration=True)

    @staticmethod
    def apply_alternative_heading_style(styles_root: ET.Element) -> None:
        """Remove before/after spacing from Heading 1 through Heading 9 styles."""
        for level in range(1, 10):
            heading = styles_root.find(
                f".//{w_tag('style')}[@{w_tag('styleId')}='Heading{level}']"
            )
            if heading is None:
                continue

            paragraph_properties = heading.find(w_tag("pPr"))
            if paragraph_properties is None:
                paragraph_properties = ET.Element(w_tag("pPr"))
                run_properties = heading.find(w_tag("rPr"))
                if run_properties is None:
                    heading.append(paragraph_properties)
                else:
                    heading.insert(list(heading).index(run_properties), paragraph_properties)

            spacing = paragraph_properties.find(w_tag("spacing"))
            if spacing is None:
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
            spacing.set(w_tag("before"), "0")
            spacing.set(w_tag("after"), "0")

    @staticmethod
    def disable_proofing(root: ET.Element) -> None:
        """Mark all text as language "None" so editors skip spell checking.

        Works on styles.xml and document.xml roots: every explicit w:lang is
        dropped and, in styles.xml, docDefaults get "zxx" (LibreOffice's
        "[None]") plus w:noProof (Word's "Do not check spelling").
        """
        for parent in list(root.iter()):
            for language in parent.findall(w_tag("lang")):
                parent.remove(language)

        defaults = root.find(f"./{w_tag('docDefaults')}")
        if defaults is None:
            return
        rpr_default = defaults.find(w_tag("rPrDefault"))
        if rpr_default is None:
            rpr_default = ET.Element(w_tag("rPrDefault"))
            defaults.insert(0, rpr_default)
        run_properties = rpr_default.find(w_tag("rPr"))
        if run_properties is None:
            run_properties = ET.SubElement(rpr_default, w_tag("rPr"))

        if run_properties.find(w_tag("noProof")) is None:
            # Schema order: noProof precedes color, size, and later properties.
            later = {
                w_tag(name)
                for name in (
                    "snapToGrid vanish webHidden color spacing w kern position sz "
                    "szCs highlight u effect bdr shd fitText vertAlign rtl cs em "
                    "lang eastAsianLayout specVanish oMath"
                ).split()
            }
            position = next(
                (i for i, child in enumerate(run_properties) if child.tag in later),
                len(run_properties),
            )
            run_properties.insert(position, ET.Element(w_tag("noProof")))

        ET.SubElement(
            run_properties,
            w_tag("lang"),
            {w_tag("val"): "zxx", w_tag("eastAsia"): "zxx", w_tag("bidi"): "zxx"},
        )

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
