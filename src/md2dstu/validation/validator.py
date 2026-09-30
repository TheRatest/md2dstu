"""DSTU structural and typographical document validator."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from md2dstu.config import ConversionConfig
from md2dstu.constants import EXCLUDED_APPENDIX_LETTERS, STRUCTURAL_HEADINGS
from md2dstu.metadata import DocumentMetadata
from md2dstu.pandoc import stringify_pandoc_node, walk_pandoc_nodes
from md2dstu.validation.models import HeadingInfo, ValidationReport


class DocumentValidator:
    """Validates Pandoc AST against DSTU 3008:2015 report structure rules."""

    def __init__(self, config: ConversionConfig) -> None:
        self.config = config

    def validate(
        self,
        ast_data: dict[str, Any],
        metadata: DocumentMetadata,
    ) -> ValidationReport:
        """Run all DSTU compliance checks on the extracted AST and metadata."""
        report = ValidationReport()
        nodes = list(walk_pandoc_nodes(ast_data.get("blocks", [])))

        headings = self._extract_headings(nodes)
        self._validate_title_page(metadata, report)
        self._validate_structural_sections(headings, report)
        self._validate_heading_syntax(headings, report)
        self._validate_resources(nodes, report)
        self._validate_tables(nodes, report)
        self._validate_formulae(nodes, report)
        self._validate_appendices(headings, report)
        self._validate_citations(nodes, metadata, report)
        self._record_applied_settings(report)

        return report

    def _extract_headings(self, nodes: list[dict[str, Any]]) -> list[HeadingInfo]:
        headings: list[HeadingInfo] = []
        for index, node in enumerate(nodes):
            if node.get("t") == "Header":
                level, attributes, inlines = node["c"]
                classes = attributes[1] if len(attributes) > 1 else []
                text = stringify_pandoc_node(inlines)
                headings.append(
                    HeadingInfo(
                        level=int(level),
                        text=text,
                        classes=classes,
                        index=index,
                    )
                )
        return headings

    def _validate_title_page(
        self,
        metadata: DocumentMetadata,
        report: ValidationReport,
    ) -> None:
        if metadata.has_manual_title_page:
            return

        if not metadata.title:
            report.add_error(
                "No title page can be generated: metadata field 'title' is missing"
            )

        for field_name in ("institution", "city", "year"):
            if not getattr(metadata, field_name, None):
                report.add_warning(f"Title-page metadata is missing: {field_name}")

        student_name = metadata.student.name or metadata.legacy_author
        if not student_name:
            report.add_warning(
                "Title-page metadata is missing: student.name (or legacy author)"
            )

        teacher_name = metadata.teacher.name or metadata.legacy_supervisor
        if not teacher_name:
            report.add_warning(
                "Title-page metadata is missing: teacher.name (or legacy supervisor)"
            )

    def _validate_structural_sections(
        self,
        headings: list[HeadingInfo],
        report: ValidationReport,
    ) -> None:
        normalized_titles = [heading.normalized_text for heading in headings]

        def find_heading_position(aliases: set[str]) -> int | None:
            return next(
                (
                    idx
                    for idx, title in enumerate(normalized_titles)
                    if title in aliases
                ),
                None,
            )

        abstract_position = find_heading_position({"реферат", "abstract"})
        intro_position = find_heading_position({"вступ", "introduction"})
        conclusions_position = find_heading_position({"висновки", "conclusions"})

        # Abstract and Introduction are optional in minimal reports, but produce warnings
        if abstract_position is None:
            report.add_warning(
                "Structural heading is absent (supported): abstract/РЕФЕРАТ"
            )
        if intro_position is None:
            report.add_warning(
                "Structural heading is absent (supported): introduction/ВСТУП"
            )

        # Conclusions are strictly required
        if conclusions_position is None:
            report.add_error(
                "Required structural heading is missing: conclusions/ВИСНОВКИ"
            )

        # Validate sequential order: abstract -> introduction -> conclusions
        present_positions = [
            pos
            for pos in (abstract_position, intro_position, conclusions_position)
            if pos is not None
        ]
        if present_positions != sorted(present_positions):
            report.add_error(
                "Present structural sections are not in abstract → introduction → conclusions order"
            )

        # Check for main-body section between Introduction and Conclusions
        if intro_position is not None and conclusions_position is not None:
            main_sections = [
                h.text
                for i, h in enumerate(headings)
                if intro_position < i < conclusions_position
                and h.level == 1
                and h.normalized_text not in STRUCTURAL_HEADINGS
                and not h.normalized_text.startswith(("додаток", "appendix"))
            ]
            if not main_sections:
                report.add_error(
                    "No level-1 main-body section was found between introduction and conclusions"
                )

    def _validate_heading_syntax(
        self,
        headings: list[HeadingInfo],
        report: ValidationReport,
    ) -> None:
        for heading in headings:
            if heading.has_trailing_period:
                report.add_warning(
                    f"Heading ends with a period (level {heading.level}): {heading.text}"
                )

    def _validate_resources(
        self,
        nodes: list[dict[str, Any]],
        report: ValidationReport,
    ) -> None:
        resource_directories = [
            self.config.input_path.parent,
            *[p.resolve() for p in self.config.resource_paths],
        ]
        images = [
            node["c"][2][0]
            for node in nodes
            if node.get("t") == "Image" and len(node.get("c", [])) > 2
        ]

        for image_target in images:
            if re.match(r"^(?:https?|data):", image_target):
                if image_target.startswith("http"):
                    report.add_warning(
                        f"Remote image reduces offline reproducibility: {image_target}"
                    )
                continue

            target_path = Path(image_target)
            if not target_path.is_absolute() and not any(
                (directory / target_path).exists() for directory in resource_directories
            ):
                report.add_error(f"Local image was not found: {image_target}")

    def _validate_tables(
        self,
        nodes: list[dict[str, Any]],
        report: ValidationReport,
    ) -> None:
        tables = [node for node in nodes if node.get("t") == "Table"]
        for index, table in enumerate(tables, start=1):
            caption_node = table["c"][1] if len(table.get("c", [])) > 1 else None
            caption_text = stringify_pandoc_node(caption_node) if caption_node else ""
            if not caption_text:
                report.add_warning(f"Table {index} has no caption")

    def _validate_formulae(
        self,
        nodes: list[dict[str, Any]],
        report: ValidationReport,
    ) -> None:
        display_math = [
            node
            for node in nodes
            if node.get("t") == "Math"
            and node.get("c", [""])[0].get("t") == "DisplayMath"
        ]
        numbered_formulae = [
            node
            for node in nodes
            if node.get("t") == "Div"
            and "formula" in node.get("c", [["", [], []]])[0][1]
            and dict(node["c"][0][2]).get("number")
        ]
        if display_math and len(numbered_formulae) < len(display_math):
            report.add_warning(
                f"Found {len(display_math)} display formula(s), but only "
                f"{len(numbered_formulae)} use a numbered .formula block; "
                "this is valid only when the other formulae are not referenced"
            )

    def _validate_appendices(
        self,
        headings: list[HeadingInfo],
        report: ValidationReport,
    ) -> None:
        for heading in headings:
            match = re.match(
                r"\s*(?:ДОДАТОК|APPENDIX)\s+([A-ZА-ЯҐЄІЇ])",
                heading.text,
                re.IGNORECASE,
            )
            if match and match.group(1).upper() in EXCLUDED_APPENDIX_LETTERS:
                report.add_warning(
                    f"Appendix label uses an excluded Ukrainian letter: {match.group(1)}"
                )
            if "appendix" in heading.classes and not match:
                report.add_warning(
                    f"Appendix heading has no visible letter in its title: {heading.text}"
                )

    def _validate_citations(
        self,
        nodes: list[dict[str, Any]],
        metadata: DocumentMetadata,
        report: ValidationReport,
    ) -> None:
        citations = {
            item["citationId"]
            for node in nodes
            if node.get("t") == "Cite"
            for item in node["c"][0]
            if isinstance(item, dict) and "citationId" in item
        }
        if citations and not metadata.bibliography and not metadata.references:
            report.add_error(
                "Citations are present, but no 'bibliography' file or inline 'references' metadata was supplied"
            )

    def _record_applied_settings(self, report: ValidationReport) -> None:
        custom_ref = self.config.reference_doc is not None
        numbering_str = (
            "none (heading numbers disabled; figures/tables numbered continuously)"
            if self.config.numbering_mode.value == "none"
            else self.config.numbering_mode.value
        )
        report.applied_settings.extend(
            [
                f"Input: {self.config.input_path.resolve()}",
                f"Output: {self.config.output_path.resolve()}",
                (
                    "User-supplied reference DOCX (its page geometry and styles override defaults)"
                    if custom_ref
                    else "A4; margins 20 mm top/bottom, 25 mm left, 10 mm right"
                ),
                (
                    "Typography is controlled by the user-supplied reference DOCX"
                    if custom_ref
                    else "Times New Roman 14 pt body; 1.5 line spacing; 1.25 cm first-line indent; justified"
                ),
                (
                    "Header/footer behavior is controlled by the user-supplied reference DOCX"
                    if custom_ref
                    else "Upper-right page number; hidden on the title page"
                ),
                f"Section/figure/table numbering mode: {numbering_str}"
                if self.config.numbering_mode.value != "none"
                else f"Numbering mode: {numbering_str}",
                f"Automatic contents field: {'enabled' if self.config.include_toc else 'disabled'}",
            ]
        )
