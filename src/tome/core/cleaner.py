import re

MULTILINGUAL_PAGE_PREFIXES = r"page|pág|página|pagina|seite|стр|страница|صفحه|ص|صفحة"

PAGE_NUMBER_REGEX = re.compile(
    rf"(?m)^\s*(?:"
    rf"(?:{MULTILINGUAL_PAGE_PREFIXES})\s*[\.\:]?\s*(?:[0-9]+|[۰-۹]+|[٠-٩]+|[ivxlcdm]+)"
    rf"|(?:[0-9]+|[۰-۹]+|[٠-٩]+|[ivxlcdm]+)\s*(?:/|of|de|von|sur|из|از)\s*(?:[0-9]+|[۰-۹]+|[٠-٩]+)"
    rf"|[-–—~*•|]\s*(?:[0-9]+|[۰-۹]+|[٠-٩]+|[ivxlcdm]+)\s*[-–—~*•|]"
    rf"|\[\s*(?:[0-9]+|[۰-۹]+|[٠-٩]+|[ivxlcdm]+)\s*\]"
    rf"|(?:[0-9]{{1,4}}|[۰-۹]{{1,4}}|[٠-٩]{{1,4}})"
    rf"|(?:[ivxlcdm]{{1,6}})"
    rf")\s*$",
    re.IGNORECASE,
)

RUNNING_HEADER_REGEX = re.compile(r"(?m)^[\s\-_–—]*[A-Z\u0400-\u04FF\u0600-\u06FF\s,.'’\-–—]{4,70}[\s\-_–—]*$")

HYPHENATED_LINEBREAK_REGEX = re.compile(
    r"(\b[a-zA-Z\u0400-\u04FF\u0600-\u06FF]{2,})-\s*\n\s*([a-zA-Z\u0400-\u04FF\u0600-\u06FF]{2,}\b)"
)
COMMON_TLDS = r"com|org|net|ir|co|io|is|ai|me|gg|in|info|biz|ru|uk|de|eu|us|ca|cn|app|dev|link|site|xyz|online|club|top|tech|store"

GENERAL_DOMAIN_REGEX_STR = rf"\b[a-zA-Z0-9_\-\.]{{2,}}\.(?:{COMMON_TLDS})(?:/[^\s)\]]*)?\b"

WATERMARK_LINE_REGEX = re.compile(
    r"^\s*(?:[#*_\->\s~=]*)\s*(?:"
    r"(?:downloaded\s+from|uploaded\s+by|scanned\s+by|shared\s+by|digitized\s+by|proofread\s+by|retail\s+epub|converted\s+by|formatted\s+by|ocr\s+by|transcribed\s+by|prepared\s+for|published\s+on|posted\s+on|epub\s+brought\s+to\s+you\s+by|join\s+(?:us|channel|group)?).*?"
    r"|(?:دانلود\s*(?:شده\s*از|رایگان\s*از)?|کانال\s*(?:رسمی|تلگرام|ایتا|بله|روبیکا)?|عضویت\s*در\s*کانال|مرجع\s*دانلود|ارائه‌شده\s*در|تهیه\s*شده\s*(?:در|توسط)|اسکن\s*اختصاصی|ترجمه\s*اختصاصی|گروه\s*ترجمه|کتابخانه\s*(?:مجازی|دیجیتال)|پایگاه\s*دانلود|منبع:).*?"
    r"|(?:téléchargé\s+sur|heruntergeladen\s+von|descargado\s+de|скачано\s+с).*?"
    rf"|(?:https?://\S+|www\.\S+|{GENERAL_DOMAIN_REGEX_STR}|t\.me/\S+).*?"
    r"|@[\w\.-]{3,}\s*$"
    r"|\[.*?\]\((?:https?://|www\.|\S+\.(?:" + COMMON_TLDS + r"))\S*\)"
    r")\s*(?:[#*_\->\s~=]*)$",
    re.IGNORECASE,
)

INLINE_WATERMARK_REGEX = re.compile(
    rf"(?:\[|\()(?:downloaded\s+from\s+)?(?:https?://\S+|www\.\S+|t\.me/\S+|{GENERAL_DOMAIN_REGEX_STR}|@[\w\.-]{{3,}})(?:\]|\))"
    rf"|https?://[^\s)\]]+"
    rf"|www\.[a-zA-Z0-9_\-\.]+\.(?:{COMMON_TLDS})(?:/[^\s)\]]*)?"
    rf"|{GENERAL_DOMAIN_REGEX_STR}"
    r"|(?<!\S)@[\w\.-]{3,}(?=[.,;!?]?(\s|$))",
    re.IGNORECASE,
)


def clean_markdown_text(text: str, keep_raw_artifacts: bool = False) -> str:
    if not text or not text.strip():
        return ""
    if keep_raw_artifacts:
        return text

    cleaned = HYPHENATED_LINEBREAK_REGEX.sub(r"\1\2", text)
    cleaned = PAGE_NUMBER_REGEX.sub("", cleaned)

    lines = cleaned.splitlines()
    filtered_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            filtered_lines.append("")
            continue

        if WATERMARK_LINE_REGEX.match(stripped):
            continue

        if stripped.startswith(("[^", "* [^", "†", "‡", "|", "#", "```", ">", "- [", "1.")):
            filtered_lines.append(INLINE_WATERMARK_REGEX.sub("", line).strip())
            continue

        if RUNNING_HEADER_REGEX.match(stripped) and len(stripped.split()) < 6 and stripped.isupper():
            continue

        cleaned_line = INLINE_WATERMARK_REGEX.sub("", line)
        cleaned_line = re.sub(r"[ \t]{2,}", " ", cleaned_line)
        if cleaned_line.strip():
            filtered_lines.append(cleaned_line)

    result = "\n".join(filtered_lines)
    return re.sub(r"\n{3,}", "\n\n", result).strip() + "\n"
