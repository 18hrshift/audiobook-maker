# Audiobook Maker — Sprint Plan

## North Star Principles Applied
- **Modularity**: extractors, TTS backends, and assembler are fully independent
- **Config is source of truth**: all paths, voices, backends in config.yaml
- **No god scripts**: each module does one thing
- **Fail loudly**: bad PDFs, missing API keys, failed TTS calls surface immediately
- **Observability**: structured logs, per-chapter progress, cost tracking for API mode
- **Test what you build**: each sprint ships with tests

---

## Sprint 1 — Foundation & PDF Extraction
**Goal:** Given a PDF, produce clean chapter-divided text files ready for TTS.

- [ ] Repo scaffold (models, config, CLI skeleton)
- [ ] PDF extractor with chapter detection cascade:
  1. PDF bookmarks/outline (PyMuPDF)
  2. Font-size heading detection (pdfplumber)
  3. Text pattern matching (Chapter N, Part I, etc.)
  4. Fallback: split by N pages
- [ ] Text cleaning pipeline (strip headers/footers, fix hyphenation, normalize quotes)
- [ ] Config system (YAML — input path, output dir, backend, voice)
- [ ] CLI: `python main.py book.pdf`
- [ ] Tests: chapter detection accuracy on sample PDFs

## Sprint 2 — EPUB & eBook Support
**Goal:** Same clean chapter output from EPUB, MOBI, AZW3 files.

- [ ] EPUB extractor (ebooklib — chapters are separate HTML files)
- [ ] MOBI/AZW3 support via Calibre CLI conversion to EPUB
- [ ] Unified Book interface (same output regardless of input format)
- [ ] Auto-detect input format by extension
- [ ] Tests: EPUB chapter extraction

## Sprint 3 — TTS Integration
**Goal:** Feed chapter text to Voxtral, get audio back.

- [ ] Abstract TTS base class
- [ ] Mistral API backend (Voxtral via `mistral-inference` or REST API)
- [ ] Local backend (HuggingFace `mistralai/Voxtral-TTS` — for main machine GPU)
- [ ] Voice cloning support (reference audio clip path in config)
- [ ] Smart chunking (respect sentence boundaries, stay under TTS token limits)
- [ ] Resume support (skip already-generated chunks on re-run)
- [ ] Cost logging for API mode (tokens used, estimated $)

## Sprint 4 — Audio Assembly
**Goal:** Per-chapter MP3s and a proper M4B audiobook file.

- [ ] Chapter audio stitcher (pydub — concatenate chunk wavs per chapter)
- [ ] Output: `output/01_chapter_one.mp3`, `02_chapter_two.mp3`, etc.
- [ ] M4B container with embedded chapter markers (ffmpeg)
- [ ] Cover art embedding (extract from PDF/EPUB or use placeholder)
- [ ] Metadata tagging (title, author, chapter names)

## Sprint 5 — Polish & Quality
**Goal:** Production-ready tool that handles real-world books cleanly.

- [ ] Number-to-words normalization ("Chapter 3" → "Chapter Three")
- [ ] Abbreviation expansion (common ones: Dr., Mr., etc.)
- [ ] Smart pause injection (paragraph breaks → slight silence)
- [ ] Multiple named voice profiles in config
- [ ] Preprocessing dry-run mode (output cleaned text without TTS for review)
- [ ] Simple progress bar / ETA
