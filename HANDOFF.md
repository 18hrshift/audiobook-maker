# HANDOFF: Zonos local audiobook (native Linux path)

> Notes from the session that added the Zonos backend, OCR helper, and `chapter_dividers`
> detection. Written on Windows before moving to native Linux. For current status and known
> bugs, `AGENTS.md` is the source of truth.

## The goal
Turn a scanned (image-only) PDF into an offline, local audiobook using this repo's pipeline
plus **Zonos-v0.1** (Zyphra) as the TTS backend. No cloud API keys. Tested hardware: one
NVIDIA GPU with 24 GB.

## Decisions made
- TTS backend: **Zonos-v0.1 (Zonos-v0.1-transformer)**, chosen over Kokoro-82M and
  Voxtral for quality. Local/offline only.
- Run environment: **native Linux**. Zonos officially supports Linux (and macOS). espeak-ng
  must be installed as a **shared C library** (`libespeak-ng.so`), which
  `sudo apt install espeak-ng` provides. ffmpeg is also needed:
  `sudo apt install -y espeak-ng ffmpeg`.
- Attempted and abandoned (don't re-explore):
  - **WSL2**: Zonos loaded and CUDA worked, but installing libespeak-ng needed an interactive
    sudo password the agent couldn't type. phonemizer loads espeak as a `.so`, so the Windows
    `espeak-ng.exe` can NOT be shimmed. WSL2 works fine if you run the apt install yourself.
  - **Native Windows**: the Zonos Windows fork is experimental, and the phonemizer espeak
    `.so` is the blocker again. Not worth it.

## Scanned-PDF workflow
1. OCR it: `python ocr_pdf.py book.pdf` writes a searchable `book_ocr.pdf` (Tesseract 5.x).
2. Check chapters: `python main.py book_ocr.pdf --chapters`. Books with full-page
   "CHAPTER N" divider pages are picked up by the `chapter_dividers` detector in
   `extractors/pdf.py`.
3. `text_cleaning.skip_pages_before_chapter_1: true` drops front matter (cover, title,
   contents). Back matter (Acknowledgments onward) is dropped by `_first_back_matter`.
4. Review a `--dry-run` before rendering. Expect a few percent of OCR artifacts
   (e.g. `E]` for `El`, mangled accents, `?` for apostrophes).

## Repo changes made in that session
- `ocr_pdf.py` (new): renders each PDF page, runs Tesseract, outputs a searchable PDF.
  Function `ocr_and_searchable()`.
- `extractors/pdf.py`: added the `chapter_dividers` detection method
  (`_detect_by_chapter_dividers`, `_first_back_matter`, `BACK_MATTER_PAT`,
  `CHAPTER_DIVIDER_PAT`) plus dispatch in the method cascade.
- `tts/zonos.py` (new): `ZonosTTS(BaseTTS)` implementing `synthesize()`. Loads
  `Zonos-v0.1-transformer` on CUDA, writes WAV via torchaudio. Optional voice clone via
  `make_speaker_embedding(reference_audio)`.
- `main.py`: wired `--backend zonos` to `ZonosTTS`.
- `config.yaml`: `tts.backend: "zonos"`; `chapter_detection.methods` includes
  `chapter_dividers`; `text_cleaning.skip_pages_before_chapter_1: true`.
- `install_zonos_linux.sh` (new): one-shot installer for the Linux side.

## On the Linux side
```bash
bash install_zonos_linux.sh /path/to/audiobook-maker /path/to/book_ocr.pdf
```
It installs `espeak-ng` and `ffmpeg` (asks for sudo), makes a Python 3.11 venv
`.venv-zonos`, installs torch (cu124), project deps and Zonos, checks CUDA and espeak-ng,
and generates `output/samples/sample_native_linux.wav` (first run downloads the weights).
`AGENTS.md` lists bugs in this script to fix first.

Then check chapters and render:
```bash
.venv-zonos/bin/python main.py /path/to/book_ocr.pdf --backend zonos --chapters
.venv-zonos/bin/python main.py /path/to/book_ocr.pdf --backend zonos
```

## Notes
- `requirements.txt` comments say torch/transformers/soundfile are only for the local
  backend. For Zonos on native Linux they ARE needed.
- Output goes to `output/` (gitignored). `assembler.py` builds the M4B with ffmpeg.
- Review a TTS sample for voice quality before committing to a full-book render.
- `pydub` is broken on Python 3.13 (no `audioop`). It is unused, and the venv is 3.11 anyway.
