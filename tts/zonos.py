"""
Local Zonos-v0.1 TTS backend (Zyphra). GPL-3.0; Linux required (official support).

Setup (see install_zonos_linux.sh, or manually on Ubuntu/Debian):
  sudo apt install -y espeak-ng ffmpeg
  uv venv .venv-zonos --python 3.11     # then uv pip install into it
  uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
  uv pip install -r requirements.txt num2words tqdm pymupdf zonos

Config:
  tts:
    backend: "zonos"
    voice: "default"        # or a voice_profiles key with reference_audio
    language: "en-us"
    max_emotion: false      # enable emotion conditioning (slower, model-dependent)
"""

import logging
from pathlib import Path

from tts.base import BaseTTS

log = logging.getLogger(__name__)


class ZonosTTS(BaseTTS):
    MODEL = "Zonos-v0.1-transformer"

    def __init__(self, config: dict):
        super().__init__(config)
        self._model = None
        self._autoencoder = None
        self._model_id = config.get("tts", {}).get("model", self.MODEL)
        self._language = config.get("tts", {}).get("language", "en-us")

    def _load(self):
        if self._model is not None:
            return
        try:
            import torch
        except ImportError:
            raise RuntimeError("Zonos requires torch with CUDA. Run in WSL2 (see module docstring).")
        try:
            from zonos.model import Zonos
        except ImportError:
            raise RuntimeError("zonos not importable. Install it (see module docstring).")

        log.info("Loading Zonos %s (first run downloads weights ~2-3GB)...", self._model_id)
        self._model = Zonos.from_pretrained(self._model_id, device="cuda")
        self._device = "cuda"
        self._sample_rate = self._model.autoencoder.sampling_rate
        log.info("Zonos loaded on %s @ %d Hz", self._device, self._sample_rate)

    def _make_conditioning(self, text: str):
        import torch
        from zonos.conditioning import make_cond_dict

        cond = make_cond_dict(text=text, language=self._language)
        return self._model.prepare_conditioning(cond)

    def _speaker_from_ref(self, reference_audio: Path):
        import torch
        import torchaudio
        wav, sr = torchaudio.load(str(reference_audio))
        return self._model.make_speaker_embedding(wav, sr)

    def synthesize(self, text: str, output_path: Path, reference_audio: Path | None = None) -> None:
        import torch
        import torchaudio

        self._load()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cond = self._make_conditioning(text)
        speaker = None
        if reference_audio and reference_audio.exists():
            speaker = self._speaker_from_ref(reference_audio)
            log.debug("Voice clone from %s", reference_audio.name)

        with torch.no_grad():
            codes = self._model.generate(cond, speaker=speaker)
            wavs = self._model.autoencoder.decode(codes).cpu()
        torchaudio.save(str(output_path), wavs[0], self._sample_rate)
        log.debug("Wrote %s (%d Hz)", output_path.name, self._sample_rate)