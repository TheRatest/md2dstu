"""OpenXML namespace definitions and XML helper utilities."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from md2dstu.constants import OPENXML_NAMESPACES, W_NAMESPACE


def register_openxml_namespaces() -> None:
    """Register all standard OpenXML namespaces with ElementTree to avoid synthetic prefixes."""
    for prefix, uri in OPENXML_NAMESPACES.items():
        ET.register_namespace(prefix, uri)


def w_tag(local_name: str) -> str:
    """Return a qualified tag name in the WordprocessingML namespace."""
    return f"{{{W_NAMESPACE}}}{local_name}"


def openxml_tag(local_name: str, namespace_uri: str) -> str:
    """Return a qualified tag name for a given namespace URI."""
    return f"{{{namespace_uri}}}{local_name}"


def child_element(parent: ET.Element, local_name: str, **attributes: str) -> ET.Element:
    """Create a WordprocessingML child element and append it to parent."""
    qualified_attributes = {w_tag(key): val for key, val in attributes.items()}
    return ET.SubElement(parent, w_tag(local_name), qualified_attributes)


def replace_child_element(parent: ET.Element, local_name: str) -> ET.Element:
    """Remove any existing child with local_name and append a new one."""
    tag = w_tag(local_name)
    existing = parent.find(tag)
    if existing is not None:
        parent.remove(existing)
    new_element = ET.Element(tag)
    parent.append(new_element)
    return new_element
