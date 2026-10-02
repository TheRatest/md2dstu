"""Pandoc subprocess interaction and AST parsing utilities."""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from md2dstu.constants import DEFAULT_CSL_PATH, DEFAULT_FILTER_PATH
from md2dstu.exceptions import ConversionError, ExternalToolError


def determine_source_format(path: Path) -> str:
    """Determine Pandoc input format based on file extension."""
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown", ".mdown", ".mkd"}:
        return (
            "markdown"
            "+yaml_metadata_block"
            "+fenced_divs"
            "+implicit_figures"
            "+table_captions"
            "+tex_math_dollars"
            "+citations"
            "+footnotes"
        )
    if suffix == ".org":
        return "org"
    raise ConversionError(
        f"Input must be a Markdown (.md) or Org (.org) file, got '{path.name}'"
    )


def stringify_pandoc_node(node: Any) -> str:
    """Extract plain text from Pandoc inline or block AST nodes."""
    text_fragments: list[str] = []

    def visit(item: Any) -> None:
        if isinstance(item, str):
            text_fragments.append(item)
        elif isinstance(item, list):
            for child in item:
                visit(child)
        elif isinstance(item, dict):
            tag_type = item.get("t")
            content = item.get("c")
            if tag_type in {"Str", "Code", "Math"}:
                text = content if isinstance(content, str) else content[-1]
                text_fragments.append(str(text))
            elif tag_type in {"Space", "SoftBreak", "LineBreak"}:
                text_fragments.append(" ")
            else:
                visit(content)

    visit(node)
    joined = "".join(text_fragments)
    return re.sub(r"\s+", " ", joined).strip()


def walk_pandoc_nodes(node: Any) -> Iterator[dict[str, Any]]:
    """Recursively yield all dictionary AST nodes from a Pandoc structure."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk_pandoc_nodes(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk_pandoc_nodes(item)


class PandocBridge:
    """Encapsulates interaction with the pandoc executable."""

    def __init__(
        self,
        filter_path: Path = DEFAULT_FILTER_PATH,
        csl_path: Path = DEFAULT_CSL_PATH,
    ) -> None:
        self.filter_path = filter_path.resolve()
        self.csl_path = csl_path.resolve()
        self._ensure_resources()

    def _ensure_resources(self) -> None:
        if not self.filter_path.is_file():
            raise ConversionError(
                f"Required Lua filter was not found at {self.filter_path}"
            )
        if not self.csl_path.is_file():
            raise ConversionError(f"Required CSL file was not found at {self.csl_path}")

    def run_command(
        self,
        arguments: list[str],
        *,
        working_directory: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Execute pandoc with given arguments and raise ExternalToolError on failure."""
        command = ["pandoc", *arguments]
        try:
            return subprocess.run(
                command,
                cwd=working_directory,
                text=True,
                capture_output=True,
                check=True,
            )
        except FileNotFoundError as exc:
            raise ExternalToolError(
                "Required program 'pandoc' not found on PATH. Please install Pandoc 3.x."
            ) from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "unknown error").strip()
            raise ExternalToolError(f"Pandoc command failed:\n{detail}") from exc

    def extract_ast(
        self,
        source_path: Path,
        source_format: str,
        metadata_files: list[Path],
    ) -> tuple[dict[str, Any], str]:
        """Extract the JSON AST from the input document."""
        args: list[str] = [
            str(source_path),
            "--from",
            source_format,
            "--to",
            "json",
        ]
        for metadata_file in metadata_files:
            args.extend(["--metadata-file", str(metadata_file)])

        completed_process = self.run_command(
            args,
            working_directory=source_path.parent,
        )
        ast_data = json.loads(completed_process.stdout)
        return ast_data, completed_process.stderr

    def build_docx(
        self,
        source_path: Path,
        target_docx: Path,
        source_format: str,
        reference_docx: Path,
        metadata_files: list[Path],
        resource_directories: list[Path],
        numbering_mode: str,
        include_toc: bool,
    ) -> list[str]:
        """Run pandoc to create an initial DOCX document before postprocessing."""
        target_docx.parent.mkdir(parents=True, exist_ok=True)
        search_paths = [source_path.parent, *resource_directories]

        args: list[str] = [
            str(source_path),
            "--from",
            source_format,
            "--to",
            "docx",
            "--standalone",
            "--reference-doc",
            str(reference_docx),
            "--lua-filter",
            str(self.filter_path),
            "--citeproc",
            "--no-highlight",
            "--csl",
            str(self.csl_path),
            "--metadata",
            f"numbering={numbering_mode}",
            "--metadata",
            f"toc={'true' if include_toc else 'false'}",
            "--resource-path",
            os.pathsep.join(str(path) for path in search_paths),
            "--output",
            str(target_docx),
        ]

        if numbering_mode != "none":
            args.append("--number-sections")

        for metadata_file in metadata_files:
            args.extend(["--metadata-file", str(metadata_file)])

        if include_toc:
            args.extend(["--toc", "--toc-depth=3", "--metadata", "toc-title=ЗМІСТ"])

        result = self.run_command(args, working_directory=source_path.parent)

        warnings: list[str] = []
        for line in result.stderr.splitlines():
            cleaned = line.strip()
            if cleaned:
                warnings.append(f"Pandoc: {cleaned}")
        return warnings
