# AGENTS.md

Guide for coding agents (Claude Code, Codex, OpenCode, Cursor, etc.) working in this repo.
Read this first, then `SETUP.md` for install steps.

**Last verified:** 2026-10-24, against commit `294c2dd`, on Linux with Python 3.11.
Anything below marked *broken* was confirmed by reading the code and checking the upstream
package, model card, or API docs. Re-check before trusting it if the code has moved on.

## What this is

A Python CLI that turns a PDF, EPUB, MOBI or AZW3 book into one MP3 per chapter, plus a single
`.m4b` audiobook with chapter markers.

`main.py` runs the pipeline: extract, preprocess, chunk, TTS, assemble.

| Stage | File | Notes |
|---|---|---|
| Extract (PDF) | `extractors/pdf.py` | Chapter detection cascade, set by `chapter_detection.methods` in `config.yaml`: `bookmarks`, `chapter_dividers`, `font_size`, `pattern`, `page_split`. First method that finds chapters wins. |
| Extract (EPUB/MOBI/AZW3) | `extractors/epub.py` | MOBI/AZW3 are converted to EPUB with Calibre's `ebook-convert` first. |
| OCR (scanned PDFs) | `ocr_pdf.py` | Standalone helper, not called by `main.py`. Needs the Tesseract binary. Run: `python ocr_pdf.py scanned.pdf` (writes `scanned_ocr.pdf`). |
| Text cleanup | `text_processor.py`, `preprocessor.py` | Hyphenation, quotes, headers/footers, abbreviations, numbers to words, pauses. `chunk_for_tts()` splits on sentence boundaries. |
| TTS | `tts/` | One class per backend, each subclasses `tts/base.py:BaseTTS` and implements `synthesize(text, output_path, reference_audio)`. Chosen by `tts.backend` in `config.yaml` or `--backend`. |
| Assembly | `assembler.py` | Shells out to `ffmpeg` and `ffprobe`. |
| Data models | `models.py` | `Book`, `Chapter`. |

Settings live in `config.yaml`. Secrets live in `.env` (gitignored, template in `.env.example`).

## Current state

### Works

- `pytest`: 15 tests pass. They cover text cleanup and preprocessing only. Nothing tests
  extraction, TTS, or assembly.
- `python main.py book.epub --chapters` lists chapters.
- `python main.py book.epub --dry-run` writes cleaned chapter text to `output/<book>/`.
  Confirmed on a generated two-chapter EPUB ("Dr. Smith walked 42 miles" came out as
  "Doctor Smith walked forty-two miles").

### Broken: every TTS backend

A full render (no `--dry-run`) will fail until at least one backend is fixed.
No end-to-end render is recorded anywhere in the repo.

**`api`: Mistral cloud (`tts/mistral_api.py`)**

1. `from mistralai import Mistral` raises `ImportError` on the current SDK (`mistralai` 3.x).
   The import is now `from mistralai.client import Mistral`. `requirements.txt` says
   `mistralai>=1.0`, so a fresh install gets 3.x.
2. It calls `client.audio.speech.create(...)`. The SDK method is `client.audio.speech.complete(...)`.
3. Model `voxtral-tts-latest` does not exist. The API names are `voxtral-mini-tts-latest`
   and `voxtral-mini-tts-2603`.
4. It sends a `voice` dict. The API takes `voice_id` (a preset or saved voice) or
   `ref_audio` (a base64 audio clip, for cloning).
5. It reads `response.content`. The response carries base64 audio in `audio_data`.
6. Chunks are saved as `.wav`, so pass `response_format` explicitly to match.

Reference: SDK docs at `github.com/mistralai/client-python/blob/main/docs/sdks/speech/README.md`,
model page at `docs.mistral.ai/models/voxtral-tts-26-03`.

**`local`: Voxtral on your GPU (`tts/local.py`)**

1. Line 63, `import soundfile as sf as sf_`, is a `SyntaxError`, so the module cannot even be imported.
2. Model `mistralai/Voxtral-TTS-v0.1` does not exist. The open-weights model is
   `mistralai/Voxtral-4B-TTS-2603`.
3. It loads the model with `transformers.AutoModelForTextToSpeech`, which is not a
   `transformers` class. The model card documents only vLLM-Omni serving.

