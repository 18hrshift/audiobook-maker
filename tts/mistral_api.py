"""
Voxtral TTS via Mistral API.
Requires MISTRAL_API_KEY in .env.

Voxtral API docs: https://docs.mistral.ai/capabilities/voxtral/
"""

import logging
import os
from pathlib import Path

from tts.base import BaseTTS

log = logging.getLogger(__name__)


class MistralAPITTS(BaseTTS):
    MODEL = "voxtral-tts-latest"

    def __init__(self, config: dict):
        super().__init__(config)
        self.api_key = os.getenv("MISTRAL_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "MISTRAL_API_KEY not set. Add it to .env — get one at console.mistral.ai"
            )
        # Lazy import so non-API users don't need the SDK
        from mistralai import Mistral
        self.client = Mistral(api_key=self.api_key)
        self._cost_tokens = 0

    def synthesize(self, text: str, output_path: Path, reference_audio: Path | None = None) -> None:
        """Call Voxtral API and write audio to output_path."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        kwargs = {
            "model": self.MODEL,
            "input": text,
            "voice": "default",
        }

        if reference_audio and reference_audio.exists():
            # Voice cloning: encode reference audio as base64
            import base64
            audio_b64 = base64.b64encode(reference_audio.read_bytes()).decode()
            kwargs["voice"] = {
                "type": "reference",
                "audio": audio_b64,
                "format": reference_audio.suffix.lstrip("."),
            }
            log.debug("Using voice clone from %s", reference_audio.name)

        log.debug("Synthesizing %d chars via Mistral API", len(text))
        response = self.client.audio.speech.create(**kwargs)

        # response.content is raw audio bytes
        output_path.write_bytes(response.content)

        # Track usage for cost reporting
        if hasattr(response, "usage") and response.usage:
            self._cost_tokens += getattr(response.usage, "total_tokens", 0)

    def cost_report(self) -> str:
        # Voxtral pricing TBD — log tokens used as proxy
        return f"API tokens used: {self._cost_tokens:,}"
