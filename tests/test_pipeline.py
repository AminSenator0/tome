from pathlib import Path
from unittest.mock import patch

from tome.config import TomeConfig
from tome.core.pipeline import run_pipeline


def test_pipeline_end_to_end(tmp_path: Path):
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4 dummy content")
    out_dir = tmp_path / "output"

    mock_meta = {
        "page_count": 10,
        "confidence": 0.9,
        "pdf_type": "text_based",
    }
    mock_md = tmp_path / "book.md"
    mock_md.write_text(
        "# Chapter 1\n"
        + ("The knight entered the fortress to break the curse. " * 20)
        + "\n\n# Chapter 2\n"
        + ("The dragon flew over the kingdom. " * 20),
        encoding="utf-8",
    )

    with patch("tome.core.pipeline.convert_pdf_to_markdown", return_value=(mock_md, mock_meta)):
        config = TomeConfig(output_dir=out_dir, skip_gliner=True, refine_metadata=False)
        res = run_pipeline(pdf, config)

        assert res.book_title == "Test"
        assert res.total_pages == 10
        assert res.total_chapters == 2
        assert len(res.chapter_paths) == 2
        assert "conversion" in res.timings
        assert "chapterization" in res.timings
        assert "total" in res.timings


def test_pipeline_direct_markdown_and_text(tmp_path: Path):
    md_file = tmp_path / "sample_book.md"
    md_file.write_text(
        "# Chapter 1\n"
        + ("The brave knight met the wizard in the castle. " * 20)
        + "\n\n# Chapter 2\n"
        + ("The wizard cast a magical spell. " * 20),
        encoding="utf-8",
    )
    config = TomeConfig(output_dir=tmp_path / "out", skip_gliner=True, refine_metadata=False)
    res = run_pipeline(md_file, config)

    assert res.book_title == "Sample Book"
    assert res.total_chapters == 2
    assert res.chapter_paths[0].exists()
    assert res.chapter_paths[1].exists()


def test_pipeline_txt_input_and_observer(tmp_path: Path):
    txt_file = tmp_path / "prose.txt"
    txt_file.write_text(
        "# Chapter 1: The Beginning\n"
        + ("The explorer stepped into the jungle. " * 30)
        + "\n\n# Chapter 2: The Temple\n"
        + ("Ancient runes glowed on the altar. " * 30),
        encoding="utf-8",
    )
    events: list[str] = []

    def observer(event: str, data: dict):
        events.append(event)

    config = TomeConfig(output_dir=tmp_path / "txt_out", skip_gliner=True, refine_metadata=False)
    res = run_pipeline(txt_file, config, observer=observer)

    assert res.book_title == "Prose"
    assert res.total_chapters == 2
    assert "chapterization_complete" in events
    assert "pipeline_complete" in events


def test_pipeline_nonexistent_input_error(tmp_path: Path):
    import pytest

    missing_file = tmp_path / "phantom.pdf"
    config = TomeConfig(output_dir=tmp_path / "out", refine_metadata=False)
    with pytest.raises(FileNotFoundError, match="Input file does not exist"):
        run_pipeline(missing_file, config)


def test_pipeline_empty_file_error(tmp_path: Path):
    import pytest

    from tome.exceptions import TomeError

    empty_md = tmp_path / "empty.md"
    empty_md.write_text("", encoding="utf-8")
    config = TomeConfig(output_dir=tmp_path / "out", refine_metadata=False)
    with pytest.raises((TomeError, ValueError)):
        run_pipeline(empty_md, config)


def test_pipeline_copies_original_file_with_cleaned_name(tmp_path: Path):
    in_file = tmp_path / "Spectacular (Stephanie Garber) (Z-Library).txt"
    in_file.write_text("# Chapter 1\n\nSome great story content here.", encoding="utf-8")
    out_dir = tmp_path / "output"
    config = TomeConfig(output_dir=out_dir, skip_gliner=True, refine_metadata=False)

    run_pipeline(in_file, config)

    dest_dir = out_dir / "Spectacular"
    assert dest_dir.exists()
    cleaned_copy = dest_dir / "original" / "Spectacular.txt"
    assert cleaned_copy.exists()
    assert cleaned_copy.read_text(encoding="utf-8") == in_file.read_text(encoding="utf-8")


def test_pipeline_renames_folder_with_ai_clean_title(tmp_path: Path):
    in_file = tmp_path / "[z-lib.org] Raw Scraped Title 123.md"
    in_file.write_text("# Chapter 1\n\nSome great story content here.", encoding="utf-8")
    out_dir = tmp_path / "output"
    config = TomeConfig(output_dir=out_dir, skip_gliner=True, refine_metadata=True)

    from tome.core.metadata import BookMetadata

    mock_refined = BookMetadata(
        title="The Secret of Focus",
        authors=["John Doe"],
        genre="self_help_psychology",
        synopsis="A powerful guide to deep focus.",
        keywords=["focus", "productivity"],
    )

    with patch("tome.core.metadata.refine_metadata_with_llm", return_value=mock_refined):
        run_pipeline(in_file, config)

    clean_dir = out_dir / "The Secret of Focus"
    assert clean_dir.exists()
    assert (clean_dir / "metadata.json").exists()
    assert (clean_dir / "original" / "The Secret of Focus.md").exists()


def test_pipeline_image_extraction_integration(tmp_path: Path):
    import io

    import pymupdf
    from PIL import Image

    pdf_path = tmp_path / "illustrated_book.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), "# Chapter 1\n\nThe castle was surrounded by dark woods.")

    img = Image.new("RGB", (120, 120), (10, 20, 30))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    page.insert_image(pymupdf.Rect(50, 100, 170, 220), stream=buf.getvalue())
    doc.save(str(pdf_path))
    doc.close()

    out_dir = tmp_path / "output_pipe_img"
    config = TomeConfig(output_dir=out_dir, skip_gliner=True, refine_metadata=False)

    fake_result = type(
        "PDFResult",
        (),
        {
            "markdown": "# Chapter 1\n\nThe castle was surrounded by dark woods.",
            "pdf_type": "text",
            "confidence": 1.0,
            "page_count": 1,
        },
    )()

    with (
        patch("pdf_inspector.process_pdf", return_value=fake_result),
        patch("pdf_inspector.extract_text_with_positions", side_effect=Exception),
    ):
        run_pipeline(pdf_path, config)

    dest_dir = out_dir / "Illustrated Book"
    assert dest_dir.exists()
    assert (dest_dir / "images").exists()
    assert (dest_dir / "images" / "image_01_p001.png").is_file()
    assert "![Illustration](images/image_01_p001.png)" in (dest_dir / "original" / "book.md").read_text(
        encoding="utf-8"
    )
