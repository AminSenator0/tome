from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from tome.api.routes import app

client = TestClient(app)


def test_api_health():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "service": "tome"}


def test_api_convert_success(tmp_path: Path):
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF dummy")
    out_dir = tmp_path / "out"

    mock_md = out_dir / "book.md"
    out_dir.mkdir()
    mock_md.write_text("# Chapter 1", encoding="utf-8")
    meta = {"page_count": 5, "pdf_type": "text_based", "confidence": 0.95}

    with patch("tome.api.routes.convert_pdf_to_markdown", return_value=(mock_md, meta)):
        res = client.post("/api/v1/convert", json={"pdf_path": str(pdf), "output_dir": str(out_dir)})
        assert res.status_code == 200
        data = res.json()
        assert data["page_count"] == 5
        assert data["pdf_type"] == "text_based"


def test_api_chapterize(tmp_path: Path):
    md = tmp_path / "test.md"
    md.write_text(
        "# Chapter 1\n" + ("Text one " * 70) + "\n\n# Chapter 2\n" + ("Text two " * 70),
        encoding="utf-8",
    )
    out_dir = tmp_path / "chapters"

    res = client.post("/api/v1/chapterize", json={"markdown_path": str(md), "output_dir": str(out_dir)})
    assert res.status_code == 200
    data = res.json()
    assert data["total_chapters"] == 2
    assert len(data["chapter_slugs"]) == 2


def test_api_ingest(tmp_path: Path):
    ch = tmp_path / "ch1.md"
    ch.write_text(
        "# Chapter 1\nText\n\n<!-- ENTITIES_START\n- [Category: People & Characters] Jacks | Translation: جکس\nENTITIES_END -->\n",
        encoding="utf-8",
    )
    gloss = tmp_path / "gloss.md"

    res = client.post("/api/v1/ingest", json={"chapter_file": str(ch), "glossary_path": str(gloss)})
    assert res.status_code == 200
    data = res.json()
    assert data["ingested_count"] == 1
    assert "ENTITIES_START" not in ch.read_text(encoding="utf-8")
    assert gloss.exists()


def test_api_edit_text():
    res = client.post("/api/v1/edit", json={"text": "او ميرود و خانه ها را ديد."})
    assert res.status_code == 200
    data = res.json()
    assert "می‌رود" in data["edited_text"]
    assert "خانه‌ها" in data["edited_text"]
    assert data["words_processed"] > 0
    assert data["words_modified"] > 0
    assert "words normalized" in data["summary"]


def test_api_edit_file(tmp_path: Path):
    sample_file = tmp_path / "chapter.md"
    sample_file.write_text("# فصل ۱\nاو ميرود.", encoding="utf-8")
    out_file = tmp_path / "edited.md"

    res = client.post(
        "/api/v1/edit",
        json={"file_path": str(sample_file), "output_path": str(out_file)},
    )
    assert res.status_code == 200
    data = res.json()
    assert "می‌رود" in data["edited_text"]
    assert out_file.exists()
    assert "می‌رود" in out_file.read_text(encoding="utf-8")


