#!/usr/bin/env python3
"""Build the deterministic DSTU 3008:2015 reference DOCX template used by md2dstu."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

# Ensure md2dstu package can be imported from src/
ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from md2dstu.constants import (
    CONTENT_TYPES_NAMESPACE,
    DEFAULT_REFERENCE_DOCX_PATH,
    FONT_NAME_TIMES,
    FONT_SIZE_BODY_HALF_POINTS,
    FONT_SIZE_FOOTNOTE_HALF_POINTS,
    FONT_SIZE_PAGE_NUMBER_HALF_POINTS,
    INDENT_FIRST_LINE_DXA,
    LINE_SPACING_1_5,
    LINE_SPACING_SINGLE,
    MARGIN_BOTTOM_DXA,
    MARGIN_FOOTER_DXA,
    MARGIN_HEADER_DXA,
    MARGIN_LEFT_DXA,
    MARGIN_RIGHT_DXA,
    MARGIN_TOP_DXA,
    PAGE_A4_HEIGHT_DXA,
    PAGE_A4_WIDTH_DXA,
    PAGE_CONTENT_CENTER_DXA,
    PAGE_CONTENT_WIDTH_DXA,
    PKG_REL_NAMESPACE,
    R_NAMESPACE,
    TITLE_SPACER_BOTTOM_DXA,
    TITLE_SPACER_MIDDLE_DXA,
    TITLE_SPACER_TOP_DXA,
)
from md2dstu.docx.namespaces import (
    child_element,
    openxml_tag,
    register_openxml_namespaces,
    w_tag,
)
from md2dstu.docx.styles import apply_paragraph_properties, apply_run_properties
from md2dstu.exceptions import ExternalToolError


class DstuReferenceBuilder:
    """Constructs the reference DOCX template encoding all DSTU layout and styling rules."""

    def __init__(self, target_path: Path = DEFAULT_REFERENCE_DOCX_PATH) -> None:
        self.target_path = target_path

    def build(self) -> Path:
        """Generate the reference DOCX file using Pandoc default template as baseline."""
        if shutil.which("pandoc") is None:
            raise ExternalToolError(
                "Program 'pandoc' is required to build the reference DOCX."
            )

        register_openxml_namespaces()
        self.target_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="md2dstu-ref-build-") as temporary_dir:
            work_dir = Path(temporary_dir)
            default_template = work_dir / "default_pandoc_reference.docx"

            # 1. Extract default Pandoc reference DOCX
            with default_template.open("wb") as stream:
                subprocess.run(
                    ["pandoc", "--print-default-data-file", "reference.docx"],
                    check=True,
                    stdout=stream,
                )

            unpacked_dir = work_dir / "unpacked"
            with zipfile.ZipFile(default_template) as archive:
                archive.extractall(unpacked_dir)

            # 2. Configure styles.xml
            styles_path = unpacked_dir / "word" / "styles.xml"
            styles_tree = ET.parse(styles_path)
            self._configure_styles(styles_tree.getroot())
            styles_tree.write(styles_path, encoding="UTF-8", xml_declaration=True)

            # 3. Configure page geometry and section properties in document.xml
            document_path = unpacked_dir / "word" / "document.xml"
            document_tree = ET.parse(document_path)
            body = document_tree.getroot().find(w_tag("body"))
            if body is not None:
                self._configure_page_geometry(body)
            document_tree.write(document_path, encoding="UTF-8", xml_declaration=True)

            # 4. Create and attach header1.xml for right-aligned page numbering
            self._create_header_part(unpacked_dir)

            # 5. Configure settings.xml (disable auto-field update on open, paragraph compatibility)
            settings_path = unpacked_dir / "word" / "settings.xml"
            settings_tree = ET.parse(settings_path)
            self._configure_settings(settings_tree.getroot())
            settings_tree.write(settings_path, encoding="UTF-8", xml_declaration=True)

            # 6. Repack into final reference DOCX
            rebuilt_docx = work_dir / "reference.docx"
            with zipfile.ZipFile(rebuilt_docx, "w", zipfile.ZIP_DEFLATED) as archive:
                for item in sorted(unpacked_dir.rglob("*")):
                    if item.is_file():
                        archive.write(item, item.relative_to(unpacked_dir).as_posix())

            shutil.copy2(rebuilt_docx, self.target_path)

        return self.target_path

    def _configure_styles(self, styles_root: ET.Element) -> None:
        """Apply DSTU fonts, sizes, indents, and custom styles."""
        # Defaults
        doc_defaults = styles_root.find(w_tag("docDefaults"))
        if doc_defaults is None:
            doc_defaults = ET.Element(w_tag("docDefaults"))
            styles_root.insert(0, doc_defaults)

        run_default = doc_defaults.find(w_tag("rPrDefault"))
        if run_default is None:
            run_default = ET.SubElement(doc_defaults, w_tag("rPrDefault"))
        apply_run_properties(run_default, size_half_points=FONT_SIZE_BODY_HALF_POINTS)

        para_default = doc_defaults.find(w_tag("pPrDefault"))
        if para_default is None:
            para_default = ET.SubElement(doc_defaults, w_tag("pPrDefault"))
        apply_paragraph_properties(
            para_default, first_line_indent=INDENT_FIRST_LINE_DXA
        )

        # Standard styles
        normal = self._get_or_create_style(styles_root, "Normal")
        apply_paragraph_properties(normal)
        apply_run_properties(normal)

        for style_id in ("BodyText", "FirstParagraph"):
            elem = self._get_or_create_style(styles_root, style_id)
            apply_paragraph_properties(elem)
            apply_run_properties(elem)

        compact = self._get_or_create_style(styles_root, "Compact")
        apply_paragraph_properties(
            compact, line_spacing=LINE_SPACING_1_5, first_line_indent=0
        )
        apply_run_properties(compact, size_half_points=FONT_SIZE_BODY_HALF_POINTS)

        # Heading 1..9
        for level in range(1, 10):
            heading_elem = self._get_or_create_style(styles_root, f"Heading{level}")
            if level == 1:
                # Level 1: Centered, bold, uppercase semantics, page break before
                apply_paragraph_properties(
                    heading_elem,
                    alignment="center",
                    spacing_before=LINE_SPACING_1_5,
                    spacing_after=LINE_SPACING_1_5,
                    first_line_indent=0,
                    keep_with_next=True,
                    page_break_before=True,
                    outline_level=0,
                )
                apply_run_properties(heading_elem, bold=True)
            else:
                # Level 2+: Left-aligned, first-line indent 1.25 cm, regular weight
                apply_paragraph_properties(
                    heading_elem,
                    alignment="left",
                    spacing_before=LINE_SPACING_1_5,
                    spacing_after=LINE_SPACING_1_5,
                    first_line_indent=INDENT_FIRST_LINE_DXA,
                    keep_with_next=True,
                    outline_level=level - 1,
                )
                apply_run_properties(heading_elem, bold=False)

        # DSTU custom paragraph styles
        self._add_paragraph_style(
            styles_root,
            "TableCaption",
            "Table Caption",
            alignment="left",
            first_line_indent=INDENT_FIRST_LINE_DXA,
            keep_with_next=True,
            spacing_after=0,
        )
        self._add_paragraph_style(
            styles_root,
            "ImageCaption",
            "Image Caption",
            alignment="center",
            first_line_indent=0,
            keep_with_next=False,
            spacing_before=0,
            spacing_after=0,
        )
        self._add_paragraph_style(
            styles_root,
            "CaptionedFigure",
            "Captioned Figure",
            alignment="center",
            first_line_indent=0,
            keep_with_next=True,
        )
        self._add_paragraph_style(
            styles_root, "Figure", "Figure", alignment="center", first_line_indent=0
        )
        self._add_paragraph_style(
            styles_root,
            "Bibliography",
            "Bibliography",
            first_line_indent=INDENT_FIRST_LINE_DXA,
            line_spacing=LINE_SPACING_1_5,
        )
        self._add_paragraph_style(
            styles_root,
            "FootnoteText",
            "Footnote Text",
            size_half_points=FONT_SIZE_FOOTNOTE_HALF_POINTS,
            line_spacing=LINE_SPACING_SINGLE,
            first_line_indent=0,
        )
        self._add_paragraph_style(
            styles_root,
            "BlockText",
            "Block Text",
            first_line_indent=0,
            alignment="left",
        )
        self._add_paragraph_style(
            styles_root,
            "TOCHeading",
            "TOC Heading",
            bold=True,
            alignment="center",
            first_line_indent=0,
            page_break_before=True,
            keep_with_next=True,
            spacing_before=0,
            spacing_after=LINE_SPACING_1_5,
        )
        self._add_paragraph_style(
            styles_root,
            "AbstractHeading",
            "Abstract Heading",
            bold=True,
            alignment="center",
            first_line_indent=0,
            page_break_before=True,
            keep_with_next=True,
            spacing_before=LINE_SPACING_1_5,
            spacing_after=LINE_SPACING_1_5,
        )

        # Formula and explanation styles
        self._add_paragraph_style(
            styles_root, "Formula", "Formula", alignment="left", first_line_indent=0
        )
        formula_props = self._get_or_create_style(styles_root, "Formula").find(
            w_tag("pPr")
        )
        if formula_props is not None:
            formula_tabs = child_element(formula_props, "tabs")
            child_element(
                formula_tabs, "tab", val="center", pos=str(PAGE_CONTENT_CENTER_DXA)
            )
            child_element(
                formula_tabs, "tab", val="right", pos=str(PAGE_CONTENT_WIDTH_DXA)
            )

        self._add_paragraph_style(
            styles_root,
            "FormulaExplanation",
            "Formula Explanation",
            alignment="left",
            first_line_indent=0,
        )

        # Title-page styles
        self._add_paragraph_style(
            styles_root,
            "TitleInstitution",
            "Title Institution",
            alignment="center",
            first_line_indent=0,
            line_spacing=LINE_SPACING_1_5,
        )
        self._add_paragraph_style(
            styles_root,
            "TitleApproval",
            "Title Approval",
            alignment="left",
            first_line_indent=PAGE_CONTENT_CENTER_DXA,
            line_spacing=LINE_SPACING_1_5,
        )
        self._add_paragraph_style(
            styles_root,
            "TitleWorkType",
            "Title Work Type",
            bold=False,
            alignment="center",
            first_line_indent=0,
            line_spacing=LINE_SPACING_1_5,
        )
        self._add_paragraph_style(
            styles_root,
            "TitleDocumentTitle",
            "Title Document Title",
            bold=False,
            alignment="center",
            first_line_indent=0,
            line_spacing=LINE_SPACING_1_5,
        )
        self._add_paragraph_style(
            styles_root,
            "TitleDetails",
            "Title Details",
            alignment="left",
            first_line_indent=PAGE_CONTENT_CENTER_DXA,
            line_spacing=LINE_SPACING_1_5,
        )
        self._add_paragraph_style(
            styles_root,
            "TitleDetailsCell",
            "Title Details Cell",
            alignment="left",
            first_line_indent=0,
            line_spacing=LINE_SPACING_1_5,
        )
        self._add_paragraph_style(
            styles_root,
            "TitlePlace",
            "Title Place",
            alignment="center",
            first_line_indent=0,
            line_spacing=LINE_SPACING_1_5,
        )
        self._add_paragraph_style(
            styles_root,
            "TitleSpacerTop",
            "Title Spacer Top",
            alignment="left",
            first_line_indent=0,
            line_spacing=LINE_SPACING_1_5,
            spacing_after=TITLE_SPACER_TOP_DXA,
        )
        self._add_paragraph_style(
            styles_root,
            "TitleSpacerMiddle",
            "Title Spacer Middle",
            alignment="left",
            first_line_indent=0,
            line_spacing=LINE_SPACING_1_5,
            spacing_after=TITLE_SPACER_MIDDLE_DXA,
        )
        self._add_paragraph_style(
            styles_root,
            "TitleSpacerBottom",
            "Title Spacer Bottom",
            alignment="left",
            first_line_indent=0,
            line_spacing=LINE_SPACING_1_5,
            spacing_after=TITLE_SPACER_BOTTOM_DXA,
        )
        self._add_paragraph_style(
            styles_root,
            "TableSpacer",
            "Table Spacer",
            alignment="left",
            first_line_indent=0,
            line_spacing=LINE_SPACING_1_5,
        )
        self._add_paragraph_style(
            styles_root,
            "FigureSpacer",
            "Figure Spacer",
            alignment="left",
            first_line_indent=0,
            line_spacing=LINE_SPACING_1_5,
        )

        # TOC1..3 styles with dot leaders
        for level in range(1, 4):
            style_id = f"TOC{level}"
            toc_elem = styles_root.find(
                f".//{w_tag('style')}[@{w_tag('styleId')}='{style_id}']"
            )
            if toc_elem is None:
                toc_elem = ET.SubElement(
                    styles_root,
                    w_tag("style"),
                    {w_tag("type"): "paragraph", w_tag("styleId"): style_id},
                )
                child_element(toc_elem, "name", val=f"TOC {level}")
                child_element(toc_elem, "basedOn", val="Normal")

            apply_paragraph_properties(
                toc_elem,
                spacing_before=0,
                spacing_after=0,
                line_spacing=LINE_SPACING_1_5,
                first_line_indent=0,
                left_indent=(level - 1) * INDENT_FIRST_LINE_DXA,
            )
            toc_props = toc_elem.find(w_tag("pPr"))
            if toc_props is not None:
                tabs = child_element(toc_props, "tabs")
                child_element(
                    tabs,
                    "tab",
                    val="right",
                    pos=str(PAGE_CONTENT_WIDTH_DXA),
                    leader="dot",
                )
            apply_run_properties(toc_elem, size_half_points=FONT_SIZE_BODY_HALF_POINTS)

    def _configure_page_geometry(self, body: ET.Element) -> None:
        """Set A4 page dimensions, margins, and header references in sectPr."""
        section_props = body.find(w_tag("sectPr"))
        if section_props is None:
            section_props = ET.SubElement(body, w_tag("sectPr"))

        for tag_name in ("pgSz", "pgMar", "titlePg"):
            old = section_props.find(w_tag(tag_name))
            if old is not None:
                section_props.remove(old)

        child_element(
            section_props,
            "pgSz",
            w=str(PAGE_A4_WIDTH_DXA),
            h=str(PAGE_A4_HEIGHT_DXA),
        )
        child_element(
            section_props,
            "pgMar",
            top=str(MARGIN_TOP_DXA),
            right=str(MARGIN_RIGHT_DXA),
            bottom=str(MARGIN_BOTTOM_DXA),
            left=str(MARGIN_LEFT_DXA),
            header=str(MARGIN_HEADER_DXA),
            footer=str(MARGIN_FOOTER_DXA),
            gutter="0",
        )
        header_ref = child_element(section_props, "headerReference", type="default")
        header_ref.set(openxml_tag("id", R_NAMESPACE), "rId100")
        child_element(section_props, "titlePg")

    def _create_header_part(self, unpacked_dir: Path) -> None:
        """Create word/header1.xml and link it in document.xml.rels and [Content_Types].xml."""
        header_elem = ET.Element(w_tag("hdr"))
        paragraph = child_element(header_elem, "p")
        props = child_element(paragraph, "pPr")
        child_element(props, "jc", val="right")
        child_element(props, "ind", firstLine="0")

        # Field: PAGE
        run_begin = child_element(paragraph, "r")
        child_element(run_begin, "fldChar", fldCharType="begin")

        run_instr = child_element(paragraph, "r")
        instr_text = child_element(run_instr, "instrText")
        instr_text.text = " PAGE "

        run_end = child_element(paragraph, "r")
        child_element(run_end, "fldChar", fldCharType="end")

        for run in paragraph.findall(w_tag("r")):
            apply_run_properties(
                run,
                font_family=FONT_NAME_TIMES,
                size_half_points=FONT_SIZE_PAGE_NUMBER_HALF_POINTS,
            )

        header_path = unpacked_dir / "word" / "header1.xml"
        ET.ElementTree(header_elem).write(
            header_path, encoding="UTF-8", xml_declaration=True
        )

        # Register in document.xml.rels
        rels_path = unpacked_dir / "word" / "_rels" / "document.xml.rels"
        rels_tree = ET.parse(rels_path)
        ET.SubElement(
            rels_tree.getroot(),
            openxml_tag("Relationship", PKG_REL_NAMESPACE),
            {
                "Id": "rId100",
                "Type": f"{R_NAMESPACE}/header",
                "Target": "header1.xml",
            },
        )
        rels_tree.write(rels_path, encoding="UTF-8", xml_declaration=True)

        # Register in [Content_Types].xml
        content_path = unpacked_dir / "[Content_Types].xml"
        content_tree = ET.parse(content_path)
        ET.SubElement(
            content_tree.getroot(),
            openxml_tag("Override", CONTENT_TYPES_NAMESPACE),
            {
                "PartName": "/word/header1.xml",
                "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml",
            },
        )
        content_tree.write(content_path, encoding="UTF-8", xml_declaration=True)

    def _configure_settings(self, settings_root: ET.Element) -> None:
        """Set Word compatibility options and disable field updates on open."""
        compat = settings_root.find(w_tag("compat"))
        if compat is None:
            compat = ET.SubElement(settings_root, w_tag("compat"))
        child_element(compat, "doNotUseHTMLParagraphAutoSpacing")
        child_element(settings_root, "updateFields", val="false")

    def _get_or_create_style(self, root: ET.Element, style_id: str) -> ET.Element:
        elem = root.find(f".//{w_tag('style')}[@{w_tag('styleId')}='{style_id}']")
        if elem is None:
            elem = ET.SubElement(
                root,
                w_tag("style"),
                {w_tag("type"): "paragraph", w_tag("styleId"): style_id},
            )
        return elem

    def _add_paragraph_style(
        self,
        root: ET.Element,
        style_id: str,
        name: str,
        *,
        based_on: str = "Normal",
        next_style: str = "BodyText",
        size_half_points: int = FONT_SIZE_BODY_HALF_POINTS,
        bold: bool = False,
        italic: bool = False,
        alignment: str = "both",
        spacing_before: int = 0,
        spacing_after: int = 0,
        line_spacing: int = LINE_SPACING_1_5,
        first_line_indent: int | None = INDENT_FIRST_LINE_DXA,
        keep_with_next: bool = False,
        page_break_before: bool = False,
    ) -> ET.Element:
        existing = root.find(f".//{w_tag('style')}[@{w_tag('styleId')}='{style_id}']")
        if existing is not None:
            root.remove(existing)

        node = ET.SubElement(
            root,
            w_tag("style"),
            {
                w_tag("type"): "paragraph",
                w_tag("styleId"): style_id,
                w_tag("customStyle"): "1",
            },
        )
        child_element(node, "name", val=name)
        child_element(node, "basedOn", val=based_on)
        child_element(node, "next", val=next_style)
        child_element(node, "qFormat")

        apply_paragraph_properties(
            node,
            alignment=alignment,
            spacing_before=spacing_before,
            spacing_after=spacing_after,
            line_spacing=line_spacing,
            first_line_indent=first_line_indent,
            keep_with_next=keep_with_next,
            page_break_before=page_break_before,
        )
        apply_run_properties(
            node,
            font_family=FONT_NAME_TIMES,
            size_half_points=size_half_points,
            bold=bold,
            italic=italic,
        )
        return node


def main() -> None:
    builder = DstuReferenceBuilder()
    output_file = builder.build()
    print(f"Created: {output_file}")


if __name__ == "__main__":
    main()
