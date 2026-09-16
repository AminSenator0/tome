import contextlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import warnings
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tome.config import TomeConfig
from tome.core.metadata import clean_filename_title

OFFICECLI_LATEST_BASE = "https://github.com/iOfficeAI/OfficeCLI/releases/latest/download"


def get_platform_binary_name() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "linux":
        if "aarch64" in machine or "arm" in machine:
            return "officecli-linux-arm64"
        return "officecli-linux-x64"
    if system == "darwin":
        if "arm" in machine or "aarch64" in machine:
            return "officecli-mac-arm64"
        return "officecli-mac-x64"
    if system == "windows":
        if "arm" in machine or "aarch64" in machine:
            return "officecli-win-arm64.exe"
        return "officecli-win-x64.exe"
    return "officecli-linux-x64"


def is_compatible_officecli_binary(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        if path.stat().st_size < 4:
            return False
        system = platform.system().lower()
        with open(path, "rb") as f:
            header = f.read(4)
        if system == "darwin":
            macho_headers = {
                b"\xfe\xed\xfa\xce",  # Mach-O 32-bit big-endian
                b"\xce\xfa\xed\xfe",  # Mach-O 32-bit little-endian
                b"\xfe\xed\xfa\xcf",  # Mach-O 64-bit big-endian
                b"\xcf\xfa\xed\xfe",  # Mach-O 64-bit little-endian (Apple Silicon / Intel 64)
                b"\xca\xfe\xba\xbe",  # Mach-O Universal / Fat binary
                b"\xbe\xba\xfe\xca",  # Mach-O Fat binary
            }
            if header not in macho_headers:
                return False
        elif system == "linux":
            if header != b"\x7fELF":
                return False
        elif system == "windows":
            if header[:2] != b"MZ":
                return False
        return True
    except Exception:
        return False


def install_officecli(target_dir: Path | None = None, observer: Callable[[str, Any], None] | None = None) -> Path:
    dest_dir = (target_dir or Path("bin")).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    binary_name = get_platform_binary_name()
    url = f"{OFFICECLI_LATEST_BASE}/{binary_name}"
    dest_file = dest_dir / ("officecli.exe" if platform.system().lower() == "windows" else "officecli")

    if observer:
        observer("officecli_download_start", {"url": url, "dest": str(dest_file)})

    req = urllib.request.Request(url, headers={"User-Agent": "Tome/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest_file, "wb") as out_f:
        shutil.copyfileobj(resp, out_f)

    if platform.system().lower() != "windows":
        os.chmod(dest_file, 0o755)

    if platform.system().lower() == "darwin":
        with contextlib.suppress(Exception):
            subprocess.run(["xattr", "-d", "com.apple.quarantine", str(dest_file)], capture_output=True, check=False)

    if observer:
        observer("officecli_download_complete", {"path": str(dest_file)})

    return dest_file


def find_officecli(auto_install: bool = True, observer: Callable[[str, Any], None] | None = None) -> Path:
    candidates = [
        Path("bin/officecli").resolve(),
        Path(sys.prefix) / "bin" / "officecli",
        Path(__file__).resolve().parent.parent.parent.parent / "bin" / "officecli",
        Path.home() / ".local" / "bin" / "officecli",
        Path.home() / "bin" / "officecli",
        Path("/opt/homebrew/bin/officecli"),
        Path("/usr/local/bin/officecli"),
    ]
    for cand in candidates:
        if cand.exists() and cand.is_file():
            if is_compatible_officecli_binary(cand):
                return cand
            elif cand == Path("bin/officecli").resolve() and auto_install:
                # Existing project binary is from a different OS architecture (e.g. Linux binary on macOS)
                if observer:
                    observer(
                        "officecli_warning",
                        {"warning": f"Existing binary '{cand}' is incompatible with {platform.system()}. Downloading native binary..."},
                    )
                return install_officecli(target_dir=cand.parent, observer=observer)

    which_path = shutil.which("officecli")
    if which_path and is_compatible_officecli_binary(Path(which_path)):
        return Path(which_path).resolve()

    if auto_install:
        return install_officecli(observer=observer)

    raise FileNotFoundError("officecli binary not found or incompatible. Place native officecli in bin/ or ensure it is available in PATH.")


def resolve_font(
    font_value: str,
    fonts_dir: Path | None = None,
    default_name: str = "Times New Roman",
    warning_handler: Callable[[str], None] | None = None,
) -> str:
    raw = (font_value or "").strip()
    if not raw:
        return default_name

    fdir = fonts_dir or Path("fonts").resolve()
    target_path = Path(raw)

    well_known = {
        "b-nazanin": "B Nazanin",
        "bnazanin": "B Nazanin",
        "b nazanin": "B Nazanin",
        "vazirmatn": "Vazirmatn",
        "vazir": "Vazirmatn",
        "times": "Times New Roman",
        "times new roman": "Times New Roman",
    }

    if target_path.suffix.lower() in (".ttf", ".otf", ".woff", ".woff2"):
        if target_path.is_file():
            stem_norm = target_path.stem.lower()
            return well_known.get(stem_norm, target_path.stem.replace("-", " ").replace("_", " "))

        local_cand = fdir / target_path.name
        if local_cand.is_file():
            stem_norm = local_cand.stem.lower()
            return well_known.get(stem_norm, local_cand.stem.replace("-", " ").replace("_", " "))

        if platform.system().lower() == "darwin":
            for sdir in [
                Path("/Library/Fonts"),
                Path("/System/Library/Fonts"),
                Path("/System/Library/Fonts/Supplemental"),
                Path.home() / "Library/Fonts",
            ]:
                scand = sdir / target_path.name
                if scand.is_file():
                    stem_norm = scand.stem.lower()
                    return well_known.get(stem_norm, scand.stem.replace("-", " ").replace("_", " "))

        msg = f"Font file '{raw}' not found in {fdir} or filesystem. Falling back to '{default_name}'."
        if warning_handler:
            warning_handler(msg)
        else:
            warnings.warn(msg, stacklevel=2)
        return default_name

    raw_norm = raw.lower().replace("-", " ")
    if raw_norm in well_known:
        match_name = well_known[raw_norm]
        search_dirs = [fdir]
        if platform.system().lower() == "darwin":
            search_dirs.extend([
                Path("/Library/Fonts"),
                Path("/System/Library/Fonts"),
                Path("/System/Library/Fonts/Supplemental"),
                Path.home() / "Library/Fonts",
            ])
        val_clean = raw_norm.replace(" ", "")
        matched_file = any(
            any(
                val_clean in f.stem.lower().replace("-", "").replace(" ", "")
                or f.stem.lower().replace("-", "").replace(" ", "") in val_clean
                for f in sdir.glob("*.[to]tf")
            )
            for sdir in search_dirs
            if sdir.exists()
        )
        if not matched_file and fdir.exists():
            msg = f"Font '{raw}' not found in {fdir} directory. Document will reference system font."
            if warning_handler:
                warning_handler(msg)
            else:
                warnings.warn(msg, stacklevel=2)
        return match_name

    search_dirs = [fdir]
    if platform.system().lower() == "darwin":
        search_dirs.extend([
            Path("/Library/Fonts"),
            Path("/System/Library/Fonts"),
            Path("/System/Library/Fonts/Supplemental"),
            Path.home() / "Library/Fonts",
        ])
    for sdir in search_dirs:
        if sdir.exists():
            for f in sdir.glob("*.[to]tf"):
                clean_stem = f.stem.lower().replace("-", " ").replace("_", " ")
                if raw_norm in clean_stem or clean_stem in raw_norm:
                    return well_known.get(f.stem.lower(), f.stem.replace("-", " ").replace("_", " "))

    if fdir.exists():
        msg = f"Font '{raw}' not found in {fdir} directory. Document will reference system font."
        if warning_handler:
            warning_handler(msg)
        else:
            warnings.warn(msg, stacklevel=2)

    return raw


def is_rtl_language(language: str) -> bool:
    lang = language.strip().lower()
    return any(rtl in lang for rtl in ("persian", "farsi", "fa", "arabic", "ar", "hebrew", "he", "urdu", "ur"))


def sort_book_markdown_files(files: list[Path]) -> list[Path]:
    def sort_key(p: Path) -> tuple[int, int, str]:
        stem = p.stem.lower()

        if "cover" in stem:
            return (0, 0, stem)
        if any(w in stem for w in ("title", "copyright", "dedication")):
            return (1, 0, stem)
        if any(w in stem for w in ("preface", "foreword", "intro", "prologue", "front_matter")):
            return (2, 0, stem)

        digits = re.findall(r"\d+", stem)
        if digits:
            return (3, int(digits[0]), stem)

        if any(
            w in stem for w in ("epilogue", "conclusion", "afterword", "appendix", "glossary", "references", "منابع")
        ):
            return (5, 0, stem)

        return (4, 0, stem)

    return sorted(files, key=sort_key)


def sanitize_markdown_for_typesetting(content: str) -> str:
    cleaned = content.strip()
    if not cleaned:
        return ""

    glossary_markers = [
        "### واژه‌نامه دزبانه",
        "### واژه‌نامه دو زبانه",
        "### واژه‌نامه دوزبانه",
        "## واژه‌نامه",
        "# واژه‌نامه",
        "## اصطلاحات تخصصی حوزه",
        "### BILINGUAL GLOSSARY",
        "## BILINGUAL GLOSSARY",
        "| Canonical Term |",
    ]
    for marker in glossary_markers:
        if marker in cleaned:
            cleaned = cleaned.split(marker)[0].rstrip()
            cleaned = re.sub(r"\n\s*---\s*$", "", cleaned).rstrip()

    cleaned = re.sub(r"<\s*(/?)\s*([a-zA-Z0-9]+)\s*>", r"<\1\2>", cleaned)
    cleaned = re.sub(r"</u>\s*(?:[،,؛;]?\s*)<u>", "</u>\n\n<u>", cleaned)
    cleaned = re.sub(r"</ins>\s*(?:[،,؛;]?\s*)<ins>", "</ins>\n\n<ins>", cleaned)
    cleaned = re.sub(
        r"(?m)^\s*<([a-zA-Z0-9]+)>\s*([0-9۰-۹]+[.\-:])\s*(.*?)\s*</\1>\s*$",
        r"\2 <\1>\3</\1>",
        cleaned,
    )
    cleaned = re.sub(
        r"(?m)^\s*<([a-zA-Z0-9]+)>\s*([*\-+•])\s*(.*?)\s*</\1>\s*$",
        r"\2 <\1>\3</\1>",
        cleaned,
    )

    cleaned = re.sub(r"(?m)^(?:\s*[-*_]\s*){3,}\s*$", "\n\n*   *   *\n\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    lines = cleaned.splitlines()
    processed_lines: list[str] = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r"^#{1,6}\s+", stripped):
            if processed_lines and processed_lines[-1] != "":
                processed_lines.append("")
            processed_lines.append(stripped)
            if i + 1 < len(lines) and lines[i + 1].strip() != "":
                processed_lines.append("")
        elif re.match(r"^\s*[-*+]\s+", line) or re.match(r"^\s*[0-9۰-۹]+\.\s+", line):
            if processed_lines and processed_lines[-1] != "" and not re.match(r"^\s*[-*+0-9۰-۹]", processed_lines[-1]):
                processed_lines.append("")
            processed_lines.append(line)
        else:
            processed_lines.append(line)

    result = "\n".join(processed_lines)
    return re.sub(r"\n{3,}", "\n\n", result).strip() + "\n"


def _convert_inline_formatting_xml(xml: str) -> str:
    def repl_run(m: re.Match) -> str:
        rpr = m.group(1) or ""
        text = m.group(2)
        if not any(tag in text for tag in ("&lt;u&gt;", "&lt;s&gt;", "&lt;del&gt;", "&lt;ins&gt;")):
            return m.group(0)

        base_rpr = rpr.strip()
        if base_rpr.endswith("/>"):
            base_rpr = ""

        tokens = re.split(
            r"(&lt;u&gt;.*?&lt;/u&gt;|&lt;ins&gt;.*?&lt;/ins&gt;|&lt;s&gt;.*?&lt;/s&gt;|&lt;del&gt;.*?&lt;/del&gt;)",
            text,
        )
        out_runs: list[str] = []
        for tok in tokens:
            if not tok:
                continue
            curr_rpr = base_rpr
            u_match = re.match(r"&lt;(?:u|ins)&gt;(.*?)&lt;/(?:u|ins)&gt;", tok)
            s_match = re.match(r"&lt;(?:s|del)&gt;(.*?)&lt;/(?:s|del)&gt;", tok)
            if u_match:
                inner = u_match.group(1)
                if "<w:u" not in curr_rpr:
                    curr_rpr = f'{curr_rpr}<w:u w:val="single"/>'
                out_runs.append(f'<w:r><w:rPr>{curr_rpr}</w:rPr><w:t xml:space="preserve">{inner}</w:t></w:r>')
            elif s_match:
                inner = s_match.group(1)
                if "<w:strike" not in curr_rpr:
                    curr_rpr = f"{curr_rpr}<w:strike/>"
                out_runs.append(f'<w:r><w:rPr>{curr_rpr}</w:rPr><w:t xml:space="preserve">{inner}</w:t></w:r>')
            else:
                if curr_rpr:
                    out_runs.append(f'<w:r><w:rPr>{curr_rpr}</w:rPr><w:t xml:space="preserve">{tok}</w:t></w:r>')
                else:
                    out_runs.append(f'<w:r><w:t xml:space="preserve">{tok}</w:t></w:r>')
        return "".join(out_runs)

    run_pattern = r"<w:r>(?:<w:rPr>(.*?)</w:rPr>|<w:rPr\s*/>)?\s*<w:t[^>]*>(.*?)</w:t>\s*</w:r>"
    xml = re.sub(run_pattern, repl_run, xml)
    return re.sub(r"&lt;/?(?:u|ins|s|del)&gt;", "", xml)


def _resolve_book_title(input_path: Path, title: str | None = None) -> str:
    if title and title.strip():
        t = title.strip()
        if t.lower() not in ("translation", "chapters", "md", "src", "output"):
            return t
    meta_candidates = [
        input_path / "book_metadata.json",
        input_path.parent / "book_metadata.json",
        input_path.parent.parent / "book_metadata.json",
    ]
    for mc in meta_candidates:
        if mc.exists() and mc.is_file():
            with contextlib.suppress(Exception):
                data = json.loads(mc.read_text(encoding="utf-8"))
                if data.get("title") and str(data["title"]).strip().lower() != "translation":
                    return str(data["title"]).strip()
    if input_path.is_dir():
        if input_path.name.lower() in ("translation", "chapters", "md", "src", "output"):
            return clean_filename_title(input_path.parent.name)
        return clean_filename_title(input_path.name)
    else:
        if input_path.stem.lower() in ("translation", "book", "full_book", "manuscript"):
            return clean_filename_title(input_path.parent.name)
    return clean_filename_title(input_path.stem)


def _inject_docx_metadata(core_xml: str, custom_xml: str | None, meta: dict[str, Any]) -> tuple[str, str]:
    title = str(meta.get("title", "")).strip()
    authors = meta.get("authors", [])
    author_str = ", ".join(authors) if isinstance(authors, list) else str(authors)
    genre = str(meta.get("genre", "")).replace("_", " ").title()
    page_count = str(meta.get("page_count", 0))
    word_count = str(meta.get("word_count", 0))
    char_count = str(meta.get("char_count", 0))
    reading_time = str(meta.get("reading_time", ""))
    year = str(meta.get("year") or "")
    publisher = str(meta.get("publisher") or "")
    isbn = str(meta.get("isbn") or "")
    synopsis = str(meta.get("synopsis") or "").strip()
    raw_keywords = meta.get("keywords")
    extra_keywords = ", ".join(raw_keywords) if isinstance(raw_keywords, list) and raw_keywords else ""

    description_parts = [
        "Book Manuscript Analysis",
        f"Title: {title}",
        f"Author(s): {author_str}",
        f"Genre: {genre}",
        f"Page Count: {page_count}",
        f"Word Count: {word_count}",
        f"Character Count: {char_count}",
        f"Est. Reading Time: {reading_time}",
    ]
    if year:
        description_parts.append(f"Year: {year}")
    if publisher:
        description_parts.append(f"Publisher: {publisher}")
    if isbn:
        description_parts.append(f"ISBN: {isbn}")
    if synopsis:
        description_parts.append(f"Synopsis: {synopsis}")
    desc_str = "\n".join(description_parts)

    keywords_parts = [
        f"Genre: {genre}",
        f"Pages: {page_count}",
        f"Words: {word_count}",
        f"Reading Time: {reading_time}",
    ]
    if extra_keywords:
        keywords_parts.append(extra_keywords)
    keywords_str = ", ".join(keywords_parts)

    ET.register_namespace("cp", "http://schemas.openxmlformats.org/package/2006/metadata/core-properties")
    ET.register_namespace("dc", "http://purl.org/dc/elements/1.1/")
    ET.register_namespace("dcterms", "http://purl.org/dc/terms/")
    ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")

    core_root = ET.fromstring(core_xml)
    dc_ns = "http://purl.org/dc/elements/1.1/"
    cp_ns = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"

    def _set_or_create(root_el, tag, text_val):
        el = root_el.find(tag)
        if el is None:
            el = ET.SubElement(root_el, tag)
        el.text = text_val

    if title:
        _set_or_create(core_root, f"{{{dc_ns}}}title", title)
    if author_str:
        _set_or_create(core_root, f"{{{dc_ns}}}creator", author_str)
    if desc_str:
        _set_or_create(core_root, f"{{{dc_ns}}}description", desc_str)
    if genre:
        _set_or_create(core_root, f"{{{dc_ns}}}subject", genre)
        _set_or_create(core_root, f"{{{cp_ns}}}category", genre)
    if keywords_str:
        _set_or_create(core_root, f"{{{cp_ns}}}keywords", keywords_str)
    _set_or_create(core_root, f"{{{cp_ns}}}lastModifiedBy", "Tome")

    new_core = ET.tostring(core_root, encoding="utf-8", xml_declaration=True).decode("utf-8")

    op_ns = "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
    vt_ns = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"
    fmtid = "{D5CDD505-2E9C-101B-9397-08002B2CF9AE}"

    ET.register_namespace("op", op_ns)
    ET.register_namespace("vt", vt_ns)

    if custom_xml:
        custom_root = ET.fromstring(custom_xml)
    else:
        custom_root = ET.Element(f"{{{op_ns}}}Properties")

    custom_props = [
        ("Title", title),
        ("Authors", author_str),
        ("Genre", genre),
        ("PageCount", page_count),
        ("WordCount", word_count),
        ("CharacterCount", char_count),
        ("ReadingTime", reading_time),
        ("Year", year),
        ("Publisher", publisher),
        ("ISBN", isbn),
        ("Synopsis", synopsis),
        ("Keywords", extra_keywords),
    ]

    existing_names = {p.attrib.get("name") for p in custom_root.findall(f"{{{op_ns}}}property")}
    next_pid = len(custom_root.findall(f"{{{op_ns}}}property")) + 2

    for prop_name, prop_val in custom_props:
        if not prop_val:
            continue
        if prop_name in existing_names:
            for p_el in custom_root.findall(f"{{{op_ns}}}property"):
                if p_el.attrib.get("name") == prop_name:
                    val_el = p_el.find(f"{{{vt_ns}}}lpwstr")
                    if val_el is None:
                        val_el = ET.SubElement(p_el, f"{{{vt_ns}}}lpwstr")
                    val_el.text = prop_val
        else:
            p_el = ET.SubElement(
                custom_root,
                f"{{{op_ns}}}property",
                {"fmtid": fmtid, "pid": str(next_pid), "name": prop_name},
            )
            val_el = ET.SubElement(p_el, f"{{{vt_ns}}}lpwstr")
            val_el.text = prop_val
            next_pid += 1

    new_custom = ET.tostring(custom_root, encoding="utf-8", xml_declaration=True).decode("utf-8")
    return new_core, new_custom


def find_soffice(extra_candidates: list[str] | None = None) -> str | None:
    system = platform.system().lower()
    candidates: list[str | None] = []
    if extra_candidates:
        candidates.extend(extra_candidates)
    candidates.extend([
        shutil.which("soffice"),
        shutil.which("libreoffice"),
    ])
    if system == "darwin":
        candidates.extend([
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
            str(Path.home() / "Applications/LibreOffice.app/Contents/MacOS/soffice"),
            "/opt/homebrew/bin/soffice",
            "/opt/homebrew/bin/libreoffice",
            "/usr/local/bin/soffice",
            "/usr/local/bin/libreoffice",
        ])
    for cand in candidates:
        if cand and Path(cand).is_file() and os.access(cand, os.X_OK):
            return str(cand)
    return None


def convert_docx_to_pdf(
    docx_path: Path,
    output_pdf: Path | None = None,
    observer: Callable[[str, Any], None] | None = None,
) -> Path | None:
    if not docx_path.exists() or docx_path.stat().st_size == 0:
        return None

    target_pdf = output_pdf or docx_path.with_suffix(".pdf")
    orig_dir = docx_path.parent / "original"
    if target_pdf.exists() and target_pdf.is_file():
        orig_copy = orig_dir / target_pdf.name
        if not orig_copy.exists():
            orig_dir.mkdir(parents=True, exist_ok=True)
            with contextlib.suppress(Exception):
                shutil.move(str(target_pdf), str(orig_copy))

    soffice = find_soffice()
    if not soffice:
        if observer:
            observer("docx_warning", {"warning": "Neither LibreOffice nor soffice found. Skipping PDF conversion."})
        return None

    if observer:
        observer("pdf_compilation_start", {"docx": str(docx_path), "pdf": str(target_pdf)})

    cmd = [
        soffice,
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(target_pdf.parent),
        str(docx_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    expected_out = target_pdf.parent / f"{docx_path.stem}.pdf"
    if expected_out.exists() and expected_out != target_pdf:
        expected_out.replace(target_pdf)

    if target_pdf.exists() and target_pdf.stat().st_size > 0:
        if observer:
            observer("pdf_compilation_complete", {"path": str(target_pdf)})
        return target_pdf

    if observer:
        observer("docx_warning", {"warning": f"PDF conversion failed: {res.stderr or res.stdout}"})
    return None


def postprocess_docx_formatting(docx_path: Path, metadata: Any | None = None) -> None:
    if not docx_path.exists() or not zipfile.is_zipfile(docx_path):
        return

    meta_dict: dict[str, Any] | None = None
    if metadata:
        meta_dict = metadata.to_dict() if hasattr(metadata, "to_dict") else dict(metadata)
    else:
        candidates = (docx_path.parent / "metadata.json", docx_path.parent.parent / "metadata.json")
        for c in candidates:
            if c.exists():
                with contextlib.suppress(Exception):
                    meta_dict = json.loads(c.read_text(encoding="utf-8"))
                    break

    temp_docx = docx_path.with_suffix(".tmp.docx")
    try:
        clean_title = _resolve_book_title(docx_path.parent)
        custom_xml_content = None
        with zipfile.ZipFile(docx_path, "r") as zin:
            if "docProps/custom.xml" in zin.namelist():
                custom_xml_content = zin.read("docProps/custom.xml").decode("utf-8")

        new_core_xml = None
        new_custom_xml = None
        with (
            zipfile.ZipFile(docx_path, "r") as zin,
            zipfile.ZipFile(temp_docx, "w", compression=zipfile.ZIP_DEFLATED) as zout,
        ):
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "word/document.xml":
                    xml = data.decode("utf-8")
                    xml = _convert_inline_formatting_xml(xml)
                    data = xml.encode("utf-8")
                elif item.filename.startswith("word/header") and item.filename.endswith(".xml"):
                    xml = data.decode("utf-8")
                    xml = re.sub(
                        r"(<w:t[^>]*>)\s*translation\s*(</w:t>)",
                        rf"\g<1>{clean_title}\g<2>",
                        xml,
                        flags=re.IGNORECASE,
                    )
                    data = xml.encode("utf-8")
                elif item.filename == "docProps/core.xml" and meta_dict:
                    core_xml = data.decode("utf-8")
                    new_core_xml, new_custom_xml = _inject_docx_metadata(core_xml, custom_xml_content, meta_dict)
                    data = new_core_xml.encode("utf-8")
                elif item.filename == "docProps/custom.xml" and meta_dict and new_custom_xml:
                    data = new_custom_xml.encode("utf-8")
                zout.writestr(item, data)

            if meta_dict and new_custom_xml and "docProps/custom.xml" not in zin.namelist():
                zout.writestr("docProps/custom.xml", new_custom_xml.encode("utf-8"))

        temp_docx.replace(docx_path)
    except Exception:
        if temp_docx.exists():
            temp_docx.unlink(missing_ok=True)


def compile_book_to_docx(
    input_path: Path,
    output_docx: Path | None = None,
    config: TomeConfig | None = None,
    title: str | None = None,
    observer: Callable[[str, Any], None] | None = None,
    metadata: Any | None = None,
) -> Path:
    cfg = config or TomeConfig.load_config()
    officecli = find_officecli(auto_install=True, observer=observer)

    excluded_names = {"glossary.md", "graph.md", "book.md", "translation.md", "character_graph.md", "full_book.md"}
    book_title = _resolve_book_title(input_path, title)
    if input_path.is_dir():
        raw_files = [
            f
            for f in input_path.glob("*.md")
            if f.is_file() and f.stat().st_size > 0 and f.name.lower() not in excluded_names
        ]
        if not raw_files:
            raise ValueError(f"No non-empty Markdown files found in directory: {input_path}")
        files = sort_book_markdown_files(raw_files)
        target_out = output_docx or (input_path.parent / f"{book_title}.docx")
    else:
        if not input_path.exists() or input_path.stat().st_size == 0:
            raise ValueError(f"Markdown file not found or empty: {input_path}")
        files = [input_path]
        target_out = output_docx or (input_path.parent / f"{book_title}.docx")

    target_out.parent.mkdir(parents=True, exist_ok=True)

    if observer:
        observer("docx_compilation_start", {"title": book_title, "file_count": len(files), "output": str(target_out)})

    if target_out.exists():
        subprocess.run(
            [str(officecli), "close", str(target_out)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        target_out.unlink()

    def warn_emitter(msg: str) -> None:
        if observer:
            observer("docx_warning", {"warning": msg})
        else:
            warnings.warn(msg, stacklevel=2)

    is_rtl = is_rtl_language(cfg.target_language)
    locale = "fa-IR" if is_rtl else "en-US"
    direction = "rtl" if is_rtl else "ltr"

    font_eastern = resolve_font(cfg.eastern_font, default_name="B Nazanin", warning_handler=warn_emitter)
    font_western = resolve_font(cfg.western_font, default_name="Times New Roman", warning_handler=warn_emitter)

    font_cs = font_eastern if is_rtl else font_western
    font_latin = font_western

    body_size = "14"
    with contextlib.suppress(Exception):
        _tome_size = json.loads(Path("tome.json").read_text(encoding="utf-8")).get("docx_body_size")
        if _tome_size:
            body_size = str(_tome_size)

    align_body = "both"
    align_h1 = "center"
    align_h2 = "right" if is_rtl else "left"

    create_cmd = [str(officecli), "create", str(target_out), "--locale", locale]
    subprocess.run(create_cmd, check=True, capture_output=True)

    margin_val = f"{cfg.margin_cm}cm"

    batch_items: list[dict[str, Any]] = [
        {
            "command": "set",
            "path": "/section[1]",
            "props": {
                "marginTop": margin_val,
                "marginBottom": margin_val,
                "marginLeft": margin_val,
                "marginRight": margin_val,
                "titlePage": "true",
            },
        },
        {
            "command": "set",
            "path": "/styles/Normal",
            "props": {
                "align": align_body,
                "size": body_size,
                "lineSpacing": cfg.line_spacing,
                "spaceAfter": "6pt",
                "firstLineIndent": cfg.paragraph_indent,
                "widowControl": "true",
                "direction": direction,
                "font.cs": font_cs,
                "font.latin": font_latin,
            },
        },
        {
            "command": "add",
            "parent": "/styles",
            "type": "style",
            "props": {
                "id": "Heading1",
                "name": "heading 1",
                "type": "paragraph",
                "font.cs": font_cs,
                "font.latin": font_latin,
                "size": "20",
                "bold": "true",
                "align": align_h1,
                "spaceBefore": "36pt",
                "spaceAfter": "18pt",
                "keepNext": "true",
                "pageBreakBefore": "true" if cfg.heading1_pagebreak else "false",
                "direction": direction,
            },
        },
        {
            "command": "add",
            "parent": "/styles",
            "type": "style",
            "props": {
                "id": "Heading2",
                "name": "heading 2",
                "type": "paragraph",
                "font.cs": font_cs,
                "font.latin": font_latin,
                "size": "15",
                "bold": "true",
                "align": align_h2,
                "spaceBefore": "18pt",
                "spaceAfter": "8pt",
                "keepNext": "true",
                "direction": direction,
            },
        },
        {
            "command": "add",
            "parent": "/styles",
            "type": "style",
            "props": {
                "id": "Heading3",
                "name": "heading 3",
                "type": "paragraph",
                "font.cs": font_cs,
                "font.latin": font_latin,
                "size": "13",
                "bold": "true",
                "align": align_h2,
                "spaceBefore": "12pt",
                "spaceAfter": "4pt",
                "keepNext": "true",
                "direction": direction,
            },
        },
        {
            "command": "add",
            "parent": "/styles",
            "type": "style",
            "props": {
                "id": "Heading4",
                "name": "heading 4",
                "type": "paragraph",
                "font.cs": font_cs,
                "font.latin": font_latin,
                "size": "11",
                "bold": "true",
                "italic": "true",
                "align": align_h2,
                "spaceBefore": "8pt",
                "spaceAfter": "2pt",
                "keepNext": "true",
                "direction": direction,
            },
        },
        {
            "command": "add",
            "parent": "/styles",
            "type": "style",
            "props": {
                "id": "Quote",
                "name": "Quote",
                "type": "paragraph",
                "font.cs": font_cs,
                "font.latin": font_latin,
                "size": "10",
                "italic": "true",
                "spaceBefore": "8pt",
                "spaceAfter": "8pt",
                "lineSpacing": "1.25x",
                "align": "both",
                "direction": direction,
            },
        },
        {
            "command": "add",
            "parent": "/",
            "type": "header",
            "props": {
                "text": book_title,
                "align": "center",
                "direction": direction,
                "font": font_cs if is_rtl else font_latin,
                "size": "10",
            },
        },
        {
            "command": "add",
            "parent": "/",
            "type": "footer",
            "props": {
                "field": "page",
                "align": "center",
                "direction": direction,
                "font": font_cs if is_rtl else font_latin,
                "size": "10",
            },
        },
    ]

    merged_sections: list[str] = []
    temp_files: list[Path] = []
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tf_title:
            tf_title.write(f"# {book_title}\n")
            title_page_path = Path(tf_title.name)
        temp_files.append(title_page_path)
        batch_items.append({"command": "add", "parent": "/", "type": "markdown", "props": {"src": str(title_page_path.resolve())}})
        if not cfg.heading1_pagebreak:
            batch_items.append({"command": "add", "parent": "/", "type": "pagebreak"})

        for idx, file_path in enumerate(files):
            raw_text = file_path.read_text(encoding="utf-8")
            sanitized = sanitize_markdown_for_typesetting(raw_text)

            images_dir = target_out.parent / "images"
            if not images_dir.exists() and (file_path.parent / "images").exists():
                images_dir = file_path.parent / "images"
            elif not images_dir.exists() and (file_path.parent.parent / "images").exists():
                images_dir = file_path.parent.parent / "images"

            if images_dir.exists():
                active_img_dir = images_dir

                def _img_abs_repl(match: re.Match[str], img_dir: Path = active_img_dir) -> str:
                    alt_text = match.group(1)
                    rel_img = match.group(2)
                    img_file = (img_dir / Path(rel_img).name).resolve()
                    if img_file.exists():
                        return f"![{alt_text}]({img_file})"
                    return match.group(0)

                sanitized = re.sub(r"!\[(.*?)\]\((images/[^)]+)\)", _img_abs_repl, sanitized)

            if sanitized.strip():
                merged_sections.append(sanitized.strip())

            with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tf:
                tf.write(sanitized)
                sanitized_path = Path(tf.name)
            temp_files.append(sanitized_path)

            batch_items.append(
                {
                    "command": "add",
                    "parent": "/",
                    "type": "markdown",
                    "props": {"src": str(sanitized_path.resolve())},
                }
            )

            if idx < len(files) - 1 and not cfg.heading1_pagebreak:
                batch_items.append({"command": "add", "parent": "/", "type": "pagebreak"})

        if merged_sections:
            merged_translation_path = target_out.parent / "translation.md"
            merged_translation_path.write_text("\n\n".join(merged_sections).strip() + "\n", encoding="utf-8")

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf_batch:
            json.dump(batch_items, tf_batch, ensure_ascii=False)
            batch_json_path = Path(tf_batch.name)

        try:
            batch_cmd = [str(officecli), "batch", str(target_out), "--input", str(batch_json_path)]
            res = subprocess.run(batch_cmd, capture_output=True, text=True, check=False)
            if res.returncode != 0:
                raise RuntimeError(
                    f"OfficeCLI batch command failed (exit code {res.returncode}): {res.stderr or res.stdout}"
                )
        finally:
            if batch_json_path.exists():
                batch_json_path.unlink()

        save_res = subprocess.run(
            [str(officecli), "save", str(target_out)], capture_output=True, text=True, check=False
        )
        if save_res.returncode != 0:
            raise RuntimeError(f"OfficeCLI save failed: {save_res.stderr or save_res.stdout}")
        subprocess.run(
            [str(officecli), "close", str(target_out)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        postprocess_docx_formatting(target_out, metadata=metadata)
        pdf_path = convert_docx_to_pdf(target_out, observer=observer)

    finally:
        for tmp_f in temp_files:
            if tmp_f.exists():
                tmp_f.unlink(missing_ok=True)

    if observer:
        observer(
            "docx_compilation_complete",
            {
                "path": str(target_out),
                "pdf_path": str(pdf_path) if pdf_path else None,
                "file_count": len(files),
            },
        )

    return target_out
