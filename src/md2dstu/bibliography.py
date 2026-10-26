"""Bibliography loading and metadata checks for DSTU reports."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from md2dstu.exceptions import ExternalToolError


REFERENCE_FILTER = (
    Path(__file__).resolve().parents[2] / "filters" / "extract-references.lua"
)


def load_bibliography_entries(
    bibliography: str | list[str] | None,
    *,
    source_directory: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Load external bibliography files through Pandoc's supported readers."""
    if not bibliography:
        return [], []

    bibliography_files = (
        bibliography if isinstance(bibliography, list) else [bibliography]
    )
    entries: list[dict[str, Any]] = []
    warnings: list[str] = []
    for bibliography_file in bibliography_files:
        path = Path(str(bibliography_file))
        if not path.is_absolute():
            path = source_directory / path
        if not path.is_file():
            warnings.append(f"Bibliography file was not found: {path}")
            continue

        bibliography_uri = path.resolve().as_uri()
        source = (
            "---\n"
            f"bibliography: {bibliography_uri}\n"
            "nocite: |\n"
            "  @*\n"
            "---\n"
        )
        command = [
            "pandoc",
            "--from",
            "markdown",
            "--to",
            "json",
            "--lua-filter",
            str(REFERENCE_FILTER),
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=source_directory,
                input=source,
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
            warnings.append(f"Could not inspect bibliography '{path.name}': {detail}")
            continue

        ast_data = json.loads(completed.stdout)
        references = ast_data.get("meta", {}).get("references", {}).get("c", [])
        entries.extend(_normalize_reference(reference) for reference in references)

    return entries, warnings


def _normalize_reference(reference: Any) -> dict[str, Any]:
    """Convert a Pandoc MetaMap bibliography record into plain Python values."""
    if not isinstance(reference, dict):
        return {}
    content = reference.get("c", reference)
    if not isinstance(content, dict):
        return {}
    return {key: _normalize_meta_value(value) for key, value in content.items()}


def _normalize_meta_value(value: Any) -> Any:
    if not isinstance(value, dict) or "t" not in value:
        return value
    tag = value["t"]
    content = value.get("c")
    if tag == "MetaMap":
        return {key: _normalize_meta_value(item) for key, item in content.items()}
    if tag == "MetaList":
        return [_normalize_meta_value(item) for item in content]
    if tag == "MetaBool":
        return bool(content)
    if tag == "MetaString":
        return str(content or "")
    if tag in {"MetaInlines", "MetaBlocks"}:
        return _stringify(content)
    return content


def _stringify(value: Any) -> str:
    fragments: list[str] = []

    def visit(item: Any) -> None:
        if isinstance(item, list):
            for child in item:
                visit(child)
        elif isinstance(item, dict):
            tag = item.get("t")
            content = item.get("c")
            if tag == "Str":
                fragments.append(str(content))
            elif tag in {"Space", "SoftBreak", "LineBreak"}:
                fragments.append(" ")
            else:
                visit(content)
        elif isinstance(item, str):
            fragments.append(item)

    visit(value)
    return "".join(fragments).strip()
