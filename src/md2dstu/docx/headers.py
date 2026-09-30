"""Header and footer adjustments, specifically page number typography."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from md2dstu.constants import FONT_NAME_TIMES, FONT_SIZE_PAGE_NUMBER_HALF_POINTS
from md2dstu.docx.namespaces import register_openxml_namespaces, w_tag


class HeaderModifier:
    """Configures headers, specifically ensuring page numbers use Times New Roman 10 pt."""

    @staticmethod
    def set_page_number_font(unpacked_dir: Path) -> None:
        """Find all PAGE field runs in header XML parts and set TNR 10 pt."""
        register_openxml_namespaces()
        word_dir = unpacked_dir / "word"

        for header_path in word_dir.glob("header*.xml"):
            tree = ET.parse(header_path)
            changed = False

            for paragraph in tree.getroot().iter(w_tag("p")):
                has_page_instruction = any(
                    "PAGE" in (item.text or "")
                    for item in paragraph.iter(w_tag("instrText"))
                )
                if not has_page_instruction:
                    continue

                for run in paragraph.findall(w_tag("r")):
                    run_props = run.find(w_tag("rPr"))
                    if run_props is None:
                        run_props = ET.Element(w_tag("rPr"))
                        run.insert(0, run_props)

                    fonts = run_props.find(w_tag("rFonts"))
                    if fonts is None:
                        fonts = ET.SubElement(run_props, w_tag("rFonts"))
                    for font_family in ("ascii", "hAnsi", "eastAsia", "cs"):
                        fonts.set(w_tag(font_family), FONT_NAME_TIMES)

                    for size_attr in ("sz", "szCs"):
                        size_elem = run_props.find(w_tag(size_attr))
                        if size_elem is None:
                            size_elem = ET.SubElement(run_props, w_tag(size_attr))
                        size_elem.set(
                            w_tag("val"),
                            str(FONT_SIZE_PAGE_NUMBER_HALF_POINTS),
                        )
                    changed = True

            if changed:
                tree.write(header_path, encoding="UTF-8", xml_declaration=True)
