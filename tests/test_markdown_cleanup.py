from rag_ingest.chunking import (
    chunk_markdown,
    clean_markdown,
    split_markdown_by_headers,
)
from rag_ingest.markers import PAGE_MARKER_PATTERN


def test_merges_wrapped_paragraph_lines():
    assert clean_markdown(
        "Intensity Global is\ncommitted to providing equal opportunities."
    ) == "Intensity Global is committed to providing equal opportunities."


def test_preserves_headings_lists_and_tables():
    assert clean_markdown("## Employee Terms and Conditions") == "## Employee Terms and Conditions"
    assert clean_markdown("- First item\n- Second item") == "- First item\n- Second item"
    table = "| Name | Role |\n|---|---|\n| Alex | Engineer |"
    assert clean_markdown(table) == table


def test_repairs_malformed_heading_and_continuation():
    text = (
        "## 2) Equal Employment Opportunity (EEO): - Intensity Global is\n\n"
        "committed to providing equal opportunities."
    )
    assert clean_markdown(text) == (
        "## 2) Equal Employment Opportunity (EEO):\n\n"
        "Intensity Global is committed to providing equal opportunities."
    )


def test_does_not_corrupt_valid_hyphenated_heading():
    for text in ("## Annual Leave - Policy", "## Section 4 - Leave Rules"):
        assert clean_markdown(text) == text


def test_heading_after_malformed_heading_is_preserved():
    text = "## Foo: - Bar baz\n\n## Next\n\nNext section content."
    cleaned = clean_markdown(text)
    assert "## Next" in cleaned
    assert "Next section content." in cleaned


def test_fenced_code_preserves_indentation_and_blank_lines():
    text = "```python\ndef example():\n    print('hello')\n\n    return True\n```"
    assert clean_markdown(text) == text


def test_page_markers_are_preserved_during_cleanup():
    cleaned = clean_markdown("<!-- page_number: 2 -->\n\nPage two content.")
    assert PAGE_MARKER_PATTERN.search(cleaned)


def test_empty_input_and_validation():
    assert clean_markdown("") == ""
    assert chunk_markdown("") == []
    try:
        chunk_markdown("text", chunk_size=0)
    except ValueError:
        pass
    else:
        raise AssertionError("chunk_size=0 must raise ValueError")

    try:
        chunk_markdown("text", chunk_size=10, chunk_overlap=10)
    except ValueError:
        pass
    else:
        raise AssertionError("chunk_overlap >= chunk_size must raise ValueError")


def test_page_boundary_keeps_sentence_and_page_metadata():
    text = (
        "<!-- page_number: 1 -->\n\n"
        "## Leave Policy\n\n"
        "Employees must submit the form\n"
        "<!-- page_number: 2 -->\n"
        "before the deadline."
    )
    cleaned = clean_markdown(text)
    assert "Employees must submit the form before the deadline." in cleaned
    sections = split_markdown_by_headers(cleaned)
    assert len(sections) == 1
    assert sections[0]["metadata"].get("h2") == "Leave Policy"
    assert sections[0]["metadata"].get("pages") == [1, 2]


def test_stranded_heading_is_attributed_to_both_pages():
    text = (
        "<!-- page_number: 1 -->\n\n"
        "## Leave Policy\n\n"
        "<!-- page_number: 2 -->\n\n"
        "Employees must submit the form."
    )
    sections = split_markdown_by_headers(clean_markdown(text))
    assert len(sections) == 1
    assert sections[0]["metadata"].get("h2") == "Leave Policy"
    assert sections[0]["metadata"].get("pages") == [1, 2]


def test_h4_content_is_kept():
    chunks = chunk_markdown("## A\n\n#### Sub only")
    assert chunks
    assert any("#### Sub only" in chunk["text"] for chunk in chunks)


def test_duplicate_headings_stay_separate():
    text = (
        "<!-- page_number: 1 -->\n\n## Leave\n\nFirst policy.\n\n"
        "<!-- page_number: 2 -->\n\n## Leave\n\nSecond policy."
    )
    sections = split_markdown_by_headers(clean_markdown(text))
    assert len(sections) == 2
    assert sections[0]["text"] != sections[1]["text"]
    assert sections[0]["metadata"]["section_id"] != sections[1]["metadata"]["section_id"]


def test_breadcrumb_is_not_duplicated_and_indexes_are_unique():
    chunks = chunk_markdown(
        "## A\n\n" + ("Some useful paragraph. " * 100),
        chunk_size=100,
        chunk_overlap=10,
        source="sample.md",
        document_hash="abc123",
    )
    assert len(chunks) > 1
    assert [c["metadata"]["chunk_index"] for c in chunks] == list(range(len(chunks)))
    for chunk in chunks:
        assert chunk["text"].count("Section: A") == 1
        assert chunk["metadata"]["document_hash"] == "abc123"
        assert chunk["metadata"]["source"] == "sample.md"


def test_heading_then_table_does_not_emit_heading_only_chunk():
    chunks = chunk_markdown(
        "## Details\n\n| Name | Role |\n|---|---|\n| Alex | Engineer |"
    )
    assert chunks
    assert all("Section: Details" in chunk["text"] for chunk in chunks)
    assert all("| Name | Role |" in chunk["text"] for chunk in chunks)


def test_table_split_repeats_header():
    rows = "\n".join(f"| Person {i} | Engineer |" for i in range(20))
    table = f"| Name | Role |\n|---|---|\n{rows}"
    chunks = chunk_markdown("## Details\n\n" + table, chunk_size=100, chunk_overlap=10)
    table_chunks = [c["text"] for c in chunks if "| Name | Role |" in c["text"]]
    assert len(table_chunks) > 1
    assert all("|---|---|" in chunk for chunk in table_chunks)


def test_fence_containing_heading_and_table_syntax_stays_intact():
    fence = "```text\n## not a heading\n| not | a table |\n```\n"
    chunks = chunk_markdown("## Code\n\n" + fence)
    assert any(fence.strip() in chunk["text"] for chunk in chunks)


def test_table_followed_by_paragraph_is_preserved():
    text = (
        "## Details\n\n| Name | Role |\n|---|---|\n| Alex | Engineer |\n\n"
        "This paragraph follows the table."
    )
    chunks = chunk_markdown(text, source="sample.md")
    combined = "\n".join(chunk["text"] for chunk in chunks)
    assert "| Name | Role |" in combined
    assert "This paragraph follows the table." in combined
    assert all(chunk["metadata"].get("source") == "sample.md" for chunk in chunks)
    assert all(chunk["text"].strip() for chunk in chunks)
