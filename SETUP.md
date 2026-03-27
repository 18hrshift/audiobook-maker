# Audiobook Maker — Setup Guide

**Your hardware:** R9 5900 · RTX 3070 Ti (12GB VRAM) · 128GB DDR4
**This guide covers:** Windows 11 and Linux. Run the block that matches your OS.

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

You have two options. Pick one (or both — they're a single config line to switch).

### Option A — Mistral API (easiest to start)
Works immediately, no GPU setup needed. Small cost per book (~cents for a novel).

1. Go to [console.mistral.ai](https://console.mistral.ai) → API Keys → Create key
2. Copy the key, then:
```bash
cp .env.example .env
```
Edit `.env`:
```
MISTRAL_API_KEY=your-key-here
TTS_BACKEND=api
```

In `config.yaml`, set:
```yaml
tts:
  backend: "api"
```

### Option B — Local GPU (fully offline, your 3070 Ti handles it easily)
No API costs. First run downloads the Voxtral model (~8GB). Subsequent runs are instant.

Install PyTorch with CUDA 12:
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install transformers soundfile accelerate
```

Verify GPU is detected:
```bash
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
# Should print: True  NVIDIA GeForce RTX 3070 Ti
```

In `config.yaml`, set:
```yaml
tts:
  backend: "local"
```

`.env` doesn't need an API key for local mode.

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
| `.pdf` | Most published books work. Scanned PDFs (images) won't — use OCR first. |
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

**`CUDA out of memory`** — Reduce `chunk_size` in `config.yaml` from 1000 to 500.

**`ebook-convert not found`** — Install Calibre and make sure `ebook-convert` is on your PATH. On Windows it's usually at `C:\Program Files\Calibre2\`.

**Voice cloning sounds off** — Try a longer clip (20–30s). Avoid clips with background music or noise.
