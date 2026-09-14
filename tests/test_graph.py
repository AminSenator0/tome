from pathlib import Path

from tome.core.graph import build_character_graph
from tome.models import Chapter, Entity


def test_build_character_graph(tmp_path: Path):
    ch1 = Chapter(
        index=1,
        title="Chapter 1",
        slug="01_chapter_1",
        content="Evangeline Fox saw Jacks in the hall. Jacks smiled at Evangeline.",
    )
    ch2 = Chapter(
        index=2,
        title="Chapter 2",
        slug="02_chapter_2",
        content="Evangeline walked into the room where Apollo and Jacks were standing.",
    )
    entities = [
        Entity(canonical="Evangeline Fox", category="People & Characters", aliases={"Evangeline"}),
        Entity(canonical="Jacks", category="People & Characters", aliases=set()),
        Entity(canonical="Prince Apollo", category="People & Characters", aliases={"Apollo"}),
    ]

    out_file = tmp_path / "graph.md"
    build_character_graph([ch1, ch2], entities, out_file, book_title="Test Book")

    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "graph TD" in content
    assert "Chapter Scene Presence Matrix" in content
    assert "Chapter 1" in content


def test_build_character_graph_empty_entities(tmp_path: Path):
    ch = Chapter(index=1, title="Solo Chapter", slug="01_solo", content="A wind blew over the hills.")
    out_file = tmp_path / "empty_graph.md"
    build_character_graph([ch], [], out_file, book_title="Empty Saga")

    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "Executive Character & Relationship Dossier" in content
    assert "No major characters extracted" in content


def test_build_character_graph_single_entity_and_non_characters(tmp_path: Path):
    ch = Chapter(index=1, title="Chapter 1", slug="01_chap", content="Arthur drew Excalibur from Camelot.")
    entities = [
        Entity(canonical="Arthur", category="People & Characters", aliases=set()),
        Entity(canonical="Excalibur", category="Magical Items & Artifacts", aliases=set()),
        Entity(canonical="Camelot", category="Locations & Realms", aliases=set()),
    ]
    out_file = tmp_path / "single_graph.md"
    build_character_graph([ch], entities, out_file, book_title="Arthurian Legend")

    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "Arthur" in content
    assert "Excalibur" not in content


def test_extract_entities_from_glossary(tmp_path: Path):
    from tome.core.graph import load_entities_from_glossary

    gloss = tmp_path / "glossary.md"
    gloss.write_text(
        "# Glossary\n\n"
        "| Canonical Term | Aliases / Variants | Category | Term Translation | Sample Context | Context Translation |\n"
        "|---|---|---|---|---|---|\n"
        "| Jacks | Prince of Hearts | People & Characters | جکس | Jacks smiled | |\n"
        "| Valenda | Northern Realm | Locations & Realms | والندا | In Valenda | |\n",
        encoding="utf-8",
    )
    ents = load_entities_from_glossary(gloss)
    assert len(ents) == 2
    canonicals = [e.canonical for e in ents]
    assert "Jacks" in canonicals
    assert "Valenda" in canonicals
    jacks = next(e for e in ents if e.canonical == "Jacks")
    assert "Prince of Hearts" in jacks.aliases
