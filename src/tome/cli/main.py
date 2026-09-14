import argparse
import contextlib
import os
import platform
import re
import sys
import time
from pathlib import Path
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from tome.config import TomeConfig, detect_genre
from tome.core.metadata import clean_filename_title

console = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tome",
        description="Universal Book Processing, Chapterization & Translation Harness",
    )
    subparsers = parser.add_subparsers(dest="command")

    run_p = subparsers.add_parser("run", help="Run full pipeline on PDF, EPUB, MOBI, MD, or TXT")
    run_p.add_argument("input", help="Path to input book (PDF, EPUB, MOBI, MD, TXT)")
    run_p.add_argument("-o", "--output", default="output", help="Output directory for generated artifacts")
    run_p.add_argument("-g", "--genre", default=None, help="Genre preset or 'auto' for automatic keyword detection")
    run_p.add_argument(
        "-m", "--model", default="urchade/gliner_medium-v2.1", help="GLiNER model identifier or local path"
    )
    run_p.add_argument("-b", "--batch-size", type=int, default=16, help="Inference batch size for CPU processing")
    run_p.add_argument("-n", "--no-gliner", action="store_true", help="Skip GLiNER entity extraction for LLM mode")
    run_p.add_argument(
        "-f", "--fast", action="store_true", help="Enable fast mode with dialogue filtering for low-spec VPS"
    )
    run_p.add_argument("-k", "--keep-raw", action="store_true", help="Do not strip page numbers, headers, and footers")
    run_p.add_argument("-np", "--no-persian-nlp", action="store_true", help="Disable Persian NLP copyeditor (Shekar)")
    run_p.add_argument("--persian-nlp", action="store_true", help="Enable Persian NLP copyeditor (Shekar)")
    run_p.add_argument(
        "-rm",
        "--refine-metadata",
        action="store_true",
        default=None,
        help="Refine and clean book metadata via LLM",
    )
    run_p.add_argument(
        "--no-refine-metadata",
        action="store_true",
        help="Disable LLM book metadata refinement",
    )
    run_p.add_argument(
        "-ni",
        "--no-images",
        action="store_true",
        help="Disable illustration and image extraction",
    )
    run_p.add_argument(
        "-t",
        "--translate",
        action="store_true",
        help="Automatically translate chapters and compile Word (.docx) manuscript",
    )
    run_p.add_argument("-l", "--lang", default=None, help="Target language override (e.g. Persian)")
    run_p.add_argument(
        "-c",
        "--chapters",
        default=None,
        help="Chapters to process (e.g. 5, '5 and 6', '5 to 10', '1,3,5-7'). Default: all",
    )
    run_p.add_argument(
        "-lm",
        "--llm-model",
        default=None,
        help="LLM translation model override (e.g. qwen3.8-flash, gemini-flash-latest, glm-5.3-flash)",
    )

    trans_p = subparsers.add_parser("translate", help="Translate segmented book chapters into target language via LLM")
    trans_p.add_argument("book_dir", help="Path to processed book directory containing chapters")
    trans_p.add_argument("-l", "--lang", default=None, help="Target language override (e.g. Persian)")
    trans_p.add_argument("-s", "--style", default=None, help="Custom style rules and narrative tone guide")
    trans_p.add_argument(
        "-c",
        "--chapters",
        default=None,
        help="Chapters to translate (e.g. 5, '5 and 6', '5 to 10', '1,3,5-7'). Default: all",
    )
    trans_p.add_argument("-np", "--no-persian-nlp", action="store_true", help="Disable Persian NLP copyeditor (Shekar)")
    trans_p.add_argument(
        "-lm",
        "--llm-model",
        default=None,
        help="LLM translation model override (e.g. qwen3.8-flash, gemini-flash-latest, glm-5.3-flash)",
    )

    genre_p = subparsers.add_parser("genre", help="Detect book genre from PDF or Markdown")
    genre_p.add_argument("input", help="Path to book PDF, Markdown, or text file")

    meta_p = subparsers.add_parser(
        "metadata",
        help="Extract, clean, and refine manuscript bibliographic metadata (title, author, genre, synopsis, keywords)",
    )
    meta_p.add_argument("input", help="Path to book file (PDF, EPUB, MOBI, TXT, MD)")
    meta_p.add_argument("-rm", "--refine", action="store_true", default=None, help="Refine metadata using LLM")
    meta_p.add_argument("--no-refine", action="store_true", help="Disable LLM refinement (heuristic only)")
    meta_p.add_argument("-o", "--output", default=None, help="Optional output path to save JSON metadata")

    images_p = subparsers.add_parser("images", help="Extract illustrations and images from PDF or EPUB document")
    images_p.add_argument("input", help="Path to PDF or EPUB document")
    images_p.add_argument("-o", "--output", default=None, help="Destination directory for extracted images")

    conv_p = subparsers.add_parser("convert", help="Convert any manuscript (PDF, EPUB, MOBI, TXT) to clean Markdown")
    conv_p.add_argument("input", help="Path to book file (PDF, EPUB, MOBI, AZW3, CBZ, CBR, TXT, MD)")
    conv_p.add_argument("-o", "--output", default="output", help="Output directory")
    conv_p.add_argument("-k", "--keep-raw", action="store_true", help="Do not strip page numbers and headers")

    chap_p = subparsers.add_parser("chapterize", help="Segment Markdown into individual chapter files")
    chap_p.add_argument("input", help="Path to Markdown file")
    chap_p.add_argument("-o", "--output", default="chapters", help="Output directory for chapters")
    chap_p.add_argument("-k", "--keep-raw", action="store_true", help="Do not strip page numbers and headers")

    graph_p = subparsers.add_parser("graph", help="Generate Character Relationship & Scene Presence Graph")
    graph_p.add_argument("chapters_dir", help="Path to directory containing segmented chapter files")
    graph_p.add_argument("-g", "--glossary", default="glossary.md", help="Path to glossary Markdown file")
    graph_p.add_argument("-o", "--output", default="graph.md", help="Output Markdown graph path")

    ing_p = subparsers.add_parser("ingest", help="Ingest LLM entity block and clean chapter")
    ing_p.add_argument("chapter_file", help="Path to translated chapter file")
    ing_p.add_argument("-g", "--glossary", default="glossary.md", help="Glossary markdown file to update")

    model_p = subparsers.add_parser("setup-model", help="Pre-download and cache GLiNER model")
    model_p.add_argument("-m", "--model", default="urchade/gliner_medium-v2.1", help="Model name to download")

    edit_p = subparsers.add_parser("edit", help="Run Persian NLP copyediting on Markdown chapter(s)")
    edit_p.add_argument("path", help="Path to Markdown file or directory of chapters")
    edit_p.add_argument("-o", "--output", default=None, help="Optional output path")

    docx_p = subparsers.add_parser("docx", help="Compile Markdown chapter files into a unified Word (.docx) book")
    docx_p.add_argument("input", help="Path to Markdown file or directory of chapters")
    docx_p.add_argument("-o", "--output", default=None, help="Output .docx file path")
    docx_p.add_argument("-t", "--title", default=None, help="Book title override for header")
    docx_p.add_argument("-l", "--lang", default=None, help="Target language (e.g. Persian, English)")
    docx_p.add_argument(
        "--font", default=None, help="Font override (font name, filename, or path e.g. 'B-Nazanin.ttf', 'Times.ttf')"
    )
    docx_p.add_argument(
        "-ef", "--eastern-font", default=None, help="Eastern font name, filename, or path (e.g. B-Nazanin.ttf)"
    )
    docx_p.add_argument(
        "-wf", "--western-font", default=None, help="Western font name, filename, or path (e.g. Times.ttf)"
    )

    web_p = subparsers.add_parser("web", help="Start Tome web platform and REST API")
    web_p.add_argument("--host", default="0.0.0.0", help="Host address to bind to (default: 0.0.0.0)")
    web_p.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    web_p.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    web_p.add_argument(
        "--register-service",
        action="store_true",
        help="Register as 24/7 auto-recovering systemd service on Linux/Ubuntu VPS",
    )

    srv_p = subparsers.add_parser("service", help="Manage 24/7 auto-recovering background service (launchd on macOS, systemd on Linux)")
    srv_p.add_argument("action", choices=["install", "uninstall", "status", "restart"], help="Service action")
    srv_p.add_argument("--host", default="0.0.0.0", help="Host address for installed service")
    srv_p.add_argument("--port", type=int, default=8000, help="Port for installed service")

    subparsers.add_parser(
        "install-cli",
        help="Register the 'tome' command globally in user PATH and shell startup files (macOS & Linux)",
    )

    return parser


