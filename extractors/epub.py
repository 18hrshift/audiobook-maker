"""
EPUB extractor — chapters are separate HTML files in the EPUB zip.
Also handles MOBI/AZW3 by converting via Calibre's ebook-convert CLI first.
"""

import logging
import re
import subprocess
import tempfile
from pathlib import Path

from bs4 import BeautifulSoup
import ebooklib
from ebooklib import epub

from extractors.base import BaseExtractor
from models import Book, Chapter
from text_processor import clean_text

log = logging.getLogger(__name__)

# HTML tags whose content should become paragraph breaks
BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "br", "li"}


class EPUBExtractor(BaseExtractor):
    def extract(self, path: Path) -> Book:
        # Convert MOBI/AZW3 to EPUB first
        if path.suffix.lower() in (".mobi", ".azw3", ".azw"):
            path = _convert_to_epub(path)

        book_obj = epub.read_epub(str(path))
        title = _get_meta(book_obj, "title") or path.stem
        author = _get_meta(book_obj, "creator") or "Unknown Author"

        chapters = _extract_chapters(book_obj)

        if not chapters:
            log.warning("No chapters extracted from EPUB — treating as single chapter")
            all_text = " ".join(
                _html_to_text(item.get_content())
                for item in book_obj.get_items_of_type(ebooklib.ITEM_DOCUMENT)
            )
            chapters = [Chapter(index=1, title=title, text=clean_text(all_text))]

        return Book(title=title, author=author, source_path=path, chapters=chapters)


# ── EPUB chapter extraction ───────────────────────────────────────────────────

def _extract_chapters(book_obj: epub.EpubBook) -> list[Chapter]:
    """
    Use the EPUB spine order (reading order) to get chapters.
    Each spine item that contains substantial text becomes a chapter.
    The title comes from the <h1>/<h2> heading or the NCX/TOC entry.
    """
    # Build a title map from the TOC
    toc_titles = _build_toc_title_map(book_obj)

    chapters = []
    idx = 1

    for item in book_obj.spine:
        item_id = item[0] if isinstance(item, tuple) else item
        doc = book_obj.get_item_with_id(item_id)
        if doc is None or doc.get_type() != ebooklib.ITEM_DOCUMENT:
            continue

        content = doc.get_content()
        text = _html_to_text(content)
        text = clean_text(text)

        if len(text.split()) < 50:  # Skip very short items (nav, cover, etc.)
            continue

        # Get chapter title: TOC lookup → heading in HTML → fallback
        title = (
            toc_titles.get(doc.get_name())
            or _extract_heading(content)
            or f"Chapter {idx}"
        )

        chapters.append(Chapter(index=idx, title=title, text=text))
        idx += 1

    return chapters


def _build_toc_title_map(book_obj: epub.EpubBook) -> dict[str, str]:
    """Map EPUB document hrefs → chapter titles from the TOC."""
    mapping = {}

    def walk(items):
        for item in items:
            if isinstance(item, epub.Link):
                # href may have fragment: "chapter01.xhtml#section1"
                href = item.href.split("#")[0]
                mapping[href] = item.title
            elif isinstance(item, tuple):
                walk(item)
            elif isinstance(item, list):
                walk(item)

    walk(book_obj.toc)
    return mapping


def _extract_heading(html_bytes: bytes) -> str | None:
    """Pull the first h1/h2/h3 from the HTML as chapter title."""
    soup = BeautifulSoup(html_bytes, "lxml")
    for tag in ("h1", "h2", "h3"):
        el = soup.find(tag)
        if el:
            text = el.get_text(strip=True)
            if text:
                return text
    return None


def _html_to_text(html_bytes: bytes) -> str:
    """Convert HTML to plain text, preserving paragraph breaks."""
    soup = BeautifulSoup(html_bytes, "lxml")

    # Remove script/style
    for tag in soup(["script", "style", "head"]):
        tag.decompose()

    lines = []
    for el in soup.body.descendants if soup.body else soup.descendants:
        if el.name in BLOCK_TAGS:
            lines.append("\n")
        elif isinstance(el, str):
            lines.append(el)

    text = "".join(lines)
    # Collapse multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── Metadata helpers ──────────────────────────────────────────────────────────

def _get_meta(book_obj: epub.EpubBook, field: str) -> str:
    items = book_obj.get_metadata("DC", field)
    if items:
        val = items[0]
        return (val[0] if isinstance(val, tuple) else val).strip()
    return ""


# ── MOBI/AZW3 conversion via Calibre ─────────────────────────────────────────

def _convert_to_epub(path: Path) -> Path:
    """Use Calibre's ebook-convert to turn MOBI/AZW3 into EPUB."""
    _check_calibre()
    tmp = tempfile.mkdtemp()
    out_path = Path(tmp) / (path.stem + ".epub")

    log.info("Converting %s → EPUB via Calibre...", path.name)
    result = subprocess.run(
        ["ebook-convert", str(path), str(out_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Calibre conversion failed:\n{result.stderr}"
        )
    log.info("Conversion complete: %s", out_path)
    return out_path


def _check_calibre():
    result = subprocess.run(["which", "ebook-convert"], capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            "Calibre not found. Install it: sudo apt install calibre\n"
            "Or download from https://calibre-ebook.com/download_linux"
        )
