import contextlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tome.config import TomeConfig


@dataclass
class BookMetadata:
    title: str
    authors: list[str] = field(default_factory=list)
    year: str | None = None
    publisher: str | None = None
    isbn: str | None = None
    page_count: int = 0
    word_count: int = 0
    char_count: int = 0
    reading_time: str = "0m"
    genre: str = "general"
    synopsis: str | None = None
    keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "publisher": self.publisher,
            "isbn": self.isbn,
            "page_count": self.page_count,
            "word_count": self.word_count,
            "char_count": self.char_count,
            "reading_time": self.reading_time,
            "genre": self.genre,
            "synopsis": self.synopsis,
            "keywords": self.keywords,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BookMetadata":
        return cls(
            title=str(data.get("title", "")),
            authors=list(data.get("authors", [])),
            year=data.get("year"),
            publisher=data.get("publisher"),
            isbn=data.get("isbn"),
            page_count=int(data.get("page_count", 0)),
            word_count=int(data.get("word_count", 0)),
            char_count=int(data.get("char_count", 0)),
            reading_time=str(data.get("reading_time", "0m")),
            genre=str(data.get("genre", "general")),
            synopsis=data.get("synopsis"),
            keywords=list(data.get("keywords", [])),
        )


def to_ascii_digits(text: str) -> str:
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    trans = str.maketrans(
        {**{p: str(i) for i, p in enumerate(persian_digits)}, **{a: str(i) for i, a in enumerate(arabic_digits)}}
    )
    return text.translate(trans)


def smart_title(text: str) -> str:
    words = text.split()
    res = []
    for w in words:
        if w.isupper() and len(w) > 1 and w.isalpha():
            res.append(w)
        else:
            res.append(w.title())
    return " ".join(res)


