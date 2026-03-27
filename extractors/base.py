from abc import ABC, abstractmethod
from pathlib import Path
from models import Book


class BaseExtractor(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def extract(self, path: Path) -> Book:
        """Extract a Book (with chapters) from the given file."""
        ...
