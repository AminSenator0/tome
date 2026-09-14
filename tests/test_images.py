import io
from pathlib import Path

import pymupdf
from PIL import Image

from tome.core.images import (
    ExtractedImage,
    embed_image_markers_in_markdown,
    extract_book_images,
    is_tile_group,
)


def create_solid_image_bytes(width: int, height: int, color: tuple = (255, 0, 0)) -> bytes:
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_no_images_creates_no_images_folder(tmp_path: Path):
    pdf_path = tmp_path / "text_only.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), "This is a simple text only manuscript with no figures.")
    doc.save(str(pdf_path))
    doc.close()

    out_dir = tmp_path / "output_test"
    out_dir.mkdir(parents=True, exist_ok=True)

    results = extract_book_images(pdf_path, out_dir)
    assert results == []
    assert not (out_dir / "images").exists()


def test_single_image_extracted_and_ordered(tmp_path: Path):
    pdf_path = tmp_path / "with_image.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Chapter 1: The Great Mountain")

    img_bytes = create_solid_image_bytes(150, 150, (0, 100, 200))
    rect = pymupdf.Rect(50, 100, 200, 250)
    page.insert_image(rect, stream=img_bytes)
    doc.save(str(pdf_path))
    doc.close()

    out_dir = tmp_path / "output_single"
    out_dir.mkdir(parents=True, exist_ok=True)

    results = extract_book_images(pdf_path, out_dir)
    assert len(results) == 1
    assert (out_dir / "images").is_dir()
    assert (out_dir / "images" / "image_01_p001.png").is_file()
    assert results[0].page_number == 1
    assert results[0].filename == "image_01_p001.png"


def test_duplicate_repeated_logos_filtered(tmp_path: Path):
    pdf_path = tmp_path / "repeated_logo.pdf"
    doc = pymupdf.open()
    logo_bytes = create_solid_image_bytes(80, 80, (50, 50, 50))

    for i in range(5):
        page = doc.new_page()
        page.insert_text((50, 50), f"Page content {i + 1}")
        page.insert_image(pymupdf.Rect(10, 10, 90, 90), stream=logo_bytes)

    doc.save(str(pdf_path))
    doc.close()

    out_dir = tmp_path / "output_duplicate"
    out_dir.mkdir(parents=True, exist_ok=True)

    results = extract_book_images(pdf_path, out_dir, max_occurrence_rate=3)
    assert results == []
    assert not (out_dir / "images").exists()


def test_tile_group_detection_and_merging(tmp_path: Path):
    rect1 = pymupdf.Rect(50, 100, 200, 200)
    rect2 = pymupdf.Rect(50, 200, 200, 300)
    assert is_tile_group([rect1, rect2]) is True

    non_tiled_1 = pymupdf.Rect(50, 50, 100, 100)
    non_tiled_2 = pymupdf.Rect(400, 600, 450, 650)
    assert is_tile_group([non_tiled_1, non_tiled_2]) is False

    pdf_path = tmp_path / "tiled.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    tile1 = create_solid_image_bytes(150, 100, (255, 0, 0))
    tile2 = create_solid_image_bytes(150, 100, (0, 255, 0))
    page.insert_image(rect1, stream=tile1)
    page.insert_image(rect2, stream=tile2)
    doc.save(str(pdf_path))
    doc.close()

    out_dir = tmp_path / "output_tiled"
    out_dir.mkdir(parents=True, exist_ok=True)

    results = extract_book_images(pdf_path, out_dir)
    assert len(results) == 1
    assert (out_dir / "images" / "image_01_p001.png").exists()


def test_vector_diagram_extracted_when_no_raster(tmp_path: Path):
    pdf_path = tmp_path / "vector_diag.pdf"
    doc = pymupdf.open()
    page = doc.new_page()

    shape = page.new_shape()
    for i in range(20):
        shape.draw_line(pymupdf.Point(100 + i * 5, 100), pymupdf.Point(100 + i * 5, 250))
    shape.finish(color=(0, 0, 0), fill=(0.5, 0.5, 0.5))
    shape.commit()

    doc.save(str(pdf_path))
    doc.close()

    out_dir = tmp_path / "output_vector"
    out_dir.mkdir(parents=True, exist_ok=True)

    results = extract_book_images(pdf_path, out_dir)
    assert len(results) == 1
    assert (out_dir / "images" / "image_01_p001.png").is_file()


def test_embed_image_markers_in_markdown():
    dummy_img = ExtractedImage(
        page_number=2,
        y_position=150.0,
        filename="image_01_p002.png",
        relative_path="images/image_01_p002.png",
        image=Image.new("RGB", (100, 100)),
        snippet="The dragon soared above",
    )

    markdown = """# Chapter 1

The hero rested by the fire.

The dragon soared above the snowy mountain peak.

The journey continued into the valley.
"""

    res = embed_image_markers_in_markdown(markdown, [dummy_img])
    assert "![Illustration](images/image_01_p002.png)" in res
    lines = res.splitlines()
    marker_idx = -1
    dragon_idx = -1
    for idx, l in enumerate(lines):
        if "images/image_01_p002.png" in l:
            marker_idx = idx
        if "The dragon soared above" in l:
            dragon_idx = idx
    assert marker_idx != -1
    assert dragon_idx != -1
    assert marker_idx < dragon_idx


def test_alpha_mask_handling(tmp_path: Path):
    from tome.core.images import extract_base_image_with_alpha

    pdf_path = tmp_path / "transparent_img.pdf"
    doc = pymupdf.open()
    page = doc.new_page()

    rgba = Image.new("RGBA", (100, 100), (255, 0, 0, 128))
    buf = io.BytesIO()
    rgba.save(buf, format="PNG")
    page.insert_image(pymupdf.Rect(50, 50, 150, 150), stream=buf.getvalue())
    doc.save(str(pdf_path))
    doc.close()

    doc2 = pymupdf.open(str(pdf_path))
    images = doc2[0].get_images(full=True)
    assert len(images) >= 1
    xref = images[0][0]
    extracted = extract_base_image_with_alpha(doc2, xref)
    assert extracted is not None
    assert extracted.mode in ("RGBA", "RGB")
    doc2.close()
