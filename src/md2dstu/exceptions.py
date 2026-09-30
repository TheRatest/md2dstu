"""Exceptions for md2dstu."""

from __future__ import annotations


class Md2DstuError(Exception):
    """Base exception for all md2dstu errors."""


class ConversionError(Md2DstuError, RuntimeError):
    """Raised when document conversion fails or requirements are missing."""


class ValidationError(Md2DstuError):
    """Raised when document structure fails strict validation."""


class ResourceNotFoundError(ConversionError):
    """Raised when an essential template, filter, or input file is missing."""


class ExternalToolError(ConversionError):
    """Raised when an external tool (pandoc, libreoffice) fails to execute."""
