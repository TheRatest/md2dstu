"""Tests for loading bibliography metadata through Pandoc."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from md2dstu.bibliography import load_bibliography_entries


class BibliographyTestCase(unittest.TestCase):
    def test_loads_and_normalizes_csl_yaml(self) -> None:
        with tempfile.TemporaryDirectory(prefix="md2dstu-bib-") as temp_dir:
            directory = Path(temp_dir)
            bibliography = directory / "references.yaml"
            bibliography.write_text(
                "references:\n"
                "  - id: web\n"
                "    type: webpage\n"
                "    title: Приклад\n"
                "    URL: https://example.com\n"
                "    accessed:\n"
                "      date-parts: [[2026, 10, 24]]\n",
                encoding="utf-8",
            )

            entries, warnings = load_bibliography_entries(
                bibliography.name,
                source_directory=directory,
            )

        self.assertEqual(warnings, [])
        self.assertEqual(entries[0]["id"], "web")
        self.assertEqual(entries[0]["title"], "Приклад")
        self.assertEqual(
            entries[0]["accessed"]["date-parts"],
            [["2026", "10", "24"]],
        )

    def test_missing_bibliography_file_returns_warning(self) -> None:
        entries, warnings = load_bibliography_entries(
            "missing.yaml",
            source_directory=Path("."),
        )

        self.assertEqual(entries, [])
        self.assertTrue(any("Bibliography file was not found" in item for item in warnings))


if __name__ == "__main__":
    unittest.main()
