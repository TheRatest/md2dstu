"""Configuration models and enums for document conversion."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from md2dstu.constants import DEFAULT_REFERENCE_DOCX_PATH
from md2dstu.exceptions import ConversionError


class NumberingMode(str, Enum):
    """Section and object numbering modes supported by md2dstu."""

    SECTION = "section"
    CONTINUOUS = "continuous"
    NONE = "none"

    @classmethod
    def from_string(cls, value: str) -> NumberingMode:
        try:
            return cls(value.lower().strip())
        except ValueError:
            valid_modes = ", ".join(m.value for m in cls)
            raise ConversionError(
                f"Invalid numbering mode '{value}'. Allowed values are: {valid_modes}"
            )


class OutputFormat(str, Enum):
    """Supported output document formats."""

    DOCX = ".docx"
    DOC = ".doc"
    ODT = ".odt"

    @classmethod
    def from_path(cls, path: Path) -> OutputFormat:
        suffix = path.suffix.lower()
        try:
            return cls(suffix)
        except ValueError:
            valid_extensions = ", ".join(f.value for f in cls)
            raise ConversionError(
                f"Unsupported output extension '{suffix}'. Expected one of: {valid_extensions}"
            )


@dataclass(slots=True)
class ConversionConfig:
    """Settings governing the entire document conversion workflow."""

    input_path: Path
    output_path: Path
    metadata_files: list[Path] = field(default_factory=list)
    reference_doc: Path | None = None
    resource_paths: list[Path] = field(default_factory=list)
    numbering_mode: NumberingMode = NumberingMode.SECTION
    include_toc: bool | None = None
    bold_heading2: bool = False
    update_toc: bool = True
    check_structural_errors: bool = False
    report_path: Path | None = None
    keep_intermediate_docx: bool = False

    @property
    def output_format(self) -> OutputFormat:
        """Return the resolved output format from output_path."""
        return OutputFormat.from_path(self.output_path)

    @property
    def is_docx_output(self) -> bool:
        """Return True if the target output file is DOCX."""
        return self.output_format == OutputFormat.DOCX

    @property
    def resolved_reference_doc(self) -> Path:
        """Return the user reference DOCX if specified, otherwise the default template."""
        if self.reference_doc is not None:
            return self.reference_doc.resolve()
        return DEFAULT_REFERENCE_DOCX_PATH.resolve()

    @property
    def effective_report_path(self) -> Path:
        """Return the explicit validation report path or default beside output."""
        if self.report_path is not None:
            return self.report_path.resolve()
        return Path(str(self.output_path) + ".validation.txt").resolve()
