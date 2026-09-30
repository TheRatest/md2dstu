"""Table formatting and border normalization according to DSTU standards."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from md2dstu.constants import BORDER_SIZE_ONE_POINT
from md2dstu.docx.namespaces import w_tag


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
