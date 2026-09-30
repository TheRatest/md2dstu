"""Unit tests for metadata extraction and normalization."""

from __future__ import annotations

import unittest

from md2dstu.metadata import DocumentMetadata, normalize_meta_value


class MetadataTestCase(unittest.TestCase):
    def test_normalize_meta_value(self) -> None:
        raw_meta = {
            "title": {"t": "MetaString", "c": "Тестовий звіт"},
            "toc": {"t": "MetaBool", "c": True},
            "keywords": {
                "t": "MetaList",
                "c": [
                    {"t": "MetaString", "c": "АЛГОРИТМ"},
                    {"t": "MetaString", "c": "СИСТЕМА"},
                ],
            },
            "student": {
                "t": "MetaMap",
                "c": {
                    "name": {"t": "MetaString", "c": "Іванов І. І."},
                    "title": {"t": "MetaString", "c": "студент"},
                },
            },
        }

        normalized = {key: normalize_meta_value(val) for key, val in raw_meta.items()}
        self.assertEqual(normalized["title"], "Тестовий звіт")
        self.assertTrue(normalized["toc"])
        self.assertEqual(normalized["keywords"], ["АЛГОРИТМ", "СИСТЕМА"])
        self.assertEqual(
            normalized["student"],
            {"name": "Іванов І. І.", "title": "студент"},
        )

    def test_document_metadata_parsing(self) -> None:
        raw_meta = {
            "title": {"t": "MetaString", "c": "Звіт про практику"},
            "institution": {"t": "MetaString", "c": "КПІ ім. Ігоря Сікорського"},
            "student": {
                "t": "MetaMap",
                "c": {
                    "name": {"t": "MetaString", "c": "Петренко П. П."},
                    "label": {"t": "MetaString", "c": "Виконав:"},
                },
            },
            "supervisor": {"t": "MetaString", "c": "Сидоренко С. С."},
        }

        metadata = DocumentMetadata.from_ast_meta(raw_meta)
        self.assertEqual(metadata.title, "Звіт про практику")
        self.assertEqual(metadata.institution, "КПІ ім. Ігоря Сікорського")
        self.assertEqual(metadata.student.name, "Петренко П. П.")
        self.assertEqual(metadata.student.label, "Виконав:")
        # Fallback to legacy supervisor
        self.assertEqual(metadata.legacy_supervisor, "Сидоренко С. С.")


if __name__ == "__main__":
    unittest.main()
