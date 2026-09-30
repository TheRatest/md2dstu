"""Headless LibreOffice service for Table of Contents updates and format conversion."""

from __future__ import annotations

import contextlib
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

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

    @classmethod
    def update_table_of_contents(cls, docx_path: Path, working_dir: Path) -> None:
        """Populate the automatic Table of Contents and page numbers using headless LibreOffice."""
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
            document = desktop.loadComponentFromURL(
                docx_path.resolve().as_uri(),
                "_blank",
                0,
                load_properties,
            )
            if document is None:
                raise ExternalToolError(
                    f"LibreOffice could not open generated file {docx_path.name} to populate TOC"
                )

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
