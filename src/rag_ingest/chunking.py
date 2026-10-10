from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, TypedDict

from langchain_text_splitters import RecursiveCharacterTextSplitter


PAGE_MARKER_PATTERN = re.compile(
    r"<!--\s*page_number:\s*(\d+)\s*-->",
    re.IGNORECASE,
)
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
FENCE_PATTERN = re.compile(r"^\s{0,3}(`{3,}|~{3,})")


class Chunk(TypedDict):
    text: str
    metadata: dict[str, Any]


def _heading_breadcrumb(metadata: dict[str, Any]) -> str:
    return " > ".join(
        str(metadata[key])
        for key in ("h1", "h2", "h3", "h4", "h5", "h6")
        if metadata.get(key)
    )


def clean_markdown(markdown_text: str) -> str:
    """Clean prose while preserving headings, page markers, tables and code."""
    if not markdown_text.strip():
        return ""

    lines = markdown_text.splitlines()
    output: list[str] = []
    paragraph: list[str] = []
    pending_pages: list[str] = []
    fence_char: str | None = None
    fence_length = 0

    def flush_paragraph() -> None:
        if paragraph:
            output.append(" ".join(part.strip() for part in paragraph))
            paragraph.clear()

    def flush_pages() -> None:
        if pending_pages:
            output.extend(pending_pages)
            pending_pages.clear()

    def is_structural(line: str) -> bool:
        stripped = line.strip()
        return bool(
            HEADING_PATTERN.match(stripped)
            or re.match(r"^(?:[-*+]\s+|\d+[.)]\s+)", stripped)
            or stripped.startswith((">", "|", "<!--"))
        )

    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Preserve all fenced-code lines without modifying them.
        if fence_char is not None:
            output.append(line)
            close = re.match(r"^\s{0,3}(`+|~+)\s*$", line)

            if (
                close
                and close.group(1)[0] == fence_char
                and len(close.group(1)) >= fence_length
            ):
                fence_char = None
                fence_length = 0

            i += 1
            continue

        opening = FENCE_PATTERN.match(line)
        if opening:
            flush_paragraph()
            flush_pages()
            output.append(line)
            fence_char = opening.group(1)[0]
            fence_length = len(opening.group(1))
            i += 1
            continue

        # Remove image placeholders outside code fences.
        if re.fullmatch(r"<!--\s*image\s*-->", stripped, re.IGNORECASE):
            i += 1
            continue

        page_match = PAGE_MARKER_PATTERN.fullmatch(stripped)
        if page_match:
            marker = stripped
            previous = paragraph[-1] if paragraph else (
                output[-1] if output else ""
            )

            # Join a sentence split across a PDF page boundary.
            if previous and not previous.endswith((".", "!", "?", ":")):
                i += 1

                while i < len(lines) and not lines[i].strip():
                    i += 1

                if i < len(lines):
                    continuation = lines[i].strip()

                    if (
                        continuation
                        and not is_structural(continuation)
                        and not FENCE_PATTERN.match(continuation)
                    ):
                        if paragraph:
                            paragraph.append(continuation)
                        elif output:
                            output[-1] = (
                                output[-1].rstrip() + " " + continuation
                            )
                        else:
                            paragraph.append(continuation)

                        pending_pages.append(marker)
                        i += 1
                        continue

            flush_paragraph()
            flush_pages()
            output.append(marker)
            i += 1
            continue

        # Repair malformed headings such as:
        # ## Equal Employment Opportunity: - Intensity Global is
        # committed to providing equal opportunities.
        malformed = re.match(
            r"^(#{1,6}\s+.+?:)\s+-\s+(.+?)\s*$",
            stripped,
        )

        if malformed:
            flush_paragraph()
            flush_pages()

            output.append(malformed.group(1).rstrip())
            output.append("")
            paragraph.append(malformed.group(2).strip())
            i += 1

            while i < len(lines) and not lines[i].strip():
                i += 1

            if i < len(lines):
                continuation = lines[i].strip()

                if (
                    continuation
                    and not is_structural(continuation)
                    and not FENCE_PATTERN.match(continuation)
                ):
                    paragraph.append(continuation)
                    i += 1

            continue

        if not stripped:
            flush_paragraph()
            flush_pages()

            if output and output[-1] != "":
                output.append("")

            i += 1
            continue

        if is_structural(stripped):
            flush_paragraph()
            flush_pages()
            output.append(stripped)
        else:
            paragraph.append(stripped)

        i += 1

    flush_paragraph()
    flush_pages()

    return re.sub(r"\n{3,}", "\n\n", "\n".join(output)).strip()


def extract_page_numbers(text: str) -> tuple[str, list[int]]:
    """Remove page markers from text and return their unique page numbers."""
    pages = [
        int(match.group(1))
        for match in PAGE_MARKER_PATTERN.finditer(text)
    ]
    cleaned = PAGE_MARKER_PATTERN.sub("", text).strip()
    return cleaned, list(dict.fromkeys(pages))


