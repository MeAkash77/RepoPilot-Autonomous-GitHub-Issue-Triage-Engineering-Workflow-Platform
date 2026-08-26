from repopilot_retrieval.chunkers import (
    CHARS_PER_TOKEN,
    ISSUE_MAX_TOKENS,
    chunk_code,
    chunk_issue,
    chunk_markdown,
)


def test_small_issue_single_chunk_with_header() -> None:
    chunks = chunk_issue(123, "Login fails", "Steps to reproduce...", state="open")
    assert len(chunks) == 1
    assert chunks[0].content.startswith("[ISSUE #123 | open] Title: Login fails")
    assert "Steps to reproduce" in chunks[0].content


def test_large_issue_split_with_overlap_and_header_on_every_chunk() -> None:
    body = " ".join(f"word{i}" for i in range(3000))
    chunks = chunk_issue(7, "Big issue", body)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.content.startswith("[ISSUE #7] Title: Big issue")
    # Overlap: consecutive chunks share some content.
    tail = chunks[0].content[-100:]
    shared = set(tail.split()) & set(chunks[1].content.split())
    assert shared


def test_markdown_splits_on_headings() -> None:
    text = "# Intro\nshort intro\n\n## Usage\n" + "usage line\n" * 400 + "\n## FAQ\nanswers"
    chunks = chunk_markdown("docs/guide.md", text)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.content.startswith("[DOC docs/guide.md]")


def test_markdown_small_doc_single_chunk() -> None:
    chunks = chunk_markdown("README.md", "# Title\nhello")
    assert len(chunks) == 1


def test_code_small_file_single_chunk() -> None:
    chunks = chunk_code("src/x.py", "def f():\n    return 1\n")
    assert len(chunks) == 1
    assert chunks[0].content.startswith("[CODE src/x.py]")


def test_code_large_file_splits_at_definitions() -> None:
    functions = "\n\n".join(f"def func_{i}():\n" + "    x = 1\n" * 40 for i in range(20))
    chunks = chunk_code("src/big.py", functions)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.content.startswith("[CODE src/big.py]")
        # No chunk wildly exceeds the cap (header + tolerance).
        assert len(chunk.content) < 500 * CHARS_PER_TOKEN


def test_chunk_indices_sequential() -> None:
    body = " ".join(f"w{i}" for i in range(ISSUE_MAX_TOKENS * 3))
    chunks = chunk_issue(1, "t", body)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
