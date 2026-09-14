from pathlib import Path

from tome.core.metadata import clean_filename_title, extract_book_metadata


def test_clean_filename_title():
    raw_path = Path("Once_Upon_a_Broken_Heart_Once_Upon_a_Broken_Heart,_1_Garber,_Stephanie.pdf")
    title = clean_filename_title(raw_path)
    assert title == "Once Upon A Broken Heart"


def test_extract_book_metadata_english():
    sample_text = """
    Title: Once upon a broken heart / Stephanie Garber.
    Names: Garber, Stephanie, author.
    Copyright © 2021 by Stephanie Garber.
    Address Flatiron Books, 120 Broadway, New York.
    ISBN: 978-1250268396.

    Chapter 1
    This is the opening of the story with some words and text.
    """
    path = Path("Once_Upon_a_Broken_Heart_Once_Upon_a_Broken_Heart,_1_Garber,_Stephanie.pdf")
    meta = extract_book_metadata(sample_text, path, page_count=341, detected_genre="fantasy")

    assert meta.title == "Once Upon A Broken Heart"
    assert "Stephanie Garber" in meta.authors
    assert meta.year == "2021"
    assert meta.publisher == "Flatiron Books"
    assert meta.isbn == "978-1250268396"
    assert meta.page_count == 341
    assert meta.word_count > 10
    assert "m" in meta.reading_time


def test_extract_book_metadata_persian():
    sample_text = """
    عنوان: بوف کور
    نویسنده: صادق هدایت
    سال انتشار: ۱۳۱۵
    ناشر: انتشارات امیرکبیر
    شابک: ۹۷۸-۹۶۴-۰۰-۰۱۱۱-۱

    # بوف کور
    در زندگی زخم‌هایی هست که مثل خوره روح را آهسته در انزوا می‌تراشد و می‌خورد.
    """
    path = Path("Boofe_Koor_Hedayat.pdf")
    meta = extract_book_metadata(sample_text, path, page_count=120, detected_genre="general")

    assert meta.title == "بوف کور"
    assert "صادق هدایت" in meta.authors
    assert meta.year == "1315"
    assert meta.publisher == "انتشارات امیرکبیر"
    assert meta.isbn is not None and "978-964" in meta.isbn


def test_extract_book_metadata_spanish():
    sample_text = """
    Título: Cien años de soledad
    Autor: Gabriel García Márquez
    Año: 1967
    Editorial: Editorial Sudamericana
    ISBN: 978-8437604947

    Muchos años después, frente al pelotón de fusilamiento...
    """
    path = Path("Cien_Anos_de_Soledad.pdf")
    meta = extract_book_metadata(sample_text, path, page_count=450, detected_genre="historical_fiction")

    assert meta.title == "Cien Años De Soledad"
    assert "Gabriel García Márquez" in meta.authors
    assert meta.year == "1967"
    assert meta.publisher == "Editorial Sudamericana"
    assert meta.isbn == "978-8437604947"


def test_extract_book_metadata_french():
    sample_text = """
    Titre: Le Petit Prince
    Auteur: Antoine de Saint-Exupéry
    Année: 1943
    Éditions: Gallimard
    ISBN: 978-2070612758

    Lorsque j'avais six ans j'ai vu, une fois, une magnifique image...
    """
    path = Path("Le_Petit_Prince.pdf")
    meta = extract_book_metadata(sample_text, path, page_count=96, detected_genre="fantasy")

    assert meta.title == "Le Petit Prince"
    assert "Antoine de Saint-Exupéry" in meta.authors
    assert meta.year == "1943"
    assert meta.publisher == "Gallimard"
    assert meta.isbn == "978-2070612758"


def test_extract_book_metadata_german():
    sample_text = """
    Titel: Der Steppenwolf
    Autor: Hermann Hesse
    Jahr: 1927
    Verlag: S. Fischer Verlag
    ISBN: 978-3518366752

    Ein Tag ging hin wie eben solche Tage hingehen...
    """
    path = Path("Der_Steppenwolf.pdf")
    meta = extract_book_metadata(sample_text, path, page_count=240, detected_genre="general")

    assert meta.title == "Der Steppenwolf"
    assert "Hermann Hesse" in meta.authors
    assert meta.year == "1927"
    assert meta.publisher == "S. Fischer Verlag"
    assert meta.isbn == "978-3518366752"


