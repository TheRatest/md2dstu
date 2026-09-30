"""Models and status definitions for DSTU structural validation reports."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class ValidationStatus(str, Enum):
    """Validation outcome status values."""

    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS WITH WARNINGS"
    FAIL = "FAIL"


@dataclass(slots=True)
class HeadingInfo:
    """Extracted heading information from Pandoc AST."""

    level: int
    text: str
    classes: list[str] = field(default_factory=list)
    index: int = 0

    @property
    def normalized_text(self) -> str:
        """Strip section numbers and trailing punctuation, converted to lowercase."""
        cleaned = re.sub(r"^\d+(?:\.\d+)*\s+", "", self.text.strip())
        return re.sub(r"[.:;!?]+$", "", cleaned).strip().casefold()

    @property
    def has_trailing_period(self) -> bool:
        """DSTU prohibits trailing periods on headings."""
        return self.text.rstrip().endswith(".")


@dataclass(slots=True)
class ValidationReport:
    """Detailed validation results containing errors, warnings, and settings."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    applied_settings: list[str] = field(default_factory=list)
    unverified_items: list[str] = field(
        default_factory=lambda: [
            "Correctness and completeness of bibliographic descriptions",
            "Whether every formula, figure, table, and appendix is cited at the proper point in the prose",
            "Visual pagination (widows/orphans, overflow, image legibility, and exact TOC page numbers)",
            "Institution-specific approval blocks and signatures",
        ]
    )

    @property
    def status(self) -> ValidationStatus:
        """Calculate overall validation status based on errors and warnings."""
        if self.errors:
            return ValidationStatus.FAIL
        if self.warnings:
            return ValidationStatus.PASS_WITH_WARNINGS
        return ValidationStatus.PASS

    @property
    def is_success(self) -> bool:
        """Return True if there are no errors."""
        return len(self.errors) == 0

    def add_error(self, message: str) -> None:
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def render_text(self) -> str:
        """Format human-readable validation report text."""
        lines = [
            f"DSTU conversion validation: {self.status.value}",
            "",
            "Applied settings:",
        ]
        lines.extend(f"- {setting}" for setting in self.applied_settings)
        lines.extend(["", "Errors:"])
        lines.extend([f"- {error}" for error in self.errors] or ["- None"])
        lines.extend(["", "Warnings:"])
        lines.extend([f"- {warning}" for warning in self.warnings] or ["- None"])
        lines.extend(["", "Not automatically verified:"])
        lines.extend(f"- {item}" for item in self.unverified_items)
        lines.extend(
            [
                "",
                "This report checks the project profile summarized in DSTU.md. It is not a certificate of full",
                "DSTU 3008:2015 or institution-specific compliance. Refresh fields and visually inspect the final file.",
                "",
            ]
        )
        return "\n".join(lines)
