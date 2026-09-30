"""Metadata extraction and structured representation for DSTU title pages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from md2dstu.pandoc import stringify_pandoc_node


def normalize_meta_value(value: Any) -> Any:
    """Recursively convert Pandoc AST metadata objects into standard Python types."""
    if not isinstance(value, dict) or "t" not in value:
        return value

    tag_type = value["t"]
    content = value.get("c")

    if tag_type == "MetaMap":
        return {key: normalize_meta_value(val) for key, val in content.items()}
    if tag_type == "MetaList":
        return [normalize_meta_value(item) for item in content]
    if tag_type == "MetaBool":
        return bool(content)
    if tag_type in {"MetaString", "MetaInlines", "MetaBlocks"}:
        return stringify_pandoc_node(content)
    return stringify_pandoc_node(content)


@dataclass(slots=True)
class PersonDetails:
    """Represents a student or teacher entry on the title page."""

    name: str = ""
    title: str = ""
    label: str = ""

    @classmethod
    def from_dict(cls, data: Any) -> PersonDetails:
        if not isinstance(data, dict):
            return cls()
        return cls(
            name=str(data.get("name", "")).strip(),
            title=str(data.get("title", "")).strip(),
            label=str(data.get("label", "")).strip(),
        )


@dataclass(slots=True)
class DocumentMetadata:
    """Parsed front-matter metadata and title-page configuration."""

    title: str = ""
    report_type: str = ""
    ministry: str = ""
    institution: str = ""
    faculty: str = ""
    department: str = ""
    approval: str = ""
    student: PersonDetails = field(default_factory=PersonDetails)
    teacher: PersonDetails = field(default_factory=PersonDetails)
    legacy_author: str = ""
    legacy_supervisor: str = ""
    group: str = ""
    city: str = ""
    year: str = ""
    numbering: str = "section"
    toc: bool = False
    bibliography: str | None = None
    references: Any = None
    keywords: list[str] = field(default_factory=list)
    has_manual_title_page: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.student, dict):
            self.student = PersonDetails.from_dict(self.student)
        if isinstance(self.teacher, dict):
            self.teacher = PersonDetails.from_dict(self.teacher)

    @classmethod
    def from_ast_meta(
        cls,
        raw_ast_meta: dict[str, Any],
        *,
        has_manual_title_page: bool = False,
    ) -> DocumentMetadata:
        """Create DocumentMetadata from raw Pandoc AST metadata map."""
        normalized = {
            key: normalize_meta_value(val) for key, val in raw_ast_meta.items()
        }

        keywords_val = normalized.get("keywords", [])
        if isinstance(keywords_val, list):
            keywords = [str(k).strip() for k in keywords_val if str(k).strip()]
        elif isinstance(keywords_val, str):
            keywords = [k.strip() for k in keywords_val.split(",") if k.strip()]
        else:
            keywords = []

        return cls(
            title=str(normalized.get("title", "")).strip(),
            report_type=str(normalized.get("report-type", "")).strip(),
            ministry=str(normalized.get("ministry", "")).strip(),
            institution=str(normalized.get("institution", "")).strip(),
            faculty=str(normalized.get("faculty", "")).strip(),
            department=str(normalized.get("department", "")).strip(),
            approval=str(normalized.get("approval", "")).strip(),
            student=PersonDetails.from_dict(normalized.get("student")),
            teacher=PersonDetails.from_dict(normalized.get("teacher")),
            legacy_author=str(normalized.get("author", "")).strip(),
            legacy_supervisor=str(normalized.get("supervisor", "")).strip(),
            group=str(normalized.get("group", "")).strip(),
            city=str(normalized.get("city", "")).strip(),
            year=str(normalized.get("year", "")).strip(),
            numbering=str(normalized.get("numbering", "section")).strip(),
            toc=bool(normalized.get("toc", False)),
            bibliography=normalized.get("bibliography"),
            references=normalized.get("references"),
            keywords=keywords,
            has_manual_title_page=has_manual_title_page,
            raw=normalized,
        )