def test_clean_filename_title_noisy():
    noisy_path = Path("[z-lib.org]_1984_George_Orwell_(2003,_Signet_Classic).epub")
    clean = clean_filename_title(noisy_path)
    assert "1984" in clean
    assert "z-lib" not in clean


def test_extract_book_metadata_empty_text_fallback():
    path = Path("The_Great_Gatsby.pdf")
    meta = extract_book_metadata("", path, page_count=0, detected_genre="general")
    assert meta.title == "The Great Gatsby"
    assert meta.authors == ["Unknown"]
    assert meta.reading_time == "1m"


def test_extract_book_metadata_arabic():
    sample_text = """
    عنوان: موسم الهجرة إلى الشمال
    المؤلف: الطيب صالح
    دار النشر: دار العودة
    سنة النشر: 1966
    """
    path = Path("Mawsim_al_Hijra.pdf")
    meta = extract_book_metadata(sample_text, path, page_count=180, detected_genre="general")
    assert meta.title == "موسم الهجرة إلى الشمال"
    assert "الطيب صالح" in meta.authors
    assert meta.publisher == "دار العودة"
    assert meta.year == "1966"


def test_detect_genre_expanded_taxonomies():
    from tome.config import detect_genre

    self_help_sample = """
    A habit is a routine or behavior that is performed regularly and automatically.
    Consistency, discipline, productivity, and focus create momentum for personal development.
    Small improvements compound into remarkable results over time.
    """
    assert detect_genre(self_help_sample) == "self_help_psychology"

    body_language_sample = """
    Nonverbal communication reveals what people are truly thinking and feeling.
    Look at their posture, eye contact, facial expression, and hand gestures.
    Subconscious micro-expressions indicate deception or interpersonal rapport.
    """
    assert detect_genre(body_language_sample) == "psychology_communication"

    spirituality_sample = """
    The law of attraction and the spoken word release divine abundance into your life.
    Faith, intuition, spiritual prayer, and trusting the subconscious mind manifest inner peace.
    """
    assert detect_genre(spirituality_sample) == "spirituality_mindset"

    health_sample = """
    Optimal Health and Nutrition: The Science of Longevity.
    Daily workout, cardiovascular exercise, and balanced diet regulate metabolism.
    A clinical doctor examines symptom patterns, immune health, and cellular recovery.
    """
    assert detect_genre(health_sample) == "health_fitness"

    academic_paper_sample = """
    Abstract
    This study investigates empirical variables using statistical regression analysis.
    Introduction and Literature Review
    The methodology incorporates peer-reviewed datasets and hypothesis testing with p-value < 0.05.
    Findings and Discussion
    Conclusion and References
    DOI: 10.1016/j.res.2024.01.002
    """
    assert detect_genre(academic_paper_sample) == "academic_research"


def test_detect_genre_persian_samples():
    from tome.config import detect_genre

    persian_self_help = "کتاب راهنمای عادات روزانه و رشد فردی و انضباط و موفقیت و تمرکز است."
    assert detect_genre(persian_self_help) == "self_help_psychology"

    persian_body_lang = "کتاب بررسی حالات چهره و حرکات بدن و ارتباط غیرکلامی در روابط اجتماعی."
    assert detect_genre(persian_body_lang) == "psychology_communication"

    persian_spirituality = "راهنمای معنویت، قانون جذب، ایمان، دعا، شکرگزاری و برکت کائنات."
    assert detect_genre(persian_spirituality) == "spirituality_mindset"

    persian_health = "کتاب سلامتی، تغذیه، رژیم غذایی و ورزش برای پیشگیری از بیماری و بهبود سلامت و درمان."
    assert detect_genre(persian_health) == "health_fitness"

    persian_paper = "مقاله علمی: چکیده، پیشینه تحقیق، روش تحقیق و آزمون فرضیه با جامعه آماری و نتیجه‌گیری و منابع."
    assert detect_genre(persian_paper) == "academic_research"


