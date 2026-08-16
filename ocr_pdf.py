"""
OCR stage — convert a scanned/image PDF into a searchable PDF for extraction.

For each page: render to image -> Tesseract OCR -> write text into a matching
page in a new PDF (same layout/dimensions, page count preserved). The resulting
PDF has real selectable text so the normal extractor + chapter detection work.

Requires: Tesseract binary on PATH (Windows: C:\\Program Files\\Tesseract-OCR\\tesseract.exe)
"""

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

import fitz

log = logging.getLogger(__name__)

# fallback list of likely Windows install paths
TESS_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe",
]


def find_tesseract() -> str:
    """Locate the Tesseract binary."""
    exe = shutil.which("tesseract")
    if exe:
        return exe
    import os
    for cand in TESS_CANDIDATES:
        cand = os.path.expandvars(cand)
        if Path(cand).exists():
            return cand
    raise RuntimeError(
        "Tesseract not found. Install from https://github.com/UB-Mannheim/tesseract "
        "or run: winget install --id UB-Mannheim.TesseractOCR"
    )


def ocr_image_to_text(tesseract: str, png_path: Path, lang: str = "eng") -> str:
    """OCR a single rendered page image and return its text."""
    with tempfile.TemporaryDirectory() as tmp:
        out_base = Path(tmp) / "out"
        subprocess.run(
            [tesseract, str(png_path), str(out_base), "-l", lang, "--psm", "3"],
            check=True,
            capture_output=True,
        )
        txt = out_base.with_suffix(".txt").read_text(encoding="utf-8")
    return txt


def _fit_ocr_text_box(page: fitz.Page, text: str) -> None:
    """Insert OCR text onto a page, shrinking font until it fits."""
    rect = page.rect
    # leave some margin
    margin = 36
    box = fitz.Rect(margin, margin, rect.width - margin, rect.height - margin)
    fontsize = 11.0
    for _ in range(12):
        try:
            rc = page.insert_textbox(
                box,
                text,
                fontname="helv",
                fontsize=fontsize,
                align=fitz.TEXT_ALIGN_LEFT,
                lineheight=1.3,
            )
            if rc >= 0:
                return
        except Exception as e:
            log.debug("insert_textbox error (shrink): %s", e)
        fontsize -= 0.5
    # last resort: insert at tiny size, truncate handled by fitz
    try:
        page.insert_textbox(box, text, fontname="helv", fontsize=3.0, lineheight=1.1)
    except Exception as e:
        log.warning("Could not insert text on page: %s", e)


def ocr_and_searchable(input_pdf: Path, output_pdf: Path,
                       dpi: int = 200, lang: str = "eng",
                       skip_pages: int = 0) -> int:
    """
    OCR input_pdf -> output_pdf (searchable). Returns number of pages written.
    `skip_pages`: number of leading pages to leave blank (e.g. cover/front matter).
    """
    tesseract = find_tesseract()
    src = fitz.open(str(input_pdf))
    dst = fitz.open()

    total = len(src)
    start = skip_pages
    log.info("OCR: %d pages, skipping first %d, DPI %d", total, start, dpi)

    for i in range(total):
        page = src[i]
        if i < start:
            # blank matching page (drop front matter text)
            dpage = dst.new_page(width=page.rect.width, height=page.rect.height)
        else:
            pix = page.get_pixmap(dpi=dpi)
            png = input_pdf.with_name(f"__ocr_tmp_{i}.png")
            pix.save(str(png))
            try:
                text = ocr_image_to_text(tesseract, png, lang)
            finally:
                png.unlink(missing_ok=True)
            dpage = dst.new_page(width=page.rect.width, height=page.rect.height)
            if text.strip():
                _fit_ocr_text_box(dpage, text)
        if (i + 1) % 25 == 0:
            log.info("  OCR progress: %d/%d", i + 1, total)

    dst.set_metadata(src.metadata or {})
    dst.save(str(output_pdf), deflate=True)
    written = len(dst)
    src.close()
    dst.close()
    log.info("OCR done: %d pages -> %s", written, output_pdf)
    return written


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    inp = Path(sys.argv[1])
    out = inp.with_name(inp.stem + "_ocr.pdf")
    ocr_and_searchable(inp, out)