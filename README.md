@'
# RAG Ingestion Pipeline

A Python-based document ingestion pipeline for preparing PDF documents
for Retrieval-Augmented Generation (RAG) applications.

## Current Features

- SHA-256 document hashing
- PDF-to-Markdown parsing using Docling
- Markdown cleanup and heading-aware chunking
- Table-aware chunk splitting with repeated headers
- Page and section metadata
- Automated tests using pytest

## Project Structure

- `src/rag_ingest/` — Core ingestion modules
- `scripts/` — Local execution scripts
- `tests/` — Automated tests
- `data/samples/` — Local sample documents (not committed)
- `out/` — Generated output (not committed)

## Local Setup

Create and activate a virtual environment:

```bash
python -m venv .venv