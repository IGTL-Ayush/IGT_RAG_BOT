
import logging
from pathlib import Path

from rag_ingest.parsing import parse_pdf_to_markdown

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)

print("\n========== PDF PARSING TEST STARTED ==========")

pdf_path = Path("data/samples/HR Policy.pdf")
output_path = Path("out/HR Policy.md")

print(f"[TEST] Input PDF: {pdf_path.resolve()}")

markdown = parse_pdf_to_markdown(
    pdf_path=pdf_path,
    output_path=output_path,
)

assert markdown.strip(), "Parsing returned empty Markdown"
assert output_path.is_file(), "Markdown output file was not created"

saved_markdown = output_path.read_text(encoding="utf-8")
assert saved_markdown.strip(), "Saved Markdown is empty"

print(f"[PASS] Markdown generated: {len(markdown)} characters")
print(f"[PASS] Markdown saved to: {output_path.resolve()}")

print("\n[PREVIEW]")
print(markdown[:2000])

print("\n========== PDF PARSING TEST PASSED ==========")
