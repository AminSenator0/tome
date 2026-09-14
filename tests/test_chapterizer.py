from pathlib import Path

from tome.core.chapterizer import clean_text_artifacts, consolidate_short_chapters, segment_chapters
from tome.models import Chapter


def test_segment_chapters_multilingual(tmp_path: Path):
    sample_text = """
# Front Matter
Copyright 2026. All rights reserved.

## Chapter 1: The Gathering
The gathering began at dusk.

## فصل ۲: گذرگاه
متن فارسی فصل دوم در اینجا قرار دارد.

### Chapitre 3
Le troisième chapitre en français.

## EPILOGUE
The journey reached its end.
"""
    chapters = segment_chapters(sample_text, tmp_path, min_bytes=0)
    assert len(chapters) == 5
    assert chapters[0].is_front_matter is True
    assert (tmp_path / f"{chapters[0].slug}.md").exists()
    assert (tmp_path / f"{chapters[1].slug}.md").exists()
    assert "فصل" in chapters[2].title
    assert chapters[4].is_epilogue is True


def test_consolidate_short_chapters():
    ch1 = Chapter(index=0, title="Part I", slug="00_part_i", content="# PART I\nA Cruelty of Curses")
    ch2 = Chapter(
        index=1,
        title="Chapter 1",
        slug="01_chapter_1",
        content="# Chapter 1\n" + ("Word " * 150),
    )
    ch3 = Chapter(index=2, title="Epilogue Note", slug="02_epilogue_note", content="Tiny closing note.")

    consolidated = consolidate_short_chapters([ch1, ch2, ch3], min_bytes=512)
    assert len(consolidated) == 1
    assert "PART I" in consolidated[0].content
    assert "Chapter 1" in consolidated[0].content
    assert "Tiny closing note" in consolidated[0].content


def test_clean_text_artifacts():
    dirty = "Line 1\nPage 142\nLine 2\n\n\n\nLine 3"
    cleaned = clean_text_artifacts(dirty)
    assert "Page 142" not in cleaned
    assert "\n\n\n" not in cleaned


def test_segment_chapters_no_headings_fallback(tmp_path: Path):
    plain_text = "This is a continuous narrative without any Markdown headings. " * 30
    chapters = segment_chapters(plain_text, tmp_path, min_bytes=100)
    assert len(chapters) >= 1
    assert chapters[0].index == 0
    assert (tmp_path / f"{chapters[0].slug}.md").exists()


def test_segment_chapters_spanish_german_and_roman(tmp_path: Path):
    text = """
# Capítulo I: El Comienzo
Historia en español con números romanos.

## Kapitel 2: Die Reise
Deutsche Erzählung hier.

## Chapter IV: The Arrival
English text with Roman numeral IV.
"""
    chapters = segment_chapters(text, tmp_path, min_bytes=0)
    assert len(chapters) == 3
    slugs = [c.slug for c in chapters]
    assert any("capítulo" in s.lower() or "capitulo" in s.lower() for s in slugs)
    assert any("kapitel" in s.lower() for s in slugs)


def test_consolidate_short_chapters_empty_and_all_short():
    assert consolidate_short_chapters([], min_bytes=512) == []

    c1 = Chapter(index=0, title="Intro", slug="00_intro", content="Tiny")
    c2 = Chapter(index=1, title="Note", slug="01_note", content="Small")
    res = consolidate_short_chapters([c1, c2], min_bytes=512)
    assert len(res) == 1
    assert "Tiny" in res[0].content
    assert "Small" in res[0].content
