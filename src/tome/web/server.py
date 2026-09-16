import asyncio
import contextlib
import io
import json
import logging
import os
import re
import secrets
import shutil
import tempfile
import threading
import time
import zipfile
from collections.abc import AsyncGenerator, Callable
from pathlib import Path
from typing import Any

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from tome.config import TomeConfig, detect_genre
from tome.core.chapterizer import segment_chapters
from tome.core.cleaner import clean_markdown_text
from tome.core.converter import convert_pdf_to_markdown
from tome.core.docx import compile_book_to_docx
from tome.core.downloader import ensure_gliner_model
from tome.core.editor import copyedit_persian_text
from tome.core.epub_converter import convert_epub_to_pdf, convert_mobi_to_pdf
from tome.core.extractor import extract_entities
from tome.core.glossary import cluster_entities
from tome.core.graph import build_character_graph
from tome.core.images import extract_book_images
from tome.core.metadata import (
    clean_filename_title,
    extract_book_metadata,
    refine_metadata_with_llm,
    sanitize_book_title,
    save_book_metadata,
)
from tome.core.pipeline import run_pipeline
from tome.core.translator import translate_book
from tome.web.auth import User, auth_manager, get_current_user

app = FastAPI(title="Tome Web API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from fastapi.responses import JSONResponse


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        t0 = time.perf_counter()
        client_ip = request.client.host if request.client else "127.0.0.1"
        method = request.method
        path = request.url.path
        try:
            response = await call_next(request)
            duration = round((time.perf_counter() - t0) * 1000, 2)
            access_logger.info(f'{client_ip} - "{method} {path}" {response.status_code} ({duration}ms)')
            return response
        except Exception:
            duration = round((time.perf_counter() - t0) * 1000, 2)
            error_logger.exception(f"Unhandled error on {method} {path} from {client_ip} ({duration}ms)")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error occurred. Please consult logs/web/error.log."},
            )


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLoggingMiddleware)

access_logger = logging.getLogger("tome.web.access")
access_logger.setLevel(logging.INFO)
security_logger = logging.getLogger("tome.web.security")
security_logger.setLevel(logging.INFO)
error_logger = logging.getLogger("tome.web.error")
error_logger.setLevel(logging.INFO)
logger = logging.getLogger(__name__)

active_tasks: dict[str, dict[str, Any]] = {}
task_event_queues: dict[str, list[asyncio.Queue]] = {}
pipeline_cancel_events: dict[str, Any] = {}


class PipelineCancelled(Exception):
    """Raised internally when the user cancels a running pipeline task."""


def _make_cancelling_observer(task_id: str, observer: Callable[[str, Any], None]) -> Callable[[str, Any], None]:
    def wrapped(event: str, data: Any) -> None:
        ev = pipeline_cancel_events.get(task_id)
        if ev is not None and ev.is_set():
            raise PipelineCancelled(f"Task {task_id} cancelled by user")
        observer(event, data)

    return wrapped


def setup_web_loggers(log_dir: Path) -> None:
    web_dir = log_dir / "web"
    web_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    if not access_logger.handlers:
        h = logging.FileHandler(web_dir / "access.log", encoding="utf-8")
        h.setFormatter(fmt)
        access_logger.addHandler(h)
    if not security_logger.handlers:
        h = logging.FileHandler(web_dir / "security.log", encoding="utf-8")
        h.setFormatter(fmt)
        security_logger.addHandler(h)
    if not error_logger.handlers:
        h = logging.FileHandler(web_dir / "error.log", encoding="utf-8")
        h.setFormatter(fmt)
        error_logger.addHandler(h)


setup_web_loggers(Path("logs"))


class LoginRequest(BaseModel):
    username: str
    password: str


class GenreRequest(BaseModel):
    text: str | None = None
    filename: str | None = None
    book_folder: str | None = None


class ExtractEntitiesRequest(BaseModel):
    text: str = ""
    genre: str = "general"
    model: str = "urchade/gliner_medium-v2.1"
    batch_size: int = 16
    book_folder: str | None = None
    filename: str | None = None


class BuildGraphRequest(BaseModel):
    chapters: list[dict[str, Any]] = []
    entities: list[dict[str, Any]] = []
    title: str = "Book"
    book_folder: str | None = None


class TranslateTextRequest(BaseModel):
    text: str
    target_language: str = "Persian"
    style_rules: str = ""
    glossary: str = ""
    genre: str | None = None
    book_folder: str | None = None


class CopyeditRequest(BaseModel):
    text: str = ""
    persian_nlp: bool = True
    book_folder: str | None = None


class CompileDocxRequest(BaseModel):
    book_title: str
    eastern_font: str = "B Nazanin"
    western_font: str = "Times New Roman"


class PromptUpdateRequest(BaseModel):
    prompts: dict[str, str]


class ConfigUpdateRequest(BaseModel):
    general: dict[str, Any] | None = None
    llm: dict[str, Any] | None = None
    proxy: dict[str, Any] | None = None
    nlp: dict[str, Any] | None = None
    translation: dict[str, Any] | None = None
    typography: dict[str, Any] | None = None


