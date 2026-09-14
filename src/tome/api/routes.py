from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from tome.config import TomeConfig
from tome.core.chapterizer import segment_chapters
from tome.core.cleaner import clean_markdown_text
from tome.core.converter import convert_pdf_to_markdown
from tome.core.editor import copyedit_persian_chapter, copyedit_persian_text
from tome.core.epub_converter import convert_epub_to_pdf, convert_mobi_to_pdf
from tome.core.glossary import ingest_chapter_delimiter_entities, write_glossary_markdown
from tome.core.pipeline import run_pipeline
from tome.core.translator import translate_book

app = FastAPI(title="Tome API", version="0.2.0")


class ProcessRequest(BaseModel):
    pdf_path: str
    output_dir: str = "output"
    genre: str = "auto"
    skip_gliner: bool = False
    model: str = "urchade/gliner_medium-v2.1"
    batch_size: int = 16
    fast_mode: bool = False
    keep_raw: bool = False
    persian_nlp: bool = True
    llm_model: str | None = None
    translate: bool = False
    target_language: str | None = None
    chapters: str | int | None = None


class ProcessResponse(BaseModel):
    book_title: str
    full_markdown_path: str
    chapter_paths: list[str]
    glossary_path: str | None = None
    total_pages: int
    total_chapters: int
    entity_count: int
    timings: dict[str, float]
    translated_files: list[str] = []


class ConvertRequest(BaseModel):
    input_path: str | None = None
    pdf_path: str | None = None
    output_dir: str = "output"
    keep_raw: bool = False


class ConvertResponse(BaseModel):
    full_markdown_path: str
    page_count: int
    pdf_type: str
    confidence: float


class ChapterizeRequest(BaseModel):
    markdown_path: str
    output_dir: str = "chapters"
    keep_raw: bool = False


class ChapterizeResponse(BaseModel):
    total_chapters: int
    chapter_slugs: list[str]


class IngestRequest(BaseModel):
    chapter_file: str
    glossary_path: str = "glossary.md"


class IngestResponse(BaseModel):
    ingested_count: int
    glossary_path: str


class EditRequest(BaseModel):
    text: str | None = None
    file_path: str | None = None
    output_path: str | None = None


class EditResponse(BaseModel):
    edited_text: str | None = None
    output_path: str | None = None
    words_processed: int
    words_modified: int
    summary: str


class TranslateRequest(BaseModel):
    book_dir: str
    target_language: str | None = None
    user_style_rules: str | None = None
    chapters: str | int | None = None
    max_chapters: int | None = None
    persian_nlp: bool = True
    llm_model: str | None = None


class TranslateResponse(BaseModel):
    book_dir: str
    total_chapters: int
    translated_files: list[str]
    timings: dict[str, float]


class GraphRequest(BaseModel):
    chapters_dir: str
    glossary_path: str | None = None
    output_path: str | None = None
    book_title: str = "Book"
    top_n: int = 15


class GraphResponse(BaseModel):
    graph_path: str
    top_characters: list[str]


class CompileDocxRequest(BaseModel):
    input_path: str
    output_docx: str | None = None
    title: str | None = None
    target_language: str = "Persian"
    eastern_font: str = "B Nazanin"
    western_font: str = "Times New Roman"
    persian_font: str | None = None


class CompileDocxResponse(BaseModel):
    output_docx: str
    output_pdf: str | None = None
    file_count: int
    title: str


