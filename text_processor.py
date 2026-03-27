"""
Text cleaning pipeline — runs on raw extracted text before it goes to TTS.
"""

import re


def clean_text(text: str) -> str:
    text = _fix_hyphenation(text)
    text = _normalize_quotes(text)
    text = _remove_page_artifacts(text)
    text = _collapse_whitespace(text)
    return text.strip()


def _fix_hyphenation(text: str) -> str:
    """Re-join words split across lines by hyphenation."""
    # "some- \nword" → "someword"
    text = re.sub(r"-\s*\n\s*", "", text)
    return text


def _normalize_quotes(text: str) -> str:
    """Curly/smart quotes → straight quotes (TTS handles these better)."""
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2013", "-").replace("\u2014", " -- ")
    text = text.replace("\u2026", "...")
    return text


def _remove_page_artifacts(text: str) -> str:
    """Strip common header/footer noise: page numbers, running titles."""
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Skip bare page numbers
        if re.fullmatch(r"\d{1,4}", stripped):
            continue
        # Skip very short lines that are likely headers/footers (< 4 chars, not punctuation)
        if len(stripped) < 4 and not re.search(r"[.!?]", stripped):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _collapse_whitespace(text: str) -> str:
    """Collapse multiple blank lines; normalize spacing."""
    # Max two consecutive newlines (paragraph break)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Trailing spaces on lines
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text


def chunk_for_tts(text: str, max_chars: int = 1000) -> list[str]:
    """
    Split text into chunks of at most max_chars, breaking only at sentence
    boundaries so TTS doesn't clip mid-sentence.
    """
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= max_chars:
            current = (current + " " + sentence).strip()
        else:
            if current:
                chunks.append(current)
            # If a single sentence exceeds max_chars, split at clause boundaries
            if len(sentence) > max_chars:
                parts = re.split(r"(?<=[,;:])\s+", sentence)
                sub = ""
                for part in parts:
                    if len(sub) + len(part) + 1 <= max_chars:
                        sub = (sub + " " + part).strip()
                    else:
                        if sub:
                            chunks.append(sub)
                        sub = part
                if sub:
                    current = sub
                else:
                    current = ""
            else:
                current = sentence

    if current:
        chunks.append(current)

    # Hard-split any chunk that still exceeds max_chars (no sentence/clause breaks found)
    final = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            final.append(chunk)
        else:
            for i in range(0, len(chunk), max_chars):
                part = chunk[i:i + max_chars].strip()
                if part:
                    final.append(part)

    return [c for c in final if c.strip()]
