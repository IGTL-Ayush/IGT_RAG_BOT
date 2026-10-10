
import logging
from pathlib import Path

from rag_ingest.chunking import chunk_markdown

logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s: %(message)s",
)

print("\n========== CHUNKING TEST STARTED ==========")

markdown_path = Path("out/HR Policy.md")

assert markdown_path.is_file(), f"Markdown not found: {markdown_path}"

markdown_text = markdown_path.read_text(encoding="utf-8")

chunks = chunk_markdown(
    markdown_text,
    chunk_size=1000,
    chunk_overlap=200,
    source=markdown_path.name,
)

assert chunks, "No chunks were generated"

print(f"\n[PASS] Chunks generated: {len(chunks)}")

for index, chunk in enumerate(chunks[:5]):
    print(f"\n--- CHUNK {index} ---")
    print(f"Metadata: {chunk['metadata']}")
    print(f"Characters: {len(chunk['text'])}")
    print(chunk["text"][:500])

print("\n========== CHUNKING TEST PASSED ==========")
