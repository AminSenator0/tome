from tome.cli.main import build_parser


def test_cli_parser_defaults():
    parser = build_parser()
    args = parser.parse_args(["run", "book.pdf", "-g", "fantasy", "--no-gliner", "--no-persian-nlp"])
    assert args.command == "run"
    assert args.input == "book.pdf"
    assert args.genre == "fantasy"
    assert args.no_gliner is True
    assert args.no_persian_nlp is True
    assert args.batch_size == 16

    args_np = parser.parse_args(["run", "book.pdf", "-np"])
    assert args_np.no_persian_nlp is True

    args_trans_np = parser.parse_args(["translate", "book_dir", "-np", "--llm-model", "qwen3.8-flash"])
    assert args_trans_np.no_persian_nlp is True
    assert args_trans_np.llm_model == "qwen3.8-flash"

    args_run_model = parser.parse_args(["run", "book.pdf", "--llm-model", "gemini-flash-latest"])
    assert args_run_model.llm_model == "gemini-flash-latest"

    args_short = parser.parse_args(["run", "book.pdf", "-lm", "glm-5.3-flash"])
    assert args_short.llm_model == "glm-5.3-flash"

    args_trans_short = parser.parse_args(["translate", "book_dir", "-lm", "qwen3.8-flash"])
    assert args_trans_short.llm_model == "qwen3.8-flash"

    args_rm = parser.parse_args(["run", "book.pdf", "-rm"])
    assert args_rm.refine_metadata is True

    args_no_rm = parser.parse_args(["run", "book.pdf", "--no-refine-metadata"])
    assert args_no_rm.no_refine_metadata is True


def test_cli_parser_subcommands():
    parser = build_parser()
    conv_args = parser.parse_args(["convert", "input.pdf", "-o", "out_dir"])
    assert conv_args.command == "convert"
    assert conv_args.input == "input.pdf"
    assert conv_args.output == "out_dir"

    epub_args = parser.parse_args(["convert", "book.epub", "-o", "out_dir"])
    assert epub_args.command == "convert"
    assert epub_args.input == "book.epub"

    chap_args = parser.parse_args(["chapterize", "full.md", "-o", "chapters_out"])
    assert chap_args.command == "chapterize"
    assert chap_args.input == "full.md"
    assert chap_args.output == "chapters_out"

    edit_args = parser.parse_args(["edit", "chap.md", "-o", "edited_chap.md"])
    assert edit_args.command == "edit"
    assert edit_args.path == "chap.md"
    assert edit_args.output == "edited_chap.md"

    docx_args = parser.parse_args(
        ["docx", "chapters/", "-o", "book.docx", "--font", "Vazirmatn", "-ef", "B-Nazanin.ttf", "-wf", "Times.ttf"]
    )
    assert docx_args.command == "docx"
    assert docx_args.input == "chapters/"
    assert docx_args.output == "book.docx"
    assert docx_args.font == "Vazirmatn"
    assert docx_args.eastern_font == "B-Nazanin.ttf"
    assert docx_args.western_font == "Times.ttf"

    graph_args = parser.parse_args(["graph", "chapters/", "-g", "glossary.md", "-o", "graph.md"])
    assert graph_args.command == "graph"
    assert graph_args.chapters_dir == "chapters/"
    assert graph_args.glossary == "glossary.md"
    assert graph_args.output == "graph.md"

    trans_args = parser.parse_args(["translate", "chapters/", "-c", "5 to 10", "-s", "Style rule 1\\nStyle rule 2"])
    assert trans_args.command == "translate"
    assert trans_args.chapters == "5 to 10"
    assert "Style rule 1" in trans_args.style

    setup_args = parser.parse_args(["setup-model", "-m", "urchade/gliner_small-v2.1"])
    assert setup_args.command == "setup-model"

    meta_args = parser.parse_args(["metadata", "manuscript.pdf", "-rm", "-o", "meta.json"])
    assert meta_args.command == "metadata"
    assert meta_args.input == "manuscript.pdf"
    assert meta_args.refine is True
    assert meta_args.output == "meta.json"

    meta_no_rf = parser.parse_args(["metadata", "manuscript.epub", "--no-refine"])
    assert meta_no_rf.command == "metadata"
    assert meta_no_rf.no_refine is True
    assert setup_args.model == "urchade/gliner_small-v2.1"

    genre_args = parser.parse_args(["genre", "book.md"])
    assert genre_args.command == "genre"
    assert genre_args.input == "book.md"

    images_args = parser.parse_args(["images", "book.pdf", "-o", "out_imgs"])
    assert images_args.command == "images"
    assert images_args.input == "book.pdf"
    assert images_args.output == "out_imgs"

    run_no_imgs = parser.parse_args(["run", "book.pdf", "--no-images"])
    assert run_no_imgs.command == "run"
    assert run_no_imgs.no_images is True

    run_short_ni = parser.parse_args(["run", "book.pdf", "-ni"])
    assert run_short_ni.no_images is True


def test_cli_main_keyboard_interrupt(monkeypatch):
    import pytest

    import tome.cli.main as cli_main

    def mock_run_cli():
        raise KeyboardInterrupt()

    monkeypatch.setattr(cli_main, "_run_cli", mock_run_cli)
    with pytest.raises(SystemExit) as exc:
        cli_main.main()
    assert exc.value.code == 130


def test_display_panels_and_tables():
    from tome.cli.main import display_metadata_panel, display_translation_metrics_panel
    from tome.core.metadata import BookMetadata

    meta = BookMetadata(
        title="Sample Book",
        authors=["Author Name"],
        year="2024",
        publisher="Publisher",
        isbn="123-4567890",
        genre="fantasy",
        page_count=100,
        word_count=25000,
        char_count=130000,
        reading_time="2h 10m",
    )
    display_metadata_panel(meta)

    metrics = {
        "model": "qwen3.8-flash",
        "total_cost_toman": 5000.0,
        "average_cost_toman_per_chapter": 2500.0,
        "total_duration_seconds": 30.0,
        "average_duration_seconds": 15.0,
        "total_tokens": 10000,
        "average_tokens_per_chapter": 5000.0,
        "initial_credit_toman": 100000.0,
        "final_credit_toman": 95000.0,
        "consumed_credit_toman": 5000.0,
        "consumed_credit_percent": 5.0,
        "nlp_words_processed": 1000,
        "nlp_words_modified": 50,
        "nlp_unique_modifications_count": 10,
        "chapters": [
            {
                "chapter_name": "ch1.md",
                "duration_seconds": 15.0,
                "total_tokens": 5000,
                "cost_toman": 2500.0,
                "words_normalized": 25,
            }
        ],
    }
    display_translation_metrics_panel(metrics)
