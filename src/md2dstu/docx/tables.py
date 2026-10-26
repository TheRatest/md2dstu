"""Table formatting and border normalization according to DSTU standards."""

from __future__ import annotations

import copy
import os
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from md2dstu.constants import BORDER_SIZE_ONE_POINT, PAGE_CONTENT_WIDTH_DXA
from md2dstu.docx.namespaces import register_openxml_namespaces, w_tag

TABLE_CONTINUED = "Продовження таблиці"
TABLE_END = "Кінець таблиці"


def split_table(docx_path: Path, table_index: int, row_index: int) -> bool:
    """Split the table_index-th body table before row_index (DSTU 3008:2015, 7.5).

    The new part repeats the header row and starts a new page under
    "Кінець таблиці N"; an earlier "Кінець" label of the same table becomes
    "Продовження таблиці N". Tables without a "Таблиця N" caption are left
    untouched and False is returned.
    """
    register_openxml_namespaces()
    with zipfile.ZipFile(docx_path) as archive:
        entries = {info: archive.read(info) for info in archive.infolist()}
    document_info = next(i for i in entries if i.filename == "word/document.xml")
    root = ET.fromstring(entries[document_info])
    body = root.find(w_tag("body"))
    children = list(body)
    table = [child for child in children if child.tag == w_tag("tbl")][table_index]
    position = children.index(table)
    label = children[position - 1] if position else None
    if label is None or label.tag != w_tag("p"):
        return False
    label_text = "".join(text.text or "" for text in label.iter(w_tag("t")))
    match = re.match(rf"(Таблиця|{TABLE_END})\s+(\S+)", label_text)
    rows = table.findall(w_tag("tr"))
    if match is None or not 2 <= row_index < len(rows):
        return False

    number = match.group(2)
    if match.group(1) == TABLE_END:
        label.find(f".//{w_tag('t')}").text = f"{TABLE_CONTINUED} {number}"

    new_label = ET.Element(w_tag("p"))
    properties = ET.SubElement(new_label, w_tag("pPr"))
    style = label.find(f"./{w_tag('pPr')}/{w_tag('pStyle')}")
    if style is not None:
        properties.append(copy.deepcopy(style))
    ET.SubElement(properties, w_tag("pageBreakBefore"))
    run = ET.SubElement(new_label, w_tag("r"))
    ET.SubElement(run, w_tag("t")).text = f"{TABLE_END} {number}"

    new_table = copy.deepcopy(table)
    for row in new_table.findall(w_tag("tr")):
        new_table.remove(row)
    new_table.append(copy.deepcopy(rows[0]))
    for row in rows[row_index:]:
        table.remove(row)
        new_table.append(row)
    body.insert(position + 1, new_label)
    body.insert(position + 2, new_table)

    entries[document_info] = ET.tostring(root, encoding="UTF-8", xml_declaration=True)
    rebuilt = docx_path.with_suffix(docx_path.suffix + ".split")
    with zipfile.ZipFile(rebuilt, "w", zipfile.ZIP_DEFLATED) as archive:
        for info, data in entries.items():
            archive.writestr(info, data)
    os.replace(rebuilt, docx_path)
    return True


