#!/usr/bin/env python3
"""Build the deterministic DSTU reference DOCX used by md2dstu."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import zipfile
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "templates" / "dstu-reference.docx"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT = "http://schemas.openxmlformats.org/package/2006/content-types"
ET.register_namespace("w", W)
ET.register_namespace("r", R)
ET.register_namespace("", PKG_REL)


def qn(namespace: str, name: str) -> str:
    return f"{{{namespace}}}{name}"


def child(parent: ET.Element, name: str, **attributes: str) -> ET.Element:
    return ET.SubElement(parent, qn(W, name), {qn(W, key): value for key, value in attributes.items()})


def style(root: ET.Element, style_id: str) -> ET.Element:
    found = root.find(f".//{qn(W, 'style')}[@{qn(W, 'styleId')}='{style_id}']")
    if found is None:
        raise RuntimeError(f"Pandoc default reference does not contain style {style_id}")
    return found


def replace_properties(owner: ET.Element, tag: str) -> ET.Element:
    old = owner.find(qn(W, tag))
    if old is not None:
        owner.remove(old)
    result = ET.Element(qn(W, tag))
    owner.append(result)
    return result


def run_properties(owner: ET.Element, *, size: int = 28, bold: bool = False, italic: bool = False) -> ET.Element:
    props = replace_properties(owner, "rPr")
    child(props, "rFonts", ascii="Times New Roman", hAnsi="Times New Roman", eastAsia="Times New Roman", cs="Times New Roman")
    child(props, "color", val="000000")
    if bold:
        child(props, "b")
        child(props, "bCs")
    if italic:
        child(props, "i")
        child(props, "iCs")
    child(props, "sz", val=str(size))
    child(props, "szCs", val=str(size))
    return props


def paragraph_properties(
    owner: ET.Element,
    *,
    align: str = "both",
    before: int = 0,
    after: int = 0,
    line: int = 360,
    first_line: int | None = 709,
    keep_next: bool = False,
    page_before: bool = False,
    outline: int | None = None,
) -> ET.Element:
    props = replace_properties(owner, "pPr")
    if keep_next:
        child(props, "keepNext")
    if page_before:
        child(props, "pageBreakBefore")
    child(props, "widowControl")
    child(props, "spacing", before=str(before), after=str(after), line=str(line), lineRule="auto")
    if first_line is not None:
        child(props, "ind", firstLine=str(first_line))
    child(props, "jc", val=align)
    if outline is not None:
        child(props, "outlineLvl", val=str(outline))
    return props


def add_paragraph_style(
    root: ET.Element,
    style_id: str,
    name: str,
    *,
    based_on: str = "Normal",
    next_style: str = "BodyText",
    size: int = 28,
    bold: bool = False,
    italic: bool = False,
    align: str = "both",
    before: int = 0,
    after: int = 0,
    line: int = 360,
    first_line: int | None = 709,
    keep_next: bool = False,
    page_before: bool = False,
) -> ET.Element:
    existing = root.find(f".//{qn(W, 'style')}[@{qn(W, 'styleId')}='{style_id}']")
    if existing is not None:
        root.remove(existing)
    node = ET.SubElement(root, qn(W, "style"), {qn(W, "type"): "paragraph", qn(W, "styleId"): style_id, qn(W, "customStyle"): "1"})
    child(node, "name", val=name)
    child(node, "basedOn", val=based_on)
    child(node, "next", val=next_style)
    child(node, "qFormat")
    paragraph_properties(node, align=align, before=before, after=after, line=line, first_line=first_line, keep_next=keep_next, page_before=page_before)
    run_properties(node, size=size, bold=bold, italic=italic)
    return node


def write_xml(tree: ET.ElementTree, path: Path) -> None:
    tree.write(path, encoding="UTF-8", xml_declaration=True)


def build() -> None:
    if shutil.which("pandoc") is None:
        raise SystemExit("pandoc is required to build the reference DOCX")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="md2dstu-reference-") as temporary:
        work = Path(temporary)
        default = work / "default.docx"
        with default.open("wb") as stream:
            subprocess.run(["pandoc", "--print-default-data-file", "reference.docx"], check=True, stdout=stream)
        unpacked = work / "unpacked"
        with zipfile.ZipFile(default) as archive:
            archive.extractall(unpacked)

        styles_path = unpacked / "word" / "styles.xml"
        styles_tree = ET.parse(styles_path)
        styles = styles_tree.getroot()

        defaults = styles.find(qn(W, "docDefaults"))
        if defaults is None:
            defaults = ET.Element(qn(W, "docDefaults"))
            styles.insert(0, defaults)
        run_default = defaults.find(qn(W, "rPrDefault"))
        if run_default is None:
            run_default = ET.SubElement(defaults, qn(W, "rPrDefault"))
        run_properties(run_default, size=28)
        para_default = defaults.find(qn(W, "pPrDefault"))
        if para_default is None:
            para_default = ET.SubElement(defaults, qn(W, "pPrDefault"))
        paragraph_properties(para_default, first_line=709)

        normal = style(styles, "Normal")
        paragraph_properties(normal)
        run_properties(normal)
        for style_id in ("BodyText", "FirstParagraph"):
            node = style(styles, style_id)
            paragraph_properties(node)
            run_properties(node)
        compact = style(styles, "Compact")
        paragraph_properties(compact, line=360, first_line=0)
        run_properties(compact, size=28)

        for level in range(1, 10):
            node = style(styles, f"Heading{level}")
            if level == 1:
                paragraph_properties(node, align="center", before=360, after=360, first_line=0, keep_next=True, page_before=True, outline=0)
                run_properties(node, bold=True)
            else:
                paragraph_properties(node, align="left", before=360, after=360, first_line=709, keep_next=True, outline=level - 1)
                run_properties(node, bold=False)

        add_paragraph_style(styles, "TableCaption", "Table Caption", align="left", first_line=709, keep_next=True, after=0)
        add_paragraph_style(styles, "ImageCaption", "Image Caption", align="center", first_line=0, keep_next=False, before=0, after=0)
        add_paragraph_style(styles, "CaptionedFigure", "Captioned Figure", align="center", first_line=0, keep_next=True)
        add_paragraph_style(styles, "Figure", "Figure", align="center", first_line=0)
        add_paragraph_style(styles, "Bibliography", "Bibliography", first_line=709, line=360)
        add_paragraph_style(styles, "FootnoteText", "Footnote Text", size=24, line=240, first_line=0)
        add_paragraph_style(styles, "BlockText", "Block Text", first_line=0, align="left")
        add_paragraph_style(styles, "TOCHeading", "TOC Heading", bold=True, align="center", first_line=0, page_before=True, keep_next=True, before=0, after=360)
        add_paragraph_style(styles, "AbstractHeading", "Abstract Heading", bold=True, align="center", first_line=0, page_before=True, keep_next=True, before=360, after=360)
        add_paragraph_style(styles, "Formula", "Formula", align="left", first_line=0)
        formula = style(styles, "Formula").find(qn(W, "pPr"))
        tabs = child(formula, "tabs")
        child(tabs, "tab", val="center", pos="4961")
        child(tabs, "tab", val="right", pos="9922")
        add_paragraph_style(styles, "FormulaExplanation", "Formula Explanation", align="left", first_line=0)
        add_paragraph_style(styles, "TitleInstitution", "Title Institution", align="center", first_line=0, line=360)
        add_paragraph_style(styles, "TitleApproval", "Title Approval", align="left", first_line=4961, line=360)
        add_paragraph_style(styles, "TitleWorkType", "Title Work Type", bold=False, align="center", first_line=0, line=360)
        add_paragraph_style(styles, "TitleDocumentTitle", "Title Document Title", bold=False, align="center", first_line=0, line=360)
        add_paragraph_style(styles, "TitleDetails", "Title Details", align="left", first_line=4961, line=360)
        add_paragraph_style(styles, "TitleDetailsCell", "Title Details Cell", align="left", first_line=0, line=360)
        add_paragraph_style(styles, "TitlePlace", "Title Place", align="center", first_line=0, line=360)
        add_paragraph_style(styles, "TitleSpacerTop", "Title Spacer Top", align="left", first_line=0, line=360, after=3000)
        add_paragraph_style(styles, "TitleSpacerMiddle", "Title Spacer Middle", align="left", first_line=0, line=360, after=2000)
        add_paragraph_style(styles, "TitleSpacerBottom", "Title Spacer Bottom", align="left", first_line=0, line=360, after=2900)
        add_paragraph_style(styles, "TableSpacer", "Table Spacer", align="left", first_line=0, line=360)
        add_paragraph_style(styles, "FigureSpacer", "Figure Spacer", align="left", first_line=0, line=360)
        # Keep TOC entries readable and guarantee dotted leaders to the
        # right-aligned page number in both Word and LibreOffice.
        for level in range(1, 4):
            toc = styles.find(f".//{qn(W, 'style')}[@{qn(W, 'styleId')}='TOC{level}']")
            if toc is None:
                toc = ET.SubElement(styles, qn(W, "style"), {qn(W, "type"): "paragraph", qn(W, "styleId"): f"TOC{level}"})
                child(toc, "name", val=f"TOC {level}")
                child(toc, "basedOn", val="Normal")
            props = replace_properties(toc, "pPr")
            tabs = child(props, "tabs")
            child(tabs, "tab", val="right", pos="9922", leader="dot")
            child(props, "spacing", before="0", after="0", line="360", lineRule="auto")
            child(props, "ind", left=str((level - 1) * 709), firstLine="0")
            run_properties(toc, size=28)
        write_xml(styles_tree, styles_path)

        document_path = unpacked / "word" / "document.xml"
        document_tree = ET.parse(document_path)
        body = document_tree.getroot().find(qn(W, "body"))
        section = body.find(qn(W, "sectPr"))
        if section is None:
            section = ET.SubElement(body, qn(W, "sectPr"))
        for tag in ("pgSz", "pgMar", "titlePg"):
            old = section.find(qn(W, tag))
            if old is not None:
                section.remove(old)
        child(section, "pgSz", w="11906", h="16838")
        child(section, "pgMar", top="1134", right="567", bottom="1134", left="1417", header="567", footer="567", gutter="0")
        child(section, "headerReference", type="default").set(qn(R, "id"), "rId100")
        child(section, "titlePg")
        write_xml(document_tree, document_path)

        header = ET.Element(qn(W, "hdr"))
        para = child(header, "p")
        props = child(para, "pPr")
        child(props, "jc", val="right")
        child(props, "ind", firstLine="0")
        run = child(para, "r")
        child(run, "fldChar", fldCharType="begin")
        run = child(para, "r")
        instruction = child(run, "instrText")
        instruction.text = " PAGE "
        run = child(para, "r")
        child(run, "fldChar", fldCharType="end")
        for header_run in para.findall(qn(W, "r")):
            rp = ET.Element(qn(W, "rPr"))
            child(rp, "rFonts", ascii="Times New Roman", hAnsi="Times New Roman")
            child(rp, "sz", val="20")
            child(rp, "szCs", val="20")
            header_run.insert(0, rp)
        ET.ElementTree(header).write(unpacked / "word" / "header1.xml", encoding="UTF-8", xml_declaration=True)

        rels_path = unpacked / "word" / "_rels" / "document.xml.rels"
        rels_tree = ET.parse(rels_path)
        ET.SubElement(
            rels_tree.getroot(),
            qn(PKG_REL, "Relationship"),
            {
                "Id": "rId100",
                "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/header",
                "Target": "header1.xml",
            },
        )
        write_xml(rels_tree, rels_path)

        content_path = unpacked / "[Content_Types].xml"
        content_tree = ET.parse(content_path)
        ET.SubElement(
            content_tree.getroot(),
            qn(CONTENT, "Override"),
            {
                "PartName": "/word/header1.xml",
                "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml",
            },
        )
        write_xml(content_tree, content_path)

        settings_path = unpacked / "word" / "settings.xml"
        settings_tree = ET.parse(settings_path)
        settings_root = settings_tree.getroot()
        compat = settings_root.find(qn(W, "compat"))
        if compat is None:
            compat = ET.SubElement(settings_root, qn(W, "compat"))
        child(compat, "doNotUseHTMLParagraphAutoSpacing")
        # Updating an empty Pandoc TOC on open can erase it in some editors;
        # users explicitly refresh fields after opening, as documented.
        child(settings_root, "updateFields", val="false")
        write_xml(settings_tree, settings_path)

        rebuilt = work / "reference.docx"
        with zipfile.ZipFile(rebuilt, "w", zipfile.ZIP_DEFLATED) as archive:
            for item in sorted(unpacked.rglob("*")):
                if item.is_file():
                    archive.write(item, item.relative_to(unpacked).as_posix())
        shutil.copy2(rebuilt, OUTPUT)
        print(f"Created {OUTPUT}")


if __name__ == "__main__":
    build()
