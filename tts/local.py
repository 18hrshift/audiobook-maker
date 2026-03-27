"""
Local Voxtral TTS — runs on GPU (main machine: R9 5900 + RTX 3070 Ti).

Setup (run once on main machine):
  pip install torch transformers soundfile
  # Model downloads automatically on first run (~8GB)

Not available on the VM (no GPU).
"""

import logging
from pathlib import Path

from tts.base import BaseTTS

log = logging.getLogger(__name__)

MODEL_ID = "mistralai/Voxtral-TTS-v0.1"


class LocalVoxtralTTS(BaseTTS):
    def __init__(self, config: dict):
        super().__init__(config)
        self._model = None
        self._processor = None

    def _load(self):
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoModelForTextToSpeech, AutoProcessor
        except ImportError:
            raise RuntimeError(
                "Local TTS requires: pip install torch transformers soundfile\n"
                "Run on the main machine (GPU required)."
            )

        import torch
        log.info("Loading Voxtral model %s (first run downloads ~8GB)...", MODEL_ID)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cpu":
            log.warning("No CUDA GPU detected — local TTS will be very slow")

        from transformers import AutoModelForTextToSpeech, AutoProcessor
        self._processor = AutoProcessor.from_pretrained(MODEL_ID)
        self._model = AutoModelForTextToSpeech.from_pretrained(
            MODEL_ID, torch_dtype=torch.float16 if device == "cuda" else torch.float32
        ).to(device)
        self._device = device
        log.info("Voxtral loaded on %s", device)

    def synthesize(self, text: str, output_path: Path, reference_audio: Path | None = None) -> None:
        import soundfile as sf
        import torch

        self._load()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        inputs = self._processor(text=text, return_tensors="pt").to(self._device)

        if reference_audio and reference_audio.exists():
            import soundfile as sf as sf_
            ref_audio, sr = sf_.read(str(reference_audio))
            ref_inputs = self._processor(
                audio=ref_audio, sampling_rate=sr, return_tensors="pt"
            ).to(self._device)
            inputs.update(ref_inputs)

        log.debug("Synthesizing %d chars locally on %s", len(text), self._device)
        with torch.no_grad():
            output = self._model.generate(**inputs)

        audio = output.cpu().numpy().squeeze()
        sample_rate = self._processor.feature_extractor.sampling_rate
        sf.write(str(output_path), audio, sample_rate)