Fix: rewrite this backend as an HTTP client. Run `vllm serve mistralai/Voxtral-4B-TTS-2603 --omni`
(needs `vllm>=0.18` and `vllm-omni>=0.18`), then `POST {base_url}/v1/audio/speech` with
`{"model", "input", "voice", "response_format"}`. Put the base URL in `config.yaml`.
That request shape is close to the cloud API, so the two backends can share code.

**`zonos`: Zonos on your GPU (`tts/zonos.py`, `install_zonos_linux.sh`)**

1. Model ID `Zonos-v0.1-transformer` has no org prefix. The Hugging Face ID is
   `Zyphra/Zonos-v0.1-transformer` (the bare ID returns 401). Same bug in step 5 of
   `install_zonos_linux.sh`.
2. Voice cloning passes `speaker=` to `model.generate()`, which has no such parameter.
   The speaker embedding goes into `make_cond_dict(text=..., language=..., speaker=...)`.
3. `generate()` defaults to `max_new_tokens=86*30`, about 30 seconds of audio. The default
   `chunk_size: 1000` characters is roughly a minute of speech, so chunks would likely be cut
   short. Lower `chunk_size` (around 400) or raise `max_new_tokens`, and check a sample.
4. `install_zonos_linux.sh` runs `pip install zonos`. The PyPI `zonos` package is an empty
   placeholder (metadata only, no code, not published by Zyphra). Install from source:
   `git clone https://github.com/Zyphra/Zonos && uv pip install -e ./Zonos`.

### Smaller gotchas

- `config.yaml` ships with `tts.backend: "zonos"`. Set it to the backend you are using.
- `.env.example` has `TTS_BACKEND`, but no code reads it. Only `config.yaml` and `--backend` pick the backend.
- `assembler.py:_check_ffmpeg()` runs `which`, which Windows doesn't have unless something like
  Git Bash put one on PATH. Without it, the M4B step raises `FileNotFoundError` after the
  chapter MP3s are written. `main.py` only catches `RuntimeError` there, so the run exits with a traceback.
- `pydub` is in `requirements.txt` but nothing imports it. On Python 3.13 it fails to import
  (no `audioop`), which is harmless today.
- Resume is per chapter: a chapter is skipped if its MP3 already exists. A crash mid-chapter
  redoes that whole chapter.
- `SPRINTS.md` checkboxes are all unchecked, but sprints 1 to 5 shipped (see `git log`).
  Treat it as history, not a to-do list.
- `HANDOFF.md` is the owner's note about converting one specific book on their own machine.
  It is not general setup guidance.

## Which backend to use

| Backend | Needs | Cost | License |
|---|---|---|---|
| `api` (Mistral cloud) | `MISTRAL_API_KEY` from console.mistral.ai, internet. No GPU. | $16 per million characters (Mistral pricing, checked 2026-10-24). A 90k-word novel is about 500k characters, so about $8. | Mistral API terms |
| `zonos` (local) | Linux or macOS, NVIDIA GPU with 6 GB+ VRAM, `espeak-ng` system library, Python 3.10+, 3.3 GB of weights | Free | Apache-2.0 (code and weights) |
| `local` (Voxtral, local) | NVIDIA GPU with 16 GB+ VRAM, vLLM and vLLM-Omni 0.18+, 8 GB of weights | Free | CC BY-NC 4.0: non-commercial use only |

Fastest path to first audio: fix `api`. It is a small change and needs no GPU.
Best offline option: fix `zonos`. Zonos needs `libespeak-ng` as a shared library, so native
Windows does not work. Use Linux, or WSL2 with `sudo apt install espeak-ng`.

## How to work here

- Run `pytest` before every commit. New code ships with tests. TTS backends can be tested by
  mocking the SDK client or model, so no GPU or API key is needed in tests.
- Settings go in `config.yaml` and get read from there. Don't hardcode paths, model IDs, or URLs.
- Fail loudly. Raise with a message that says what to install or set. Don't swallow errors.
- Never commit `.env`, API keys, book files, or `output/`. `.gitignore` already covers
  `.env`, `output/`, and audio files. Don't commit copyrighted books.
- Keep one module per job. A new backend is a new file in `tts/` plus one branch in
  `main.py:get_tts()` and one `--backend` choice.
- When you fix something listed under *Broken*, update this file in the same commit.

## Contributing

The repo is public at `github.com/18hrshift/audiobook-maker`. Fork it and open a pull request
against `main`.
