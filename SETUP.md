# Audiobook Maker — Setup Guide

**This guide covers:** Windows 11 and Linux. Run the block that matches your OS.

> **Status (2026-10-24):** extraction, `--chapters` and `--dry-run` work. All three TTS
> backends have known bugs, so a full render fails until one is fixed. See `AGENTS.md`
> for each bug and its fix.

---

## 1. Prerequisites

### Python 3.11+
**Windows:** Download from [python.org](https://python.org) — check "Add to PATH" during install.
**Linux:** `sudo apt install python3 python3-pip python3-venv`

Verify: `python --version` (Windows) or `python3 --version` (Linux)

### Git
**Windows:** [git-scm.com](https://git-scm.com/download/win)
**Linux:** `sudo apt install git`

### ffmpeg (required for audio assembly)
**Windows:**
```powershell
winget install ffmpeg
# or: choco install ffmpeg  (if you have Chocolatey)
```
**Linux:**
```bash
sudo apt install ffmpeg
```

Verify: `ffmpeg -version`

### Calibre (only needed for MOBI/AZW3 Kindle files)
**Windows/Linux:** [calibre-ebook.com/download](https://calibre-ebook.com/download)

---

## 2. Clone and install

```bash
git clone https://github.com/18hrshift/audiobook-maker
cd audiobook-maker
```

Create a virtual environment (keeps deps clean):

**Windows:**
```powershell
python -m venv .venv
.venv\Scripts\activate
```

**Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install core dependencies:
```bash
pip install -r requirements.txt
```

---

## 3. Choose your TTS backend

Three backends. Switching is one line in `config.yaml` (`tts.backend`) or `--backend` on the
command line. The repo ships with `backend: "zonos"`, so change it if you pick another.

| Backend | Needs | Cost |
|---|---|---|
| `api` | Mistral API key, no GPU | $16 per million characters (about $8 for a 90k-word novel) |
| `zonos` | Linux or macOS, NVIDIA GPU with 6 GB+ VRAM | Free |
| `local` | NVIDIA GPU with 16 GB+ VRAM | Free, but CC BY-NC 4.0 (non-commercial only) |

### Option A: Mistral API (easiest, no GPU)
*Known broken: `tts/mistral_api.py` targets an old SDK. Fix list in `AGENTS.md`.*

1. Go to [console.mistral.ai](https://console.mistral.ai), then API Keys, then Create key
2. Copy the key, then:
```bash
cp .env.example .env
```
Edit `.env`:
```
MISTRAL_API_KEY=your-key-here
```

In `config.yaml`, set:
```yaml
tts:
  backend: "api"
```

### Option B: Zonos on your GPU (offline, Linux or macOS)
*Known broken: wrong model ID and voice-clone call in `tts/zonos.py`. Fix list in `AGENTS.md`.*

Zonos needs `espeak-ng` as a shared library, so native Windows won't work. WSL2 is fine.

```bash
sudo apt install -y espeak-ng ffmpeg
git clone https://github.com/Zyphra/Zonos
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install -e ./Zonos
```

Don't `pip install zonos` from PyPI. That package is an empty placeholder, not Zyphra's code.
First run downloads about 3.3 GB of weights.

Verify the GPU is detected:
```bash
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

In `config.yaml`, set:
```yaml
tts:
  backend: "zonos"
```

### Option C: Voxtral on your GPU (offline, non-commercial)
*Known broken: `tts/local.py` doesn't import and targets a model that doesn't exist.
It needs a rewrite as a client for the server below. Details in `AGENTS.md`.*

Voxtral 4B TTS runs as a server through vLLM-Omni (16 GB+ VRAM, about 8 GB of weights):
```bash
pip install -U "vllm>=0.18" "vllm-omni>=0.18"
vllm serve mistralai/Voxtral-4B-TTS-2603 --omni
```

`.env` doesn't need an API key for either local option.

---

## 4. Voice cloning (optional)

Record yourself (or use any clean audio clip) — 10–30 seconds, no background noise.
Save it anywhere, e.g. `voices/john.wav`.

In `config.yaml`:
```yaml
tts:
  voice: "john"

voice_profiles:
  john:
    reference_audio: "./voices/john.wav"
```

Then run with: `python main.py mybook.pdf --voice john`

Good recording tips:
- Quiet room, close to mic
- Read a paragraph of normal prose (not a word list)
- WAV or MP3 both work
- 16kHz+ sample rate preferred

---

## 5. First run

```bash
# Check chapter detection
python main.py mybook.pdf --chapters

# Preview cleaned text before committing to TTS
python main.py mybook.pdf --dry-run

# Full audiobook render
python main.py mybook.pdf
```

Output lands in `output/mybook/`:
- `01_chapter_one.mp3`, `02_chapter_two.mp3`, ...
- `mybook.m4b` — single file with chapter markers, works in any audiobook app

To render just one chapter (useful for testing voice settings):
```bash
python main.py mybook.pdf --chapter 1
```

---

## 6. Supported formats

| Format | Notes |
|--------|-------|
| `.pdf` | Most published books work. Scanned PDFs (images) won't — OCR first with `python ocr_pdf.py scanned.pdf` (needs Tesseract). |
| `.epub` | Best quality — chapters are cleanly defined. |
| `.mobi` / `.azw3` | Requires Calibre (auto-converted on the fly). |

---

## 7. Updating

```bash
git pull origin main
pip install -r requirements.txt  # in case new deps were added
```

---

## 8. Troubleshooting

**`No chapters detected`** — Run `--chapters` to see what was found. Try loosening the detection by checking `config.yaml → chapter_detection.methods`. Most scanned PDFs need manual splitting.

**`ffmpeg not found`** — Make sure ffmpeg is on your PATH. On Windows, restart your terminal after installing.

**`CUDA out of memory`** — Reduce `chunk_size` in `config.yaml` from 1000 to 500. With Zonos, keep chunks under about 400 characters anyway, since it caps each clip at about 30 seconds.

**`ebook-convert not found`** — Install Calibre and make sure `ebook-convert` is on your PATH. On Windows it's usually at `C:\Program Files\Calibre2\`.

**Voice cloning sounds off** — Try a longer clip (20–30s). Avoid clips with background music or noise.
