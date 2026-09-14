from pathlib import Path

from fastapi.testclient import TestClient

from tome.api.routes import app
from tome.config import TomeConfig
from tome.core.docx import (
    compile_book_to_docx,
    find_officecli,
    is_rtl_language,
    resolve_font,
    sort_book_markdown_files,
)


def test_find_officecli():
    cli_path = find_officecli()
    assert cli_path.exists()
    assert cli_path.is_file()


def test_platform_binary_name():
    from tome.core.docx import get_platform_binary_name

    name = get_platform_binary_name()
    assert "officecli" in name


def test_platform_binary_name_matrix(monkeypatch):
    import platform

    from tome.core.docx import get_platform_binary_name

    # macOS Apple Silicon
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")
    assert get_platform_binary_name() == "officecli-mac-arm64"

    # macOS Intel
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")
    assert get_platform_binary_name() == "officecli-mac-x64"

    # Linux x64
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")
    assert get_platform_binary_name() == "officecli-linux-x64"

    # Linux ARM64
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(platform, "machine", lambda: "aarch64")
    assert get_platform_binary_name() == "officecli-linux-arm64"

    # Windows x64
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(platform, "machine", lambda: "AMD64")
    assert get_platform_binary_name() == "officecli-win-x64.exe"


def test_is_compatible_officecli_binary(tmp_path, monkeypatch):
    import platform

    from tome.core.docx import is_compatible_officecli_binary

    elf_file = tmp_path / "elf_bin"
    elf_file.write_bytes(b"\x7fELF\x02\x01\x01\x00")

    macho_file = tmp_path / "macho_bin"
    macho_file.write_bytes(b"\xcf\xfa\xed\xfe\x07\x00\x00\x01")

    win_file = tmp_path / "win_bin.exe"
    win_file.write_bytes(b"MZ\x90\x00\x03\x00\x00\x00")

    # On macOS
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    assert is_compatible_officecli_binary(macho_file) is True
    assert is_compatible_officecli_binary(elf_file) is False
    assert is_compatible_officecli_binary(win_file) is False

    # On Linux
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    assert is_compatible_officecli_binary(elf_file) is True
    assert is_compatible_officecli_binary(macho_file) is False
    assert is_compatible_officecli_binary(win_file) is False

    # On Windows
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    assert is_compatible_officecli_binary(win_file) is True
    assert is_compatible_officecli_binary(elf_file) is False
    assert is_compatible_officecli_binary(macho_file) is False


def test_find_soffice_darwin_candidates(monkeypatch, tmp_path):
    import platform
    import shutil

    from tome.core.docx import find_soffice

    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(shutil, "which", lambda cmd: None)

    fake_app_soffice = tmp_path / "Applications" / "LibreOffice.app" / "Contents" / "MacOS" / "soffice"
    fake_app_soffice.parent.mkdir(parents=True, exist_ok=True)
    fake_app_soffice.write_bytes(b"fake binary")
    fake_app_soffice.chmod(0o755)

    res = find_soffice(extra_candidates=[str(fake_app_soffice)])
    assert res == str(fake_app_soffice)


def test_is_rtl_language():
    assert is_rtl_language("Persian") is True
    assert is_rtl_language("Farsi") is True
    assert is_rtl_language("Arabic") is True
    assert is_rtl_language("Urdu") is True
    assert is_rtl_language("English") is False
    assert is_rtl_language("French") is False
    assert is_rtl_language("Spanish") is False


def test_resolve_font():
    fonts_dir = Path("fonts").resolve()
    w_list: list[str] = []

    f1 = resolve_font("B-Nazanin.ttf", fonts_dir, warning_handler=w_list.append)
    assert f1 == "B Nazanin"

    f2 = resolve_font("Vazirmatn.ttf", fonts_dir, warning_handler=w_list.append)
    assert f2 == "Vazirmatn"

    f3 = resolve_font("Times.ttf", fonts_dir, warning_handler=w_list.append)
    assert f3 == "Times New Roman"

    f_default = resolve_font("B-Nazanin.ttf")
    assert f_default == "B Nazanin"

    w_missing: list[str] = []
    f4 = resolve_font("NonExistentFont.ttf", fonts_dir, default_name="FallbackFont", warning_handler=w_missing.append)
    assert f4 == "FallbackFont"
    assert len(w_missing) == 1
    assert "not found" in w_missing[0]


def test_sort_book_markdown_files(tmp_path):
    files = [
        tmp_path / "02_chapter_2.md",
        tmp_path / "01_chapter_1.md",
        tmp_path / "10_chapter_10.md",
        tmp_path / "00_cover.md",
        tmp_path / "conclusion.md",
        tmp_path / "preface.md",
    ]
    for f in files:
        f.write_text("content", encoding="utf-8")

    sorted_files = sort_book_markdown_files(files)
    stems = [f.stem for f in sorted_files]
    assert stems == [
        "00_cover",
        "preface",
        "01_chapter_1",
        "02_chapter_2",
        "10_chapter_10",
        "conclusion",
    ]


