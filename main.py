#!/usr/bin/env python3
"""
audiobook-maker — Convert PDFs and eBooks to chapter-divided audio.

Usage:
  python main.py mybook.pdf                      # Full run
  python main.py mybook.pdf --dry-run            # Extract + preprocess text only
  python main.py mybook.pdf --chapters           # List detected chapters and exit
  python main.py mybook.pdf --chapter 3          # Render only chapter 3
  python main.py mybook.pdf --voice john         # Use 'john' voice profile
  python main.py mybook.pdf --backend local      # Override TTS backend
"""

import logging
import sys
import tempfile
from pathlib import Path

import click
import yaml
from dotenv import load_dotenv
from tqdm import tqdm

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
        raise ValueError(f"Unknown TTS backend: {backend}. Use 'api' or 'local'")


def get_reference_audio(config: dict, voice_override: str | None = None) -> Path | None:
    tts_cfg = config.get("tts", {})
    profiles = config.get("voice_profiles", {})
    voice_name = voice_override or tts_cfg.get("voice", "default")
    profile = profiles.get(voice_name, {})
    ref = profile.get("reference_audio", "")
    if not ref:
        return None
    p = Path(ref)
    if not p.exists():
        log.warning("Voice profile '%s' reference audio not found: %s", voice_name, ref)
        return None
    log.info("Voice profile: %s (%s)", voice_name, p.name)
    return p


@click.command()
@click.argument("book_path", type=click.Path(exists=True))
@click.option("--config", "config_path", default="config.yaml", show_default=True)
@click.option("--dry-run", is_flag=True, help="Extract + preprocess text, skip TTS")
@click.option("--chapters", "list_chapters", is_flag=True, help="Show chapter list and exit")
@click.option("--chapter", "only_chapter", type=int, default=None, help="Render only this chapter")
@click.option("--voice", default=None, help="Voice profile name from config")
@click.option("--backend", type=click.Choice(["api", "local"]), default=None)
@click.option("-v", "--verbose", is_flag=True)
def main(book_path, config_path, dry_run, list_chapters, only_chapter, voice, backend, verbose):
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    config = load_config(config_path)
    out_cfg = config.get("output", {})
    pre_cfg = config.get("preprocessing", {})
    path = Path(book_path)

    # ── Extract ───────────────────────────────────────────────────────────────
    log.info("Loading: %s", path.name)
    extractor = get_extractor(path, config)
    book = extractor.extract(path)

    print()
    print(book.summary())
    print()

    if list_chapters:
        return

    chapters = book.chapters
    if only_chapter is not None:
        chapters = [c for c in chapters if c.index == only_chapter]
        if not chapters:
            print(f"Chapter {only_chapter} not found.", file=sys.stderr)
            sys.exit(1)

    out_dir = Path(out_cfg.get("dir", "./output")) / path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    fmt = out_cfg.get("format", "mp3")

    # ── Preprocess text ───────────────────────────────────────────────────────
    if any(pre_cfg.get(k, True) for k in ("expand_abbreviations", "convert_numbers", "inject_pauses")):
        from preprocessor import preprocess_for_tts
        for ch in chapters:
            ch.text = preprocess_for_tts(ch.text)

    # ── Dry run ───────────────────────────────────────────────────────────────
    if dry_run:
        for ch in chapters:
            out = out_dir / f"{ch.slug()}.txt"
            out.write_text(ch.text, encoding="utf-8")
            log.info("Wrote %s (%d words)", out.name, ch.word_count())
        print(f"Dry run complete. Preprocessed text in: {out_dir}")
        return

    # ── TTS rendering ─────────────────────────────────────────────────────────
    from text_processor import chunk_for_tts
    from assembler import assemble_chapter, build_m4b

    tts = get_tts(config, backend)
    ref_audio = get_reference_audio(config, voice)
    chunk_size = config.get("tts", {}).get("chunk_size", 1000)

    log.info("Backend: %s | Voice: %s", tts.backend_name(), voice or "default")

    chapter_audio_paths = []
    total_words = sum(c.word_count() for c in chapters)

    with tqdm(total=total_words, unit="word", desc="Rendering", ncols=80) as pbar:
        for ch in chapters:
            chapter_out = out_dir / f"{ch.slug()}.{fmt}"

            if chapter_out.exists():
                log.info("Skipping (already rendered): %s", chapter_out.name)
                chapter_audio_paths.append((ch, chapter_out))
                pbar.update(ch.word_count())
                continue

            chunks = chunk_for_tts(ch.text, max_chars=chunk_size)
            pbar.set_description(f"Ch {ch.index:02d}: {ch.title[:30]}")

            with tempfile.TemporaryDirectory() as tmp:
                chunk_files = []
                for i, chunk in enumerate(chunks):
                    chunk_path = Path(tmp) / f"chunk_{i:04d}.wav"
                    tts.synthesize(chunk, chunk_path, reference_audio=ref_audio)
                    chunk_files.append(chunk_path)
                    words_in_chunk = len(chunk.split())
                    pbar.update(words_in_chunk)

                assemble_chapter(chunk_files, chapter_out)

            log.info("Done: %s", chapter_out.name)
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
            log.warning("M4B creation failed: %s", e)

    print(f"Output: {out_dir}")
    if hasattr(tts, "cost_report"):
        print(tts.cost_report())


if __name__ == "__main__":
    main()
