#!/usr/bin/env python3
"""
audiobook-maker — Convert PDFs and eBooks to chapter-divided audio.

Usage:
  python main.py mybook.pdf                  # Full run
  python main.py mybook.pdf --dry-run        # Extract text only, no TTS
  python main.py mybook.pdf --chapters       # List detected chapters and exit
  python main.py mybook.pdf --chapter 3      # Only render chapter 3
"""

import logging
import sys
from pathlib import Path

import click
import yaml
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_extractor(path: Path, config: dict):
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from extractors.pdf import PDFExtractor
        return PDFExtractor(config)
    elif suffix == ".epub":
        from extractors.epub import EPUBExtractor
        return EPUBExtractor(config)
    else:
        raise ValueError(f"Unsupported format: {suffix}. Supported: .pdf, .epub")


@click.command()
@click.argument("book_path", type=click.Path(exists=True))
@click.option("--config", "config_path", default="config.yaml", show_default=True)
@click.option("--dry-run", is_flag=True, help="Extract text only, skip TTS")
@click.option("--chapters", "list_chapters", is_flag=True, help="Show chapter list and exit")
@click.option("--chapter", "only_chapter", type=int, default=None, help="Render only this chapter number")
@click.option("-v", "--verbose", is_flag=True)
def main(book_path, config_path, dry_run, list_chapters, only_chapter, verbose):
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    config = load_config(config_path)
    path = Path(book_path)

    log.info("Loading: %s", path.name)
    extractor = get_extractor(path, config)
    book = extractor.extract(path)

    print()
    print(book.summary())
    print()

    if list_chapters:
        return

    if dry_run:
        out_dir = Path(config["output"]["dir"]) / path.stem
        out_dir.mkdir(parents=True, exist_ok=True)
        for ch in book.chapters:
            out = out_dir / f"{ch.slug()}.txt"
            out.write_text(ch.text, encoding="utf-8")
            log.info("Wrote %s (%d words)", out.name, ch.word_count())
        print(f"\nDry run complete. Text files in: {out_dir}")
        return

    # TTS rendering (Sprint 3)
    print("TTS rendering not yet implemented — coming in Sprint 3.")
    print("Run with --dry-run to extract and inspect chapter text.")


if __name__ == "__main__":
    main()
