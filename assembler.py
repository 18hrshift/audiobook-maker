"""
Audio assembler — stitches TTS chunk files into per-chapter MP3s,
then optionally bundles everything into a single M4B with chapter markers.
"""

import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def assemble_chapter(chunk_paths: list[Path], output_path: Path) -> None:
    """Concatenate audio chunks into a single chapter MP3 using ffmpeg."""
    if not chunk_paths:
        raise ValueError("No chunks to assemble")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if len(chunk_paths) == 1:
        # Single chunk — just copy/convert
        _ffmpeg_convert(chunk_paths[0], output_path)
        return

    # Write a concat list file for ffmpeg
    list_file = output_path.parent / f"_{output_path.stem}_concat.txt"
    list_file.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in chunk_paths),
        encoding="utf-8",
    )

    try:
        _run_ffmpeg([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c:a", "libmp3lame", "-q:a", "4",
            str(output_path),
        ])
    finally:
        list_file.unlink(missing_ok=True)

    log.info("Assembled %s from %d chunks", output_path.name, len(chunk_paths))


def build_m4b(chapter_paths: list[Path], chapter_titles: list[str],
              book_title: str, author: str, output_path: Path) -> None:
    """
    Bundle all chapter MP3s into a single M4B with chapter markers.
    Requires ffmpeg with AAC support.
    """
    _check_ffmpeg()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Step 1: concat all chapters into one AAC file
    combined = output_path.parent / "_combined.aac"
    list_file = output_path.parent / "_m4b_concat.txt"
    list_file.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in chapter_paths),
        encoding="utf-8",
    )

    try:
        _run_ffmpeg([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c:a", "aac", "-b:a", "128k",
            str(combined),
        ])
    finally:
        list_file.unlink(missing_ok=True)

    # Step 2: get chapter durations to build chapter metadata
    durations = [_get_duration(p) for p in chapter_paths]
    meta_file = _write_chapter_metadata(
        output_path.parent / "_chapters.txt",
        chapter_titles,
        durations,
        book_title,
        author,
    )

    # Step 3: mux AAC + metadata into M4B
    try:
        _run_ffmpeg([
            "ffmpeg", "-y",
            "-i", str(combined),
            "-i", str(meta_file),
            "-map_metadata", "1",
            "-c", "copy",
            "-f", "mp4",
            str(output_path),
        ])
    finally:
        combined.unlink(missing_ok=True)
        meta_file.unlink(missing_ok=True)

    log.info("M4B created: %s", output_path)


def _write_chapter_metadata(path: Path, titles: list[str],
                            durations: list[float],
                            book_title: str, author: str) -> Path:
    lines = [
        ";FFMETADATA1",
        f"title={book_title}",
        f"artist={author}",
        "",
    ]
    start_ms = 0
    for title, dur in zip(titles, durations):
        end_ms = start_ms + int(dur * 1000)
        lines += [
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={start_ms}",
            f"END={end_ms}",
            f"title={title}",
            "",
        ]
        start_ms = end_ms

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _get_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def _ffmpeg_convert(src: Path, dst: Path) -> None:
    _run_ffmpeg(["ffmpeg", "-y", "-i", str(src), "-c:a", "libmp3lame", "-q:a", "4", str(dst)])


def _run_ffmpeg(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{result.stderr[-2000:]}")


def _check_ffmpeg():
    result = subprocess.run(["which", "ffmpeg"], capture_output=True)
    if result.returncode != 0:
        raise RuntimeError("ffmpeg not found. Install: sudo apt install ffmpeg")
