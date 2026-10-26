"""Headless LibreOffice service for layout-dependent fixes, TOC updates, and format conversion."""

from __future__ import annotations

import contextlib
import os
import shutil
import socket
import subprocess
import tempfile
import time
from itertools import pairwise
from pathlib import Path
from typing import Any

from md2dstu.docx.tables import split_table
from md2dstu.docx.toc_casing import apply_sentence_case_to_toc
from md2dstu.exceptions import ConversionError, ExternalToolError


def publish_file_atomically(source_path: Path, destination_path: Path) -> None:
    """Publish a completed file atomically, working reliably across filesystems."""
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_path_name = tempfile.mkstemp(
        prefix=f".{destination_path.name}.",
        suffix=".tmp",
        dir=destination_path.parent,
    )
    os.close(descriptor)
    temporary_path = Path(temporary_path_name)
    try:
        shutil.copy2(source_path, temporary_path)
        with temporary_path.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary_path, destination_path)
    finally:
        temporary_path.unlink(missing_ok=True)


class LibreOfficeService:
    """Interacts with headless LibreOffice for TOC field evaluation and file conversion."""

    @staticmethod
    def is_libreoffice_available() -> bool:
        """Return True if the libreoffice binary exists in PATH."""
        return shutil.which("libreoffice") is not None

    @staticmethod
    def is_uno_available() -> bool:
        """Return True if the LibreOffice Python UNO binding can be imported."""
        try:
            import uno  # noqa: F401

            return True
        except ImportError:
            return False

    @staticmethod
    def remove_blank_lines_at_page_top(document: Any) -> None:
        """Drop an empty paragraph that a page break pushed to the top of a page above a heading.

        The heading gets an explicit page break instead, so it stays at the top of
        that page and the post-processor does not re-insert the blank line.
        """
        from com.sun.star.style.BreakType import PAGE_BEFORE

        text = document.getText()
        view_cursor = document.getCurrentController().getViewCursor()
        enumeration = text.createEnumeration()
        paragraphs = []
        while enumeration.hasMoreElements():
            paragraphs.append(enumeration.nextElement())

        # Each removal shifts later content up, so query the live layout one by one.
        for blank, heading in pairwise(paragraphs):
            if not (
                blank.supportsService("com.sun.star.text.Paragraph")
                and heading.supportsService("com.sun.star.text.Paragraph")
                and heading.OutlineLevel > 0
                and not blank.getString().strip()
            ):
                continue
            view_cursor.gotoRange(blank.getStart(), False)
            view_cursor.jumpToStartOfPage()
            if text.compareRegionStarts(view_cursor, blank.getStart()) != 0:
                continue
            heading.BreakType = PAGE_BEFORE
            blank.dispose()

    @staticmethod
    def find_table_page_break(
        document: Any, first_table: int
    ) -> tuple[int, int] | None:
        """Return (table index, row index) of the first row not on its table's first page.

        Only body tables from first_table on are checked. A table whose first
        data row already leaves the first page is not reported: there is nothing
        to split off.
        """
        text = document.getText()
        view_cursor = document.getCurrentController().getViewCursor()
        enumeration = text.createEnumeration()
        tables = []
        while enumeration.hasMoreElements():
            element = enumeration.nextElement()
            if element.supportsService("com.sun.star.text.TextTable"):
                tables.append(element)

        def page_of(text_range: Any) -> int:
            view_cursor.gotoRange(text_range, False)
            return view_cursor.getPage()

        for table_index in range(first_table, len(tables)):
            table = tables[table_index]
            columns = table.getColumns().getCount()
            try:
                first_page = page_of(table.getCellByPosition(0, 0).getStart())
                for row in range(1, table.getRows().getCount()):
                    # A row split across pages counts as leaving the page.
                    if any(
                        page_of(table.getCellByPosition(column, row).getEnd())
                        != first_page
                        for column in range(columns)
                    ):
                        if row >= 2:
                            return table_index, row
                        break
            except Exception:  # noqa: BLE001, S112 - merged cells have no position
                continue
        return None

    @classmethod
    def finalize_layout(cls, docx_path: Path, working_dir: Path) -> None:
        """Apply page-dependent fixes and populate the Table of Contents using headless LibreOffice."""
        try:
            import uno
            from com.sun.star.beans import PropertyValue
        except ImportError as exc:
            raise ExternalToolError(
                "LibreOffice Python UNO bindings (pyuno) are missing; "
                "install the pyuno package or use --no-update-toc"
            ) from exc

        def make_property(name: str, value: Any) -> PropertyValue:
            prop = PropertyValue()
            prop.Name = name
            prop.Value = value
            return prop

        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]

        profile_dir = working_dir / "libreoffice-profile"
        profile_dir.mkdir(parents=True, exist_ok=True)

        process = subprocess.Popen(
            [
                "libreoffice",
                "--headless",
                "--nologo",
                "--nodefault",
                "--nofirststartwizard",
                "--norestore",
                f"-env:UserInstallation={profile_dir.as_uri()}",
                f"--accept=socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )

        document = None
        try:
            local_context = uno.getComponentContext()
            resolver = local_context.ServiceManager.createInstanceWithContext(
                "com.sun.star.bridge.UnoUrlResolver", local_context
            )
            remote_context = None

            # Retry loop to connect to the socket
            for _ in range(100):
                if process.poll() is not None:
                    error_detail = (
                        process.stderr.read().strip() if process.stderr else ""
                    )
                    raise ExternalToolError(
                        f"LibreOffice exited prematurely while starting TOC update: {error_detail or 'unknown error'}"
                    )
                try:
                    remote_context = resolver.resolve(
                        f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext"
                    )
                    break
                except Exception:  # noqa: BLE001 - UNO bridge raises various connection exceptions before socket is ready
                    time.sleep(0.1)

            if remote_context is None:
                raise ExternalToolError(
                    "Timed out waiting for LibreOffice headless instance to start"
                )

            desktop = remote_context.ServiceManager.createInstanceWithContext(
                "com.sun.star.frame.Desktop", remote_context
            )
            load_properties = (
                make_property("Hidden", True),
                make_property("ReadOnly", False),
            )

            def load() -> Any:
                loaded = desktop.loadComponentFromURL(
                    docx_path.resolve().as_uri(),
                    "_blank",
                    0,
                    load_properties,
                )
                if loaded is None:
                    raise ExternalToolError(
                        f"LibreOffice could not open generated file {docx_path.name} to populate TOC"
                    )
                return loaded

            document = load()

            # Each split changes the layout after it, so re-measure after every one.
            first_table = 0
            while (
                found := cls.find_table_page_break(document, first_table)
            ) is not None:
                table_index, row_index = found
                document.close(True)
                document = None
                split_table(docx_path, table_index, row_index)
                first_table = table_index + 1
                document = load()

            cls.remove_blank_lines_at_page_top(document)
            indexes = document.getDocumentIndexes()
            for index in range(indexes.getCount()):
                table_of_contents = indexes.getByIndex(index)
                table_of_contents.update()

            document.store()
            document.close(True)
            document = None
        except (ConversionError, ExternalToolError):
            raise
        except Exception as exc:
            raise ExternalToolError(
                f"Failed to populate document contents with LibreOffice: {exc}"
            ) from exc
        finally:
            if document is not None:
                with contextlib.suppress(Exception):
                    document.close(True)
            if process.stderr:
                with contextlib.suppress(Exception):
                    process.stderr.close()
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

        # Update TOC entries to sentence case (DSTU style)
        apply_sentence_case_to_toc(docx_path)

    @classmethod
    def convert_format(
        cls,
        source_docx: Path,
        target_output: Path,
        working_dir: Path,
    ) -> Path:
        """Convert a DOCX file to DOC or ODT using LibreOffice."""
        if not cls.is_libreoffice_available():
            raise ExternalToolError(
                f"LibreOffice is required to create '{target_output.suffix}' files"
            )

        extension = target_output.suffix.lower()
        filter_name = "doc:MS Word 97" if extension == ".doc" else "odt"

        profile_dir = working_dir / "libreoffice-convert-profile"
        profile_dir.mkdir(parents=True, exist_ok=True)

        command = [
            "libreoffice",
            "--headless",
            f"-env:UserInstallation={profile_dir.as_uri()}",
            "--convert-to",
            filter_name,
            "--outdir",
            str(working_dir),
            str(source_docx),
        ]

        try:
            subprocess.run(
                command,
                cwd=working_dir,
                text=True,
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "unknown error").strip()
            raise ExternalToolError(
                f"LibreOffice conversion to {extension} failed:\n{detail}"
            ) from exc

        converted_path = working_dir / f"{source_docx.stem}{extension}"
        if not converted_path.is_file():
            raise ExternalToolError(
                f"LibreOffice did not produce the expected file: {converted_path.name}"
            )

        return converted_path