@app.get("/api/v1/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "tome"}


@app.post("/api/v1/process", response_model=ProcessResponse)
def process_book_endpoint(req: ProcessRequest) -> ProcessResponse:
    pdf_file = Path(req.pdf_path)
    if not pdf_file.exists():
        raise HTTPException(status_code=404, detail=f"PDF file not found: {req.pdf_path}")

    config = TomeConfig(
        output_dir=Path(req.output_dir),
        genre=req.genre,
        skip_gliner=req.skip_gliner,
        default_model=req.model,
        batch_size=req.batch_size,
        fast_mode=req.fast_mode,
        keep_raw_artifacts=req.keep_raw,
        persian_nlp=req.persian_nlp,
    )
    if req.llm_model:
        config.llm_model = req.llm_model
    result = run_pipeline(pdf_file, config)
    translated_files: list[str] = []
    if req.translate and result.chapter_paths:
        book_dir = result.chapter_paths[0].parent.parent
        if req.target_language:
            config.target_language = req.target_language
        translated, trans_timings = translate_book(book_dir, config, chapters=req.chapters)
        translated_files = [str(p) for p in translated]
        result.timings.update(trans_timings)

    return ProcessResponse(
        book_title=result.book_title,
        full_markdown_path=str(result.full_markdown_path),
        chapter_paths=[str(p) for p in result.chapter_paths],
        glossary_path=str(result.glossary_path) if result.glossary_path else None,
        total_pages=result.total_pages,
        total_chapters=result.total_chapters,
        entity_count=result.entity_count,
        timings=result.timings,
        translated_files=translated_files,
    )


@app.post("/api/v1/convert", response_model=ConvertResponse)
def convert_endpoint(req: ConvertRequest) -> ConvertResponse:
    target_input = req.input_path or req.pdf_path
    if not target_input:
        raise HTTPException(status_code=400, detail="Either input_path or pdf_path must be provided")

    in_file = Path(target_input)
    if not in_file.exists():
        raise HTTPException(status_code=404, detail=f"Input file not found: {target_input}")

    out_dir = Path(req.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = in_file.suffix.lower()

    if suffix in (".epub", ".mobi", ".azw3", ".cbz", ".cbr"):
        pdf_temp = out_dir / "intermediate.pdf"
        if suffix == ".mobi":
            pdf_path = convert_mobi_to_pdf(in_file, pdf_temp)
        else:
            pdf_path = convert_epub_to_pdf(in_file, pdf_temp)
    elif suffix == ".pdf":
        pdf_path = in_file
    else:
        content = in_file.read_text(encoding="utf-8")
        if not req.keep_raw:
            content = clean_markdown_text(content)
        md_out = out_dir / "book.md"
        md_out.write_text(content, encoding="utf-8")
        return ConvertResponse(
            full_markdown_path=str(md_out),
            page_count=1,
            pdf_type="plain_text",
            confidence=1.0,
        )

    md_path, meta = convert_pdf_to_markdown(pdf_path, out_dir)
    if not req.keep_raw:
        cleaned = clean_markdown_text(md_path.read_text(encoding="utf-8"))
        md_path.write_text(cleaned, encoding="utf-8")

    return ConvertResponse(
        full_markdown_path=str(md_path),
        page_count=meta.get("page_count", 0),
        pdf_type=meta.get("pdf_type", "unknown"),
        confidence=meta.get("confidence", 0.0),
    )


@app.post("/api/v1/chapterize", response_model=ChapterizeResponse)
def chapterize_endpoint(req: ChapterizeRequest) -> ChapterizeResponse:
    md_file = Path(req.markdown_path)
    if not md_file.exists():
        raise HTTPException(status_code=404, detail=f"Markdown file not found: {req.markdown_path}")

    chapters = segment_chapters(
        md_file.read_text(encoding="utf-8"),
        Path(req.output_dir),
        keep_raw_artifacts=req.keep_raw,
    )
    return ChapterizeResponse(
        total_chapters=len(chapters),
        chapter_slugs=[ch.slug for ch in chapters],
    )


@app.post("/api/v1/ingest", response_model=IngestResponse)
def ingest_endpoint(req: IngestRequest) -> IngestResponse:
    ch_path = Path(req.chapter_file)
    if not ch_path.exists():
        raise HTTPException(status_code=404, detail=f"Chapter file not found: {req.chapter_file}")

    cleaned, entities = ingest_chapter_delimiter_entities(ch_path.read_text(encoding="utf-8"))
    ch_path.write_text(cleaned, encoding="utf-8")
    if entities:
        grouped = {e.category: [e] for e in entities}
        write_glossary_markdown(grouped, Path(req.glossary_path))

    return IngestResponse(
        ingested_count=len(entities),
        glossary_path=req.glossary_path,
    )


@app.post("/api/v1/edit", response_model=EditResponse)
def edit_persian_nlp_endpoint(req: EditRequest) -> EditResponse:
    if req.text is not None:
        edited, stats = copyedit_persian_text(req.text)
        out_str = None
        if req.output_path:
            out_p = Path(req.output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(edited, encoding="utf-8")
            out_str = str(out_p)
        return EditResponse(
            edited_text=edited,
            output_path=out_str,
            words_processed=stats.words_processed,
            words_modified=stats.words_modified,
            summary=stats.summary(),
        )

    if req.file_path is not None:
        in_p = Path(req.file_path)
        if not in_p.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {req.file_path}")
        out_p = Path(req.output_path) if req.output_path else None
        res_p, stats = copyedit_persian_chapter(in_p, out_p)
        return EditResponse(
            edited_text=res_p.read_text(encoding="utf-8"),
            output_path=str(res_p),
            words_processed=stats.words_processed,
            words_modified=stats.words_modified,
            summary=stats.summary(),
        )

    raise HTTPException(status_code=400, detail="Either 'text' or 'file_path' must be provided")


@app.post("/api/v1/translate", response_model=TranslateResponse)
def translate_book_endpoint(req: TranslateRequest) -> TranslateResponse:
    b_path = Path(req.book_dir)
    if not b_path.exists():
        raise HTTPException(status_code=404, detail=f"Book directory not found: {req.book_dir}")

    config = TomeConfig.load_config()
    if req.llm_model:
        config.llm_model = req.llm_model
    if req.target_language:
        config.target_language = req.target_language
    if req.user_style_rules:
        config.user_style_rules = req.user_style_rules
    config.persian_nlp = req.persian_nlp

    outputs, timings = translate_book(b_path, config, chapters=req.chapters, max_chapters=req.max_chapters)
    return TranslateResponse(
        book_dir=str(b_path),
        total_chapters=len(outputs),
        translated_files=[str(p) for p in outputs],
        timings=timings,
    )


@app.post("/api/v1/graph", response_model=GraphResponse)
def generate_graph_endpoint(req: GraphRequest) -> GraphResponse:
    chap_dir = Path(req.chapters_dir)
    if not chap_dir.exists():
        raise HTTPException(status_code=404, detail=f"Chapters directory not found: {req.chapters_dir}")

    from tome.core.graph import build_character_graph, load_entities_from_glossary
    from tome.models import Chapter, Entity

    excluded = {"book.md", "full_book.md", "glossary.md", "graph.md", "character_graph.md", "translation.md"}
    chapter_files = sorted([f for f in chap_dir.glob("*.md") if f.name not in excluded])
    if not chapter_files:
        raise HTTPException(status_code=400, detail=f"No chapter markdown files found in: {req.chapters_dir}")

    chapters: list[Chapter] = []
    for idx, cf in enumerate(chapter_files, start=1):
        chapters.append(Chapter(index=idx, title=cf.stem, slug=cf.stem, content=cf.read_text(encoding="utf-8")))

    entities: list[Entity] = []
    g_path = (
        Path(req.glossary_path)
        if req.glossary_path
        else (
            chap_dir.parent / "glossary.md" if (chap_dir.parent / "glossary.md").exists() else chap_dir / "glossary.md"
        )
    )
    if g_path.exists():
        entities = load_entities_from_glossary(g_path)

    out_p = Path(req.output_path) if req.output_path else (chap_dir.parent / "graph.md")
    res_graph = build_character_graph(chapters, entities, out_p, book_title=req.book_title, top_n=req.top_n)

    top_chars: list[str] = [ent.canonical for ent in entities[: req.top_n]]
    return GraphResponse(graph_path=str(res_graph), top_characters=top_chars)


@app.post("/api/v1/compile-docx", response_model=CompileDocxResponse)
def compile_docx_endpoint(req: CompileDocxRequest) -> CompileDocxResponse:
    in_p = Path(req.input_path)
    if not in_p.exists():
        raise HTTPException(status_code=404, detail=f"Input path not found: {req.input_path}")

    from tome.core.docx import compile_book_to_docx

    config = TomeConfig.load_config()
    config.target_language = req.target_language
    config.eastern_font = req.persian_font or req.eastern_font
    config.western_font = req.western_font

    out_p = Path(req.output_docx) if req.output_docx else None
    try:
        res = compile_book_to_docx(in_p, out_p, config=config, title=req.title)
        files = list(in_p.glob("*.md")) if in_p.is_dir() else [in_p]
        pdf_candidate = res.with_suffix(".pdf")
        pdf_out = str(pdf_candidate) if pdf_candidate.exists() else None
        return CompileDocxResponse(
            output_docx=str(res),
            output_pdf=pdf_out,
            file_count=len(files),
            title=req.title or in_p.stem,
        )
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


class MetadataRequest(BaseModel):
    input_file: str
    refine: bool = True


class MetadataResponse(BaseModel):
    title: str
    authors: list[str]
    year: str | None = None
    publisher: str | None = None
    isbn: str | None = None
    page_count: int = 0
    word_count: int = 0
    char_count: int = 0
    reading_time: str = "0m"
    genre: str = "general"
    synopsis: str | None = None
    keywords: list[str] = []


@app.post("/api/v1/metadata", response_model=MetadataResponse)
def metadata_endpoint(req: MetadataRequest) -> MetadataResponse:
    in_path = Path(req.input_file)
    if not in_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {req.input_file}")

    from tome.core.cleaner import clean_markdown_text
    from tome.core.metadata import extract_book_metadata, refine_metadata_with_llm

    config = TomeConfig.load_config()
    config.refine_metadata = req.refine

    ext = in_path.suffix.lower()
    if ext == ".pdf":
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            md_path, meta = convert_pdf_to_markdown(in_path, Path(tmp_dir))
            raw_text = md_path.read_text(encoding="utf-8")
            pages = meta.get("page_count", 0)
    elif ext in (".epub", ".mobi"):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_pdf = Path(tmp_dir) / "converted.pdf"
            if ext == ".mobi":
                pdf_path = convert_mobi_to_pdf(in_path, temp_pdf)
            else:
                pdf_path = convert_epub_to_pdf(in_path, temp_pdf)
            md_path, meta = convert_pdf_to_markdown(pdf_path, Path(tmp_dir))
            raw_text = md_path.read_text(encoding="utf-8")
            pages = meta.get("page_count", 0)
    else:
        raw_text = in_path.read_text(encoding="utf-8", errors="ignore")
        pages = max(1, len(raw_text.split()) // 275)

    sanitized = clean_markdown_text(raw_text)
    detected_genre = config.resolve_genre(sanitized)
    book_meta = extract_book_metadata(sanitized, in_path, page_count=pages, detected_genre=detected_genre)

    if req.refine:
        book_meta = refine_metadata_with_llm(book_meta, in_path, sanitized, config)

    return MetadataResponse(
        title=book_meta.title,
        authors=book_meta.authors,
        year=book_meta.year,
        publisher=book_meta.publisher,
        isbn=book_meta.isbn,
        page_count=book_meta.page_count,
        word_count=book_meta.word_count,
        char_count=book_meta.char_count,
        reading_time=book_meta.reading_time,
        genre=book_meta.genre,
        synopsis=book_meta.synopsis,
        keywords=book_meta.keywords,
    )


class ExtractImagesRequest(BaseModel):
    input_file: str
    output_dir: str | None = None


class ExtractImagesResponse(BaseModel):
    image_count: int
    images: list[str]
    images_dir: str | None = None


@app.post("/api/v1/images", response_model=ExtractImagesResponse)
def extract_images_endpoint(req: ExtractImagesRequest) -> ExtractImagesResponse:
    in_file = Path(req.input_file)
    if not in_file.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {req.input_file}")

    cfg = TomeConfig.load_config()
    out_dir = Path(req.output_dir) if req.output_dir else (cfg.output_dir / in_file.stem)
    from tome.core.images import extract_book_images

    extracted = extract_book_images(in_file, out_dir)
    imgs_dir = str(out_dir / "images") if extracted else None
    return ExtractImagesResponse(
        image_count=len(extracted),
        images=[img.filename for img in extracted],
        images_dir=imgs_dir,
    )