def sanitize_book_title(title: str) -> str:
    cleaned = re.sub(r'[\\/*?:"<>|]', "", title)
    cleaned = cleaned.replace("_", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ._-")
    return cleaned or "Untitled"


def clean_filename_title(path: Path | str) -> str:
    p = Path(path) if isinstance(path, str) else path
    name = p.stem
    name = re.sub(r"https?://\S+|www\.\S+", "", name)
    name = re.sub(r"\[.*?\]|\(.*?\)", "", name)
    name = name.replace("_", " ")
    name = re.sub(
        r"(?i)\b(?:[a-zA-Z0-9_\-\.]+\.(?:com|org|net|ir|co|io|is|ai|me|gg|info|biz|site|xyz|online|top)|archive|library|download|ebook|libgen|pdfdrive)\b.*",
        "",
        name,
    )
    name = re.sub(r",?\s*\b(?:by|نویسنده|اثر|autor|auteur|von)\s+[^\W\d_]+.*$", "", name, flags=re.UNICODE)
    name = re.sub(r",?\s*\b\d+\b.*?(?:[A-Za-z]+,\s*[A-Za-z]+).*$", "", name)
    name = re.sub(r",?\s*\b\d+\s*$", "", name)
    words = name.split()
    half = len(words) // 2
    if half >= 2 and words[:half] == words[half : 2 * half]:
        name = " ".join(words[:half])
    cleaned = re.sub(r"\s+", " ", name).strip()
    return smart_title(cleaned) if cleaned else p.stem


def extract_book_metadata(
    markdown_text: str,
    file_path: Path,
    page_count: int,
    detected_genre: str,
) -> BookMetadata:
    sample = markdown_text[:35000]
    tail = markdown_text[-25000:]
    combined_scope = sample + "\n" + tail
    ascii_scope = to_ascii_digits(combined_scope)

    title_match = re.search(
        r"(?im)^\s*(?:title|book\s*title|عنوان|نام\s*کتاب|عنوان\s*کتاب|عنوان\s*اثر|اسم\s*الكتاب|título|titre|titel)\s*[:：]\s*([^\n\r/|]+)",
        combined_scope,
    )
    if not title_match:
        for line in sample.splitlines()[:50]:
            clean_line = line.strip()
            if clean_line.startswith("# ") and not clean_line.startswith("##"):
                cand = clean_line[2:].strip()
                if not re.search(
                    r"(?i)\b(?:chapter|فصل|part|prologue|epilogue|table of contents|فهرست|contents)\b", cand
                ):
                    title = smart_title(cand)
                    break
        else:
            title = clean_filename_title(file_path)
    else:
        title = smart_title(title_match.group(1).strip())

    authors: list[str] = []
    names_cip_match = re.search(r"(?i)\bNames:\s*([^,\n\r]+,\s*[^,\n\r]+?)(?:,\s*author|\.|\s*$)", combined_scope)
    if names_cip_match:
        raw_cip = names_cip_match.group(1).strip()
        cip_parts = [p.strip() for p in raw_cip.split(",") if p.strip()]
        if len(cip_parts) == 2:
            authors.append(f"{cip_parts[1]} {cip_parts[0]}")
        else:
            authors.append(raw_cip)
    else:
        author_match = re.search(
            r"(?im)^\s*(?:authors?|written\s*by|نویسندگان|نویسنده|پدیدآورنده|نگارش|مؤلف|مولف|به\s*قلم|بقلم|اثر|المؤلف|تأليف|autor(?:es|en)?|escrito\s*por|auteurs?|écrit\s*par|verfasser|von|geschrieben\s*von)\s*[:：]\s*([^\n\r]+)",
            combined_scope,
        )
        if not author_match:
            author_match = re.search(
                r"(?i)Copyright\s*©\s*\d{4}\s+(?:by\s+)?([^\W\d_]+(?:\s+[^\W\d_]+)+)", combined_scope
            )

        if author_match:
            raw_author = author_match.group(1).strip()
            raw_author = re.sub(
                r"(?i)\b(?:author|writer|all rights reserved|rights reserved)\b.*", "", raw_author
            ).strip()
            delimiters = ["&", " and ", " و ", " y ", " et ", " und "]
            split_pattern = "|".join(re.escape(d) for d in delimiters)
            parts = [p.strip() for p in re.split(split_pattern, raw_author) if p.strip()]
            for p in parts:
                if "," in p:
                    subparts = [sp.strip() for sp in p.split(",") if sp.strip()]
                    if len(subparts) == 2:
                        authors.append(f"{subparts[1]} {subparts[0]}")
                    else:
                        authors.append(p)
                else:
                    authors.append(p)
        else:
            by_match = re.search(r"(?im)^\s*(?:by|به قلم|por|par|von)\s+([^\W\d_]+(?:\s+[^\W\d_]+)+)", sample)
            if by_match:
                authors.append(by_match.group(1).strip())
            else:
                authors.append("Unknown")

    year_match = re.search(
        r"(?i)(?:copyright\s*©?|published(?:\s+in)?|سال\s*انتشار|تاریخ\s*انتشار|سال\s*چاپ|چاپ|año|année|jahr|erschienen)\s*[:：]?\s*(\d{4})",
        ascii_scope,
    )
    if not year_match:
        year_match = re.search(r"\b(13\d{2}|14\d{2}|18\d{2}|19\d{2}|20\d{2})\b", ascii_scope)

    publisher_match = re.search(
        r"(?im)^\s*(?:publisher|published\s*by|ناشر|انتشارات|نشر|دار\s*النشر|editorial|publicado\s*por|éditeur|éditions|verlag|herausgeber)\s*[:：]\s*([^\n\r,]+)",
        combined_scope,
    )
    if not publisher_match:
        publisher_match = re.search(
            r"(?im)(?:published by|address|imprint of)\s+([A-Za-z\s]+(?:Books|Press|Publishing|Publishers|House))",
            combined_scope,
        )

    isbn_match = re.search(
        r"\b(?:ISBN(?:-1[03])?|شابک|ردمك)\s*[:：]?\s*(97[89][-\d\s]{10,17}|[\d-]{9,15}[\dX])",
        ascii_scope,
        re.IGNORECASE,
    )

    words = len(markdown_text.split())
    chars = len(markdown_text)
    reading_time = calculate_reading_time(words, chars, image_count=0, language=detected_genre)

    if file_path:
        p = Path(file_path)
        if p.is_file() and p.suffix.lower() in (".pdf", ".epub", ".xps", ".mobi", ".fb2"):
            with contextlib.suppress(Exception):
                import pymupdf

                doc = pymupdf.open(str(p))
                if doc.metadata:
                    pdf_title = str(doc.metadata.get("title") or "").strip()
                    pdf_author = str(doc.metadata.get("author") or "").strip()
                    if pdf_title and not re.match(
                        r"(?i)^(?:microsoft word|untitled|document\d*|scan\d*|calibre)$", pdf_title
                    ):
                        title = pdf_title
                    if pdf_author and authors == ["Unknown"]:
                        authors = [pdf_author]
                doc.close()

    return BookMetadata(
        title=title,
        authors=authors,
        year=year_match.group(1) if year_match else None,
        publisher=publisher_match.group(1).strip() if publisher_match else None,
        isbn=isbn_match.group(1).strip() if isbn_match else None,
        page_count=page_count,
        word_count=words,
        char_count=chars,
        reading_time=reading_time,
        genre=detected_genre,
    )


def calculate_reading_time(
    word_count: int,
    char_count: int = 0,
    image_count: int = 0,
    language: str = "en",
) -> str:
    if word_count <= 0:
        return "1m"

    is_eastern = any("\u0600" <= c <= "\u06ff" for c in language) or language.lower() in (
        "persian",
        "fa",
        "arabic",
        "ar",
    )
    if is_eastern:
        base_wpm = 190.0
    else:
        avg_word_len = (char_count / word_count) if (char_count > 0 and word_count > 0) else 5.0
        if avg_word_len > 6.0:
            base_wpm = 205.0
        elif avg_word_len < 4.5:
            base_wpm = 260.0
        else:
            base_wpm = 238.0

    prose_seconds = (word_count / base_wpm) * 60.0

    image_seconds = 0.0
    for i in range(1, image_count + 1):
        if i <= 10:
            image_seconds += max(3.0, 13.0 - i)
        else:
            image_seconds += 3.0

    total_seconds = prose_seconds + image_seconds
    total_minutes = max(1, round(total_seconds / 60.0))

    hours = total_minutes // 60
    mins = total_minutes % 60
    if hours > 0:
        return f"{hours}h {mins}m" if mins > 0 else f"{hours}h"
    return f"{mins}m"


def save_book_metadata(
    meta: BookMetadata,
    destination_dir: Path,
    log_dir: Path | None = None,
    book_name: str | None = None,
) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    json_path = destination_dir / "metadata.json"
    data_json = json.dumps(meta.to_dict(), indent=2, ensure_ascii=False)
    json_path.write_text(data_json, encoding="utf-8")

    if log_dir and book_name:
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / f"{book_name}_metadata.json").write_text(data_json, encoding="utf-8")

    return json_path


