# audiobook-maker

Turn a PDF, EPUB, MOBI or AZW3 book into chapter MP3s and a single `.m4b` audiobook with
chapter markers.

```bash
python main.py mybook.epub --chapters   # list detected chapters
python main.py mybook.epub --dry-run    # write cleaned chapter text, no audio
python main.py mybook.epub              # full render
```

## Status (2026-10-24)

Chapter extraction and text cleanup work. **The TTS backends all need fixes before a full
render works.** `AGENTS.md` lists each bug and its fix.

Three backends, picked in `config.yaml` (`tts.backend`) or with `--backend`:

| Backend | Runs on | Needs |
|---|---|---|
| `api` | Mistral cloud (Voxtral TTS) | API key, no GPU, about $16 per million characters |
| `zonos` | Your GPU (Zonos v0.1) | Linux or macOS, NVIDIA GPU with 6 GB+ VRAM |
| `local` | Your GPU (Voxtral 4B TTS via vLLM-Omni) | NVIDIA GPU with 16 GB+ VRAM, non-commercial license |

## Docs

- [`SETUP.md`](SETUP.md): install and first run
- [`AGENTS.md`](AGENTS.md): architecture, known bugs, and rules for coding agents
- [`config.yaml`](config.yaml): every setting, with comments
