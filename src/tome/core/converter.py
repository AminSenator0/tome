from pathlib import Path
from typing import Any

from tome.exceptions import PDFExtractionError


def convert_pdf_to_markdown(
    pdf_path: Path,
    output_dir: Path,
) -> tuple[Path, dict[str, Any]]:
    if not pdf_path.is_file():
        raise PDFExtractionError(f"Target PDF file does not exist: {pdf_path}")

    try:
        import pdf_inspector
    except ImportError as err:
        raise PDFExtractionError("pdf-inspector library is not installed.") from err

    try:
        result = pdf_inspector.process_pdf(str(pdf_path))
    except Exception as err:
        raise PDFExtractionError(f"Failed to inspect PDF: {err}") from err

    base_markdown = getattr(result, "markdown", None)
    if not base_markdown or not base_markdown.strip():
        raise PDFExtractionError(f"No text extracted from PDF: {pdf_path}")

    try:
        items = pdf_inspector.extract_text_with_positions(str(pdf_path))
        pages_res = pdf_inspector.extract_pages_markdown(str(pdf_path))

        page_headings: dict[int, str] = {}
        for it in items:
            raw_text = it.text.strip()
            if it.y > 570 and (
                raw_text.isdigit() or raw_text.startswith("PART ") or raw_text in {"Epilogue", "Prologue"}
            ):
                if raw_text.isdigit():
                    heading = f"# Chapter {raw_text}"
                else:
                    heading = f"# {raw_text}"
                if it.page not in page_headings:
                    page_headings[it.page] = heading

        if page_headings:
            assembled_parts = []
            for p in pages_res.pages:
                h = page_headings.get(p.page)
                page_md = p.markdown.strip()
                if h:
                    assembled_parts.append(f"{h}\n\n{page_md}")
                elif page_md:
                    assembled_parts.append(page_md)
            markdown_text = "\n\n".join(assembled_parts)
        else:
            markdown_text = base_markdown
    except Exception:
        markdown_text = base_markdown

    output_dir.mkdir(parents=True, exist_ok=True)
    full_markdown_file = output_dir / "book.md"
    full_markdown_file.write_text(markdown_text, encoding="utf-8")

    metadata: dict[str, Any] = {
        "pdf_type": getattr(result, "pdf_type", "unknown"),
        "confidence": getattr(result, "confidence", 0.0),
        "page_count": getattr(result, "page_count", 0),
        "char_count": len(markdown_text),
    }

    return full_markdown_file, metadata
