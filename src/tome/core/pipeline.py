import contextlib
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tome.config import TomeConfig
from tome.core.chapterizer import segment_chapters
from tome.core.cleaner import clean_markdown_text
from tome.core.converter import convert_pdf_to_markdown
from tome.core.epub_converter import convert_epub_to_pdf, convert_mobi_to_pdf
from tome.core.extractor import extract_entities
from tome.core.glossary import cluster_entities, write_glossary_markdown
from tome.core.graph import build_character_graph
from tome.core.logging import setup_logger
from tome.core.metadata import clean_filename_title, extract_book_metadata, sanitize_book_title
from tome.exceptions import TomeError
from tome.models import PipelineResult


def run_pipeline(
    input_file: Path,
    config: TomeConfig | None = None,
    observer: Callable[[str, Any], None] | None = None,
) -> PipelineResult:
    start_total = time.perf_counter()
    timings: dict[str, float] = {}

    if config is None:
        config = TomeConfig()

    initial_title = clean_filename_title(input_file)
    logger = setup_logger(config.log_dir, book_title=initial_title)

    if config.output_dir.name == initial_title:
        destination_dir = config.output_dir
    else:
        destination_dir = config.output_dir / initial_title
    destination_dir.mkdir(parents=True, exist_ok=True)
    original_dir = destination_dir / "original"
    original_dir.mkdir(parents=True, exist_ok=True)

    if input_file.is_file():
        cleaned_dest_name = f"{initial_title}{input_file.suffix.lower()}"
        cleaned_input_copy = original_dir / cleaned_dest_name
        legacy_input_copy = destination_dir / cleaned_dest_name
        if legacy_input_copy.exists() and not cleaned_input_copy.exists():
            with contextlib.suppress(Exception):
                legacy_input_copy.rename(cleaned_input_copy)
        if not cleaned_input_copy.exists() or cleaned_input_copy.stat().st_size != input_file.stat().st_size:
            with contextlib.suppress(Exception):
                import shutil

                shutil.copy2(input_file, cleaned_input_copy)

    ext = input_file.suffix.lower()
    full_md_path = original_dir / "book.md"
    legacy_md = destination_dir / "book.md"
    if not full_md_path.exists() and legacy_md.exists() and legacy_md.stat().st_size > 0:
        with contextlib.suppress(Exception):
            import shutil

            shutil.copy2(legacy_md, full_md_path)

    meta: dict[str, Any] = {}
    working_pdf: Path | None = None

    if not input_file.is_file() and not (full_md_path.exists() and full_md_path.stat().st_size > 0):
        raise FileNotFoundError(f"Input file does not exist: {input_file}")

    if (
        input_file.is_file()
        and input_file.stat().st_size == 0
        and not (full_md_path.exists() and full_md_path.stat().st_size > 0)
    ):
        raise TomeError(f"Input file is empty: {input_file}")

    if full_md_path.exists() and full_md_path.stat().st_size > 0:
        logger.info(f"Using existing manuscript from {full_md_path}")
        sanitized_markdown = full_md_path.read_text(encoding="utf-8")
        word_count = len(sanitized_markdown.split())
        estimated_pages = max(1, word_count // 275)
        meta = {
            "page_count": estimated_pages,
            "confidence": 1.0,
            "pdf_type": "cached",
        }
        timings["conversion"] = 0.0
        if observer:
            observer("conversion_complete", {**meta, "duration": 0.0, "cached": True})
    elif ext in {".md", ".txt"}:
        logger.info(f"Loading direct text manuscript from {input_file}")
        raw_text = input_file.read_text(encoding="utf-8", errors="ignore")
        sanitized_text = clean_markdown_text(raw_text, keep_raw_artifacts=config.keep_raw_artifacts)
        full_md_path.write_text(sanitized_text, encoding="utf-8")
        word_count = len(sanitized_text.split())
        estimated_pages = max(1, word_count // 275)
        meta = {
            "page_count": estimated_pages,
            "confidence": 1.0,
            "pdf_type": "plain_text",
        }
        timings["conversion"] = 0.01
        if observer:
            observer("conversion_complete", {**meta, "duration": 0.01})
    else:
        working_pdf = input_file
        if ext == ".epub":
            logger.info(f"Converting EPUB to PDF: {input_file}")
            t0 = time.perf_counter()
            working_pdf = convert_epub_to_pdf(input_file, original_dir / f"{initial_title}_converted.pdf")
            timings["epub_to_pdf"] = round(time.perf_counter() - t0, 2)
        elif ext == ".mobi":
            logger.info(f"Converting MOBI to PDF: {input_file}")
            t0 = time.perf_counter()
            working_pdf = convert_mobi_to_pdf(input_file, original_dir / f"{initial_title}_converted.pdf")
            timings["mobi_to_pdf"] = round(time.perf_counter() - t0, 2)

        if observer:
            observer("stage_start", {"stage": "conversion", "file": str(working_pdf)})
        logger.info(f"Starting conversion for {working_pdf}")

        t0 = time.perf_counter()
        full_md_path, meta = convert_pdf_to_markdown(working_pdf, original_dir)
        timings["conversion"] = round(time.perf_counter() - t0, 2)
        logger.info(
            f"Converted PDF: {meta['page_count']} pages in {timings['conversion']}s (confidence: {meta['confidence']})"
        )
        if observer:
            observer("conversion_complete", {**meta, "duration": timings["conversion"]})

        raw_markdown_text = full_md_path.read_text(encoding="utf-8")
        sanitized_markdown = clean_markdown_text(raw_markdown_text, keep_raw_artifacts=config.keep_raw_artifacts)
        full_md_path.write_text(sanitized_markdown, encoding="utf-8")

    sanitized_markdown = full_md_path.read_text(encoding="utf-8")

    if config.extract_images:
        t0 = time.perf_counter()
        from tome.core.images import embed_image_markers_in_markdown, extract_book_images

        source_doc = working_pdf if (working_pdf and working_pdf.is_file()) else input_file
        extracted_images = []
        if source_doc.is_file() and source_doc.suffix.lower() in (
            ".pdf",
            ".epub",
            ".xps",
            ".mobi",
            ".cbz",
            ".cbr",
            ".fb2",
        ):
            logger.info(f"Extracting illustrations from {source_doc.name}")
            extracted_images = extract_book_images(source_doc, destination_dir)
            if extracted_images:
                logger.info(f"Extracted {len(extracted_images)} illustrations to {destination_dir / 'images'}")
                sanitized_markdown = embed_image_markers_in_markdown(sanitized_markdown, extracted_images)
                full_md_path.write_text(sanitized_markdown, encoding="utf-8")
            else:
                logger.info("No illustrations found in manuscript.")
        timings["image_extraction"] = round(time.perf_counter() - t0, 2)
        if observer:
            observer(
                "images_extracted",
                {
                    "image_count": len(extracted_images),
                    "images": [img.filename for img in extracted_images],
                    "duration": timings["image_extraction"],
                },
            )

    t0 = time.perf_counter()
    resolved_genre = config.resolve_genre(sanitized_markdown)
    timings["genre_detection"] = round(time.perf_counter() - t0, 2)
    logger.info(f"Detected book genre: {resolved_genre} in {timings['genre_detection']}s")
    if observer:
        observer("genre_detected", {"genre": resolved_genre, "duration": timings["genre_detection"]})

    book_meta = extract_book_metadata(
        sanitized_markdown,
        input_file,
        page_count=meta.get("page_count", 0),
        detected_genre=resolved_genre,
    )
    clean_ai_title: str | None = None
    if getattr(config, "refine_metadata", True):
        from tome.core.metadata import refine_metadata_with_llm

        logger.info(f"Refining metadata with LLM for {book_meta.title}")
        book_meta = refine_metadata_with_llm(
            book_meta,
            input_file,
            sanitized_markdown,
            config,
            observer=observer,
        )
        if book_meta.genre and book_meta.genre.lower() != "general":
            resolved_genre = book_meta.genre.lower()

        clean_ai_title = sanitize_book_title(book_meta.title)
        if clean_ai_title and clean_ai_title != initial_title and config.output_dir.name != initial_title:
            new_dest_dir = config.output_dir / clean_ai_title
            if not new_dest_dir.exists() and destination_dir.exists():
                with contextlib.suppress(Exception):
                    import shutil

                    shutil.move(str(destination_dir), str(new_dest_dir))
                    destination_dir = new_dest_dir
                    original_dir = destination_dir / "original"
                    full_md_path = (
                        original_dir / "book.md" if (original_dir / "book.md").exists() else destination_dir / "book.md"
                    )
                    logger.info(f"Renamed output folder to clean AI book title: {destination_dir}")

                    old_input = original_dir / f"{initial_title}{input_file.suffix.lower()}"
                    new_input = original_dir / f"{clean_ai_title}{input_file.suffix.lower()}"
                    if old_input.exists() and not new_input.exists():
                        old_input.rename(new_input)
                    legacy_old_input = destination_dir / f"{initial_title}{input_file.suffix.lower()}"
                    if legacy_old_input.exists() and not new_input.exists():
                        legacy_old_input.rename(new_input)

                    old_log = config.log_dir / f"{initial_title}_execution.log"
                    new_log = config.log_dir / f"{clean_ai_title}_execution.log"
                    if old_log.exists() and not new_log.exists():
                        old_log.rename(new_log)
                    old_jsonl = config.log_dir / f"{initial_title}_execution.jsonl"
                    new_jsonl = config.log_dir / f"{clean_ai_title}_execution.jsonl"
                    if old_jsonl.exists() and not new_jsonl.exists():
                        old_jsonl.rename(new_jsonl)

    from tome.core.metadata import save_book_metadata

    active_title = clean_ai_title if clean_ai_title else initial_title
    save_book_metadata(book_meta, destination_dir, config.log_dir, active_title)
    if observer:
        observer("metadata_extracted", book_meta)
    logger.info(f"Metadata extracted: {book_meta.title} by {', '.join(book_meta.authors)} ({book_meta.year})")

    chapters_dir = destination_dir / "chapters"
    existing_chapters = sorted(
        [f for f in chapters_dir.glob("*.md") if f.is_file() and f.name != "book.md" and f.stat().st_size > 0]
    )
    if existing_chapters:
        from tome.models import Chapter

        chapters = []
        for i, ch_p in enumerate(existing_chapters):
            slug = ch_p.stem
            chapters.append(
                Chapter(
                    index=i,
                    title=slug.split("_", 1)[-1].replace("_", " ").title() if "_" in slug else slug,
                    slug=slug,
                    content=ch_p.read_text(encoding="utf-8"),
                    is_front_matter=(i == 0 and "front" in slug),
                )
            )
        chapter_paths = existing_chapters
        timings["chapterization"] = 0.0
        if observer:
            observer(
                "chapterization_complete",
                {"chapter_count": len(chapters), "chapters": chapters, "duration": 0.0, "cached": True},
            )
    else:
        if observer:
            observer("stage_start", {"stage": "chapterization"})
        logger.info("Starting chapter segmentation")
        t0 = time.perf_counter()
        chapters = segment_chapters(
            sanitized_markdown,
            chapters_dir,
            keep_raw_artifacts=config.keep_raw_artifacts,
        )
        chapter_paths = [chapters_dir / f"{ch.slug}.md" for ch in chapters]
        timings["chapterization"] = round(time.perf_counter() - t0, 2)
        logger.info(f"Detected and written {len(chapters)} chapters in {timings['chapterization']}s")
        if observer:
            observer(
                "chapterization_complete",
                {"chapter_count": len(chapters), "chapters": chapters, "duration": timings["chapterization"]},
            )

    glossary_path: Path | None = None
    character_graph_path: Path | None = None
    total_entities = 0

    if not config.skip_gliner:
        g_path = destination_dir / "glossary.md"
        gr_path = destination_dir / "graph.md"
        glossary_path = g_path
        character_graph_path = gr_path

        if g_path.exists() and g_path.stat().st_size > 0 and gr_path.exists() and gr_path.stat().st_size > 0:
            logger.info(f"Using existing glossary from {g_path} and graph from {gr_path}")
            timings["extraction"] = 0.0
            timings["glossary_clustering"] = 0.0
            timings["graph_generation"] = 0.0
            if observer:
                observer("extraction_complete", {"entity_count": 0, "categories": {}, "duration": 0.0, "cached": True})
        else:
            if observer:
                observer("stage_start", {"stage": "extraction"})
            logger.info(f"Starting GLiNER extraction with model {config.default_model}")

            t0 = time.perf_counter()

            def extraction_progress(current: int, total: int) -> None:
                if observer:
                    observer("extraction_progress", {"current": current, "total": total})

            raw_entities = extract_entities(
                text=sanitized_markdown,
                model_identifier=config.default_model,
                taxonomy=config.get_taxonomy(resolved_genre),
                batch_size=config.batch_size,
                chunk_size=config.chunk_size_words,
                chunk_overlap=config.chunk_overlap_words,
                fast_filter=config.fast_mode,
                progress_callback=extraction_progress,
            )
            timings["extraction"] = round(time.perf_counter() - t0, 2)
            logger.info(f"Raw entities extracted: {len(raw_entities)} in {timings['extraction']}s")

            t0 = time.perf_counter()
            clustered = cluster_entities(
                raw_entities,
                min_frequency=config.min_entity_frequency,
                high_confidence_threshold=config.high_confidence_threshold,
                similarity_threshold=config.fuzzy_similarity_threshold,
                max_edit_distance=config.max_levenshtein_distance,
            )

            write_glossary_markdown(clustered, g_path, book_title=book_meta.title)
            total_entities = sum(len(items) for items in clustered.values())
            timings["glossary_clustering"] = round(time.perf_counter() - t0, 2)
            logger.info(
                f"Clustered glossary generated at {g_path} ({total_entities} terms) in {timings['glossary_clustering']}s"
            )

            t0 = time.perf_counter()
            all_entities_flat = [ent for group in clustered.values() for ent in group]
            build_character_graph(chapters, all_entities_flat, gr_path, book_title=book_meta.title)
            timings["graph_generation"] = round(time.perf_counter() - t0, 2)
            logger.info(f"Character relationship graph generated at {gr_path} in {timings['graph_generation']}s")

            if observer:
                observer(
                    "extraction_complete",
                    {"entity_count": total_entities, "categories": clustered, "duration": timings["extraction"]},
                )
    else:
        logger.info("GLiNER extraction skipped via configuration.")

    timings["total"] = round(time.perf_counter() - start_total, 2)
    logger.info(f"Total pipeline execution time: {timings['total']}s")

    result = PipelineResult(
        book_title=book_meta.title,
        full_markdown_path=full_md_path,
        chapter_paths=chapter_paths,
        glossary_path=glossary_path,
        character_graph_path=character_graph_path,
        total_pages=meta.get("page_count", 0),
        total_chapters=len(chapters),
        entity_count=total_entities,
        timings=timings,
        metadata=book_meta,
    )

    if observer:
        observer("pipeline_complete", result)

    return result