def display_metadata_panel(meta) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2), expand=True)
    table.add_column("Key", style="bold cyan", width=22)
    table.add_column("Value", style="white")

    table.add_row("Title", meta.title)
    table.add_row("Author(s)", ", ".join(meta.authors))
    if meta.year:
        table.add_row("Year", meta.year)
    if meta.publisher:
        table.add_row("Publisher", meta.publisher)
    if meta.isbn:
        table.add_row("ISBN", meta.isbn)
    table.add_row("Genre", meta.genre.replace("_", " ").title())
    table.add_row("Page Count", f"{meta.page_count:,}")
    table.add_row("Word Count", f"{meta.word_count:,}")
    table.add_row("Character Count", f"{meta.char_count:,}")
    table.add_row("Est. Reading Time", meta.reading_time)
    if getattr(meta, "keywords", None) and meta.keywords:
        table.add_row("Keywords", ", ".join(meta.keywords))
    if getattr(meta, "synopsis", None):
        table.add_row("Synopsis", meta.synopsis)

    console.print(
        Panel(
            table,
            title="[bold green]Book Manuscript Analysis[/bold green]",
            border_style="green",
            box=box.ROUNDED,
        )
    )


def display_translation_metrics_panel(metrics: dict[str, Any]) -> None:
    chapters = metrics.get("chapters", [])
    if chapters:
        tbl = Table(
            title="[bold green]Chapter Translation Metrics & Costs[/bold green]",
            box=box.ROUNDED,
            border_style="green",
            header_style="bold cyan",
            expand=True,
        )
        tbl.add_column("Chapter", style="white")
        tbl.add_column("Duration", style="green", justify="right")
        tbl.add_column("Tokens", style="yellow", justify="right")
        tbl.add_column("Cost (Toman)", style="magenta", justify="right")
        tbl.add_column("NLP Fixed", style="dim white", justify="right")
        for ch in chapters:
            c_name = ch.get("chapter_name", "")
            dur = f"{ch.get('duration_seconds', 0):.1f}s"
            toks = f"{ch.get('total_tokens', 0):,}"
            val_toman = ch.get("cost_toman", ch.get("cost_irt", 0))
            toman_str = f"{val_toman:,.0f} Toman"
            nlp = f"{ch.get('words_normalized', 0)}"
            tbl.add_row(c_name, dur, toks, toman_str, nlp)
        console.print(tbl)

    tot_toman = metrics.get("total_cost_toman", metrics.get("total_cost_irt", 0))
    avg_toman = metrics.get("average_cost_toman_per_chapter", metrics.get("average_cost_irt_per_chapter", 0))
    summary_lines = [
        f"[bold]Model:[/] {metrics.get('model', 'Unknown')}",
        f"[bold]Total Translation Time:[/] {metrics.get('total_duration_seconds', 0):.1f}s (avg {metrics.get('average_duration_seconds', 0):.1f}s / chapter)",
        f"[bold]Total Tokens Consumed:[/] {metrics.get('total_tokens', 0):,} (avg {metrics.get('average_tokens_per_chapter', 0):,.1f} / chapter)",
        f"[bold]Total Estimated Cost:[/] [magenta]{tot_toman:,.0f} Toman[/magenta] (avg {avg_toman:,.0f} Toman / chapter)",
    ]
    init_credit = metrics.get("initial_credit_toman", metrics.get("initial_credit_irt"))
    final_credit = metrics.get("final_credit_toman", metrics.get("final_credit_irt"))
    consumed_credit = metrics.get("consumed_credit_toman", metrics.get("consumed_credit_irt", 0))
    consumed_pct = metrics.get("consumed_credit_percent", 0)
    if init_credit is not None:
        bal_str = f"Initial: {init_credit:,.0f} Toman"
        if final_credit is not None:
            bal_str += f" | Final: {final_credit:,.0f} Toman"
        bal_str += f" | Consumed: [bold magenta]{consumed_credit:,.0f} Toman ({consumed_pct:.2f}%)[/bold magenta]"
        summary_lines.append(f"[bold]Wallet Balance Usage:[/] {bal_str}")

    w_proc = metrics.get("nlp_words_processed", 0)
    w_mod = metrics.get("nlp_words_modified", 0)
    uniq_mod = metrics.get("nlp_unique_modifications_count", 0)
    if w_proc > 0:
        summary_lines.append(
            f"[bold]NLP Processing:[/] {w_mod:,}/{w_proc:,} words normalized ({uniq_mod:,} unique word corrections logged)"
        )

    console.print(
        Panel(
            "\n".join(summary_lines),
            title="[bold green]Translation & Cost Summary[/bold green]",
            box=box.ROUNDED,
            border_style="green",
        )
    )


