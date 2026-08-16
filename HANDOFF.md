# HANDBOFF: Gangster Warlords — Zonos Audiobook (native Linux path)

> Written by opencode on Windows (A:\dev\audiobook-maker) before branching to native Linux.
> This file travels with the repo so the session on the Linux side has full context.

## The goal
Turn the scanned PDF of **"Gangster Warlords" by Ioan Grillo** into an offline, local
audiobook using this repo's pipeline + **Zonos-v0.1** (Zyphra) as the TTS backend.
No cloud API keys. All on a local RTX 3090 (24GB).

## Decisions made (locked in)
- TTS backend: **Zonos-v0.1 (Zonos-v0.1-transformer)** — chosen over Kokoro-82M and
  Voxtral. Best quality; local/offline only.
- Run environment: **native Linux** (the dual-boot Ubuntu on this machine). Zonos
  officially supports Linux only. espeak-ng must be installed as a **shared C library**
  (`libespeak-ng.so`), which `sudo apt install espeak-ng` provides. ffmpeg also needed:
  `sudo apt install -y espeak-ng ffmpeg`.
- Attempted-and-abandoned paths (don't re-explore):
  - **WSL2**: Zonos already loaded + CUDA worked, but installing libespeak-ng needed an
    interactive sudo password I couldn't type. (open Friction: phonemizer loads espeak as
    a `.so`, so the Windows `espeak-ng.exe` can NOT be shimmed.)
  - **Native Windows**: Zonos's Windows fork is experimental; phonemizer espeak `.so`
    is the blocker again. Not worth it.

## Book structure (verified against OCR)
- OCR'd searchable PDF: `gangster-warlords_ocr.pdf` (418 pages, image-only original).
- Original at `C:\Users\Jbyrn\Downloads\gangster-warlords_ocr.pdf` (Windows) — copy to Linux.
- **51 chapters, 120,041 words.** Front matter (cover/title/Contents/Part I divider) skipped;
  back matter (Acknowledgments onward) dropped.
- Chapter 1 starts on what scanners call page 4 (0-indexed p4). Detector = `chapter_dividers`
  (full-page "CHAPTER N" dividers) via `extractors/pdf.py`.

## Repo changes made on this side (all committed with this note)
- `ocr_pdf.py` (new): renders each PDF page → Tesseract → outputs a searchable PDF.
  Function `ocr_and_searchable()`. Tesseract 5.4.
- `extractors/pdf.py`: added `chapter_dividers` detection method
  (`_detect_by_chapter_dividers`, `_first_back_matter`, `BACK_MATTER_PAT`,
  `CHAPTER_DIVIDER_PAT`) + dispatch in the method cascade.
- `tts/zonos.py` (new): `ZonosTTS(BaseTTS)` implementing `synthesize()`. Loads
  `Zonos-v0.1-transformer` on cuda, generates WAV via torchaudio. Supports optional
  voice-clone via `make_speaker_embedding(reference_audio)`.
- `main.py`: wired `--backend zonos` choice → `ZonosTTS`; added to CLI choices.
- `config.yaml`: `tts.backend: "zonos"`; `chapter_detection.methods` includes `chapter_dividers`;
  `text_cleaning.skip_pages_before_chapter_1: true`.
- `install_zonos_linux.sh` (new): TURNKEY installer for the Linux side (see next section).

## On the Linux side (run this to stand up)
```bash
bash install_zonos_linux.sh /path/to/audiobook-maker /path/to/gangster-warlords_ocr.pdf
```
It will: install `espeak-ng`+`ffmpeg` (asks for sudo), make a py3.11 venv `.venv-zonos`,
install torch (cu124) + project deps + `zonos`, verify CUDA + espeak-ng, and generate
`output/samples/sample_native_linux.wav` (downloads ~2-3GB weights on first run).

Then render the full book:
```bash
PYBIN=".venv-zonos/bin/python"   # relative to the repo root
"$PYBIN" main.py "$PDF" --backend zonos --chapters
```
(replace $PYBIN with `.venv-zonos/bin/python` relative to the repo).

## Verification tips
- `requirements.txt` has a comment noting torch/transformers/soundfile are only for the local
  backend — on native Linux they ARE needed.
- Output MP3s go to `output/` (gitignored). M4B bundling is handled by `assembler.py` via ffmpeg.
- Chapter text (preprocessed, 51 files) was previously generated to `output/gangster-warlords_ocr/`
  on Windows — gitignored, will regenerate on Linux.

## Notes / open items
- OCR had ~4% low-confidence artifacts (e.g. "E] Paso", "cafAc", "He?s") — optional cleanup.
- TTS sample should be reviewed for voice quality before committing to a 51-chapter render.
- `pydub` is broken on host Python 3.13 (audioop). On native Linux py3.11 this is a non-issue;
  assembler uses ffmpeg directly anyway.