#!/usr/bin/env python3
"""
audiobook-maker — Convert PDFs and eBooks to chapter-divided audio.

Usage:
  python main.py mybook.pdf                  # Full run (TTS + audio assembly)
  python main.py mybook.pdf --dry-run        # Extract text only, no TTS
  python main.py mybook.pdf --chapters       # List detected chapters and exit
  python main.py mybook.pdf --chapter 3      # Only render chapter 3
  python main.py mybook.pdf --backend local  # Override TTS backend
"""

import logging
import os
import sys
import tempfile
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


def load_config(config_path: str) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_extractor(path: Path, config: dict):
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from extractors.pdf import PDFExtractor
        return PDFExtractor(config)
    elif suffix in (".epub", ".mobi", ".azw3", ".azw"):
        from extractors.epub import EPUBExtractor
        return EPUBExtractor(config)
    else:
        raise ValueError(f"Unsupported format: {suffix}. Supported: .pdf, .epub, .mobi, .azw3")


def get_tts(config: dict, backend_override: str | None = None):
    backend = backend_override or config.get("tts", {}).get("backend", "api")
    if backend == "api":
        from tts.mistral_api import MistralAPITTS
        return MistralAPITTS(config)
    elif backend == "local":
        from tts.local import LocalVoxtralTTS
        return LocalVoxtralTTS(config)
    else:
        raise ValueError(f"Unknown TTS backend: {backend}. Choose 'api' or 'local'")


@click.command()
@click.argument("book_path", type=click.Path(exists=True))
@click.option("--config", "config_path", default="config.yaml", show_default=True)
@click.option("--dry-run", is_flag=True, help="Extract + clean text only, skip TTS")
@click.option("--chapters", "list_chapters", is_flag=True, help="Show chapter list and exit")
@click.option("--chapter", "only_chapter", type=int, default=None, help="Render only this chapter number")
@click.option("--backend", type=click.Choice(["api", "local"]), default=None, help="Override TTS backend")
@click.option("-v", "--verbose", is_flag=True)
def main(book_path, config_path, dry_run, list_chapters, only_chapter, backend, verbose):
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    config = load_config(config_path)
    tts_cfg = config.get("tts", {})
    out_cfg = config.get("output", {})
    path = Path(book_path)

    # ── Extract ──────────────────────────────────────────────────────────────
    log.info("Loading: %s", path.name)
    extractor = get_extractor(path, config)
    book = extractor.extract(path)

    print()
    print(book.summary())
    print()

    if list_chapters:
        return

    # ── Filter to requested chapter ───────────────────────────────────────────
    chapters = book.chapters
    if only_chapter is not None:
        chapters = [c for c in chapters if c.index == only_chapter]
        if not chapters:
            print(f"Chapter {only_chapter} not found.", file=sys.stderr)
            sys.exit(1)

    # ── Dry run: write text files ─────────────────────────────────────────────
    out_dir = Path(out_cfg.get("dir", "./output")) / path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    if dry_run:
        for ch in chapters:
            out = out_dir / f"{ch.slug()}.txt"
            out.write_text(ch.text, encoding="utf-8")
            log.info("Wrote %s (%d words)", out.name, ch.word_count())
        print(f"Dry run complete. Text files in: {out_dir}")
        return

    # ── TTS rendering ─────────────────────────────────────────────────────────
    from text_processor import chunk_for_tts
    from assembler import assemble_chapter, build_m4b

    tts = get_tts(config, backend)
    log.info("TTS backend: %s", tts.backend_name())

    ref_audio = None
    ref_path = tts_cfg.get("reference_audio", "")
    if ref_path:
        ref_audio = Path(ref_path)
        if not ref_audio.exists():
            log.warning("Reference audio not found: %s — using default voice", ref_path)
            ref_audio = None

    chunk_size = tts_cfg.get("chunk_size", 1000)
    fmt = out_cfg.get("format", "mp3")
    chapter_audio_paths = []

    for ch in chapters:
        log.info("Rendering chapter %d: %s (%d words)", ch.index, ch.title, ch.word_count())
        chapter_out = out_dir / f"{ch.slug()}.{fmt}"

        # Skip if already rendered
        if chapter_out.exists():
            log.info("  Already rendered, skipping: %s", chapter_out.name)
            chapter_audio_paths.append((ch, chapter_out))
            continue

        chunks = chunk_for_tts(ch.text, max_chars=chunk_size)
        log.info("  %d chunks", len(chunks))

        chunk_files = []
        with tempfile.TemporaryDirectory() as tmp:
            for i, chunk in enumerate(chunks):
                chunk_path = Path(tmp) / f"chunk_{i:04d}.wav"
                tts.synthesize(chunk, chunk_path, reference_audio=ref_audio)
                chunk_files.append(chunk_path)
                print(f"  [{ch.index:02d}] chunk {i+1}/{len(chunks)}", end="\r", flush=True)

            print()
            assemble_chapter(chunk_files, chapter_out)

        log.info("  → %s", chapter_out)
        chapter_audio_paths.append((ch, chapter_out))

    # ── M4B bundle ────────────────────────────────────────────────────────────
    if out_cfg.get("also_make_m4b", True) and len(chapter_audio_paths) > 1:
        m4b_path = out_dir / f"{path.stem}.m4b"
        log.info("Building M4B: %s", m4b_path.name)
        try:
            build_m4b(
                chapter_paths=[p for _, p in chapter_audio_paths],
                chapter_titles=[c.title for c, _ in chapter_audio_paths],
                book_title=book.title,
                author=book.author,
                output_path=m4b_path,
            )
            print(f"\nAudiobook: {m4b_path}")
        except RuntimeError as e:
            log.warning("M4B creation failed (ffmpeg issue?): %s", e)

    print(f"\nDone. Output: {out_dir}")

    if hasattr(tts, "cost_report"):
        print(tts.cost_report())


if __name__ == "__main__":
    main()