def ensure_shell_path_configured() -> list[str]:
    """Ensure ~/.local/bin and ~/bin are exported in user shell profiles (zsh/bash)."""
    home = Path.home()
    updated_files: list[str] = []

    # Target profiles for macOS (zsh default) and Linux
    target_profiles: list[Path] = []
    if platform.system().lower() == "darwin":
        target_profiles.extend([home / ".zprofile", home / ".zshrc"])
    else:
        target_profiles.extend([home / ".bashrc", home / ".profile"])

    for extra in [home / ".zshrc", home / ".bashrc", home / ".zprofile", home / ".bash_profile"]:
        if extra.exists() and extra not in target_profiles:
            target_profiles.append(extra)

    export_snippet = (
        "\n# Added by Tome (Book Processing & Translation)\n"
        'export PATH="$HOME/.local/bin:$HOME/bin:$PATH"\n'
    )

    for prof in target_profiles:
        try:
            content = prof.read_text(encoding="utf-8") if prof.exists() else ""
            if ".local/bin" not in content and "$HOME/bin" not in content and "~/bin" not in content:
                with prof.open("a", encoding="utf-8") as f:
                    f.write(export_snippet)
                updated_files.append(str(prof))
        except OSError:
            continue

    return updated_files


def ensure_tome_installed_in_path(verbose: bool = False) -> list[Path]:
    installed_paths: list[Path] = []
    current_py = Path(sys.executable).resolve()
    venv_tome = current_py.parent / "tome"

    target_dirs: list[Path] = []
    # If on macOS, prioritize /opt/homebrew/bin or /usr/local/bin if writable (standard PATH)
    if platform.system().lower() == "darwin" and os.access("/opt/homebrew/bin", os.W_OK):
        target_dirs.append(Path("/opt/homebrew/bin"))
    if os.access("/usr/local/bin", os.W_OK):
        target_dirs.append(Path("/usr/local/bin"))

    # Always ensure user-local bin directories
    target_dirs.extend([
        Path.home() / ".local" / "bin",
        Path.home() / "bin",
    ])

    for bin_dir in target_dirs:
        try:
            bin_dir.mkdir(parents=True, exist_ok=True)
            tome_bin = bin_dir / "tome"

            if venv_tome.exists():
                if not tome_bin.exists() or tome_bin.resolve() != venv_tome.resolve():
                    if tome_bin.is_symlink() or tome_bin.is_file():
                        tome_bin.unlink()
                    tome_bin.symlink_to(venv_tome)
                installed_paths.append(tome_bin)
            else:
                wrapper_script = (
                    "#!/usr/bin/env bash\n"
                    f'exec "{sys.executable}" -m tome.cli.main "$@"\n'
                )
                if not tome_bin.exists() or tome_bin.read_text(encoding="utf-8", errors="ignore") != wrapper_script:
                    tome_bin.write_text(wrapper_script, encoding="utf-8")
                    tome_bin.chmod(0o755)
                installed_paths.append(tome_bin)
        except OSError:
            continue

    ensure_shell_path_configured()
    return installed_paths


