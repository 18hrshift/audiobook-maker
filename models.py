from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Chapter:
    index: int           # 1-based chapter number
    title: str           # "Chapter 1" or detected heading text
    text: str            # Cleaned body text
    page_start: Optional[int] = None
    page_end: Optional[int] = None

    def slug(self) -> str:
        """Filesystem-safe name: '01_chapter_one'"""
        safe = self.title.lower()
        safe = "".join(c if c.isalnum() or c == " " else "" for c in safe).strip()
        safe = "_".join(safe.split())
        return f"{self.index:02d}_{safe}"

    def word_count(self) -> int:
        return len(self.text.split())


@dataclass
class Book:
    title: str
    author: str
    source_path: Path
    chapters: list[Chapter] = field(default_factory=list)

    def total_words(self) -> int:
        return sum(c.word_count() for c in self.chapters)

    def summary(self) -> str:
        lines = [
            f"Book:     {self.title}",
            f"Author:   {self.author}",
            f"Source:   {self.source_path.name}",
            f"Chapters: {len(self.chapters)}",
            f"Words:    {self.total_words():,}",
        ]
        for ch in self.chapters:
            lines.append(f"  [{ch.index:02d}] {ch.title} ({ch.word_count():,} words)")
        return "\n".join(lines)
