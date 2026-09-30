"""DOCX postprocessing and formatting package."""

from md2dstu.docx.postprocessor import DocxPostProcessor
from md2dstu.docx.toc_casing import apply_sentence_case_to_toc

__all__ = [
    "DocxPostProcessor",
    "apply_sentence_case_to_toc",
]