class TableModifier:
    """Manages table borders, title-page detail table recognition, and header row repetition."""

    @staticmethod
    def is_title_details_table(table: ET.Element) -> bool:
        """Identify if a table represents the two-column title-page metadata block."""
        caption = table.find(f"./{w_tag('tblPr')}/{w_tag('tblCaption')}")
        if caption is not None and caption.get(w_tag("val")) == "md2dstu-title-details":
            return True

        # LibreOffice removes tblCaption when updating/populating contents.
        # Check for the dedicated TitleDetailsCell style which survives round-tripping.
        return any(
            style.get(w_tag("val")) == "TitleDetailsCell"
            for style in table.findall(f".//{w_tag('pStyle')}")
        )

    @staticmethod
    def set_invisible_table_borders(table: ET.Element) -> None:
        """Remove all borders from a table and its individual cells."""
        properties = table.find(w_tag("tblPr"))
        if properties is None:
            properties = ET.Element(w_tag("tblPr"))
            table.insert(0, properties)

        borders = properties.find(w_tag("tblBorders"))
        if borders is None:
            borders = ET.SubElement(properties, w_tag("tblBorders"))

        for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
            border = borders.find(w_tag(side))
            if border is None:
                border = ET.SubElement(borders, w_tag(side))
            border.set(w_tag("val"), "nil")

        for cell in table.iter(w_tag("tc")):
            cell_props = cell.find(w_tag("tcPr"))
            if cell_props is None:
                cell_props = ET.Element(w_tag("tcPr"))
                cell.insert(0, cell_props)

            cell_borders = cell_props.find(w_tag("tcBorders"))
            if cell_borders is None:
                cell_borders = ET.SubElement(cell_props, w_tag("tcBorders"))

            for side in ("top", "left", "bottom", "right"):
                border = cell_borders.find(w_tag(side))
                if border is None:
                    border = ET.SubElement(cell_borders, w_tag(side))
                border.set(w_tag("val"), "nil")

    @staticmethod
    def set_table_borders(table: ET.Element) -> None:
        """Apply 1 pt solid black borders across table edges and cells."""
        properties = table.find(w_tag("tblPr"))
        if properties is None:
            properties = ET.Element(w_tag("tblPr"))
            table.insert(0, properties)

        borders = properties.find(w_tag("tblBorders"))
        if borders is None:
            borders = ET.SubElement(properties, w_tag("tblBorders"))

        for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
            border = borders.find(w_tag(side))
            if border is None:
                border = ET.SubElement(borders, w_tag(side))
            border.set(w_tag("val"), "single")
            border.set(w_tag("sz"), str(BORDER_SIZE_ONE_POINT))
            border.set(w_tag("space"), "0")
            border.set(w_tag("color"), "000000")

        # Explicit cell borders override table borders in Word/LibreOffice, so normalize each cell
        for cell in table.iter(w_tag("tc")):
            cell_props = cell.find(w_tag("tcPr"))
            if cell_props is None:
                cell_props = ET.Element(w_tag("tcPr"))
                cell.insert(0, cell_props)

            cell_borders = cell_props.find(w_tag("tcBorders"))
            if cell_borders is None:
                cell_borders = ET.SubElement(cell_props, w_tag("tcBorders"))

            for side in ("top", "left", "bottom", "right"):
                border = cell_borders.find(w_tag(side))
                if border is None:
                    border = ET.SubElement(cell_borders, w_tag(side))
                border.set(w_tag("val"), "single")
                border.set(w_tag("sz"), str(BORDER_SIZE_ONE_POINT))
                border.set(w_tag("space"), "0")
                border.set(w_tag("color"), "000000")

    @staticmethod
    def ensure_repeating_table_header(table: ET.Element) -> None:
        """Mark first row with tblHeader so table headers repeat on page breaks (DSTU item 7.5.3)."""
        first_row = table.find(w_tag("tr"))
        if first_row is None:
            return

        row_props = first_row.find(w_tag("trPr"))
        if row_props is None:
            row_props = ET.Element(w_tag("trPr"))
            first_row.insert(0, row_props)

        if row_props.find(w_tag("tblHeader")) is None:
            ET.SubElement(row_props, w_tag("tblHeader"), {w_tag("val"): "true"})

    @staticmethod
    def stretch_to_page_width(table: ET.Element) -> None:
        """Scale column widths proportionally so the table spans the full text width."""
        columns = table.findall(f"./{w_tag('tblGrid')}/{w_tag('gridCol')}")
        total = sum(int(col.get(w_tag("w"), "0")) for col in columns)
        if total <= 0:
            return
        factor = PAGE_CONTENT_WIDTH_DXA / total

        for col in columns:
            col.set(w_tag("w"), str(round(int(col.get(w_tag("w"))) * factor)))
        for cell_width in table.iter(w_tag("tcW")):
            if cell_width.get(w_tag("type")) == "dxa":
                width = int(cell_width.get(w_tag("w"), "0"))
                cell_width.set(w_tag("w"), str(round(width * factor)))

        properties = table.find(w_tag("tblPr"))
        if properties is None:
            properties = ET.Element(w_tag("tblPr"))
            table.insert(0, properties)
        table_width = properties.find(w_tag("tblW"))
        if table_width is None:
            table_width = ET.SubElement(properties, w_tag("tblW"))
        table_width.set(w_tag("type"), "dxa")
        table_width.set(w_tag("w"), str(PAGE_CONTENT_WIDTH_DXA))
