import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from text_processor import clean_text, chunk_for_tts


def test_fix_hyphenation():
    assert "someword" in clean_text("some-\nword")
    assert "well-known" in clean_text("well-known")  # intentional hyphen preserved


def test_normalize_quotes():
    result = clean_text("\u201cHello\u201d said he")
    assert '"Hello"' in result


def test_remove_page_numbers():
    result = clean_text("Some text\n42\nMore text")
    assert "42" not in result
    assert "Some text" in result
    assert "More text" in result


def test_chunk_respects_sentences():
    text = "First sentence. Second sentence. Third sentence."
    chunks = chunk_for_tts(text, max_chars=30)
    # Each chunk should end with punctuation (no mid-sentence splits)
    for chunk in chunks:
        assert chunk.strip()[-1] in ".!?", f"Chunk doesn't end cleanly: {chunk!r}"


def test_chunk_fits_within_limit():
    text = "A " * 500  # 1000 chars
    chunks = chunk_for_tts(text, max_chars=100)
    for chunk in chunks:
        assert len(chunk) <= 110  # small tolerance for edge cases


def test_chunk_no_empty():
    chunks = chunk_for_tts("Hello world.", max_chars=1000)
    assert all(c.strip() for c in chunks)