def test_api_translate(tmp_path: Path):
    book_dir = tmp_path / "Book"
    chap_dir = book_dir / "chapters"
    chap_dir.mkdir(parents=True)
    (chap_dir / "01_chap.md").write_text("# Chapter 1\nHello.", encoding="utf-8")

    out_file = book_dir / "translation" / "01_chap.md"
    out_file.parent.mkdir(parents=True)
    out_file.write_text("# فصل ۱\nسلام.", encoding="utf-8")

    with patch("tome.api.routes.translate_book", return_value=([out_file], {"total": 1.2})):
        res = client.post(
            "/api/v1/translate",
            json={"book_dir": str(book_dir), "persian_nlp": True, "llm_model": "gemini-flash-latest"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total_chapters"] == 1
        assert str(out_file) in data["translated_files"]


def test_api_graph(tmp_path: Path):
    chap_dir = tmp_path / "chapters"
    chap_dir.mkdir()
    (chap_dir / "01_chap1.md").write_text("Jacks spoke to Evangeline in the grand hall.", encoding="utf-8")
    (chap_dir / "02_chap2.md").write_text("Evangeline met Jacks and Apollo.", encoding="utf-8")

    gloss_file = tmp_path / "glossary.md"
    gloss_file.write_text(
        "# Glossary\n| Canonical Term | Aliases / Variants | Term Translation | Sample Context | Context Translation |\n"
        "|---|---|---|---|---|\n"
        "| Jacks | Prince of Hearts | جکس | Jacks smiled | |\n"
        "| Evangeline | Eva | اوانجلین | Evangeline wept | |\n",
        encoding="utf-8",
    )

    res = client.post(
        "/api/v1/graph",
        json={"chapters_dir": str(chap_dir), "glossary_path": str(gloss_file), "book_title": "Test Saga"},
    )
    assert res.status_code == 200
    data = res.json()
    assert Path(data["graph_path"]).exists()
    content = Path(data["graph_path"]).read_text(encoding="utf-8")
    assert "Executive Character & Relationship Dossier" in content
    assert "Jacks" in content
    assert "Evangeline" in content


def test_api_process_with_translate(tmp_path: Path):
    from tome.models import PipelineResult

    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF dummy")
    out_dir = tmp_path / "output"
    book_md = out_dir / "book.md"
    ch1 = out_dir / "Book" / "chapters" / "01_chapter_1.md"
    ch1.parent.mkdir(parents=True)
    ch1.write_text("# Chapter 1", encoding="utf-8")

    trans_ch1 = out_dir / "Book" / "translation" / "01_chapter_1.md"
    trans_ch1.parent.mkdir(parents=True)
    trans_ch1.write_text("# فصل ۱", encoding="utf-8")

    mock_result = PipelineResult(
        book_title="Book",
        full_markdown_path=book_md,
        chapter_paths=[ch1],
        glossary_path=None,
        total_pages=10,
        total_chapters=1,
        entity_count=5,
        timings={"conversion": 1.0},
    )

    with (
        patch("tome.api.routes.run_pipeline", return_value=mock_result),
        patch("tome.api.routes.translate_book", return_value=([trans_ch1], {"translation": 2.0})),
    ):
        res = client.post(
            "/api/v1/process",
            json={
                "pdf_path": str(pdf),
                "output_dir": str(out_dir),
                "translate": True,
                "target_language": "Persian",
                "chapters": "1",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["book_title"] == "Book"
        assert len(data["translated_files"]) == 1
        assert str(trans_ch1) in data["translated_files"]


def test_api_error_handling_404_and_400():
    res = client.post("/api/v1/process", json={"pdf_path": "nonexistent.pdf"})
    assert res.status_code == 404

    res = client.post("/api/v1/convert", json={})
    assert res.status_code == 400

    res = client.post("/api/v1/convert", json={"input_path": "missing.pdf"})
    assert res.status_code == 404

    res = client.post("/api/v1/chapterize", json={"markdown_path": "missing.md"})
    assert res.status_code == 404

    res = client.post("/api/v1/ingest", json={"chapter_file": "missing.md"})
    assert res.status_code == 404

    res = client.post("/api/v1/edit", json={})
    assert res.status_code == 400

    res = client.post("/api/v1/edit", json={"file_path": "missing.md"})
    assert res.status_code == 404

    res = client.post("/api/v1/translate", json={"book_dir": "missing_dir"})
    assert res.status_code == 404

    res = client.post("/api/v1/graph", json={"chapters_dir": "missing_chapters"})
    assert res.status_code == 404

    res = client.post("/api/v1/compile-docx", json={"input_path": "missing_path", "output_docx": "out.docx"})
    assert res.status_code == 404

    res = client.post("/api/v1/metadata", json={"input_file": "missing.md"})
    assert res.status_code == 404


def test_api_metadata_success(tmp_path: Path):
    md = tmp_path / "book.md"
    md.write_text(
        "Title: The Way of Kings\nAuthor: Brandon Sanderson\nPublisher: Tor Books\nISBN: 978-0765326355\nPublished 2010\n\n"
        + ("sword magic dragon spell sorcerer kingdom knight elf fantasy " * 20),
        encoding="utf-8",
    )

    res = client.post("/api/v1/metadata", json={"input_file": str(md), "refine": False})
    assert res.status_code == 200
    data = res.json()
    assert data["title"].lower() == "the way of kings"
    assert "Brandon Sanderson" in data["authors"]
    assert data["year"] == "2010"
    assert data["genre"] == "fantasy"
    assert data["page_count"] >= 1
    assert data["word_count"] > 50


def test_api_images_404():
    res = client.post("/api/v1/images", json={"input_file": "missing.pdf"})
    assert res.status_code == 404


def test_api_images_success(tmp_path: Path):
    import io

    import pymupdf
    from PIL import Image

    pdf_path = tmp_path / "book_with_art.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Some text")

    img = Image.new("RGB", (100, 100), (255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    page.insert_image(pymupdf.Rect(50, 50, 150, 150), stream=buf.getvalue())
    doc.save(str(pdf_path))
    doc.close()

    out_dir = tmp_path / "api_out"
    res = client.post("/api/v1/images", json={"input_file": str(pdf_path), "output_dir": str(out_dir)})
    assert res.status_code == 200
    data = res.json()
    assert data["image_count"] == 1
    assert len(data["images"]) == 1
    assert "image_01_p001.png" in data["images"][0]
    assert data["images_dir"] == str(out_dir / "images")