def refine_metadata_with_llm(
    heuristic_meta: BookMetadata,
    input_file: Path,
    sanitized_markdown: str,
    config: "TomeConfig",
    observer: Any = None,
) -> BookMetadata:
    if not getattr(config, "refine_metadata", True) or not getattr(config, "llm_api_key", ""):
        return heuristic_meta

    from tome.config import DEFAULT_PROMPTS
    from tome.core.translator import execute_llm_completion, get_openai_client

    front_sample = sanitized_markdown[:6000].strip()
    chapter_sample = ""
    ch1_match = re.search(
        r"(?:^|\n)(#{1,3}\s+(?:chapter|فصل|part|بخش|1\b|one\b)[^\n]*\n[\s\S]{200,6000})",
        sanitized_markdown,
        re.IGNORECASE,
    )
    if ch1_match:
        chapter_sample = ch1_match.group(1).strip()
    elif len(sanitized_markdown) > 6000:
        chapter_sample = sanitized_markdown[6000:12000].strip()

    cover_b64: str | None = None
    doc_internal_meta: dict[str, Any] = {}
    if input_file.is_file() and input_file.suffix.lower() in (".pdf", ".epub", ".xps", ".mobi", ".fb2"):
        import base64
        import io

        import pymupdf
        from PIL import Image

        with contextlib.suppress(Exception):
            doc = pymupdf.open(str(input_file))
            if doc.metadata:
                doc_internal_meta = {k: v for k, v in doc.metadata.items() if v and isinstance(v, str) and v.strip()}
            for pno in range(min(5, len(doc))):
                page = doc[pno]
                if page.get_images():
                    pix = page.get_pixmap(dpi=150)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    img.thumbnail((800, 800))
                    buf = io.BytesIO()
                    img.convert("RGB").save(buf, format="JPEG", quality=85)
                    cover_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                    break
            doc.close()

    doc_meta_str = json.dumps(doc_internal_meta, ensure_ascii=False, indent=2) if doc_internal_meta else "None"
    metadata_payload = (
        f"<manuscript_filename>\n{input_file.name}\n</manuscript_filename>\n\n"
        f"<document_internal_metadata>\n{doc_meta_str}\n</document_internal_metadata>\n\n"
        f"<extracted_metadata>\n{json.dumps(heuristic_meta.to_dict(), ensure_ascii=False, indent=2)}\n</extracted_metadata>\n\n"
        f"<front_matter>\n{front_sample}\n</front_matter>\n\n"
        f"<chapter_one>\n{chapter_sample}\n</chapter_one>"
    )

    prompt_template = config.prompts.get(
        "metadata_refinement_system_prompt",
        DEFAULT_PROMPTS["metadata_refinement_system_prompt"],
    )
    system_prompt = prompt_template.replace("{metadata}", metadata_payload)

    user_content: Any
    if cover_b64:
        user_content = [
            {
                "type": "text",
                "text": "Clean, verify, and output the finalized JSON metadata record now. Inspect the attached cover image and document metadata to verify the true authorial title.",
            },
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{cover_b64}"}},
        ]
    else:
        user_content = "Clean, verify, and output the finalized JSON metadata record now."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    try:
        clean_title = clean_filename_title(input_file)
        client = get_openai_client(config)
        try:
            raw_resp = execute_llm_completion(
                client=client,
                config=config,
                messages=messages,
                observer=observer,
                identifier="metadata_refinement",
                book_title=clean_title,
            )
        except Exception:
            if cover_b64:
                messages[1] = {
                    "role": "user",
                    "content": "Clean, verify, and output the finalized JSON metadata record now.",
                }
                raw_resp = execute_llm_completion(
                    client=client,
                    config=config,
                    messages=messages,
                    observer=observer,
                    identifier="metadata_refinement",
                    book_title=clean_title,
                )
            else:
                raise
        cleaned_json = raw_resp.strip()
        if cleaned_json.startswith("```"):
            cleaned_json = re.sub(r"^```(?:json)?\s*", "", cleaned_json)
            cleaned_json = re.sub(r"\s*```$", "", cleaned_json)

        data = json.loads(cleaned_json)
        if not isinstance(data, dict):
            return heuristic_meta

        title = str(data.get("title") or "").strip() or heuristic_meta.title
        authors_raw = data.get("authors")
        if isinstance(authors_raw, list) and authors_raw:
            authors = [str(a).strip() for a in authors_raw if str(a).strip()]
        else:
            authors = heuristic_meta.authors

        year = str(data.get("year")).strip() if data.get("year") else heuristic_meta.year
        publisher = str(data.get("publisher")).strip() if data.get("publisher") else heuristic_meta.publisher
        isbn = str(data.get("isbn")).strip() if data.get("isbn") else heuristic_meta.isbn
        genre = str(data.get("genre")).strip() if data.get("genre") else heuristic_meta.genre
        synopsis = str(data.get("synopsis")).strip() if data.get("synopsis") else None
        keywords_raw = data.get("keywords")
        keywords = [str(k).strip() for k in keywords_raw if str(k).strip()] if isinstance(keywords_raw, list) else []

        return BookMetadata(
            title=title,
            authors=authors,
            year=year,
            publisher=publisher,
            isbn=isbn,
            page_count=heuristic_meta.page_count,
            word_count=heuristic_meta.word_count,
            char_count=heuristic_meta.char_count,
            reading_time=heuristic_meta.reading_time,
            genre=genre,
            synopsis=synopsis,
            keywords=keywords,
        )
    except Exception:
        return heuristic_meta