def test_compile_book_to_docx_directory(tmp_path):
    book_dir = tmp_path / "manuscript"
    book_dir.mkdir()

    (book_dir / "00_cover.md").write_text("# نغمه آتش و یخ\n\nنویسنده: جورج آر. آر. مارتین\n", encoding="utf-8")
    (book_dir / "01_chapter_1.md").write_text(
        "# فصل ۱: وینترفل\n\nبرن استارک از فراز برج‌ها به دوردست‌ها نگریست.\n\n«زمستان در راه است.»\n",
        encoding="utf-8",
    )
    (book_dir / "02_chapter_2.md").write_text(
        "# فصل ۲: آن سوی دیوار\n\nسرمای استخوان‌سوزی در جنگل پرسه می‌زد.\n",
        encoding="utf-8",
    )

    out_docx = tmp_path / "complete_book.docx"
    events = []

    def obs(ev, data):
        events.append((ev, data))

    cfg = TomeConfig(target_language="Persian", eastern_font="B-Nazanin.ttf")
    res = compile_book_to_docx(book_dir, out_docx, config=cfg, title="نغمه آتش و یخ", observer=obs)

    assert res.exists()
    assert res.stat().st_size > 0
    assert any(e[0] == "docx_compilation_start" for e in events)
    assert any(e[0] == "docx_compilation_complete" for e in events)

    merged_md = tmp_path / "translation.md"
    assert merged_md.exists()
    merged_text = merged_md.read_text(encoding="utf-8")
    assert "فصل ۱: وینترفل" in merged_text
    assert "فصل ۲: آن سوی دیوار" in merged_text


def test_compile_book_to_docx_western(tmp_path):
    book_dir = tmp_path / "western_book"
    book_dir.mkdir()

    (book_dir / "chapter_1.md").write_text(
        "# Chapter 1: The Departure\n\nThe morning was cold and damp as Jack packed his satchel.\n",
        encoding="utf-8",
    )

    out_docx = tmp_path / "western.docx"
    cfg = TomeConfig(target_language="English", western_font="Times.ttf")
    res = compile_book_to_docx(book_dir, out_docx, config=cfg, title="Western Saga")

    assert res.exists()
    assert res.stat().st_size > 0


