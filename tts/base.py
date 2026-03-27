from abc import ABC, abstractmethod
from pathlib import Path


class BaseTTS(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def synthesize(self, text: str, output_path: Path, reference_audio: Path | None = None) -> None:
        """Synthesize text to audio and write to output_path."""
        ...

    def backend_name(self) -> str:
        return self.__class__.__name__
