from pathlib import Path

from tome.core.editor import copyedit_persian_chapter, copyedit_persian_text


def test_copyedit_persian_text_half_spaces():
    raw = "او ميرود و خانه ها را ميبيند. شمشير بزرگ تر بود."
    res, stats = copyedit_persian_text(raw)
    assert "می‌رود" in res
    assert "خانه‌ها" in res
    assert "بزرگ‌تر" in res
    assert stats.words_processed > 0
    assert stats.words_modified > 0


def test_copyedit_persian_text_punctuation_and_quotes():
    raw = 'او گفت: "آیا تو آنجا هستی؟" جک پاسخ داد: "بله, مطمئنم...!"'
    res, stats = copyedit_persian_text(raw)
    assert "«آیا تو آنجا هستی؟»" in res
    assert "«بله، مطمئنم" in res
    assert "،" in res
    assert stats.words_processed > 0


def test_copyedit_persian_text_emojis_and_repeated_letters():
    raw = "سلاااام 😊 کتاب 📚 عالییییی بود"
    res, stats = copyedit_persian_text(raw)
    assert "😊" not in res
    assert "📚" not in res
    assert stats.words_processed > 0


def test_copyedit_persian_text_markdown_preservation():
    raw = (
        "# فصل ۱: آزمون\n\n"
        "> اين يك نقل قول است.\n\n"
        "```python\n"
        'print("do not touch")\n'
        "```\n\n"
        "<!-- ENTITIES_START\n"
        "- [Category: People & Characters] Jack | Translation: جک\n"
        "ENTITIES_END -->"
    )
    res, stats = copyedit_persian_text(raw)
    assert res.startswith("# فصل ۱: آزمون")
    assert "> این" in res
    assert 'print("do not touch")' in res
    assert "<!-- ENTITIES_START" in res
    assert "ENTITIES_END -->" in res
    assert "words normalized" in stats.summary()


def test_copyedit_persian_chapter_file(tmp_path: Path):
    ch_file = tmp_path / "01_chap.md"
    ch_file.write_text("# فصل ۱\nاو ميرود.", encoding="utf-8")

    out_file, _ = copyedit_persian_chapter(ch_file)
    assert out_file == ch_file
    text = out_file.read_text(encoding="utf-8")
    assert "می‌رود" in text


def test_copyedit_arabic_kaf_yeh_and_verbal_prefixes():
    raw = "كتاب علي را بياور. او ميرود و نمیافتد."
    res, _ = copyedit_persian_text(raw)
    assert "کتاب" in res
    assert "علی" in res
    assert "بیاور" in res
    assert "نمی‌افتد" in res


def test_copyedit_preserves_markdown_links_and_latin_urls():
    raw = "برای مطالعه [سایت رسمی](https://example.com/api?user=123&test=ok) را بررسی کنید."
    res, _ = copyedit_persian_text(raw)
    assert "[سایت رسمی](https://example.com/api?user=123&test=ok)" in res


def test_copyedit_pure_english_passthrough():
    english_raw = "Hello world! This is a standard sentence, right?"
    res, stats = copyedit_persian_text(english_raw)
    assert "Hello world!" in res
    assert stats.words_modified > 0


def test_copyedit_persian_text_tracks_modifications_with_arrow(tmp_path: Path):
    from tome.core.editor import save_persian_nlp_modifications

    raw = "او ميرود و خانه ها را ميبيند."
    _res, stats = copyedit_persian_text(raw)
    assert len(stats.modifications) > 0
    assert any("→" in k for k in stats.modifications)
    assert not any("=>" in k for k in stats.modifications)

    log_file = tmp_path / "changes.log"
    save_persian_nlp_modifications(stats.modifications, log_file)
    content = log_file.read_text(encoding="utf-8")
    assert "→" in content
    assert "=>" not in content
    assert "# Persian NLP Modifications" in content