def test_api_compile_docx(tmp_path):
    doc_dir = tmp_path / "api_doc"
    doc_dir.mkdir()
    (doc_dir / "ch1.md").write_text("# فصل اول\n\nمتن نمونه برای بررسی خروجی ورد.\n", encoding="utf-8")

    client = TestClient(app)
    out_docx = tmp_path / "api_output.docx"

    resp = client.post(
        "/api/v1/compile-docx",
        json={
            "input_path": str(doc_dir),
            "output_docx": str(out_docx),
            "title": "کتاب نمونه",
            "target_language": "Persian",
            "eastern_font": "Vazirmatn.ttf",
            "western_font": "Times.ttf",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["file_count"] == 1
    assert Path(data["output_docx"]).exists()


def test_compile_book_to_docx_single_file(tmp_path):
    single_file = tmp_path / "standalone.md"
    single_file.write_text("# Lone Chapter\nOnly one chapter to compile.\n", encoding="utf-8")
    out_docx = tmp_path / "single.docx"

    res = compile_book_to_docx(single_file, out_docx)
    assert res.exists()
    assert res.stat().st_size > 0


def test_compile_book_to_docx_empty_directory_error(tmp_path):
    import pytest

    empty_dir = tmp_path / "empty_chapters"
    empty_dir.mkdir()
    out_docx = tmp_path / "fail.docx"

    with pytest.raises(ValueError, match="No non-empty Markdown files found"):
        compile_book_to_docx(empty_dir, out_docx)


def test_compile_book_to_docx_nonexistent_input_error(tmp_path):
    import pytest

    missing_path = tmp_path / "does_not_exist"
    out_docx = tmp_path / "fail.docx"

    with pytest.raises(ValueError, match="Markdown file not found or empty"):
        compile_book_to_docx(missing_path, out_docx)


def test_sanitize_markdown_formatting_and_lists():
    from tome.core.docx import sanitize_markdown_for_typesetting

    raw = """# فهرست

< u >صفحۀ عنوان< /u >< u >اطلاعات حق نشر< /u >

< u >۱. گوی‌های برفی و کلوچه‌های مادربزرگ< /u >
< u >۲. شب پیش شب تعطیلات بزرگ< /u >
<u>3. Third Chapter</u>
"""
    cleaned = sanitize_markdown_for_typesetting(raw)
    assert "< u >" not in cleaned
    assert "< /u >" not in cleaned
    assert "<u>صفحۀ عنوان</u>" in cleaned
    assert "<u>اطلاعات حق نشر</u>" in cleaned
    assert "۱. <u>گوی‌های برفی و کلوچه‌های مادربزرگ</u>" in cleaned
    assert "۲. <u>شب پیش شب تعطیلات بزرگ</u>" in cleaned
    assert "3. <u>Third Chapter</u>" in cleaned


def test_convert_inline_formatting_xml():
    from tome.core.docx import _convert_inline_formatting_xml

    sample = (
        "<w:p>"
        '<w:r><w:rPr /><w:t xml:space="preserve">&lt;u&gt;Underlined text&lt;/u&gt;</w:t></w:r>'
        '<w:r><w:rPr><w:b /></w:rPr><w:t xml:space="preserve">Normal &lt;s&gt;Strikethrough&lt;/s&gt;</w:t></w:r>'
        "</w:p>"
    )
    result = _convert_inline_formatting_xml(sample)
    assert '<w:u w:val="single"/>' in result
    assert "Underlined text" in result
    assert "<w:strike/>" in result
    assert "Strikethrough" in result
    assert "&lt;u&gt;" not in result
    assert "&lt;s&gt;" not in result


def test_resolve_book_title_directory_fallback(tmp_path: Path):
    from tome.core.docx import _resolve_book_title

    book_dir = tmp_path / "My Amazing Novel"
    trans_dir = book_dir / "translation"
    trans_dir.mkdir(parents=True)

    assert _resolve_book_title(trans_dir) == "My Amazing Novel"

    meta_file = book_dir / "book_metadata.json"
    meta_file.write_text('{"title": "The Golden Compass"}', encoding="utf-8")
    assert _resolve_book_title(trans_dir) == "The Golden Compass"

    assert _resolve_book_title(trans_dir, title="Custom Title") == "Custom Title"


def test_postprocess_docx_formatting_cleans_translation_header(tmp_path: Path):
    import zipfile

    from tome.core.docx import postprocess_docx_formatting

    book_dir = tmp_path / "Epic Fantasy"
    book_dir.mkdir(parents=True)
    fake_docx = book_dir / "Epic Fantasy.docx"

    with zipfile.ZipFile(fake_docx, "w") as z:
        z.writestr("word/document.xml", "<w:p><w:t>Hello</w:t></w:p>")
        z.writestr("word/header1.xml", '<w:p><w:r><w:t xml:space="preserve">translation</w:t></w:r></w:p>')

    postprocess_docx_formatting(fake_docx)

    with zipfile.ZipFile(fake_docx, "r") as z:
        hdr_xml = z.read("word/header1.xml").decode("utf-8")
        assert "translation" not in hdr_xml
        assert "Epic Fantasy" in hdr_xml


def test_docx_metadata_injection(tmp_path: Path):
    import zipfile

    from tome.core.docx import postprocess_docx_formatting
    from tome.core.metadata import BookMetadata

    book_dir = tmp_path / "SciFi Epic"
    book_dir.mkdir(parents=True)
    docx_file = book_dir / "SciFi Epic.docx"

    initial_core = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        "<dc:title>Old</dc:title>"
        "</cp:coreProperties>"
    )

    with zipfile.ZipFile(docx_file, "w") as z:
        z.writestr("word/document.xml", "<w:p><w:t>Body</w:t></w:p>")
        z.writestr("docProps/core.xml", initial_core)

    meta = BookMetadata(
        title="Dune Messiah",
        authors=["Frank Herbert"],
        genre="science_fiction",
        page_count=350,
        word_count=85000,
        char_count=450000,
        reading_time="6h 15m",
        year="1969",
        publisher="Chilton Books",
        isbn="978-0441172696",
        synopsis="A gripping tale of Paul Atreides.",
        keywords=["dune", "arrakis", "scifi"],
    )

    postprocess_docx_formatting(docx_file, metadata=meta)

    with zipfile.ZipFile(docx_file, "r") as z:
        core_xml = z.read("docProps/core.xml").decode("utf-8")
        assert "Dune Messiah" in core_xml
        assert "Frank Herbert" in core_xml
        assert "Science Fiction" in core_xml
        assert "Book Manuscript Analysis" in core_xml
        assert "A gripping tale of Paul Atreides." in core_xml
        assert "dune, arrakis, scifi" in core_xml
        assert "docProps/custom.xml" in z.namelist()
        custom_xml = z.read("docProps/custom.xml").decode("utf-8")
        assert "Dune Messiah" in custom_xml
        assert "Frank Herbert" in custom_xml
        assert "85000" in custom_xml


def test_convert_docx_to_pdf_conversion(tmp_path: Path):
    import shutil

    from tome.core.docx import convert_docx_to_pdf

    docx_path = Path("output/The Ballad of Never After/The Ballad of Never After.docx")
    if docx_path.exists() and (shutil.which("soffice") or shutil.which("libreoffice")):
        target_pdf = tmp_path / "test_output.pdf"
        obs_events = []
        res = convert_docx_to_pdf(docx_path, output_pdf=target_pdf, observer=lambda ev, d: obs_events.append(ev))
        assert res is not None
        assert res.exists()
        assert res.stat().st_size > 0
        assert "pdf_compilation_start" in obs_events
        assert "pdf_compilation_complete" in obs_events
