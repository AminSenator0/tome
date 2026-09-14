from pathlib import Path

from tome.core.glossary import (
    cluster_entities,
    ingest_chapter_delimiter_entities,
    write_glossary_markdown,
)


def test_clustering_and_coreference(tmp_path: Path):
    raw = [
        {
            "text": "Xaden Riorson",
            "label": "character",
            "category": "People & Characters",
            "score": 0.96,
            "context": "Xaden spoke.",
        },
        {
            "text": "Xaden",
            "label": "character",
            "category": "People & Characters",
            "score": 0.91,
            "context": "She saw Xaden.",
        },
        {
            "text": "Basgiath War College",
            "label": "location",
            "category": "Locations, Realms & Coordinates",
            "score": 0.95,
            "context": "Entering Basgiath.",
        },
        {
            "text": "Basgiath",
            "label": "location",
            "category": "Locations, Realms & Coordinates",
            "score": 0.89,
            "context": "Welcome to Basgiath.",
        },
    ]
    clusters = cluster_entities(raw, min_frequency=1)
    assert "People & Characters" in clusters
    chars = clusters["People & Characters"]
    assert chars[0].canonical == "Xaden Riorson"
    assert "Xaden" in chars[0].aliases
    assert chars[0].count == 2

    glossary_path = tmp_path / "glossary.md"
    write_glossary_markdown(clusters, glossary_path, book_title="Test Book")
    assert glossary_path.exists()
    content = glossary_path.read_text(encoding="utf-8")
    assert "| Xaden Riorson | Xaden | | Xaden spoke. | |" in content
    assert (
        "| Canonical Term | Aliases / Variants | Term Translation | Sample Context | Context Translation |" in content
    )


def test_ingest_chapter_delimiter():
    text = """# Chapter 1
Translated text line.

<!-- ENTITIES_START
- [Category: People & Characters] Violet Sorrengail | Translation: وایولت سورنگیل | Aliases: Violet
ENTITIES_END -->
"""
    cleaned, entities = ingest_chapter_delimiter_entities(text)
    assert "ENTITIES_START" not in cleaned
    assert len(entities) == 1
    assert entities[0].canonical == "Violet Sorrengail"
    assert "Violet" in entities[0].aliases


def test_ingest_chapter_delimiter_no_block_and_unclosed():
    plain = "# Chapter 1\nJust normal prose with no delimiters."
    cleaned, entities = ingest_chapter_delimiter_entities(plain)
    assert cleaned == plain
    assert entities == []

    unclosed = "# Chapter 1\n<!-- ENTITIES_START\n- [Category: People] Jack\nProse continues without end"
    c2, e2 = ingest_chapter_delimiter_entities(unclosed)
    assert c2 == unclosed
    assert e2 == []


def test_cluster_entities_empty_and_fuzzy():
    assert cluster_entities([], min_frequency=1) == {}

    raw = [
        {"text": "Dumbledore", "label": "char", "category": "People", "score": 0.9, "context": "Albus spoke."},
        {"text": "Dumbledor", "label": "char", "category": "People", "score": 0.85, "context": "Typo in text."},
    ]
    clusters = cluster_entities(raw, min_frequency=1)
    people = clusters.get("People", [])
    assert len(people) == 1
    assert people[0].canonical == "Dumbledore"
    assert "Dumbledor" in people[0].aliases


def test_write_glossary_markdown_empty_clusters(tmp_path: Path):
    glossary_path = tmp_path / "empty_glossary.md"
    write_glossary_markdown({}, glossary_path, book_title="Empty Lore")
    assert glossary_path.exists()
    content = glossary_path.read_text(encoding="utf-8")
    assert "# Glossary: Empty Lore" in content
    assert "Empty Lore" in content
