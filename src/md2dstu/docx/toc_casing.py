"""TOC sentence case capitalization adjustments."""

from __future__ import annotations

import os
import re
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from md2dstu.docx.namespaces import register_openxml_namespaces, w_tag


def toc_sentence_case(value: str) -> str:
    """Transform an uppercase heading title to sentence case, preserving appendix letters."""
    lowered = value.lower()
    first_letter = next((i for i, char in enumerate(lowered) if char.isalpha()), None)
    if first_letter is None:
        return lowered

    capitalized = (
        lowered[:first_letter]
        + lowered[first_letter].upper()
        + lowered[first_letter + 1 :]
    )
    # Appendix letters are capitalized identifier symbols (e.g. Додаток А)
    return re.sub(
        r"^(Додаток|Appendix)\s+([а-яa-z])\b",
        lambda m: f"{m.group(1)} {m.group(2).upper()}",
        capitalized,
    )


def apply_sentence_case_to_toc(docx_path: Path) -> None:
    """Enforce sentence case in generated Table of Contents entries within docx_path."""
    register_openxml_namespaces()
    with tempfile.TemporaryDirectory(prefix="md2dstu-toc-case-") as temporary_dir:
        unpacked = Path(temporary_dir)
        with zipfile.ZipFile(docx_path) as archive:
            archive.extractall(unpacked)

        document_path = unpacked / "word" / "document.xml"
        tree = ET.parse(document_path)
        root = tree.getroot()

        for sdt_element in root.iter(w_tag("sdt")):
            gallery = sdt_element.find(f".//{w_tag('docPartGallery')}")
            if gallery is None or gallery.get(w_tag("val")) != "Table of Contents":
                continue

            for paragraph in sdt_element.iter(w_tag("p")):
                style_elem = paragraph.find(f"./{w_tag('pPr')}/{w_tag('pStyle')}")
                style_name = (
                    style_elem.get(w_tag("val"), "") if style_elem is not None else ""
                )
                if not re.fullmatch(r"TOC[1-9]", style_name):
                    continue

                text_nodes = list(paragraph.iter(w_tag("t")))
                if not text_nodes:
                    continue

                # The last node is typically the page number digits; do not alter numbers
                is_last_page_number = (
                    len(text_nodes) > 1 and (text_nodes[-1].text or "").isdigit()
                )
                title_nodes = text_nodes[:-1] if is_last_page_number else text_nodes

                full_title = "".join(node.text or "" for node in title_nodes)
                sentence_cased = toc_sentence_case(full_title)

                offset = 0
                for node in title_nodes:
                    node_len = len(node.text or "")
                    node.text = sentence_cased[offset : offset + node_len]
                    offset += node_len

                for hyperlink in paragraph.iter(w_tag("hyperlink")):
                    tooltip = hyperlink.get(w_tag("tooltip"))
                    if tooltip:
                        hyperlink.set(w_tag("tooltip"), toc_sentence_case(tooltip))

        tree.write(document_path, encoding="UTF-8", xml_declaration=True)

        rebuilt_path = docx_path.with_suffix(docx_path.suffix + ".toc-case")
        with zipfile.ZipFile(rebuilt_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for item in sorted(unpacked.rglob("*")):
                if item.is_file():
                    archive.write(item, item.relative_to(unpacked).as_posix())

        os.replace(rebuilt_path, docx_path)