@app.post("/api/auth/login")
async def api_login(req: LoginRequest, request: Request, response: Response) -> dict[str, Any]:
    client_ip = request.client.host if request.client else "127.0.0.1"
    token = auth_manager.authenticate(req.username, req.password, client_ip)
    if not token:
        security_logger.warning(f"Failed login attempt for {req.username} from {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials or account locked due to too many attempts",
        )

    security_logger.info(f"Successful login for {req.username} from {client_ip}")
    response.set_cookie(
        key="session_token",
        value=token,
        max_age=86400 * 7,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return {"token": token, "username": req.username}


@app.get("/api/auth/me")
async def api_me(user: User = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "is_admin": user.is_admin,
    }


@app.post("/api/auth/logout")
async def api_logout(request: Request, response: Response) -> dict[str, str]:
    token = request.cookies.get("session_token")
    if token:
        auth_manager.revoke_session(token)
    response.delete_cookie("session_token")
    return {"status": "ok"}


@app.post("/api/tools/upload")
async def api_upload(file: UploadFile = File(...), user: User = Depends(get_current_user)) -> dict[str, Any]:
    raw_name = Path(file.filename or "uploaded_file").name
    suffix = Path(raw_name).suffix.lower()
    allowed_exts = {".pdf", ".epub", ".mobi", ".md", ".txt"}
    if suffix not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{suffix}'. Allowed formats: {', '.join(sorted(allowed_exts))}",
        )

    config = TomeConfig.load_config()
    safe_name = sanitize_book_title(raw_name) + suffix
    book_slug = clean_filename_title(raw_name)
    book_dir = config.output_dir / book_slug
    if book_dir.exists():
        n = 2
        while (config.output_dir / f"{book_slug}_{n}").exists():
            n += 1
        book_slug = f"{book_slug}_{n}"
        book_dir = config.output_dir / book_slug
    orig_dir = book_dir / "original"
    orig_dir.mkdir(parents=True, exist_ok=True)

    target_orig = orig_dir / safe_name
    content = await file.read()
    target_orig.write_bytes(content)

    # Prepare markdown conversion
    book_md = orig_dir / "book.md"
    try:
        if suffix in (".md", ".txt"):
            book_md.write_bytes(content)
        elif suffix == ".pdf":
            convert_pdf_to_markdown(target_orig, orig_dir)
        elif suffix == ".epub":
            pdf_path = convert_epub_to_pdf(target_orig, orig_dir)
            convert_pdf_to_markdown(pdf_path, orig_dir)
        elif suffix == ".mobi":
            pdf_path = convert_mobi_to_pdf(target_orig, orig_dir)
            convert_pdf_to_markdown(pdf_path, orig_dir)
    except Exception as e:
        logger.warning("Auto-markdown conversion for %s encountered notice: %s", safe_name, e)
        if not book_md.exists():
            with contextlib.suppress(Exception):
                book_md.write_text(content.decode("utf-8", errors="ignore"), encoding="utf-8")

    # Extract metadata immediately with LLM refinement if possible
    meta = None
    try:
        meta = extract_book_metadata(target_orig)
        try:
            meta = refine_metadata_with_llm(target_orig, meta, config=config)
        except Exception as llm_err:
            logger.info("LLM metadata refinement skipped: %s", llm_err)
        save_book_metadata(meta, book_dir)
    except Exception as meta_err:
        logger.warning("Metadata extraction notice for %s: %s", safe_name, meta_err)

    title = meta.title if meta and meta.title else book_slug.replace("_", " ")
    return {
        "filename": safe_name,
        "path": str(book_md.resolve()) if book_md.exists() else str(target_orig.resolve()),
        "book_folder": book_slug,
        "title": title,
        "genre": meta.genre if meta and meta.genre else "general",
    }



def _resolve_manuscript_path(path_str: str | None, config: TomeConfig) -> Path | None:
    if not path_str:
        return None
    p = Path(path_str)
    candidates = [
        p,
        config.output_dir / p,
        config.output_dir / path_str,
        Path.cwd() / p,
    ]
    if p.name == "original":
        candidates.insert(0, p.parent)
        candidates.insert(1, config.output_dir / p.parent.name)

    base_root = Path.cwd().resolve()
    for c in candidates:
        if c.exists():
            resolved = c.resolve()
            # Prevent path traversal
            try:
                resolved.relative_to(base_root)
            except ValueError:
                continue

            if resolved.is_file():
                return resolved
            if resolved.is_dir():
                orig_dir = resolved / "original"
                if orig_dir.exists() and orig_dir.is_dir():
                    for ext in [".pdf", ".epub", ".mobi", ".md", ".txt"]:
                        matches = list(orig_dir.glob(f"*{ext}"))
                        if matches:
                            return matches[0].resolve()
                for name in ["full_book.md", "book.md", "Book.md"]:
                    target = resolved / name
                    if target.exists():
                        return target.resolve()
                chap_dir = resolved / "chapters"
                if chap_dir.exists() and chap_dir.is_dir():
                    chaps = sorted(chap_dir.glob("*.md"))
                    if chaps:
                        return chaps[0].resolve()
                md_files = list(resolved.glob("*.md"))
                if md_files:
                    return md_files[0].resolve()
    return None

@app.post("/api/tools/detect-genre")
async def api_detect_genre(req: GenreRequest, user: User = Depends(get_current_user)) -> dict[str, Any]:
    config = TomeConfig.load_config()
    text = ""
    lookup = req.book_folder or req.filename
    if lookup:
        m_file = _resolve_manuscript_path(lookup, config)
        if m_file and m_file.exists():
            text = m_file.read_text(encoding="utf-8", errors="ignore")[:120000]

    if not text.strip() and req.text:
        text = req.text[:120000]

    detected = detect_genre(text)
    genre = config.resolve_genre(text)
    return {
        "genre": genre,
        "detected": detected,
    }


