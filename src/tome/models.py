from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Entity:
    canonical: str
    category: str
    count: int = 1
    aliases: set[str] = field(default_factory=set)
    sample_context: str = ""

    def merge_alias(self, alias: str, count: int = 1) -> None:
        if alias.lower() != self.canonical.lower():
            self.aliases.add(alias)
        self.count += count


@dataclass
class Chapter:
    index: int
    title: str
    slug: str
    content: str
    is_front_matter: bool = False
    is_epilogue: bool = False


@dataclass
class PipelineResult:
    book_title: str
    full_markdown_path: Path
    chapter_paths: list[Path]
    glossary_path: Path | None = None
    character_graph_path: Path | None = None
    total_pages: int = 0
    total_chapters: int = 0
    entity_count: int = 0
    timings: dict[str, float] = field(default_factory=dict)
    metadata: Any | None = None
