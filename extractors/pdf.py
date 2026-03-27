"""
PDF extractor — chapter detection cascade:
  1. PDF bookmarks/outline (most reliable)
  2. Font-size heading detection
  3. Text pattern matching (Chapter N, Part I, etc.)
  4. Page-split fallback
"""

import re
import logging
from collections import Counter
from pathlib import Path
from typing import Optional

import fitz          # PyMuPDF
import pdfplumber

from extractors.base import BaseExtractor
from models import Book, Chapter
from text_processor import clean_text

log = logging.getLogger(__name__)

# Patterns that indicate a chapter heading
CHAPTER_PATTERNS = [
    re.compile(r"^chapter\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten|"
               r"eleven|twelve|[ivxlcdm]+)\b", re.IGNORECASE),
    re.compile(r"^part\s+(\d+|one|two|three|four|five|[ivxlcdm]+)\b", re.IGNORECASE),
    re.compile(r"^(prologue|epilogue|introduction|preface|afterword|foreword"
               r"|acknowledgements?|conclusion|appendix)\b", re.IGNORECASE),
]


class PDFExtractor(BaseExtractor):
    def extract(self, path: Path) -> Book:
        cfg = self.config.get("chapter_detection", {})
        methods = cfg.get("methods", ["bookmarks", "font_size", "pattern", "page_split"])

        doc = fitz.open(str(path))
        title, author = _get_metadata(doc)

        pages_text = _extract_pages(doc)
        log.info("Extracted %d pages from %s", len(pages_text), path.name)

        chapters = None
        for method in methods:
            log.info("Trying chapter detection: %s", method)
            if method == "bookmarks":
                chapters = _detect_by_bookmarks(doc, pages_text)
            elif method == "font_size":
                chapters = _detect_by_font_size(path, pages_text)
            elif method == "pattern":
                chapters = _detect_by_pattern(pages_text)
            elif method == "page_split":
                n = cfg.get("page_split_size", 20)
                chapters = _detect_by_page_split(pages_text, n)

            if chapters:
                log.info("Chapter detection '%s' found %d chapters", method, len(chapters))
                break

        if not chapters:
            log.warning("No chapters detected — treating whole book as one chapter")
            full_text = "\n\n".join(pages_text)
            chapters = [Chapter(index=1, title="Book", text=clean_text(full_text))]

        doc.close()
        return Book(title=title, author=author, source_path=path, chapters=chapters)


# ── Metadata ──────────────────────────────────────────────────────────────────

def _get_metadata(doc: fitz.Document) -> tuple[str, str]:
    meta = doc.metadata or {}
    title = meta.get("title", "").strip() or "Unknown Title"
    author = meta.get("author", "").strip() or "Unknown Author"
    return title, author


# ── Page text extraction ───────────────────────────────────────────────────────

def _extract_pages(doc: fitz.Document) -> list[str]:
    pages = []
    for page in doc:
        text = page.get_text("text")
        pages.append(text)
    return pages


# ── Method 1: PDF bookmarks ───────────────────────────────────────────────────

def _detect_by_bookmarks(doc: fitz.Document, pages_text: list[str]) -> list[Chapter] | None:
    toc = doc.get_toc()  # [[level, title, page], ...]
    if not toc:
        return None

    # Only keep top-level entries (level == 1) that look like chapters
    top = [(title, page - 1) for level, title, page in toc if level == 1]
    if len(top) < 2:
        return None

    chapters = []
    for i, (title, start_page) in enumerate(top):
        end_page = top[i + 1][1] if i + 1 < len(top) else len(pages_text)
        text = "\n\n".join(pages_text[start_page:end_page])
        chapters.append(Chapter(
            index=i + 1,
            title=title.strip(),
            text=clean_text(text),
            page_start=start_page + 1,
            page_end=end_page,
        ))
    return chapters or None


# ── Method 2: Font-size heading detection ─────────────────────────────────────

def _detect_by_font_size(path: Path, pages_text: list[str]) -> list[Chapter] | None:
    try:
        heading_pages = _find_heading_pages_by_font(path)
    except Exception as e:
        log.warning("Font-size detection failed: %s", e)
        return None

    if len(heading_pages) < 2:
        return None

    chapters = []
    for i, (page_idx, heading) in enumerate(heading_pages):
        end_page = heading_pages[i + 1][0] if i + 1 < len(heading_pages) else len(pages_text)
        text = "\n\n".join(pages_text[page_idx:end_page])
        chapters.append(Chapter(
            index=i + 1,
            title=heading,
            text=clean_text(text),
            page_start=page_idx + 1,
            page_end=end_page,
        ))
    return chapters or None


def _find_heading_pages_by_font(path: Path) -> list[tuple[int, str]]:
    """Return [(page_idx, heading_text)] for pages that start with a large heading."""
    font_sizes = []

    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            chars = page.chars
            if chars:
                sizes = [c["size"] for c in chars if c.get("size")]
                font_sizes.extend(sizes)

    if not font_sizes:
        return []

    # Body text is near the mode; headings are significantly larger
    size_counts = Counter(round(s) for s in font_sizes)
    body_size = size_counts.most_common(1)[0][0]
    heading_threshold = body_size * 1.4  # 40% larger than body = heading

    headings = []
    with pdfplumber.open(str(path)) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            chars = page.chars
            if not chars:
                continue
            # Check if the first substantial text block on this page is a heading
            top_chars = [c for c in chars if c.get("size", 0) >= heading_threshold]
            if not top_chars:
                continue
            # Get the text of the heading block (first line of large text)
            top_chars.sort(key=lambda c: (c["top"], c["x0"]))
            first_y = top_chars[0]["top"]
            heading_chars = [c for c in top_chars if abs(c["top"] - first_y) < 5]
            heading_text = "".join(c["text"] for c in heading_chars).strip()
            if heading_text and len(heading_text) > 2:
                headings.append((page_idx, heading_text))

    return headings


# ── Method 3: Text pattern matching ───────────────────────────────────────────

def _detect_by_pattern(pages_text: list[str]) -> list[Chapter] | None:
    split_pages: list[tuple[int, str]] = []  # (page_idx, heading)

    for page_idx, text in enumerate(pages_text):
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for line in lines[:5]:  # Check first 5 lines of each page
            for pat in CHAPTER_PATTERNS:
                if pat.match(line):
                    split_pages.append((page_idx, line))
                    break
            else:
                continue
            break

    if len(split_pages) < 2:
        return None

    chapters = []
    for i, (page_idx, heading) in enumerate(split_pages):
        end_page = split_pages[i + 1][0] if i + 1 < len(split_pages) else len(pages_text)
        text = "\n\n".join(pages_text[page_idx:end_page])
        chapters.append(Chapter(
            index=i + 1,
            title=heading,
            text=clean_text(text),
            page_start=page_idx + 1,
            page_end=end_page,
        ))
    return chapters or None


# ── Method 4: Page-split fallback ─────────────────────────────────────────────

def _detect_by_page_split(pages_text: list[str], pages_per_chunk: int) -> list[Chapter]:
    chunks = []
    for i in range(0, len(pages_text), pages_per_chunk):
        chunk = pages_text[i:i + pages_per_chunk]
        text = "\n\n".join(chunk)
        idx = i // pages_per_chunk + 1
        chunks.append(Chapter(
            index=idx,
            title=f"Part {idx}",
            text=clean_text(text),
            page_start=i + 1,
            page_end=min(i + pages_per_chunk, len(pages_text)),
        ))
    return chunks