def _run_cli() -> None:
    ensure_tome_installed_in_path()

    if len(sys.argv) == 1:
        from tome.cli.tui import TomeApp

        app = TomeApp()
        app.run()
        return

    parser = build_parser()
    args = parser.parse_args()

    if args.command == "install-cli":
        paths = ensure_tome_installed_in_path(verbose=True)
        profiles = ensure_shell_path_configured()
        console.print("[bold green]✓ Tome CLI Registration[/bold green]")
        for p in paths:
            console.print(f"  • Registered executable: [cyan]{p}[/cyan]")
        if profiles:
            for prof in profiles:
                console.print(f"  • Updated shell profile: [cyan]{prof}[/cyan]")
        console.print("[green]The 'tome' command is now registered and ready to use in your terminal.[/green]")
        return

    if args.command == "genre":
        file_path = Path(args.input)
        if not file_path.exists():
            console.print(f"[bold red]File not found: {args.input}[/bold red]")
            sys.exit(1)

        if file_path.suffix.lower() == ".pdf":
            import pdf_inspector

            res = pdf_inspector.process_pdf(str(file_path))
            text = res.markdown or ""
        else:
            text = file_path.read_text(encoding="utf-8", errors="ignore")

        detected = detect_genre(text)
        console.print(
            f"[bold cyan]Detected Genre:[/bold cyan] [bold green]{detected.replace('_', ' ').title()}[/bold green]"
        )
        return

    if args.command == "metadata":
        file_path = Path(args.input)
        if not file_path.exists():
            console.print(f"[bold red]File not found: {args.input}[/bold red]")
            sys.exit(1)

        config = TomeConfig.load_config()
        if getattr(args, "no_refine", False):
            config.refine_metadata = False
        elif getattr(args, "refine", None):
            config.refine_metadata = True

        from tome.core.cleaner import clean_markdown_text
        from tome.core.converter import convert_pdf_to_markdown
        from tome.core.epub_converter import convert_epub_to_pdf, convert_mobi_to_pdf
        from tome.core.metadata import extract_book_metadata, refine_metadata_with_llm

        console.print(f"[cyan]Reading manuscript from {file_path.name}[/cyan]")
        ext = file_path.suffix.lower()
        if ext == ".pdf":
            import tempfile

            with tempfile.TemporaryDirectory() as tmp_dir:
                md_path, meta = convert_pdf_to_markdown(file_path, Path(tmp_dir))
                raw_text = md_path.read_text(encoding="utf-8")
                pages = meta.get("page_count", 0)
        elif ext in (".epub", ".mobi"):
            import tempfile

            with tempfile.TemporaryDirectory() as tmp_dir:
                temp_pdf = Path(tmp_dir) / "converted.pdf"
                if ext == ".mobi":
                    pdf_path = convert_mobi_to_pdf(file_path, temp_pdf)
                else:
                    pdf_path = convert_epub_to_pdf(file_path, temp_pdf)
                md_path, meta = convert_pdf_to_markdown(pdf_path, Path(tmp_dir))
                raw_text = md_path.read_text(encoding="utf-8")
                pages = meta.get("page_count", 0)
        else:
            raw_text = file_path.read_text(encoding="utf-8", errors="ignore")
            pages = max(1, len(raw_text.split()) // 275)

        sanitized = clean_markdown_text(raw_text)
        detected_genre = config.resolve_genre(sanitized)
        book_meta = extract_book_metadata(sanitized, file_path, page_count=pages, detected_genre=detected_genre)

        if config.refine_metadata:
            console.print("[cyan]‣ Refining bibliographic metadata with LLM[/cyan]")
            book_meta = refine_metadata_with_llm(book_meta, file_path, sanitized, config)

        display_metadata_panel(book_meta)
        from tome.core.metadata import save_book_metadata

        clean_name = clean_filename_title(file_path)
        dest_dir = Path(args.output) if getattr(args, "output", None) else (config.output_dir / clean_name)
        save_book_metadata(book_meta, dest_dir, config.log_dir, clean_name)
        console.print(f"[bold green]• Saved metadata to {dest_dir}[/bold green]")
        return

    if args.command == "images":
        from tome.core.images import extract_book_images

        config = TomeConfig.load_config()

        file_path = Path(args.input)
        if not file_path.exists():
            console.print(f"[bold red]File not found: {file_path}[/bold red]")
            sys.exit(1)

        out_dir = Path(args.output) if getattr(args, "output", None) else (config.output_dir / file_path.stem)
        t0 = time.perf_counter()
        imgs = extract_book_images(file_path, out_dir)
        duration = round(time.perf_counter() - t0, 2)
        if imgs:
            console.print(
                f"[bold green]• Extracted {len(imgs)} illustrations to {out_dir / 'images'} in {duration}s[/bold green]"
            )
        else:
            console.print(f"[yellow]• No illustrations found in manuscript ({duration}s)[/yellow]")
        return

    if args.command == "translate":
        from tome.core.pipeline import run_pipeline
        from tome.core.translator import translate_book

        config = TomeConfig.load_config()
        if args.lang:
            config.target_language = args.lang
        if args.style:
            config.user_style_rules = args.style
        if args.no_persian_nlp:
            config.persian_nlp = False
        if getattr(args, "llm_model", None):
            config.llm_model = args.llm_model

        book_path = Path(args.book_dir)
        if book_path.is_file():
            title = clean_filename_title(book_path)
            dest_dir = config.output_dir / title
            dest_dir.mkdir(parents=True, exist_ok=True)
            orig_dir = dest_dir / "original"
            orig_dir.mkdir(parents=True, exist_ok=True)
            cleaned_file = orig_dir / f"{title}{book_path.suffix.lower()}"
            if not cleaned_file.exists() or cleaned_file.stat().st_size != book_path.stat().st_size:
                with contextlib.suppress(Exception):
                    import shutil

                    shutil.copy2(book_path, cleaned_file)
            if (
                not (dest_dir / "chapters").exists()
                and not (orig_dir / "book.md").exists()
                and not (dest_dir / "book.md").exists()
            ):
                console.print(f"[cyan]Running preparation pipeline for {book_path.name}[/cyan]")
                run_pipeline(book_path, config)
            book_path = dest_dir

        console.print(f"[bold cyan]Starting translation for {book_path.name} to {config.target_language}[/bold cyan]")

        thinking_printed = False

        def trans_observer(event: str, data: Any) -> None:
            nonlocal thinking_printed
            if event == "stage_start" and data.get("stage") == "glossary_translation":
                console.print(f"[magenta]‣ Translating bilingual glossary ({data.get('count')} entries)[/magenta]")
                thinking_printed = False
            elif event == "glossary_translation_complete":
                if thinking_printed:
                    print()
                console.print(f"[bold green]• Bilingual glossary translated in {data.get('duration')}s[/bold green]")
                thinking_printed = False
            elif event == "chapter_translation_start":
                console.print(
                    f"[cyan]‣ Translating chapter [{data.get('index')}/{data.get('total')}]: {data.get('chapter')}[/cyan]"
                )
                thinking_printed = False
            elif event == "persian_nlp_complete":
                if thinking_printed:
                    print()
                console.print(f"[cyan]• NLP Processing:[/] {data.get('chapter')} -> [dim]{data.get('stats')}[/dim]")
                thinking_printed = False
            elif event == "docx_compilation_start":
                if thinking_printed:
                    print()
                console.print(f"[magenta]‣ Compiling {data.get('file_count')} chapters into Word (.docx)[/magenta]")
                thinking_printed = False
            elif event == "docx_compilation_complete":
                if thinking_printed:
                    print()
                console.print(f"[bold green]• Word manuscript compiled and saved to {data.get('path')}[/bold green]")
                thinking_printed = False
            elif event == "pdf_compilation_complete":
                if thinking_printed:
                    print()
                console.print(f"[bold green]• PDF manuscript compiled and saved to {data.get('path')}[/bold green]")
                thinking_printed = False
            elif event == "officecli_download_start":
                if thinking_printed:
                    print()
                console.print(f"[yellow]‣ Downloading OfficeCLI from {data.get('url')}[/yellow]")
                thinking_printed = False
            elif event == "officecli_download_complete":
                if thinking_printed:
                    print()
                console.print(f"[bold green]• OfficeCLI installed to {data.get('path')}[/bold green]")
                thinking_printed = False
            elif event == "docx_warning":
                if thinking_printed:
                    print()
                console.print(f"[bold yellow]{data.get('warning')}[/bold yellow]")
                thinking_printed = False
            elif event == "avalai_credit_info":
                rem_toman = data.get("remaining_irt", data.get("remaining_toman", 0))
                console.print(f"[bold cyan]• Account Connected:[/] Balance: {rem_toman:,.0f} Toman")
            elif event == "wallet_warning":
                console.print(f"[bold yellow]• {data.get('warning')}[/bold yellow]")
            elif event == "wallet_empty":
                console.print(f"[bold red]• {data.get('error')}[/bold red]")
            elif event == "rate_limit_wait":
                console.print(
                    f"[yellow]• Rate limit reached. Backing off for {data.get('wait_seconds', 15):.1f}s[/yellow]"
                )
            elif event == "chapter_translation_complete":
                if thinking_printed:
                    print()
                toks_info = ""
                if data.get("tokens"):
                    val_toman = data.get("cost_toman", data.get("cost_irt", 0))
                    toks_info = f" (Tokens: {data.get('tokens', 0):,} | Cost: ~{val_toman:,.0f} Toman)"
                console.print(
                    f"[green]• Chapter {data.get('chapter')} translated in {data.get('duration')}s{toks_info}[/green]"
                )
                thinking_printed = False
            elif event == "translation_metrics":
                display_translation_metrics_panel(data)
            elif event == "llm_reasoning_chunk":
                if not thinking_printed:
                    print("\n[Thinking] ", end="", flush=True)
                    thinking_printed = True
                print(f"\033[2m{data}\033[0m", end="", flush=True)
            elif event == "llm_content_chunk":
                pass
            elif event == "api_retry":
                console.print(
                    f"[yellow]API communication error, retrying [{data['attempt']}/{data['max']}]: {data['error']}[/yellow]"
                )
            elif event == "translation_attempt":
                if thinking_printed:
                    print()
                    thinking_printed = False
                att = data.get("attempt", 1)
                max_att = data.get("max_attempts", 3)
                strat = data.get("strategy", "")
                chap = data.get("chapter", "")
                if att > 1:
                    reason = data.get("reason", "")
                    console.print(
                        f"[yellow]• {chap} [Attempt {att}/{max_att}: {strat.title()}] - Output rejected: {reason}[/yellow]"
                    )

        outputs, timings = translate_book(book_path, config, chapters=args.chapters, observer=trans_observer)

        table = Table(
            title="[bold green]Translation Timings[/bold green]",
            box=box.ROUNDED,
            border_style="green",
            header_style="bold cyan",
            expand=True,
        )
        table.add_column("Part", style="white")
        table.add_column("Duration", style="green", justify="right")
        for part, dur in timings.items():
            table.add_row(part, f"{dur:.2f}s")
        console.print(table)
        console.print(
            f"[bold green]Translation complete! {len(outputs)} chapters translated into {book_path / 'translation'}[/bold green]"
        )
        return

    if args.command == "run":
        from tome.core.pipeline import run_pipeline
        from tome.core.translator import translate_book

        config = TomeConfig.load_config()
        config.output_dir = Path(args.output)
        if getattr(args, "genre", None) is not None:
            config.genre = args.genre
        if getattr(args, "model", None) is not None and args.model != "urchade/gliner_medium-v2.1":
            config.default_model = args.model
        if getattr(args, "no_gliner", False):
            config.skip_gliner = True
        if getattr(args, "persian_nlp", False):
            config.persian_nlp = True
        elif getattr(args, "no_persian_nlp", False):
            config.persian_nlp = False
        if getattr(args, "fast", False):
            config.fast_mode = True
        if getattr(args, "batch_size", None) is not None and args.batch_size != 16:
            config.batch_size = args.batch_size
        if getattr(args, "keep_raw", False):
            config.keep_raw_artifacts = True
        if getattr(args, "no_refine_metadata", False):
            config.refine_metadata = False
        elif getattr(args, "refine_metadata", None):
            config.refine_metadata = True
        if getattr(args, "no_images", False):
            config.extract_images = False
        if getattr(args, "llm_model", None):
            config.llm_model = args.llm_model

        def cli_observer(event: str, data: dict) -> None:
            if event == "stage_start":
                stage_name = str(data.get("stage", "")).replace("_", " ").title()
                console.print(f"[cyan]‣ Starting {stage_name}[/cyan]")
            elif event == "conversion_complete":
                cached_tag = " (cached)" if data.get("cached") else ""
                console.print(
                    f"[green]• Manuscript loaded ({data.get('page_count')} pages){cached_tag} in {data.get('duration')}s[/green]"
                )
            elif event == "images_extracted":
                cnt = data.get("image_count", 0)
                dur = data.get("duration", 0)
                if cnt > 0:
                    console.print(f"[green]• Extracted {cnt} illustrations in {dur}s[/green]")
                else:
                    console.print(f"[dim]• No illustrations found ({dur}s)[/dim]")
            elif event == "genre_detected":
                console.print(f"[magenta]• Detected Genre: {data.get('genre')} in {data.get('duration')}s[/magenta]")
            elif event == "metadata_extracted":
                display_metadata_panel(data)
            elif event == "chapterization_complete":
                cached_tag = " (cached)" if data.get("cached") else ""
                console.print(
                    f"[green]• Found {data.get('chapter_count')} chapters{cached_tag} in {data.get('duration')}s[/green]"
                )
            elif event == "extraction_progress":
                print(f"\r  [{data['current']}/{data['total']}] Extracting entities", end="", flush=True)
            elif event == "extraction_complete":
                if not data.get("cached"):
                    print()
                    console.print(
                        f"[green]• Extracted {data.get('entity_count')} entities in {data.get('duration')}s[/green]"
                    )
                else:
                    console.print("[green]• Entities loaded (cached)[/green]")
            elif event == "glossary_translation_complete":
                console.print(f"[bold green]• Bilingual glossary translated in {data.get('duration')}s[/bold green]")
            elif event == "chapter_cached":
                idx = data.get("index", 1)
                total = max(data.get("total", 1), 1)
                console.print(f"[green]• Chapter [{idx}/{total}] {data.get('chapter')} (cached)[/green]")
            elif event == "chapter_translation_start":
                idx = data.get("index", 1)
                total = max(data.get("total", 1), 1)
                console.print(f"[cyan]‣ Translating chapter [{idx}/{total}]: {data.get('chapter')}[/cyan]")
            elif event == "persian_nlp_complete":
                console.print(f"[cyan]• NLP Processing:[/] {data.get('chapter', '')} -> [dim]{data.get('stats')}[/dim]")
            elif event == "docx_compilation_start":
                console.print(f"[magenta]‣ Compiling {data.get('file_count')} chapters into Word (.docx)[/magenta]")
            elif event == "docx_compilation_complete":
                console.print(f"[bold green]• Word manuscript compiled and saved to {data.get('path')}[/bold green]")
            elif event == "pdf_compilation_complete":
                console.print(f"[bold green]• PDF manuscript compiled and saved to {data.get('path')}[/bold green]")
            elif event == "officecli_download_start":
                console.print(f"[yellow]‣ Downloading OfficeCLI from {data.get('url')}[/yellow]")
            elif event == "officecli_download_complete":
                console.print(f"[bold green]• OfficeCLI installed to {data.get('path')}[/bold green]")
            elif event == "docx_warning":
                console.print(f"[bold yellow]{data.get('warning')}[/bold yellow]")
            elif event == "avalai_credit_info":
                rem_toman = data.get("remaining_irt", data.get("remaining_toman", 0))
                console.print(f"[bold cyan]• Account Connected:[/] Balance: {rem_toman:,.0f} Toman")
            elif event == "wallet_warning":
                console.print(f"[bold yellow]• {data.get('warning')}[/bold yellow]")
            elif event == "wallet_empty":
                console.print(f"[bold red]• {data.get('error')}[/bold red]")
            elif event == "rate_limit_wait":
                console.print(
                    f"[yellow]• Rate limit reached. Backing off for {data.get('wait_seconds', 15):.1f}s[/yellow]"
                )
            elif event == "chapter_translation_complete":
                toks_info = ""
                if data.get("tokens"):
                    val_toman = data.get("cost_toman", data.get("cost_irt", 0))
                    toks_info = f" (Tokens: {data.get('tokens', 0):,} | Cost: ~{val_toman:,.0f} Toman)"
                console.print(
                    f"[green]• Chapter {data.get('chapter')} translated in {data.get('duration')}s{toks_info}[/green]"
                )
            elif event == "translation_metrics":
                display_translation_metrics_panel(data)
            elif event == "api_retry":
                console.print(f"[yellow]Network retry [{data['attempt']}/{data['max']}]: {data['error']}[/yellow]")
            elif event == "translation_attempt":
                att = data.get("attempt", 1)
                max_att = data.get("max_attempts", 3)
                strat = data.get("strategy", "")
                chap = data.get("chapter", "")
                if att > 1:
                    reason = data.get("reason", "")
                    console.print(
                        f"[yellow]• {chap} [Attempt {att}/{max_att}: {strat.title()}] - Output rejected: {reason}[/yellow]"
                    )

        result = run_pipeline(Path(args.input), config, observer=cli_observer)

        table = Table(
            title="[bold green]Execution Timings[/bold green]",
            box=box.ROUNDED,
            border_style="green",
            header_style="bold cyan",
            expand=True,
        )
        table.add_column("Step", style="white")
        table.add_column("Duration", style="green", justify="right")
        for step, dur in result.timings.items():
            table.add_row(step.replace("_", " ").title(), f"{dur:.2f}s")
        console.print(table)
        console.print(f"[bold green]Processing complete! Saved to {result.chapter_paths[0].parent.parent}[/bold green]")

        if getattr(args, "translate", False):
            if args.lang:
                config.target_language = args.lang
            console.print("\n[bold cyan]‣ Translating manuscript[/bold cyan]")
            outputs, _ = translate_book(
                result.chapter_paths[0].parent.parent,
                config,
                chapters=args.chapters,
                observer=cli_observer,
            )
            console.print(
                f"[bold green]Full pipeline finished! Translated {len(outputs)} chapters and compiled Word (.docx) book[/bold green]"
            )

    elif args.command == "convert":
        from tome.core.cleaner import clean_markdown_text
        from tome.core.converter import convert_pdf_to_markdown
        from tome.core.epub_converter import convert_epub_to_pdf, convert_mobi_to_pdf

        in_path = Path(args.input)
        if not in_path.exists():
            console.print(f"[bold red]File not found: {in_path}[/bold red]")
            return

        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)
        suffix = in_path.suffix.lower()

        if suffix in (".epub", ".mobi", ".azw3", ".cbz", ".cbr"):
            console.print(f"[cyan]Converting {in_path.name} to intermediate PDF[/cyan]")
            temp_pdf = out_dir / "converted_intermediate.pdf"
            if suffix == ".mobi":
                pdf_path = convert_mobi_to_pdf(in_path, temp_pdf)
            else:
                pdf_path = convert_epub_to_pdf(in_path, temp_pdf)
            md_path, _ = convert_pdf_to_markdown(pdf_path, out_dir)
            if not args.keep_raw:
                cleaned = clean_markdown_text(md_path.read_text(encoding="utf-8"))
                md_path.write_text(cleaned, encoding="utf-8")
        elif suffix == ".pdf":
            md_path, _ = convert_pdf_to_markdown(in_path, out_dir)
            if not args.keep_raw:
                cleaned = clean_markdown_text(md_path.read_text(encoding="utf-8"))
                md_path.write_text(cleaned, encoding="utf-8")
        else:
            md_path = out_dir / "book.md"
            content = in_path.read_text(encoding="utf-8")
            if not args.keep_raw:
                content = clean_markdown_text(content)
            md_path.write_text(content, encoding="utf-8")

        console.print(f"[green]• Saved Markdown to {md_path}[/green]")

    elif args.command == "chapterize":
        from tome.core.chapterizer import segment_chapters

        md_text = Path(args.input).read_text(encoding="utf-8")
        chapters = segment_chapters(md_text, Path(args.output), keep_raw_artifacts=args.keep_raw)
        console.print(f"[green]• Segmented {len(chapters)} chapters into {args.output}[/green]")

    elif args.command == "graph":
        from tome.core.graph import build_character_graph

        chap_dir = Path(args.chapters_dir)
        gloss_path = Path(args.glossary)
        out_path = Path(args.output)
        from tome.models import Chapter, Entity

        chapters = []
        for f in sorted(chap_dir.glob("*.md")):
            chapters.append(
                Chapter(index=len(chapters), title=f.stem, slug=f.stem, content=f.read_text(encoding="utf-8"))
            )

        entities = []
        if gloss_path.exists():
            for line in gloss_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("|") and not line.startswith("| Canonical") and not line.startswith("|---"):
                    cols = [c.strip() for c in line.split("|")[1:-1]]
                    if len(cols) >= 2 and cols[0]:
                        aliases = {a.strip() for a in cols[1].split(",") if a.strip() and a != "—"}
                        entities.append(Entity(canonical=cols[0], category="People & Characters", aliases=aliases))

        build_character_graph(chapters, entities, out_path)
        console.print(f"[green]• Character Relationship Graph saved to {out_path}[/green]")

    elif args.command == "ingest":
        from tome.core.glossary import ingest_chapter_delimiter_entities, write_glossary_markdown

        ch_path = Path(args.chapter_file)
        cleaned, entities = ingest_chapter_delimiter_entities(ch_path.read_text(encoding="utf-8"))
        ch_path.write_text(cleaned, encoding="utf-8")
        if entities:
            grouped = {e.category: [e] for e in entities}
            write_glossary_markdown(grouped, Path(args.glossary))
            console.print(f"[green]• Ingested {len(entities)} entities into {args.glossary}[/green]")

    elif args.command == "setup-model":
        from tome.core.downloader import ensure_gliner_model

        ensure_gliner_model(args.model)
        console.print(f"[green]• Model {args.model} ready.[/green]")

    elif args.command == "edit":
        from tome.core.editor import copyedit_persian_chapter, save_persian_nlp_modifications

        target = Path(args.path)
        out = Path(args.output) if args.output else None
        config = TomeConfig.load_config()
        clean_name = re.sub(r"[^\w\.-]", "_", target.stem if target.is_file() else target.name)
        log_p = config.log_dir / f"persian_nlp_{clean_name}_changes.log"
        from tome.core.logging import prune_old_metrics_and_nlp_logs

        if target.is_file():
            res, stats = copyedit_persian_chapter(target, out, log_path=log_p)
            prune_old_metrics_and_nlp_logs(config.log_dir, max_age_days=config.log_retention_days)
            console.print(f"[green]• Copyedited Persian chapter saved to {res} ({stats.summary()})[/green]")
        elif target.is_dir():
            files = sorted(target.glob("*.md"))
            all_mods: dict[str, int] = {}
            tot_words = 0
            tot_mod = 0
            for f in files:
                out_file = (out / f.name) if out else f
                if out:
                    out.mkdir(parents=True, exist_ok=True)
                _, stats = copyedit_persian_chapter(f, out_file)
                tot_words += stats.words_processed
                tot_mod += stats.words_modified
                for k, v in stats.modifications.items():
                    all_mods[k] = all_mods.get(k, 0) + v
            if all_mods:
                save_persian_nlp_modifications(all_mods, log_p)
            prune_old_metrics_and_nlp_logs(config.log_dir, max_age_days=config.log_retention_days)
            console.print(
                f"[green]• Copyedited {len(files)} chapters in {target} ({tot_mod}/{tot_words} words normalized)[/green]"
            )
        else:
            console.print(f"[red]Error: Path not found: {target}[/red]")

    elif args.command == "docx":
        from tome.core.docx import compile_book_to_docx, is_rtl_language

        config = TomeConfig.load_config()
        if args.lang:
            config.target_language = args.lang
        if getattr(args, "eastern_font", None):
            config.eastern_font = args.eastern_font
        if getattr(args, "western_font", None):
            config.western_font = args.western_font
        if args.font:
            if is_rtl_language(config.target_language):
                config.eastern_font = args.font
            else:
                config.western_font = args.font

        target = Path(args.input)
        out = Path(args.output) if args.output else None

        def docx_obs(ev: str, d: Any) -> None:
            if ev == "officecli_download_start":
                console.print(f"[yellow]‣ Downloading OfficeCLI from {d.get('url')}[/yellow]")
            elif ev == "officecli_download_complete":
                console.print(f"[bold green]• OfficeCLI installed to {d.get('path')}[/bold green]")
            elif ev == "docx_warning":
                console.print(f"[bold yellow]{d.get('warning')}[/bold yellow]")
            elif ev == "docx_compilation_start":
                console.print(f"[cyan]‣ Compiling {d.get('file_count')} Markdown files into Word document[/cyan]")
            elif ev == "docx_compilation_complete":
                console.print(f"[bold green]• Word book successfully compiled to {d.get('path')}[/bold green]")
            elif ev == "pdf_compilation_complete":
                console.print(f"[bold green]• PDF book successfully compiled to {d.get('path')}[/bold green]")

        try:
            res = compile_book_to_docx(target, out, config=config, title=args.title, observer=docx_obs)
            console.print(f"[bold green]• Complete! Generated: {res}[/bold green]")
        except Exception as err:
            console.print(f"[bold red]Word compilation failed: {err}[/bold red]")

    elif args.command == "service":
        from tome.web.service import install_service, service_status, uninstall_service

        if args.action == "install":
            ok, msg = install_service(host=args.host, port=args.port)
            color = "green" if ok else "red"
            console.print(f"[{color}]• {msg}[/{color}]")
        elif args.action == "uninstall":
            ok, msg = uninstall_service()
            console.print(f"[yellow]• {msg}[/yellow]")
        elif args.action == "status":
            ok, msg = service_status()
            console.print(f"[cyan]{msg}[/cyan]")
        elif args.action == "restart":
            uninstall_service()
            ok, msg = install_service(host=args.host, port=args.port)
            color = "green" if ok else "red"
            console.print(f"[{color}]• Service restarted: {msg}[/{color}]")

    elif args.command == "web":
        if getattr(args, "register_service", False):
            from tome.web.service import install_service

            ok, msg = install_service(host=args.host, port=args.port)
            color = "green" if ok else "red"
            console.print(f"[{color}]• {msg}[/{color}]")
            return

        import uvicorn

        active_port = find_available_port(args.port, args.host)
        if active_port != args.port:
            console.print(f"[yellow]• Port {args.port} is already in use. Switched to available port {active_port}[/yellow]")

        console.print(f"[bold green]• Starting Tome Web Platform on http://{args.host}:{active_port}[/bold green]")
        uvicorn.run("tome.web.server:app", host=args.host, port=active_port, reload=args.reload)
    else:
        parser.print_help()

def find_available_port(start_port: int, host: str = "127.0.0.1") -> int:
    import socket
    port = start_port
    bind_host = "0.0.0.0" if host in ("0.0.0.0", "") else host
    while port < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((bind_host, port))
                return port
            except OSError:
                port += 1
    return start_port


def main() -> None:
    try:
        _run_cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]• Operation cancelled by user.[/yellow]")
        sys.exit(130)


if __name__ == "__main__":
    main()
