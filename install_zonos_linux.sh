#!/usr/bin/env bash
# Native-Linux setup for Gangster Warlords audiobook (Zonos-v0.1 local TTS).
# Run from a terminal inside the Linux install:
#   bash install_zonos_linux.sh <abs-path-to-cloned-repo> [path-to-ocr-pdf]
set -euo pipefail

PROJ="${1:?usage: bash install_zonos_linux.sh <repo-dir> [ocr-pdf]}"
PDF="${2:-}"
cd "$PROJ"

echo "=== 1/5 system packages (needs sudo, enter password when asked) ==="
if ! command -v espeak-ng >/dev/null; then
  sudo apt update && sudo apt install -y espeak-ng ffmpeg
fi
if ! command -v uv >/dev/null && ! command -v pip >/dev/null; then
  echo "install uv..."; curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

echo "=== 2/5 python venv (3.11) ==="
PYBIN="$PROJ/.venv-zonos/bin/python"
command -v uv >/dev/null && uv venv "$PROJ/.venv-zonos" --python 3.11 || python3.11 -m venv "$PROJ/.venv-zonos"

V() { if command -v uv >/dev/null; then uv pip install --python "$PYBIN" "$@"; else "$PYBIN" -m pip install "$@"; fi; }

echo "=== 3/5 torch (CUDA build) + project deps + Zonos ==="
V torch torchaudio --index-url https://download.pytorch.org/whl/cu124
V -r "$PROJ/requirements.txt" num2words tqdm pymupdf
V zonos  # or: git clone https://github.com/Zyphra/Zonos.git /tmp/Zonos && cd /tmp/Zonos && (V . )

echo "=== 4/5 verify espeak + GPU ==="
"$PYBIN" -c "import torch; print('CUDA', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"
"$PYBIN" -c "from phonemizer import phonemize; print('espeak OK:', phonemize('Hello from native linux.', language='en-us'))"

echo "=== 5/5 generate a voice sample (first run downloads ~2-3GB weights) ==="
"$PYBIN" -c "
import torch, time
from pathlib import Path
from zonos.model import Zonos
from zonos.conditioning import make_cond_dict
print('loading Zonos (downloads weights on first run)...', flush=True)
m = Zonos.from_pretrained('Zonos-v0.1-transformer', device='cuda')
cond = m.prepare_conditioning(make_cond_dict(text='This is the handoff sample from native Linux. The crime wars book is ready to record.', language='en-us'))
with torch.no_grad():
    wavs = m.autoencoder.decode(m.generate(cond)).cpu()
out = Path('$PROJ/output/samples/sample_native_linux.wav'); out.parent.mkdir(parents=True, exist_ok=True)
import torchaudio; torchaudio.save(str(out), wavs[0], m.autoencoder.sampling_rate)
print('sample ->', out)
"

echo "DONE. Review the sample, then render:"
echo "  $PYBIN main.py \"$PDF\" --backend zonos --chapters"