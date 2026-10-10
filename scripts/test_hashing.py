
import hashlib
import logging
from pathlib import Path

from rag_ingest.hashing import sha256_file, hash_and_write

# Enable debug logs
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s: %(message)s"
)

print("\n========== HASHING TEST STARTED ==========")

# Paths relative to the project root
pdf_path = Path("data/samples/HR Policy.pdf")
output_path = Path("out/report.sha256")

print(f"\n[TEST] PDF path: {pdf_path.resolve()}")

# 1. Check that the PDF exists
assert pdf_path.is_file(), f"PDF not found: {pdf_path}"
print("[PASS] PDF exists")

# 2. Calculate the hash using our function
hash1 = sha256_file(pdf_path)
print(f"[RESULT] SHA-256: {hash1}")

# 3. Check hash length and format
assert len(hash1) == 64, "Hash must contain 64 characters"
assert all(c in "0123456789abcdef" for c in hash1), (
    "Hash contains invalid characters"
)
print("[PASS] Hash is 64 hexadecimal characters")

# 4. Hash the same file again
hash2 = sha256_file(pdf_path)

assert hash1 == hash2, "Repeated hashes do not match"
print("[PASS] Repeated hashing produces the same hash")

# 5. Save the hash to a file
saved_hash = hash_and_write(pdf_path, output_path)
print(f"[RESULT] Saved hash to: {output_path.resolve()}")

# 6. Verify the saved hash
stored_hash = output_path.read_text(encoding="utf-8").strip()

assert stored_hash == saved_hash == hash1, (
    "Saved hash does not match calculated hash"
)
print("[PASS] Saved hash matches calculated hash")

# 7. Independently verify using hashlib with 1 MB blocks
print("[TEST] Performing independent SHA-256 verification...")

independent_hasher = hashlib.sha256()

with open(pdf_path, "rb") as file:
    while True:
        block = file.read(1024 * 1024)

        if not block:
            break

        independent_hasher.update(block)

expected_hash = independent_hasher.hexdigest()

assert hash1 == expected_hash, (
    f"Hash mismatch!\n"
    f"Our function: {hash1}\n"
    f"Independent hash: {expected_hash}"
)

print("[PASS] Independent SHA-256 verification matches")

print("\n========== ALL HASHING TESTS PASSED ==========")
