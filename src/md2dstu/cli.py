"""Command-line interface entry point for md2dstu."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from md2dstu.config import ConversionConfig, NumberingMode
from md2dstu.converter import ReportConverter
from md2dstu.exceptions import Md2DstuError


def build_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="md2dstu",
        description="Convert Markdown or Org documents to a DSTU 3008:2015-oriented DOCX, DOC, or ODT report.",
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to UTF-8 Markdown (.md) or Org (.org) source file",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Path to output .docx, .doc, or .odt file (defaults to input stem with .docx)",
    )
    parser.add_argument(
        "--metadata-file",
        action="append",
        default=[],
        type=Path,
        help="Additional YAML metadata file (can be specified multiple times)",
    )
    parser.add_argument(
        "--reference-doc",
        type=Path,
        help="Custom institutional reference DOCX to override default typography and margins",
    )
    parser.add_argument(
        "--resource-path",
        action="append",
        default=[],
        type=Path,
        help="Additional directory to search for images and assets (repeatable)",
    )
    parser.add_argument(
        "--numbering",
        choices=("section", "continuous", "none"),
        help="Numbering mode: 'section', 'continuous', or 'none' (none disables heading numbers only)",
    )
    parser.add_argument(
        "--toc",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Insert an automatic Table of Contents field (use --no-toc to disable)",
    )
    parser.add_argument(
        "--bold-heading2",
        action="store_true",
        help="Apply bold weight to level-2 headings (Heading 2)",
    )
    parser.add_argument(
        "--no-update-toc",
        action="store_true",
        help="Do not invoke LibreOffice to populate the Table of Contents field",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit with status code 2 if DSTU structural validation reports any errors",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Custom path for the validation report file (default: <output>.validation.txt)",
    )
    parser.add_argument(
        "--keep-docx",
        action="store_true",
        help="Preserve intermediate .docx file when converting to legacy .doc or .odt",
    )
    return parser


def parse_arguments_to_config(argv: list[str] | None = None) -> ConversionConfig:
    """Parse CLI arguments into a validated ConversionConfig instance."""
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    input_path = args.input.resolve()
    output_path = (args.output or input_path.with_suffix(".docx")).resolve()

    numbering_mode = (
        NumberingMode.from_string(args.numbering)
        if args.numbering
        else NumberingMode.SECTION
    )

    return ConversionConfig(
        input_path=input_path,
        output_path=output_path,
        metadata_files=[p.resolve() for p in args.metadata_file],
        reference_doc=args.reference_doc.resolve() if args.reference_doc else None,
        resource_paths=[p.resolve() for p in args.resource_path],
        numbering_mode=numbering_mode,
        include_toc=args.toc,
        bold_heading2=args.bold_heading2,
        update_toc=not args.no_update_toc,
        check_structural_errors=args.check,
        report_path=args.report.resolve() if args.report else None,
        keep_intermediate_docx=args.keep_docx,
    )


def main(argv: list[str] | None = None) -> int:
    """Execute main CLI command workflow."""
    try:
        config = parse_arguments_to_config(argv)
        converter = ReportConverter(config)
        result = converter.convert()

        report = result.validation_report
        print(f"Created: {result.output_path}")
        print(f"Validation: {result.report_path}")
        print(f"Status: {report.status.value}")

        if report.errors:
            for error_message in report.errors:
                print(f"  error: {error_message}", file=sys.stderr)

        if config.check_structural_errors and not report.is_success:
            return 2
        return 0

    except Md2DstuError as exc:
        print(f"md2dstu: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - Top-level CLI exception handler to prevent unhandled tracebacks
        print(f"md2dstu: unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
