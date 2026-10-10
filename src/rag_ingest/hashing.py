"""Stable file hashing and atomic text output helpers."""

import hashlib
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 hex digest for a file."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as file_obj:
        for block in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write_text(
    path: str | Path,
    content: str,
    encoding: str = "utf-8",
) -> None:
    """Atomically write text, using readable permissions for the final file."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    final_mode = (target.stat().st_mode & 0o777) if target.exists() else 0o644

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=encoding,
            newline="",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())

        os.chmod(temp_path, final_mode)
        os.replace(temp_path, target)
        temp_path = None
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not remove temporary file %s", temp_path)

def hash_and_write(
    input_path: str | Path,
    output_path: str | Path,
) -> str:
    """Calculate a file's SHA-256 hash and save it to an output file."""
    file_hash = sha256_file(input_path)
    atomic_write_text(output_path, file_hash + "\n")
    logger.info("SHA-256 hash saved to %s", output_path)
    return file_hash
