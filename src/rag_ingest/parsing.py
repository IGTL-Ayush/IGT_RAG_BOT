"""PDF-to-Markdown parsing using Docling."""

import logging
from pathlib import Path
from typing import Any

from docling.document_converter import DocumentConverter

from .hashing import atomic_write_text, sha256_file
from .markers import page_marker

logger = logging.getLogger(__name__)


def parse_pdf(
    pdf_path: str | Path,
    output_path: str | Path,
    converter: Any | None = None,
) -> tuple[Path, str]:
    """Convert a PDF to Markdown and return (output_path, source_sha256).

    Pass a converter to reuse Docling's loaded models across multiple files.
    Page-specific export errors are raised instead of silently losing markers.
    """
    source = Path(pdf_path)
    target = Path(output_path)

    if not source.is_file():
        raise FileNotFoundError(f"PDF not found: {source}")

    source_hash = sha256_file(source)
    active_converter = converter if converter is not None else DocumentConverter()
    result = active_converter.convert(str(source))
    document = result.document

    page_items = sorted(
        getattr(document, "pages", {}).items(),
        key=lambda item: int(item[0]),
    )
    if not page_items:
        raise RuntimeError(
            f"Docling returned no page metadata for {source}; "
            "cannot safely add page markers."
        )

    fragments: list[str] = []
    empty_pages: list[int] = []

    for page_key, _page in page_items:
        page_number = int(page_key)
        # Deliberately fail loudly if this Docling version does not support page_no.
        page_markdown = document.export_to_markdown(page_no=page_number)

        if not page_markdown.strip():
            empty_pages.append(page_number)
            logger.warning(
                "Page %d of %s exported no text; scanned/image-only content may "
                "require OCR configuration.",
                page_number,
                source.name,
            )
            continue

        fragments.append(
            f"{page_marker(page_number)}\n\n{page_markdown.strip()}"
        )

    if not fragments:
        raise RuntimeError(
            f"Docling exported no text from any page of {source}. "
            "Check whether OCR is configured for scanned pages."
        )

    markdown = "\n\n".join(fragments).strip()
    atomic_write_text(target, markdown)
    logger.info(
        "Parsed %s to %s: %d/%d pages exported; sha256=%s; empty_pages=%s",
        source.name,
        target,
        len(fragments),
        len(page_items),
        source_hash,
        empty_pages,
    )
    return target, source_hash

def parse_pdf_to_markdown(
    pdf_path: str | Path,
    output_path: str | Path,
) -> str:
    """Parse a PDF and return the generated Markdown string."""
    output_path, _document_hash = parse_pdf(
        pdf_path=pdf_path,
        output_path=output_path,
    )
    return output_path.read_text(encoding="utf-8")