def test_refine_metadata_with_llm_success(monkeypatch, tmp_path):
    from unittest.mock import MagicMock

    from tome.config import TomeConfig
    from tome.core.metadata import BookMetadata, refine_metadata_with_llm

    heuristic = BookMetadata(
        title="[z-lib.org] The Secret of Focus",
        authors=["John Doe, author"],
        year="2020",
        publisher="Random Distributor",
        isbn=None,
        page_count=150,
        word_count=35000,
        char_count=180000,
        reading_time="2h 35m",
        genre="general",
    )

    mock_json = """{
        "title": "The Secret of Focus",
        "authors": ["John Doe"],
        "year": "2021",
        "publisher": "Acme Publishing",
        "isbn": "978-0-123456-47-2",
        "genre": "self_help_psychology",
        "synopsis": "A practical guide to mastering deep focus and habit routines.",
        "keywords": ["focus", "productivity", "habits", "attention"]
    }"""

    mock_execute = MagicMock(return_value=mock_json)
    monkeypatch.setattr("tome.core.translator.execute_llm_completion", mock_execute)
    monkeypatch.setattr("tome.core.translator.get_openai_client", MagicMock())

    config = TomeConfig(llm_api_key="mock-key", refine_metadata=True)
    file_path = tmp_path / "The Secret of Focus.epub"
    file_path.write_text("dummy")

    refined = refine_metadata_with_llm(
        heuristic_meta=heuristic,
        input_file=file_path,
        sanitized_markdown="# Chapter 1\nDeep work is essential...",
        config=config,
    )

    assert refined.title == "The Secret of Focus"
    assert refined.authors == ["John Doe"]
    assert refined.year == "2021"
    assert refined.publisher == "Acme Publishing"
    assert refined.isbn == "978-0-123456-47-2"
    assert refined.genre == "self_help_psychology"
    assert refined.synopsis == "A practical guide to mastering deep focus and habit routines."
    assert "focus" in refined.keywords


def test_refine_metadata_with_llm_fallbacks(monkeypatch, tmp_path):
    from unittest.mock import MagicMock

    from tome.config import TomeConfig
    from tome.core.metadata import BookMetadata, refine_metadata_with_llm

    heuristic = BookMetadata(
        title="Fallback Book Title",
        authors=["Original Author"],
        year="2019",
        publisher="Original Press",
        isbn=None,
        page_count=100,
        word_count=20000,
        char_count=100000,
        reading_time="1h 28m",
        genre="fantasy",
    )

    disabled_cfg = TomeConfig(llm_api_key="mock-key", refine_metadata=False)
    file_path = tmp_path / "Fallback Book Title.epub"
    file_path.write_text("dummy")

    res_disabled = refine_metadata_with_llm(
        heuristic_meta=heuristic,
        input_file=file_path,
        sanitized_markdown="Content",
        config=disabled_cfg,
    )
    assert res_disabled.title == "Fallback Book Title"

    mock_execute = MagicMock(return_value="INVALID NON-JSON RESPONSE FROM LLM")
    monkeypatch.setattr("tome.core.translator.execute_llm_completion", mock_execute)
    monkeypatch.setattr("tome.core.translator.get_openai_client", MagicMock())

    enabled_cfg = TomeConfig(llm_api_key="mock-key", refine_metadata=True)
    res_corrupted = refine_metadata_with_llm(
        heuristic_meta=heuristic,
        input_file=file_path,
        sanitized_markdown="Content",
        config=enabled_cfg,
    )
    assert res_corrupted.title == "Fallback Book Title"
    assert res_corrupted.authors == ["Original Author"]


def test_calculate_reading_time():
    from tome.core.metadata import calculate_reading_time

    assert calculate_reading_time(0) == "1m"
    assert calculate_reading_time(238) == "1m"
    assert calculate_reading_time(2380) == "10m"
    assert calculate_reading_time(23800) == "1h 40m"
    time_with_images = calculate_reading_time(238, image_count=5)
    assert "m" in time_with_images
    persian_time = calculate_reading_time(1900, language="fa")
    assert persian_time == "10m"


def test_save_book_metadata(tmp_path):
    import json

    from tome.core.metadata import BookMetadata, save_book_metadata

    meta = BookMetadata(
        title="Sample Book",
        authors=["Author One"],
        year="2023",
        publisher="Sample Imprint",
        isbn="978-1-234567-89-0",
        page_count=200,
        word_count=50000,
        char_count=250000,
        reading_time="3h 30m",
        genre="fantasy",
        synopsis="A wondrous adventure.",
        keywords=["magic", "adventure"],
    )

    dest_dir = tmp_path / "sample_book"
    log_dir = tmp_path / "logs"

    json_p = save_book_metadata(meta, dest_dir, log_dir, "sample_book")
    assert json_p.exists()
    assert (log_dir / "sample_book_metadata.json").exists()

    data = json.loads(json_p.read_text(encoding="utf-8"))
    assert data["title"] == "Sample Book"
    assert data["genre"] == "fantasy"
    assert data["synopsis"] == "A wondrous adventure."