def split_markdown_by_headers(markdown_text: str) -> list[Chunk]:
    """Split by headings while retaining heading context and page metadata."""
    if not markdown_text.strip():
        return []

    sections: list[Chunk] = []
    headings: dict[str, str] = {}
    current_lines: list[str] = []
    current_pages: list[int] = []
    section_counter = 0
    fence_char: str | None = None
    fence_length = 0

    def has_body(lines: list[str]) -> bool:
        return any(
            line.strip()
            and not HEADING_PATTERN.match(line.strip())
            and not PAGE_MARKER_PATTERN.fullmatch(line.strip())
            for line in lines
        )

    def flush() -> None:
        nonlocal section_counter

        content = "\n".join(current_lines).strip()

        if content:
            metadata: dict[str, Any] = dict(headings)
            metadata["pages"] = sorted(set(current_pages))
            metadata["section_id"] = f"section-{section_counter:05d}"

            sections.append({
                "text": content,
                "metadata": metadata,
            })
            section_counter += 1

        current_lines.clear()
        current_pages.clear()

    for line in markdown_text.splitlines():
        stripped = line.strip()
        fence = FENCE_PATTERN.match(line)

        if fence_char is not None:
            current_lines.append(line)
            close = re.match(r"^\s{0,3}(`+|~+)\s*$", line)

            if (
                close
                and close.group(1)[0] == fence_char
                and len(close.group(1)) >= fence_length
            ):
                fence_char = None
                fence_length = 0

            continue

        if fence:
            current_lines.append(line)
            fence_char = fence.group(1)[0]
            fence_length = len(fence.group(1))
            continue

        page_match = PAGE_MARKER_PATTERN.fullmatch(stripped)
        if page_match:
            page = int(page_match.group(1))
            if page not in current_pages:
                current_pages.append(page)
            continue

        heading = HEADING_PATTERN.match(stripped)

        if heading:
            # Don't split a heading away from a body that follows it.
            if has_body(current_lines):
                flush()

            level = len(heading.group(1))

            for deeper in range(level, 7):
                headings.pop(f"h{deeper}", None)

            headings[f"h{level}"] = heading.group(2).strip()
            current_lines.append(stripped)
        else:
            current_lines.append(line)

    flush()

    # Merge a stranded heading-only section with its following body if
    # the heading context is identical.
    merged: list[Chunk] = []

    for section in sections:
        section_text = section["text"]
        metadata = section["metadata"]

        body_lines = [
            line
            for line in section_text.splitlines()
            if line.strip()
            and not HEADING_PATTERN.match(line.strip())
        ]

        if (
            merged
            and not body_lines
            and all(
                metadata.get(key) == merged[-1]["metadata"].get(key)
                for key in ("h1", "h2", "h3", "h4", "h5", "h6")
            )
        ):
            merged[-1]["text"] += "\n" + section_text
            merged[-1]["metadata"]["pages"] = sorted(
                set(merged[-1]["metadata"].get("pages", []))
                | set(metadata.get("pages", []))
            )
        else:
            merged.append(section)

    return merged


