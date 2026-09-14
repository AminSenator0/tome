from pathlib import Path

from PIL import Image

from tome.core.epub_converter import convert_comic_images_to_pdf


def test_convert_comic_images_to_pdf(tmp_path: Path):
    im_dir = tmp_path / "images"
    im_dir.mkdir()

    img1_path = im_dir / "page_01.png"
    img2_path = im_dir / "page_02.png"

    img1 = Image.new("RGB", (100, 150), color="red")
    img1.save(img1_path)

    img2 = Image.new("RGB", (100, 150), color="blue")
    img2.save(img2_path)

    out_pdf = tmp_path / "comic.pdf"
    res = convert_comic_images_to_pdf([img1_path, img2_path], out_pdf)

    assert res.exists()
    assert res.stat().st_size > 500


def test_convert_comic_images_empty_list():
    import pytest

    from tome.core.epub_converter import ConversionError

    with pytest.raises(ConversionError, match="No images found"):
        convert_comic_images_to_pdf([], Path("out.pdf"))


def test_convert_comic_images_corrupt_files(tmp_path: Path):
    import pytest

    from tome.core.epub_converter import ConversionError

    corrupt = tmp_path / "broken.png"
    corrupt.write_bytes(b"not a valid png file header")

    with pytest.raises(ConversionError, match="Failed to parse valid images"):
        convert_comic_images_to_pdf([corrupt], tmp_path / "out.pdf")


def test_convert_epub_missing_and_corrupt_file(tmp_path: Path):
    import pytest

    from tome.core.epub_converter import ConversionError, convert_epub_to_pdf

    with pytest.raises(ConversionError, match="Input file not found"):
        convert_epub_to_pdf(tmp_path / "missing.epub")

    corrupt_epub = tmp_path / "corrupt.epub"
    corrupt_epub.write_bytes(b"invalid zip data")
    with pytest.raises(ConversionError, match="Cannot unpack EPUB"):
        convert_epub_to_pdf(corrupt_epub)
