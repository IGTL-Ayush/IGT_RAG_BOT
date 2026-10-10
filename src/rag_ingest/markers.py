"""Shared structural markers used by parsing and chunking."""

import re

PAGE_MARKER_TEMPLATE = "<!-- page_number: {page_number} -->"
PAGE_MARKER_PATTERN = re.compile(
    r"<!--\s*page_number:\s*(\d+)\s*-->",
    flags=re.IGNORECASE,
)
IMAGE_MARKER_PATTERN = re.compile(r"<!--\s*image\s*-->", flags=re.IGNORECASE)


def page_marker(page_number: int) -> str:
    """Render the canonical one-based page marker."""
    if page_number < 1:
        raise ValueError("page_number must be >= 1")
    return PAGE_MARKER_TEMPLATE.format(page_number=page_number)
