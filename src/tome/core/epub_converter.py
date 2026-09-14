import shutil
import tempfile
import zipfile
from pathlib import Path

import ebooklib
from ebooklib import epub
from PIL import Image

from tome.exceptions import TomeError


class ConversionError(TomeError):
    pass


def convert_comic_images_to_pdf(image_paths: list[Path], output_pdf: Path) -> Path:
    if not image_paths:
        raise ConversionError("No images found in comic archive.")

    images: list[Image.Image] = []
    first_image: Image.Image | None = None

    for p in image_paths:
        try:
            im = Image.open(p)
            if im.mode != "RGB":
                im = im.convert("RGB")
            if first_image is None:
                first_image = im
            else:
                images.append(im)
        except (OSError, ValueError):
            continue

    if first_image is None:
        raise ConversionError("Failed to parse valid images for comic PDF.")

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    first_image.save(output_pdf, "PDF", resolution=100.0, save_all=True, append_images=images)
    return output_pdf


def convert_epub_to_pdf(input_path: Path, output_pdf: Path | None = None) -> Path:
    if not input_path.exists():
        raise ConversionError(f"Input file not found: {input_path}")

    if output_pdf is None:
        output_pdf = input_path.with_suffix(".pdf")

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)

        try:
            with zipfile.ZipFile(input_path, "r") as z:
                z.extractall(tmp_dir)
        except Exception as err:
            raise ConversionError(f"Cannot unpack EPUB/MOBI container: {err}") from err

        image_extensions = {".jpg", ".jpeg", ".png", ".webp"}
        image_files = sorted(
            [p for p in tmp_dir.rglob("*") if p.suffix.lower() in image_extensions],
            key=lambda x: x.name,
        )

        html_files = [p for p in tmp_dir.rglob("*") if p.suffix.lower() in {".html", ".xhtml", ".htm"}]

        if len(image_files) > 10 and (not html_files or len(image_files) > len(html_files) * 2):
            return convert_comic_images_to_pdf(image_files, output_pdf)

        try:
            book = epub.read_epub(str(input_path))
            html_parts: list[str] = []

            for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
                content = item.get_content().decode("utf-8", errors="ignore")
                html_parts.append(content)

            full_html = (
                "<!DOCTYPE html><html><head><meta charset='utf-8'/><style>"
                "@page { margin: 2cm; } body { font-family: serif; font-size: 11pt; line-height: 1.6; } "
                "img { max-width: 100%; height: auto; } h1, h2 { page-break-before: always; }"
                "</style></head><body>" + "<div class='page-break'></div>".join(html_parts) + "</body></html>"
            )

            import weasyprint

            html_doc = weasyprint.HTML(string=full_html, base_url=str(tmp_dir))
            output_pdf.parent.mkdir(parents=True, exist_ok=True)
            html_doc.write_pdf(target=str(output_pdf))
            return output_pdf

        except Exception:
            if image_files:
                return convert_comic_images_to_pdf(image_files, output_pdf)
            raise ConversionError("Failed to convert EPUB text content to PDF.")


def convert_mobi_to_pdf(input_path: Path, output_pdf: Path | None = None) -> Path:
    if not input_path.exists():
        raise ConversionError(f"Input file not found: {input_path}")

    if output_pdf is None:
        output_pdf = input_path.with_suffix(".pdf")

    import mobi

    extracted_dir, _ = mobi.extract(str(input_path))
    extracted_path = Path(extracted_dir)

    image_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    image_files = sorted(
        [p for p in extracted_path.rglob("*") if p.suffix.lower() in image_extensions],
        key=lambda x: x.name,
    )

    html_files = list(extracted_path.rglob("*.html")) + list(extracted_path.rglob("*.xhtml"))

    if len(image_files) > 10 and (not html_files or len(image_files) > len(html_files) * 2):
        result = convert_comic_images_to_pdf(image_files, output_pdf)
        shutil.rmtree(extracted_dir, ignore_errors=True)
        return result

    if html_files:
        import weasyprint

        html_doc = weasyprint.HTML(filename=str(html_files[0]), base_url=str(extracted_path))
        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        html_doc.write_pdf(target=str(output_pdf))
        shutil.rmtree(extracted_dir, ignore_errors=True)
        return output_pdf

    shutil.rmtree(extracted_dir, ignore_errors=True)
    raise ConversionError("No valid content found in MOBI archive.")