def _split_table(
    lines: list[str],
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """Split a Markdown table and repeat its header and separator."""
    if len(lines) < 3:
        return ["\n".join(lines)]

    header = lines[0]
    separator = lines[1]
    rows = lines[2:]
    prefix = f"{header}\n{separator}"

    parts: list[str] = []
    current_rows: list[str] = []

    for row in rows:
        candidate = prefix + "\n" + "\n".join(current_rows + [row])

        if current_rows and len(candidate) > chunk_size:
            parts.append(prefix + "\n" + "\n".join(current_rows))

            overlap_rows: list[str] = []
            used = 0

            if chunk_overlap > 0:
                for previous in reversed(current_rows):
                    if used + len(previous) + 1 > chunk_overlap:
                        break

                    overlap_rows.insert(0, previous)
                    used += len(previous) + 1

            current_rows = overlap_rows + [row]
        else:
            current_rows.append(row)

    if current_rows:
        parts.append(prefix + "\n" + "\n".join(current_rows))

    return parts


def split_sections_by_size(
    sections: list[Chunk],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    source: str | None = None,
    document_hash: str | None = None,
) -> list[Chunk]:
    """Split sections while preserving metadata, tables, and fenced code."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError(
            "chunk_overlap must be >= 0 and smaller than chunk_size"
        )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        strip_whitespace=True,
        keep_separator=True,
    )

    chunks: list[Chunk] = []

    for section in sections:
        text = section["text"].strip()
        metadata = section["metadata"].copy()
        breadcrumb = _heading_breadcrumb(metadata)

        if source:
            metadata["source"] = source

        if document_hash:
            metadata["document_hash"] = document_hash

        lines = text.splitlines()

        # Detect meaningful content outside headings and page markers.
        has_body = any(
            line.strip()
            and not PAGE_MARKER_PATTERN.fullmatch(line.strip())
            and not HEADING_PATTERN.match(line.strip())
            for line in lines
        )

        # Remove section headings from body chunks, but never interpret
        # heading-like lines inside fenced code as real Markdown headings.
        # If there is no body, retain the heading-only section as content.
        if has_body:
            filtered_lines: list[str] = []
            active_fence: str | None = None
            active_fence_length = 0

            for line in lines:
                stripped = line.strip()
                fence_match = FENCE_PATTERN.match(line)

                if active_fence is not None:
                    filtered_lines.append(line)
                    close = re.match(r"^\s{0,3}(`+|~+)\s*$", line)

                    if (
                        close
                        and close.group(1)[0] == active_fence
                        and len(close.group(1)) >= active_fence_length
                    ):
                        active_fence = None
                        active_fence_length = 0

                    continue

                if fence_match:
                    filtered_lines.append(line)
                    active_fence = fence_match.group(1)[0]
                    active_fence_length = len(fence_match.group(1))
                    continue

                if (
                    HEADING_PATTERN.match(stripped)
                    or PAGE_MARKER_PATTERN.fullmatch(stripped)
                ):
                    continue

                filtered_lines.append(line)

            lines = filtered_lines

        # Important: chunk generation happens regardless of has_body.
        # This preserves sections such as "#### Sub only".
        parts: list[str] = []
        normal_lines: list[str] = []
        table_lines: list[str] = []
        fence_lines: list[str] = []
        active_fence: str | None = None
        active_fence_length = 0

        def flush_normal() -> None:
            if normal_lines:
                content = "\n".join(normal_lines).strip()
                if content:
                    parts.extend(splitter.split_text(content))
                normal_lines.clear()

        def flush_table() -> None:
            if table_lines:
                parts.extend(
                    _split_table(
                        table_lines,
                        chunk_size,
                        chunk_overlap,
                    )
                )
                table_lines.clear()

        for line in lines:
            fence_match = FENCE_PATTERN.match(line)

            if active_fence is not None:
                fence_lines.append(line)
                close = re.match(r"^\s{0,3}(`+|~+)\s*$", line)

                if (
                    close
                    and close.group(1)[0] == active_fence
                    and len(close.group(1)) >= active_fence_length
                ):
                    flush_normal()
                    flush_table()

                    # Keep the complete fenced block together.
                    parts.append("\n".join(fence_lines))
                    fence_lines.clear()
                    active_fence = None
                    active_fence_length = 0

                continue

            if fence_match:
                flush_normal()
                flush_table()
                active_fence = fence_match.group(1)[0]
                active_fence_length = len(fence_match.group(1))
                fence_lines.append(line)
                continue

            if line.strip().startswith("|"):
                flush_normal()
                table_lines.append(line)
            else:
                flush_table()
                normal_lines.append(line)

        # Keep unclosed fences instead of dropping their contents.
        if fence_lines:
            flush_normal()
            flush_table()
            parts.append("\n".join(fence_lines))
            fence_lines.clear()

        flush_normal()
        flush_table()

        # Fallback for any non-empty section that produced no parts.
        if not parts and text:
            parts = [text]

        for part in parts:
            part = part.strip()
            if not part:
                continue

            label = f"Section: {breadcrumb}" if breadcrumb else ""

            if label and label not in part:
                part = f"{label}\n\n{part}"

            part, pages_from_text = extract_page_numbers(part)

            chunk_metadata = metadata.copy()
            pages = list(chunk_metadata.get("pages", []))
            pages.extend(pages_from_text)

            if pages:
                chunk_metadata["pages"] = sorted(set(pages))

            chunk_metadata["chunk_index"] = len(chunks)
            chunk_metadata["chunk_id"] = f"chunk-{len(chunks):05d}"

            chunks.append({
                "text": part,
                "metadata": chunk_metadata,
            })

    return chunks


def chunk_markdown(
    markdown_text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    source: str | Path | None = None,
    document_hash: str | None = None,
) -> list[Chunk]:
    """Clean, split and chunk Markdown for RAG ingestion."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError(
            "chunk_overlap must be >= 0 and smaller than chunk_size"
        )

    cleaned = clean_markdown(markdown_text)
    sections = split_markdown_by_headers(cleaned)

    if document_hash is None:
        document_hash = hashlib.sha256(
            markdown_text.encode("utf-8")
        ).hexdigest()

    source_name = Path(source).name if source is not None else None

    return split_sections_by_size(
        sections=sections,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        source=source_name,
        document_hash=document_hash,
    )