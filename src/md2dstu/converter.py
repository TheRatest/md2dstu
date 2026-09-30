"""High-level document conversion orchestrator for md2dstu."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from md2dstu.config import ConversionConfig, NumberingMode
from md2dstu.constants import DEFAULT_CSL_PATH, DEFAULT_FILTER_PATH
from md2dstu.docx.postprocessor import DocxPostProcessor
from md2dstu.exceptions import ConversionError, ResourceNotFoundError
from md2dstu.libreoffice import LibreOfficeService, publish_file_atomically
from md2dstu.metadata import DocumentMetadata
from md2dstu.pandoc import PandocBridge, determine_source_format
from md2dstu.validation.models import ValidationReport
from md2dstu.validation.validator import DocumentValidator


@dataclass(slots=True)
class ConversionResult:
    """Outcome of a document conversion run."""

    output_path: Path
    report_path: Path
    validation_report: ValidationReport


class ReportConverter:
    """Coordinates validation, Pandoc compilation, DOCX postprocessing, and LibreOffice exports."""

    def __init__(
        self,
        config: ConversionConfig,
        filter_path: Path = DEFAULT_FILTER_PATH,
        csl_path: Path = DEFAULT_CSL_PATH,
    ) -> None:
        self.config = config
        self.pandoc_bridge = PandocBridge(filter_path=filter_path, csl_path=csl_path)
        self.validator = DocumentValidator(config)

    def convert(self) -> ConversionResult:
        """Execute the end-to-end conversion process."""
        self._validate_paths()

        source_format = determine_source_format(self.config.input_path)
        ast_data, ast_warnings = self.pandoc_bridge.extract_ast(
            self.config.input_path,
            source_format,
            self.config.metadata_files,
        )

        has_manual_title_page = self._has_manual_title_page(ast_data)
        metadata = DocumentMetadata.from_ast_meta(
            ast_data.get("meta", {}),
            has_manual_title_page=has_manual_title_page,
        )

        # Reconcile numbering and TOC settings with metadata defaults
        if (
            self.config.numbering_mode == NumberingMode.SECTION
            and metadata.numbering != "section"
        ):
            self.config.numbering_mode = NumberingMode.from_string(metadata.numbering)

        if self.config.include_toc is None:
            self.config.include_toc = metadata.toc

        validation_report = self.validator.validate(ast_data, metadata)
        if ast_warnings.strip():
            for line in ast_warnings.splitlines():
                if line.strip():
                    validation_report.add_warning(line.strip())

        with tempfile.TemporaryDirectory(prefix="md2dstu-work-") as temporary_dir:
            work_dir = Path(temporary_dir)
            draft_docx = work_dir / "draft_document.docx"

            pandoc_warnings = self.pandoc_bridge.build_docx(
                source_path=self.config.input_path,
                target_docx=draft_docx,
                source_format=source_format,
                reference_docx=self.config.resolved_reference_doc,
                metadata_files=self.config.metadata_files,
                resource_directories=self.config.resource_paths,
                numbering_mode=self.config.numbering_mode.value,
                include_toc=bool(self.config.include_toc),
            )
            for warning in pandoc_warnings:
                validation_report.add_warning(warning)

            # Post-process XML structures
            postprocessor = DocxPostProcessor(bold_heading2=self.config.bold_heading2)
            postprocessor.process(draft_docx)

            # Update TOC if requested and LibreOffice is available
            if self.config.include_toc and self.config.update_toc:
                if LibreOfficeService.is_libreoffice_available():
                    LibreOfficeService.update_table_of_contents(draft_docx, work_dir)
                    # LibreOffice updates can rewrite properties; re-assert exact DSTU styling
                    postprocessor.process(draft_docx)
                else:
                    validation_report.add_warning(
                        "LibreOffice is unavailable, so the contents field was inserted but "
                        "not populated; update it in Word/LibreOffice"
                    )

            # Output publication
            if self.config.is_docx_output:
                publish_file_atomically(draft_docx, self.config.output_path)
            else:
                converted_target = LibreOfficeService.convert_format(
                    draft_docx, self.config.output_path, work_dir
                )
                publish_file_atomically(converted_target, self.config.output_path)
                if self.config.keep_intermediate_docx:
                    publish_file_atomically(
                        draft_docx, self.config.output_path.with_suffix(".docx")
                    )

        # Write validation report
        report_path = self.config.effective_report_path
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_temporary = report_path.with_suffix(report_path.suffix + ".tmp")
        report_temporary.write_text(validation_report.render_text(), encoding="utf-8")
        os.replace(report_temporary, report_path)

        return ConversionResult(
            output_path=self.config.output_path,
            report_path=report_path,
            validation_report=validation_report,
        )

    def _validate_paths(self) -> None:
        source = self.config.input_path.resolve()
        if not source.is_file():
            raise ConversionError(f"Input file does not exist: {source}")

        for metadata_file in self.config.metadata_files:
            if not metadata_file.resolve().is_file():
                raise ConversionError(f"Metadata file does not exist: {metadata_file}")

        reference = self.config.resolved_reference_doc
        if not reference.is_file():
            hint = (
                "Run: python3 tools/build_reference.py"
                if self.config.reference_doc is None
                else "Check --reference-doc"
            )
            raise ResourceNotFoundError(
                f"Reference DOCX does not exist: {reference}. {hint}"
            )

        output_parent = self.config.output_path.resolve().parent
        output_parent.mkdir(parents=True, exist_ok=True)
        if not os.access(output_parent, os.W_OK):
            raise ConversionError(f"Output directory is not writable: {output_parent}")

    @staticmethod
    def _has_manual_title_page(ast_data: dict[str, any]) -> bool:
        blocks = ast_data.get("blocks", [])
        if not blocks:
            return False
        first_block = blocks[0]
        if first_block.get("t") == "Div":
            classes = first_block.get("c", [["", [], []]])[0][1]
            return "title-page" in classes
        return False
