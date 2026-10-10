"""Manual smoke test for the local HR PDF Markdown output; not collected by pytest."""

import logging
from pathlib import Path

from rag_ingest.chunking import chunk_markdown
from rag_ingest.hashing import sha256_file

logging.basicConfig(level=logging.INFO)
ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_PATH = ROOT / "out" / "HR Policy.md"
PDF_PATH = ROOT / "data" / "samples" / "HR Policy.pdf"


def main() -> None:
    if not MARKDOWN_PATH.is_file():
        raise FileNotFoundError(f"{MARKDOWN_PATH} is missing; parse the PDF first.")

    markdown = MARKDOWN_PATH.read_text(encoding="utf-8")
    document_hash = sha256_file(PDF_PATH) if PDF_PATH.is_file() else None
    chunks = chunk_markdown(
        markdown,
        chunk_size=1000,
        chunk_overlap=200,
        source=MARKDOWN_PATH.name,
        document_hash=document_hash,
    )

    print(f"Total chunks: {len(chunks)}")
    start = max(0, len(chunks) // 2 - 5)
    end = min(len(chunks), start + 15)
    for index in range(start, end):
        chunk = chunks[index]
        print(f"\n--- Chunk {index} ---")
        print("Metadata:", chunk["metadata"])
        print(chunk["text"][:1000])


if __name__ == "__main__":
    main()