@app.post("/api/tools/extract-images")
async def api_extract_images(
    file: UploadFile | None = File(None),
    path: str | None = Form(None),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    config = TomeConfig.load_config()
    _cleanup_stale_uploads()
    target_path = None
    temp_dir = None
    if file and file.filename:
        temp_dir = tempfile.mkdtemp()
        p = Path(temp_dir) / file.filename
        p.write_bytes(await file.read())
        target_path = p
    elif path:
        target_path = _resolve_manuscript_path(path, config)

    clean_name = clean_filename_title(Path(path or (file.filename if file else "")))
    out_dir = config.output_dir / clean_name
    out_dir.mkdir(parents=True, exist_ok=True)

    # Check for pre-existing extracted images
    candidate_img_dirs = [out_dir / "images"]
    if target_path:
        candidate_img_dirs.append(target_path.parent / "images")
        candidate_img_dirs.append(target_path.parent.parent / "images")

    for idir in candidate_img_dirs:
        if idir.exists():
            pngs = sorted(idir.glob("*.png"))
            if pngs:
                entries = []
                for idx, f in enumerate(pngs, 1):
                    p_num = idx
                    m = re.search(r"_p(\d+)", f.stem)
                    if m:
                        p_num = int(m.group(1))
                    entries.append({
                        "index": idx,
                        "page_num": p_num,
                        "filename": f.name,
                        "path": str(f),
                        "width": 800,
                        "height": 600,
                        "url": f"/api/books/{clean_name}/images/{f.name}",
                    })
                return {
                    "book_title": clean_name,
                    "count": len(entries),
                    "duration_seconds": 0.0,
                    "images": entries,
                }

    if not target_path or not target_path.exists():
        raise HTTPException(status_code=400, detail="Valid file or path required")

    doc_target = target_path
    if doc_target.suffix.lower() not in (".pdf", ".epub", ".mobi", ".cbz", ".cbr"):
        # Check if original directory has a pdf
        orig_dir = out_dir / "original"
        if orig_dir.exists():
            cand_pdfs = list(orig_dir.glob("*.pdf"))
            if cand_pdfs:
                doc_target = cand_pdfs[0]

    t0 = time.perf_counter()
    images = extract_book_images(doc_target, out_dir)
    duration = round(time.perf_counter() - t0, 2)

    image_entries = []
    for idx, img in enumerate(images, 1):
        fn = getattr(img, "filename", f"img_{idx}.png")
        w = getattr(img.image, "width", 800) if hasattr(img, "image") and img.image else 800
        h = getattr(img.image, "height", 600) if hasattr(img, "image") and img.image else 600
        p_num = getattr(img, "page_number", idx)
        image_entries.append(
            {
                "index": idx,
                "page_num": p_num,
                "filename": fn,
                "path": str(out_dir / "images" / fn),
                "width": w,
                "height": h,
                "url": f"/api/books/{clean_name}/images/{fn}",
            }
        )

    return {
        "book_title": clean_name,
        "count": len(images),
        "duration_seconds": duration,
        "images": image_entries,
    }


@app.get("/api/books/{title}/images/{filename}")
async def api_get_book_image(title: str, filename: str) -> FileResponse:
    config = TomeConfig.load_config()
    clean_title = Path(title).name
    clean_fn = Path(filename).name
    img_path = config.output_dir / clean_title / "images" / clean_fn
    if not img_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(img_path)


def _cleanup_stale_uploads(max_age_seconds: int = 86400) -> None:
    upload_dir = Path("uploads")
    if not upload_dir.exists():
        return
    cutoff = time.time() - max_age_seconds
    for f in upload_dir.iterdir():
        with contextlib.suppress(Exception):
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()


@app.post("/api/tools/extract-metadata")
async def api_extract_metadata(
    file: UploadFile | None = File(None),
    path: str | None = Form(None),
    refine: bool = Form(True),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    config = TomeConfig.load_config()
    _cleanup_stale_uploads()
    target_path = None
    if file and file.filename:
        upload_dir = Path("uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        target_path = upload_dir / Path(file.filename).name
        target_path.write_bytes(await file.read())
    elif path:
        target_path = _resolve_manuscript_path(path, config)

    if not target_path or not target_path.exists():
        clean_name = clean_filename_title(Path(path or ""))
        meta_file = config.output_dir / clean_name / "metadata.json"
        if meta_file.exists():
            try:
                return json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception as e:
                logger.debug("Failed to read cached metadata %s: %s", meta_file, e)
        raise HTTPException(status_code=400, detail="Valid file or path required")

    ext = target_path.suffix.lower()

    if ext in (".pdf", ".epub", ".mobi", ".xps", ".cbz", ".cbr"):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_p = Path(tmp_dir)
            active_pdf = target_path
            if ext == ".epub":
                active_pdf = convert_epub_to_pdf(target_path, tmp_p / "conv.pdf")
            elif ext == ".mobi":
                active_pdf = convert_mobi_to_pdf(target_path, tmp_p / "conv.pdf")
            md_path, meta_dict = convert_pdf_to_markdown(active_pdf, tmp_p)
            raw_text = md_path.read_text(encoding="utf-8")
            pages = meta_dict.get("page_count", 1)
    else:
        raw_text = target_path.read_text(encoding="utf-8", errors="ignore")
        pages = max(1, len(raw_text.split()) // 275)

    sanitized = clean_markdown_text(raw_text)
    detected_genre = config.resolve_genre(sanitized)
    book_meta = extract_book_metadata(sanitized, target_path, page_count=pages, detected_genre=detected_genre)

    if refine:
        book_meta = refine_metadata_with_llm(book_meta, target_path, sanitized, config)

    title = clean_filename_title(target_path)
    dest_dir = config.output_dir / title
    save_book_metadata(book_meta, dest_dir, config.log_dir, title)

    return book_meta.to_dict()


@app.post("/api/tools/convert")
async def api_convert(
    file: UploadFile | None = File(None),
    path: str | None = Form(None),
    keep_raw: bool = Form(False),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    config = TomeConfig.load_config()
    _cleanup_stale_uploads()
    target_path = None
    if file and file.filename:
        upload_dir = Path("uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        target_path = upload_dir / Path(file.filename).name
        target_path.write_bytes(await file.read())
    elif path:
        target_path = _resolve_manuscript_path(path, config)

    if not target_path or not target_path.exists():
        raise HTTPException(status_code=400, detail="Valid file or path required")

    title = clean_filename_title(target_path)
    out_dir = config.output_dir / title / "original"
    out_dir.mkdir(parents=True, exist_ok=True)

    ext = target_path.suffix.lower()
    if ext in (".md", ".txt"):
        raw = target_path.read_text(encoding="utf-8", errors="ignore")
        if not keep_raw:
            raw = clean_markdown_text(raw)
        md_path = out_dir / "book.md"
        md_path.write_text(raw, encoding="utf-8")
        meta = {"page_count": max(1, len(raw.split()) // 275), "confidence": 1.0}
    else:
        working_pdf = target_path
        if ext == ".epub":
            working_pdf = convert_epub_to_pdf(target_path, out_dir / f"{title}_converted.pdf")
        elif ext == ".mobi":
            working_pdf = convert_mobi_to_pdf(target_path, out_dir / f"{title}_converted.pdf")

        md_path, meta = convert_pdf_to_markdown(working_pdf, out_dir)
        raw = md_path.read_text(encoding="utf-8")
        if not keep_raw:
            raw = clean_markdown_text(raw)
            md_path.write_text(raw, encoding="utf-8")

    return {
        "book_title": title,
        "markdown_path": str(md_path),
        "page_count": meta.get("page_count", 1),
        "confidence": meta.get("confidence", 1.0),
        "preview": raw[:2000],
    }


@app.post("/api/tools/chapterize")
async def api_chapterize(
    file: UploadFile | None = File(None),
    markdown: str | None = Form(None),
    path: str | None = Form(None),
    book_title: str = Form("Book"),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    config = TomeConfig.load_config()
    text = markdown or ""
    if file and file.filename:
        text = (await file.read()).decode("utf-8", errors="ignore")
    elif not text.strip() and path:
        m_file = _resolve_manuscript_path(path, config)
        if m_file and m_file.exists():
            text = m_file.read_text(encoding="utf-8", errors="ignore")

    if not text.strip():
        raise HTTPException(status_code=400, detail="Markdown content required")

    config = TomeConfig.load_config()
    title = clean_filename_title(book_title)
    chap_dir = config.output_dir / title / "chapters"
    chapters = segment_chapters(text, chap_dir)

    entries = []
    for ch in chapters:
        ch_path = chap_dir / f"{ch.slug}.md"
        cnt = ch_path.read_text(encoding="utf-8") if ch_path.exists() else ""
        entries.append(
            {
                "slug": ch.slug,
                "title": ch.title,
                "word_count": len(cnt.split()),
                "preview": cnt[:300],
            }
        )

    return {
        "book_title": title,
        "total_chapters": len(chapters),
        "chapter_count": len(chapters),
        "output_dir": str(chap_dir),
        "chapters": entries,
    }


@app.post("/api/tools/extract-entities")
async def api_extract_entities(req: ExtractEntitiesRequest, user: User = Depends(get_current_user)) -> dict[str, Any]:
    config = TomeConfig.load_config()
    text = req.text or ""
    lookup = req.book_folder or req.filename
    if not text.strip() and lookup:
        m_file = _resolve_manuscript_path(lookup, config)
        if m_file and m_file.exists():
            text = m_file.read_text(encoding="utf-8", errors="ignore")[:25000]

    if not text.strip():
        raise HTTPException(status_code=400, detail="Text or valid book required for entity extraction")

    tax = config.get_taxonomy(req.genre)
    raw = extract_entities(text, req.model, tax, batch_size=req.batch_size)
    clustered = cluster_entities(raw)
    return {
        "raw_count": len(raw),
        "clustered": {cat: [e.to_dict() for e in ents] for cat, ents in clustered.items()},
    }


@app.post("/api/tools/build-graph")
async def api_build_graph(req: BuildGraphRequest, user: User = Depends(get_current_user)) -> dict[str, Any]:
    from tome.models import Chapter, Entity

    config = TomeConfig.load_config()
    target_book = req.book_folder or req.title
    clean_title = Path(target_book).name if target_book else "Book"
    book_dir = None
    if target_book:
        for cand in [
            config.output_dir / target_book,
            config.output_dir / clean_title,
            config.output_dir / clean_filename_title(Path(target_book)),
        ]:
            if cand.exists() and cand.is_dir():
                book_dir = cand
                clean_title = cand.name
                break

    chapters: list[Chapter] = []
    entities: list[Entity] = []

    # If book_dir has chapters on disk, load them with their content (matching CLI tome graph main.py:750)
    if book_dir and (book_dir / "chapters").exists():
        for f in sorted((book_dir / "chapters").glob("*.md")):
            chapters.append(
                Chapter(index=len(chapters), title=f.stem, slug=f.stem, content=f.read_text(encoding="utf-8"))
            )
        gloss_path = book_dir / "glossary.md"
        if gloss_path.exists():
            for line in gloss_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("|") and not line.startswith("| Canonical") and not line.startswith("|---"):
                    cols = [c.strip() for c in line.split("|")[1:-1]]
                    if len(cols) >= 2 and cols[0]:
                        aliases = {a.strip() for a in cols[1].split(",") if a.strip() and a != "—"}
                        entities.append(Entity(canonical=cols[0], category="People & Characters", aliases=aliases))

    if not chapters and req.chapters:
        for idx, c in enumerate(req.chapters):
            chapters.append(
                Chapter(
                    index=idx,
                    slug=c.get("slug", f"ch_{idx}"),
                    title=c.get("title", f"Chapter {idx}"),
                    content=c.get("content", c.get("text", "")),
                )
            )

    if not entities and req.entities:
        for ed in req.entities:
            entities.append(
                Entity(
                    canonical=ed.get("canonical", ""),
                    category=ed.get("category", "General"),
                    confidence=ed.get("confidence", 1.0),
                    aliases=set(ed.get("aliases", [])),
                )
            )

    out_file = (book_dir / "graph.md") if book_dir else (config.output_dir / clean_title / "graph.md")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    build_character_graph(chapters, entities, out_file, book_title=clean_title)
    graph_text = out_file.read_text(encoding="utf-8") if out_file.exists() else ""

    return {"graph": graph_text, "graph_markdown": graph_text}


@app.post("/api/tools/translate")
async def api_translate(req: TranslateTextRequest, user: User = Depends(get_current_user)) -> dict[str, Any]:
    config = TomeConfig.load_config()
    config.target_language = req.target_language
    from tome.core.translator import get_openai_client, translate_chapter

    genre = req.genre
    if not genre and req.book_folder:
        for cand in [
            config.output_dir / req.book_folder / "metadata.json",
            config.output_dir / clean_filename_title(Path(req.book_folder)) / "metadata.json",
        ]:
            if cand.exists():
                with contextlib.suppress(Exception):
                    m_data = json.loads(cand.read_text(encoding="utf-8"))
                    genre = m_data.get("genre")
                    if genre:
                        break
    if not genre:
        genre = config.resolve_genre(req.text)

    client = get_openai_client(config)
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_p = Path(tmp_dir)
        in_file = tmp_p / "input.md"
        in_file.write_text(req.text, encoding="utf-8")
        metrics_out: dict[str, Any] = {}
        translated, _ = translate_chapter(
            chapter_path=in_file,
            config=config,
            client=client,
            glossary_content=req.glossary,
            metrics_out=metrics_out,
            genre=genre,
        )

    return {
        "translated": translated,
        "translated_text": translated,
        "metrics": metrics_out,
        "genre": genre,
    }


@app.post("/api/tools/edit")
async def api_edit(req: CopyeditRequest, user: User = Depends(get_current_user)) -> dict[str, Any]:
    config = TomeConfig.load_config()
    text = req.text or ""
    if not text.strip() and req.book_folder:
        book_dir = None
        for cand in [
            config.output_dir / req.book_folder,
            config.output_dir / clean_filename_title(Path(req.book_folder)),
        ]:
            if cand.exists() and cand.is_dir():
                book_dir = cand
                break
        if book_dir:
            for sdir in [book_dir / "translation", book_dir / "chapters"]:
                if sdir.exists():
                    mdfs = sorted(sdir.glob("*.md"))
                    if mdfs:
                        text = mdfs[0].read_text(encoding="utf-8")
                        break

    if not text.strip():
        raise HTTPException(status_code=400, detail="Text required for copyediting")

    t0 = time.perf_counter()
    edited, stats = copyedit_persian_text(text)
    duration = round(time.perf_counter() - t0, 3)
    return {
        "edited_text": edited,
        "normalized": edited,
        "words_processed": stats.words_processed,
        "words_modified": stats.words_modified,
        "changes": stats.modifications,
        "summary": stats.summary(),
        "duration_seconds": duration,
    }


@app.post("/api/tools/compile-docx")
async def api_compile_docx(req: CompileDocxRequest, user: User = Depends(get_current_user)) -> dict[str, Any]:
    config = TomeConfig.load_config()
    if req.eastern_font:
        config.eastern_font = req.eastern_font
    if req.western_font:
        config.western_font = req.western_font

    book_title = req.book_title.strip()
    book_dir = None
    for cand in [
        config.output_dir / book_title,
        config.output_dir / Path(book_title).name,
        config.output_dir / clean_filename_title(Path(book_title)),
        config.output_dir / re.sub(r"[^\w\.-]", "_", book_title).strip("_"),
    ]:
        if cand.exists() and cand.is_dir():
            book_dir = cand
            break

    if not book_dir:
        raise HTTPException(status_code=404, detail=f"Book directory not found for: {book_title}")

    clean_title = book_dir.name
    trans_dir = book_dir / "translation"
    chap_dir = book_dir / "chapters"

    target_input: Path
    if trans_dir.exists() and any(trans_dir.glob("*.md")):
        target_input = trans_dir
    elif chap_dir.exists() and any(chap_dir.glob("*.md")):
        target_input = chap_dir
    elif (book_dir / "original" / "book.md").exists():
        target_input = book_dir / "original" / "book.md"
    elif (book_dir / "full_book.md").exists():
        target_input = book_dir / "full_book.md"
    elif (book_dir / "book.md").exists():
        target_input = book_dir / "book.md"
    else:
        raise HTTPException(status_code=404, detail=f"No Markdown files found to compile in {clean_title}")

    out_docx = book_dir / f"{clean_title}.docx"
    meta_json = book_dir / "metadata.json"
    meta_obj = json.loads(meta_json.read_text(encoding="utf-8")) if meta_json.exists() else None

    compile_book_to_docx(
        input_path=target_input,
        output_docx=out_docx,
        config=config,
        title=clean_title,
        metadata=meta_obj,
    )

    pdf_path = out_docx.with_suffix(".pdf")
    return {
        "docx_path": str(out_docx),
        "pdf_path": str(pdf_path) if pdf_path.exists() else None,
        "docx_url": f"/api/books/{clean_title}/download/docx",
        "pdf_url": f"/api/books/{clean_title}/download/pdf" if pdf_path.exists() else None,
    }


@app.get("/api/books/{title}/quality")
async def api_book_quality(title: str, user: User = Depends(get_current_user)) -> dict[str, Any]:
    config = TomeConfig.load_config()
    clean_title = Path(title).name
    qpath = config.output_dir / clean_title / "quality_scores.json"
    data: dict[str, Any] = {}
    with contextlib.suppress(Exception):
        if qpath.exists():
            data = json.loads(qpath.read_text(encoding="utf-8"))
    return {"book": clean_title, "scores": data}


@app.get("/api/metrics/dashboard")
async def api_metrics_dashboard(user: User = Depends(get_current_user)) -> dict[str, Any]:
    config = TomeConfig.load_config()
    from tome.core.avalai import resolve_exchange_rate

    current_rate = resolve_exchange_rate(config)
    books: list[dict[str, Any]] = []
    totals = {
        "books": 0, "chapters": 0, "tokens": 0, "prompt_tokens": 0,
        "completion_tokens": 0, "reasoning_tokens": 0,
        "cost_toman": 0.0, "cost_usd": 0.0, "cost_toman_current": 0.0, "duration_seconds": 0.0,
    }
    by_model: dict[str, dict[str, Any]] = {}
    output_root = Path(config.output_dir)
    if output_root.is_dir():
        for metrics_file in sorted(output_root.glob("*/metrics.json")):
            with contextlib.suppress(Exception):
                data = json.loads(metrics_file.read_text(encoding="utf-8"))
                folder = metrics_file.parent.name
                chapters = data.get("chapters") or []
                prompt_tokens = sum(int(c.get("prompt_tokens") or 0) for c in chapters)
                completion_tokens = sum(int(c.get("completion_tokens") or 0) for c in chapters)
                reasoning_tokens = sum(int(c.get("reasoning_tokens") or 0) for c in chapters)
                total_tokens = prompt_tokens + completion_tokens + reasoning_tokens
                cost_toman = round(sum(float(c.get("cost_toman") or c.get("cost_irt") or 0) for c in chapters), 2)
                if not chapters:
                    total_tokens = int(data.get("total_tokens") or 0)
                    cost_toman = float(data.get("total_cost_toman") or 0)
                book_rate = float(data.get("exchange_rate") or 70000.0)
                cost_usd = round(cost_toman / book_rate, 6)
                cost_toman_current = round(cost_usd * current_rate, 2)
                duration = float(data.get("total_duration_seconds") or 0)
                model = str(data.get("model") or "unknown")
                entry = {
                    "folder": folder,
                    "title": data.get("book_title") or folder,
                    "model": model,
                    "chapters": len(chapters) or int(data.get("total_chapters") or 0),
                    "tokens": total_tokens,
                    "cost_toman": cost_toman,
                    "cost_usd": cost_usd,
                    "exchange_rate": book_rate,
                    "cost_toman_current": cost_toman_current,
                    "duration_seconds": duration,
                    "updated_at": metrics_file.stat().st_mtime,
                }
                books.append(entry)
                totals["books"] += 1
                totals["chapters"] += entry["chapters"]
                totals["tokens"] += total_tokens
                totals["prompt_tokens"] += prompt_tokens
                totals["completion_tokens"] += completion_tokens
                totals["reasoning_tokens"] += reasoning_tokens
                totals["cost_toman"] = round(totals["cost_toman"] + cost_toman, 2)
                totals["cost_usd"] = round(totals["cost_usd"] + cost_usd, 6)
                totals["cost_toman_current"] = round(totals["cost_toman_current"] + cost_toman_current, 2)
                totals["duration_seconds"] = round(totals["duration_seconds"] + duration, 2)
                m = by_model.setdefault(model, {"model": model, "books": 0, "chapters": 0, "tokens": 0, "cost_toman": 0.0})
                m["books"] += 1
                m["chapters"] += entry["chapters"]
                m["tokens"] += total_tokens
                m["cost_toman"] = round(m["cost_toman"] + cost_toman, 2)

    books.sort(key=lambda b: b["cost_toman"], reverse=True)
    credit = None
    with contextlib.suppress(Exception):
        from tome.core.avalai import get_avalai_credit, is_avalai_endpoint

        base_url = getattr(config, "llm_base_url", None) or ""
        api_key = getattr(config, "llm_api_key", None) or ""
        proxy_url = getattr(config, "proxy_url", None)
        if api_key and is_avalai_endpoint(base_url):
            credit = get_avalai_credit(api_key, proxy_url=proxy_url)
    rate_info = {"auto": False, "auto_value": None, "auto_at": None}
    with contextlib.suppress(Exception):
        tj = json.loads(Path("tome.json").read_text(encoding="utf-8"))
        rate_info = {
            "auto": bool(tj.get("exchange_rate_auto")),
            "auto_value": tj.get("exchange_rate_auto_value"),
            "auto_at": tj.get("exchange_rate_auto_at"),
        }
    return {
        "totals": totals,
        "books": books,
        "models": sorted(by_model.values(), key=lambda x: x["cost_toman"], reverse=True),
        "credit": credit,
        "current_exchange_rate": current_rate,
        "rate_info": rate_info,
        "generated_at": time.time(),
    }


@app.delete("/api/books/{title}")
async def api_delete_book(title: str, user: User = Depends(get_current_user)) -> dict[str, str]:
    config = TomeConfig.load_config()
    clean_title = Path(title).name
    book_dir = config.output_dir / clean_title
    if not book_dir.exists() or not book_dir.is_dir():
        raise HTTPException(status_code=404, detail="Book not found")
    shutil.rmtree(book_dir)
    return {"status": "ok", "deleted": clean_title}


@app.get("/api/books")
async def api_list_books(user: User = Depends(get_current_user)) -> list[dict[str, Any]]:
    config = TomeConfig.load_config()
    books = []
    if not config.output_dir.exists():
        return []

    for item in sorted(config.output_dir.iterdir()):
        if item.is_dir() and item.name not in ("logs", "cache", "uploads"):
            meta_file = item / "metadata.json"
            metrics_file = item / "metrics.json"
            meta_data: dict[str, Any] = {}
            if meta_file.exists():
                with contextlib.suppress(Exception):
                    meta_data = json.loads(meta_file.read_text(encoding="utf-8"))

            metrics_data: dict[str, Any] = {}
            if metrics_file.exists():
                with contextlib.suppress(Exception):
                    metrics_data = json.loads(metrics_file.read_text(encoding="utf-8"))

            chap_dir = item / "chapters"
            trans_dir = item / "translation"
            images_dir = item / "images"
            orig_dir = item / "original"

            orig_file = None
            if orig_dir.exists():
                cand = [f for f in orig_dir.iterdir() if f.is_file() and f.suffix.lower() in (".pdf", ".epub", ".mobi", ".md", ".txt")]
                if cand:
                    orig_file = cand[0].name

            total_chapters = len(list(chap_dir.glob("*.md"))) if chap_dir.exists() else 0
            trans_chapters = len(list(trans_dir.glob("*.md"))) if trans_dir.exists() else 0
            image_count = len(list(images_dir.glob("*.png"))) if images_dir.exists() else 0

            books.append(
                {
                    "folder": item.name,
                    "title": meta_data.get("title", item.name.replace("_", " ")),
                    "authors": meta_data.get("authors", []),
                    "genre": meta_data.get("genre", "general"),
                    "year": meta_data.get("year"),
                    "reading_time": meta_data.get("reading_time"),
                    "page_count": meta_data.get("page_count", 0),
                    "word_count": meta_data.get("word_count", 0),
                    "synopsis": meta_data.get("synopsis", ""),
                    "keywords": meta_data.get("keywords", []),
                    "total_chapters": total_chapters,
                    "translated_chapters": trans_chapters,
                    "image_count": image_count,
                    "has_docx": (item / f"{item.name}.docx").exists(),
                    "has_pdf": (item / f"{item.name}.pdf").exists(),
                    "has_original": orig_file is not None,
                    "original_filename": orig_file,
                    "has_glossary": (item / "glossary.md").exists(),
                    "has_graph": (item / "graph.md").exists(),
                    "has_metrics": metrics_file.exists(),
                    "total_tokens": metrics_data.get("total_tokens", 0),
                    "total_cost_toman": metrics_data.get("total_cost_toman", 0.0),
                }
            )

    return books


@app.get("/api/books/{title}")
async def api_get_book(title: str, user: User = Depends(get_current_user)) -> dict[str, Any]:
    config = TomeConfig.load_config()
    clean_title = Path(title).name
    book_dir = config.output_dir / clean_title
    if not book_dir.exists():
        raise HTTPException(status_code=404, detail="Book not found")

    meta_file = book_dir / "metadata.json"
    meta_data = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}

    metrics_file = book_dir / "metrics.json"
    metrics_data = json.loads(metrics_file.read_text(encoding="utf-8")) if metrics_file.exists() else {}

    chap_dir = book_dir / "chapters"
    trans_dir = book_dir / "translation"

    chapters = []
    if chap_dir.exists():
        for ch_file in sorted(chap_dir.glob("*.md")):
            tr_file = trans_dir / ch_file.name if trans_dir.exists() else None
            is_translated = tr_file.exists() if tr_file else False
            chapters.append(
                {
                    "slug": ch_file.stem,
                    "filename": ch_file.name,
                    "is_translated": is_translated,
                    "word_count": len(ch_file.read_text(encoding="utf-8").split()),
                }
            )

    gloss_file = book_dir / "glossary.md"
    gloss_content = gloss_file.read_text(encoding="utf-8") if gloss_file.exists() else ""

    graph_file = book_dir / "graph.md"
    graph_content = graph_file.read_text(encoding="utf-8") if graph_file.exists() else ""

    images_dir = book_dir / "images"
    image_items = []
    if images_dir.exists():
        for idx, f in enumerate(sorted(images_dir.glob("*.png")), 1):
            p_num = idx
            m = re.search(r"_p(\d+)", f.stem)
            if m:
                p_num = int(m.group(1))
            image_items.append({
                "index": idx,
                "filename": f.name,
                "page_num": p_num,
                "url": f"/api/books/{clean_title}/images/{f.name}",
            })

    book_md_content = ""
    for candidate_name in ["full_book.md", "book.md", "Book.md"]:
        for parent_p in [book_dir / "original", book_dir]:
            target_candidate = parent_p / candidate_name
            if target_candidate.is_file():
                book_md_content = target_candidate.read_text(encoding="utf-8", errors="ignore")
            elif target_candidate.is_dir():
                # Legacy repair: books uploaded by the buggy uploader have a DIRECTORY
                # named "book.md" with the real markdown nested inside it.
                nested = target_candidate / candidate_name
                nested_files = [nested] if nested.is_file() else sorted(target_candidate.glob('*.md'))
                if nested_files:
                    book_md_content = nested_files[0].read_text(encoding="utf-8", errors="ignore")
                break
        if book_md_content:
            break

    if not book_md_content and chapters:
        sample_chaps = [book_dir / "chapters" / f"{ch['slug']}.md" for ch in chapters]
        existing_chaps = [cp for cp in sample_chaps if cp.exists()]
        if existing_chaps:
            book_md_content = "\n\n".join(cp.read_text(encoding="utf-8", errors="ignore") for cp in existing_chaps[:10])

    return {
        "folder": clean_title,
        "metadata": meta_data,
        "metrics": metrics_data,
        "chapters": chapters,
        "glossary": gloss_content,
        "graph": graph_content,
        "graph_markdown": graph_content,
        "book_md": book_md_content,
        "images": image_items,
        "has_docx": (book_dir / f"{clean_title}.docx").exists(),
        "has_pdf": (book_dir / f"{clean_title}.pdf").exists(),
        "has_original": (book_dir / "original").exists() and any((book_dir / "original").iterdir()),
    }


@app.get("/api/books/{title}/chapters/{chapter_slug}")
async def api_get_book_chapter(title: str, chapter_slug: str, user: User = Depends(get_current_user)) -> dict[str, Any]:
    config = TomeConfig.load_config()
    clean_title = Path(title).name
    clean_slug = Path(chapter_slug).name
    book_dir = config.output_dir / clean_title

    if not book_dir.exists():
        raise HTTPException(status_code=404, detail="Book not found")

    ch_file = book_dir / "chapters" / f"{clean_slug}.md"
    tr_file = book_dir / "translation" / f"{clean_slug}.md"

    if not ch_file.exists() and not tr_file.exists():
        raise HTTPException(status_code=404, detail="Chapter not found")

    orig_text = ch_file.read_text(encoding="utf-8") if ch_file.exists() else ""
    trans_text = tr_file.read_text(encoding="utf-8") if tr_file.exists() else ""

    return {
        "slug": clean_slug,
        "original": orig_text,
        "translated": trans_text,
    }


@app.post("/api/books/{title}/glossary")
async def api_save_glossary(title: str, req: dict[str, str], user: User = Depends(get_current_user)) -> dict[str, str]:
    config = TomeConfig.load_config()
    clean_title = Path(title).name
    book_dir = config.output_dir / clean_title
    content = req.get("content", "")
    (book_dir / "glossary.md").write_text(content, encoding="utf-8")
    return {"status": "ok"}


@app.get("/api/books/{title}/download/{artifact_type}")
async def api_download_artifact(title: str, artifact_type: str, user: User = Depends(get_current_user)) -> Any:
    config = TomeConfig.load_config()
    clean_title = Path(title).name
    book_dir = config.output_dir / clean_title
    if not book_dir.exists():
        raise HTTPException(status_code=404, detail="Book directory not found")

    if artifact_type == "docx":
        f = book_dir / f"{clean_title}.docx"
        if f.exists():
            return FileResponse(f, filename=f"{clean_title}.docx")
    elif artifact_type == "pdf":
        f = book_dir / f"{clean_title}.pdf"
        if f.exists():
            return FileResponse(f, filename=f"{clean_title}.pdf")
    elif artifact_type == "metadata_json":
        f = book_dir / "metadata.json"
        if f.exists():
            return FileResponse(f, filename=f"{clean_title}_metadata.json")
    elif artifact_type == "metrics_json":
        f = book_dir / "metrics.json"
        if f.exists():
            return FileResponse(f, filename=f"{clean_title}_metrics.json")
    elif artifact_type == "book_md":
        f = book_dir / "original" / "book.md"
        if not f.exists():
            f = book_dir / "book.md"
        if f.exists():
            return FileResponse(f, filename=f"{clean_title}_book.md")
    elif artifact_type == "translation_md":
        f = book_dir / "translation" / "translation.md"
        if f.exists():
            return FileResponse(f, filename=f"{clean_title}_translated.md")
    elif artifact_type in ("original", "original_pdf"):
        orig_dir = book_dir / "original"
        if orig_dir.exists():
            cand = [c for c in orig_dir.iterdir() if c.is_file() and c.suffix.lower() in (".pdf", ".epub", ".mobi", ".md", ".txt")]
            if cand:
                return FileResponse(cand[0], filename=cand[0].name)
    elif artifact_type == "images_zip":
        images_dir = book_dir / "images"
        if images_dir.exists():
            mem_zip = io.BytesIO()
            with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                for img_p in sorted(images_dir.glob("*.png")):
                    zf.write(img_p, arcname=img_p.name)
            mem_zip.seek(0)
            return StreamingResponse(
                mem_zip,
                media_type="application/zip",
                headers={"Content-Disposition": f'attachment; filename="{clean_title}_images.zip"'},
            )

    elif artifact_type == "unified_zip":
        mem_zip = io.BytesIO()
        with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(book_dir):
                for file_name in files:
                    full_p = Path(root) / file_name
                    rel_p = full_p.relative_to(book_dir)
                    zf.write(full_p, arcname=str(rel_p))
        mem_zip.seek(0)
        return StreamingResponse(
            mem_zip,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{clean_title}_complete_package.zip"'},
        )

    raise HTTPException(status_code=404, detail=f"Artifact {artifact_type} not found")


class PipelineRunRequest(BaseModel):
    file_path: str
    genre: str = "auto"
    llm_model: str | None = None
    target_language: str = "Persian"
    translate: bool = False
    skip_gliner: bool = False
    persian_nlp: bool = True
    extract_images: bool = True
    chapters: str | None = None


@app.post("/api/pipeline/run")
async def api_run_pipeline_task(
    req: PipelineRunRequest,
    bg_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    cfg = TomeConfig.load_config()
    p = _resolve_manuscript_path(req.file_path, cfg)
    if not p or not p.exists():
        direct = Path(req.file_path)
        if direct.exists():
            p = direct
        else:
            raise HTTPException(status_code=400, detail=f"File not found: {req.file_path}")

    cutoff = time.time() - 86400
    for _tid in [t for t, i in active_tasks.items() if i.get("status") in ("completed", "failed", "cancelled") and i.get("created_at", 0) < cutoff]:
        active_tasks.pop(_tid, None)
        task_event_queues.pop(_tid, None)
        pipeline_cancel_events.pop(_tid, None)
    task_id = f"task_{int(time.time())}_{secrets.token_hex(4)}"
    active_tasks[task_id] = {
        "task_id": task_id,
        "file_path": str(p),
        "status": "running",
        "progress": 0,
        "logs": [],
        "created_at": time.time(),
    }
    task_event_queues[task_id] = []

    def _observer(event: str, data: Any) -> None:
        msg = {"event": event, "data": data, "timestamp": time.time()}
        if task_id in active_tasks:
            active_tasks[task_id]["logs"].append(msg)
            if event == "stage_start":
                active_tasks[task_id]["current_stage"] = data.get("stage")
            elif event == "pipeline_complete":
                active_tasks[task_id]["status"] = "completed"
                active_tasks[task_id]["progress"] = 100

        for q in task_event_queues.get(task_id, []):
            q.put_nowait(msg)

    def _runner() -> None:
        pipeline_cancel_events[task_id] = threading.Event()
        _runner_observer = _make_cancelling_observer(task_id, _observer)
        try:
            runner_cfg = TomeConfig.load_config()
            if req.genre:
                runner_cfg.genre = req.genre
            if req.llm_model:
                runner_cfg.llm_model = req.llm_model
            if req.target_language:
                runner_cfg.target_language = req.target_language
            runner_cfg.skip_gliner = req.skip_gliner
            runner_cfg.persian_nlp = req.persian_nlp
            runner_cfg.extract_images = req.extract_images

            base_out = runner_cfg.output_dir.resolve()
            p_res = p.resolve()
            if p_res.is_relative_to(base_out):
                rel = p_res.relative_to(base_out)
                book_dir = base_out / rel.parts[0]
            elif p_res.is_dir():
                book_dir = p_res
            else:
                book_dir = base_out / clean_filename_title(p_res)

            chap_dir = book_dir / "chapters"
            has_existing_chapters = chap_dir.exists() and any(chap_dir.glob("*.md"))

            if req.chapters or (req.translate and has_existing_chapters):
                _observer("stage_start", {"stage": "chapter_translation", "chapters": req.chapters})
                translate_book(book_dir, runner_cfg, chapters=req.chapters, observer=_runner_observer)
            else:
                run_pipeline(p, runner_cfg, observer=_runner_observer)
                if req.translate:
                    translate_book(book_dir, runner_cfg, chapters=req.chapters, observer=_runner_observer)

            if req.translate:
                try:
                    from tome.core.docx import compile_book_to_docx

                    trans_dir = book_dir / "translation"
                    target_input = (
                        trans_dir
                        if (trans_dir.exists() and any(trans_dir.glob("*.md")))
                        else (book_dir / "chapters")
                    )
                    meta_json = book_dir / "metadata.json"
                    meta_obj = json.loads(meta_json.read_text(encoding="utf-8")) if meta_json.exists() else None
                    compile_book_to_docx(
                        input_path=target_input,
                        output_docx=book_dir / f"{book_dir.name}.docx",
                        config=runner_cfg,
                        title=book_dir.name,
                        observer=_runner_observer,
                        metadata=meta_obj,
                    )
                except Exception as comp_err:
                    _observer("warning", {"warning": f"Auto-compilation notice: {comp_err}"})

            if task_id in active_tasks:
                active_tasks[task_id]["status"] = "completed"
                active_tasks[task_id]["book_folder"] = book_dir.name
            _observer("pipeline_complete", {"book_folder": book_dir.name, "status": "completed"})
            pipeline_cancel_events.pop(task_id, None)
        except PipelineCancelled:
            pipeline_cancel_events.pop(task_id, None)
            if task_id in active_tasks:
                active_tasks[task_id]["status"] = "cancelled"
            _observer("pipeline_cancelled", {"message": "Pipeline cancelled by user"})
        except Exception as err:
            pipeline_cancel_events.pop(task_id, None)
            if task_id in active_tasks:
                active_tasks[task_id]["status"] = "failed"
                active_tasks[task_id]["error"] = str(err)
            _observer("error", {"error": str(err)})

    bg_tasks.add_task(_runner)
    return {"task_id": task_id, "status": "started"}


@app.get("/api/pipeline/status/{task_id}")
async def api_pipeline_status(task_id: str, user: User = Depends(get_current_user)) -> dict[str, Any]:
    info = active_tasks.get(task_id)
    if not info:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "task_id": task_id,
        "status": info.get("status", "unknown"),
        "progress": info.get("progress", 0),
        "current_stage": info.get("current_stage", ""),
        "book_folder": info.get("book_folder", ""),
        "file_path": info.get("file_path", ""),
        "error": info.get("error", ""),
        "logs": info.get("logs", []),
    }


@app.post("/api/pipeline/cancel/{task_id}")
async def api_pipeline_cancel(task_id: str, user: User = Depends(get_current_user)) -> dict[str, str]:
    info = active_tasks.get(task_id)
    if not info:
        raise HTTPException(status_code=404, detail="Task not found")
    if info.get("status") != "running":
        return {"status": "ignored", "detail": f"Task already {info.get('status')}"}
    ev = pipeline_cancel_events.setdefault(task_id, threading.Event())
    ev.set()
    info["status"] = "cancelling"
    for q in task_event_queues.get(task_id, []):
        q.put_nowait({
            "event": "cancelling",
            "data": {"message": "Cancellation requested by user"},
            "timestamp": time.time(),
        })
    return {"status": "ok"}


@app.get("/api/pipeline/events/{task_id}")
async def api_pipeline_events(task_id: str, request: Request) -> StreamingResponse:
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    queue: asyncio.Queue = asyncio.Queue()
    for past_log in active_tasks[task_id]["logs"]:
        queue.put_nowait(past_log)

    task_event_queues.setdefault(task_id, []).append(queue)

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event_data = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"data: {json.dumps(event_data, default=str)}\n\n"
                except TimeoutError:
                    yield ": ping\n\n"
                if active_tasks[task_id]["status"] in ("completed", "failed", "cancelled") and queue.empty():
                    break
        finally:
            if task_id in task_event_queues and queue in task_event_queues[task_id]:
                task_event_queues[task_id].remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/prompts")
async def api_get_prompts(user: User = Depends(get_current_user)) -> dict[str, str]:
    config = TomeConfig.load_config()
    res = dict(config.prompts)
    res["user_style_rules"] = config.user_style_rules
    return res


@app.post("/api/prompts")
async def api_update_prompts(req: PromptUpdateRequest, user: User = Depends(get_current_user)) -> dict[str, str]:
    tome_json = Path("tome.json")
    data: dict[str, Any] = {}
    if tome_json.exists():
        data = json.loads(tome_json.read_text(encoding="utf-8"))

    prompts_dict = data.setdefault("prompts", {})
    alias_map = {
        "translate_chapter": "chapter_translation_with_glossary_system_prompt",
        "translate_chapter_no_glossary": "chapter_translation_no_gliner_system_prompt",
        "fantasy_guidelines": "fantasy_translation_guidelines",
        "fantasy": "fantasy_translation_guidelines",
        "extract_metadata": "metadata_refinement_system_prompt",
        "user_rules": "user_style_rules",
    }
    for k, v in req.prompts.items():
        canonical_k = alias_map.get(k, k)
        if canonical_k == "user_style_rules":
            data["user_style_rules"] = v
        prompts_dict[canonical_k] = v

    tome_json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    TomeConfig.load_config()
    return {"status": "ok"}


@app.get("/api/config")
async def api_get_config(user: User = Depends(get_current_user)) -> dict[str, Any]:
    tome_json = Path("tome.json")
    if tome_json.exists():
        return json.loads(tome_json.read_text(encoding="utf-8"))
    config = TomeConfig.load_config()
    return config.to_modular_dict()


@app.post("/api/config")
async def api_update_config(req: dict[str, Any], user: User = Depends(get_current_user)) -> dict[str, str]:
    tome_json = Path("tome.json")
    data: dict[str, Any] = {}
    if tome_json.exists():
        data = json.loads(tome_json.read_text(encoding="utf-8"))

    section_names = ("general", "llm", "proxy", "nlp", "translation", "typography")
    for section_name in section_names:
        val = req.get(section_name)
        if val is not None:
            data.setdefault(section_name, {}).update(val)

    for key, value in req.items():
        if key not in section_names:
            data[key] = value

    tome_json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    TomeConfig.load_config()
    return {"status": "ok"}


@app.get("/favicon.svg")
async def api_favicon() -> Response:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <rect width="100" height="100" rx="28" fill="#27272a"/>
  <text x="50" y="68" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="56" font-weight="600" fill="#d4d4d8" text-anchor="middle">
    *.
  </text>
</svg>"""
    return Response(content=svg, media_type="image/svg+xml")


@app.get("/robots.txt")
async def api_robots() -> Response:
    content = "User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n"
    return Response(content=content, media_type="text/plain")


@app.get("/sitemap.xml")
async def api_sitemap() -> Response:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>/</loc>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>"""
    return Response(content=xml, media_type="application/xml")


@app.get("/manifest.json")
async def api_manifest() -> Response:
    manifest = {
        "name": "Tome",
        "short_name": "Tome",
        "description": "Literary Translation and Publishing Engine",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0b0f17",
        "theme_color": "#1e40af",
        "icons": [
            {
                "src": "/favicon.svg",
                "sizes": "any",
                "type": "image/svg+xml",
            }
        ],
    }
    return Response(content=json.dumps(manifest), media_type="application/json")


static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str) -> Response:
        target = static_dir / full_path
        if target.is_file() and target.exists():
            return FileResponse(target)
        index_p = static_dir / "index.html"
        if index_p.exists():
            return FileResponse(index_p)
        return Response("Tome Web Frontend Not Built", status_code=404)
