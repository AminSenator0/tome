from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tome.core.converter import convert_pdf_to_markdown
from tome.exceptions import PDFExtractionError


def test_convert_pdf_to_markdown_success(tmp_path: Path):
    mock_result = MagicMock()
    mock_result.markdown = "# Book Title\n\nChapter 1 text"
    mock_result.pdf_type = "text_based"
    mock_result.confidence = 0.98
    mock_result.page_count = 50

    mock_pdf_inspector = MagicMock()
    mock_pdf_inspector.process_pdf.return_value = mock_result

    with patch.dict("sys.modules", {"pdf_inspector": mock_pdf_inspector}):
        pdf_file = tmp_path / "sample.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 dummy content")
        out_file, metadata = convert_pdf_to_markdown(pdf_file, tmp_path)

        assert out_file.exists()
        assert out_file.read_text(encoding="utf-8") == "# Book Title\n\nChapter 1 text"
        assert metadata["page_count"] == 50
        assert metadata["pdf_type"] == "text_based"


def test_convert_pdf_nonexistent(tmp_path: Path):
    with pytest.raises(PDFExtractionError):
        convert_pdf_to_markdown(tmp_path / "nonexistent.pdf", tmp_path)


def test_convert_pdf_empty_extracted_text(tmp_path: Path):
    mock_result = MagicMock()
    mock_result.markdown = "   \n\t  "
    mock_pdf_inspector = MagicMock()
    mock_pdf_inspector.process_pdf.return_value = mock_result

    with patch.dict("sys.modules", {"pdf_inspector": mock_pdf_inspector}):
        pdf_file = tmp_path / "blank.pdf"
        pdf_file.write_bytes(b"%PDF dummy")
        with pytest.raises(PDFExtractionError, match="No text extracted"):
            convert_pdf_to_markdown(pdf_file, tmp_path)


def test_convert_pdf_inspection_crash(tmp_path: Path):
    mock_pdf_inspector = MagicMock()
    mock_pdf_inspector.process_pdf.side_effect = RuntimeError("PDF parser segfault")

    with patch.dict("sys.modules", {"pdf_inspector": mock_pdf_inspector}):
        pdf_file = tmp_path / "broken.pdf"
        pdf_file.write_bytes(b"%PDF corrupted")
        with pytest.raises(PDFExtractionError, match="Failed to inspect PDF"):
            convert_pdf_to_markdown(pdf_file, tmp_path)
