from tome.core.cleaner import clean_markdown_text


def test_multilingual_page_cleaning():
    text = """
Chapter 1
Some narrative text here.

Page 42

More narrative text.

Página 43

Still more narrative.

صفحه ۴۴

Another paragraph.

XIV

Final line of chapter.
[^1]: This is a footnote that must be kept.
"""
    cleaned = clean_markdown_text(text)
    assert "Page 42" not in cleaned
    assert "Página 43" not in cleaned
    assert "صفحه ۴۴" not in cleaned
    assert "XIV" not in cleaned
    assert "[^1]: This is a footnote that must be kept." in cleaned


def test_running_header_cleaning():
    text = """
STEPHANIE GARBER

Evangeline walked through the door.

ONCE UPON A BROKEN HEART

She saw Jacks waiting.
"""
    cleaned = clean_markdown_text(text)
    assert "STEPHANIE GARBER" not in cleaned
    assert "ONCE UPON A BROKEN HEART" not in cleaned
    assert "Evangeline walked through the door." in cleaned


def test_cleaner_german_french_and_isbn_stamps():
    text = """
# Chapter 2
Narrative text begins.

Seite 99
Page 100

More text here.
"""
    cleaned = clean_markdown_text(text)
    assert "Seite 99" not in cleaned
    assert "Page 100" not in cleaned
    assert "More text here." in cleaned


def test_cleaner_preserves_markdown_tables_and_quotes():
    text = """
| Chapter | Page Count | Notes |
|---|---|---|
| Chapter 1 | 42 | Introduction |
| Chapter 2 | 43 | Development |

> Quote from Page 42 that must be kept.
"""
    cleaned = clean_markdown_text(text)
    assert "| Chapter 1 | 42 | Introduction |" in cleaned
    assert "> Quote from Page 42 that must be kept." in cleaned


def test_cleaner_empty_and_whitespace():
    assert clean_markdown_text("") == ""
    assert clean_markdown_text("   \n\n\t  ") == ""


def test_cleaner_removes_annas_archive_and_zlibrary_watermarks():
    raw = """
Downloaded from Anna’s Archive
Z-Library Project (z-lib.org)

# Chapter 1

This is the genuine chapter story.

Downloaded from https://oceanofpdf.com
"""
    cleaned = clean_markdown_text(raw)
    assert "# Chapter 1" in cleaned
    assert "genuine chapter story" in cleaned
    assert "Anna’s Archive" not in cleaned
    assert "oceanofpdf" not in cleaned


def test_cleaner_removes_telegram_channel_watermarks():
    raw = """
Join @book_channel on Telegram for more books!
t.me/ebook_central

# Chapter 2

The journey begins under starlight.
"""
    cleaned = clean_markdown_text(raw)
    assert "# Chapter 2" in cleaned
    assert "The journey begins under starlight." in cleaned
    assert "t.me/ebook_central" not in cleaned


def test_cleaner_removes_ble_and_eitaa_watermarks():
    raw = """
کانال رسمی در بله: https://ble.ir/novels_channel
عضویت در کانال ایتا: eitaa.com/persian_books
دانلود شده از eitaa.ir/books
مرجع دانلود رمان @roman_center

# فصل اول

خورشید بر فراز تپه‌ها می‌درخشید. (دانلود شده از ble.ir/novels_channel)

پایان فصل.
"""
    cleaned = clean_markdown_text(raw)
    assert "# فصل اول" in cleaned
    assert "خورشید بر فراز تپه‌ها می‌درخشید." in cleaned
    assert "پایان فصل." in cleaned
    assert "ble.ir" not in cleaned
    assert "eitaa.com" not in cleaned
    assert "eitaa.ir" not in cleaned
    assert "مرجع دانلود" not in cleaned


def test_cleaner_general_domains_and_usernames():
    raw = """
Check out https://custom-book-vault.xyz/download
Join our community: @secret_novel_club!
Mirror at www.archive-hub.tech/library
Read on novels-online.net today.

# Chapter 3

The castle gates creaked open in the moonlight. (found on ebook-sharing.co)
"""
    cleaned = clean_markdown_text(raw)
    assert "# Chapter 3" in cleaned
    assert "The castle gates creaked open in the moonlight." in cleaned
    assert "custom-book-vault.xyz" not in cleaned
    assert "@secret_novel_club" not in cleaned
    assert "archive-hub.tech" not in cleaned
    assert "novels-online.net" not in cleaned
    assert "ebook-sharing.co" not in cleaned
