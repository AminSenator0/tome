import re
from pathlib import Path

from tome.core.cleaner import clean_markdown_text
from tome.models import Chapter


def sanitize_slug(title: str, index: int) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", title).strip().lower()
    cleaned = re.sub(r"[\s_-]+", "_", cleaned)
    if not cleaned:
        cleaned = f"chapter_{index}"
    return f"{index:02d}_{cleaned[:40]}"


def consolidate_short_chapters(chapters: list[Chapter], min_bytes: int = 512) -> list[Chapter]:
    if not chapters or min_bytes <= 0:
        return chapters

    consolidated: list[Chapter] = []
    pending_prefix = ""

    for idx, ch in enumerate(chapters):
        current_content = (f"{pending_prefix}\n\n{ch.content}").strip() if pending_prefix else ch.content.strip()
        pending_prefix = ""

        content_bytes = len(current_content.encode("utf-8"))
        if content_bytes < min_bytes:
            if idx + 1 < len(chapters):
                pending_prefix = current_content
                continue
            elif consolidated:
                last_ch = consolidated[-1]
                last_ch.content = f"{last_ch.content}\n\n{current_content}".strip()
                continue

        ch.content = current_content
        consolidated.append(ch)

    if pending_prefix and consolidated:
        consolidated[-1].content = f"{consolidated[-1].content}\n\n{pending_prefix}".strip()

    reindexed: list[Chapter] = []
    for i, ch in enumerate(consolidated):
        ch.index = i
        ch.slug = sanitize_slug(ch.title, i)
        reindexed.append(ch)

    return reindexed


def segment_chapters(
    markdown_content: str,
    output_dir: Path,
    keep_raw_artifacts: bool = False,
    min_bytes: int = 512,
) -> list[Chapter]:
    output_dir.mkdir(parents=True, exist_ok=True)

    pattern = re.compile(
        r"^(?:"
        r"#{1,3}\s+(?:chapter|part|book|prologue|epilogue|act|scene|capítulo|chapitre|kapitel|глава|فصل|بخش|قسمت)\b.*|"
        r"(?:chapter|part|book|prologue|epilogue|capítulo|chapitre|kapitel|глава|فصل|بخش|قسمت)\s+(?:[0-9]+|[ivxlcdm]+|[۰-۹]+)\b.*|"
        r"#{1,3}\s+[0-9IVXLCDM۰-۹]+\s*$"
        r")",
        re.IGNORECASE | re.MULTILINE,
    )
    matches = list(pattern.finditer(markdown_content))
    if len(matches) <= 1:
        h1_matches = list(re.finditer(r"^#\s+[^\n\r]+$", markdown_content, re.MULTILINE))
        h2_matches = list(re.finditer(r"^##\s+[^\n\r]+$", markdown_content, re.MULTILINE))
        if len(h1_matches) >= 2:
            matches = h1_matches
        elif len(h2_matches) >= 2:
            matches = h2_matches

    chapters: list[Chapter] = []

    if not matches:
        ch = Chapter(
            index=0,
            title="Full Manuscript",
            slug="00_full_manuscript",
            content=clean_markdown_text(markdown_content, keep_raw_artifacts=keep_raw_artifacts),
            is_front_matter=False,
            is_epilogue=False,
        )
        file_path = output_dir / f"{ch.slug}.md"
        file_path.write_text(ch.content, encoding="utf-8")
        return [ch]

    first_start = matches[0].start()
    if first_start > 0:
        front_matter = markdown_content[:first_start].strip()
        if len(front_matter) > 50:
            cleaned_fm = clean_markdown_text(front_matter, keep_raw_artifacts=keep_raw_artifacts)
            chapters.append(
                Chapter(
                    index=0,
                    title="Front Matter",
                    slug="00_front_matter",
                    content=cleaned_fm,
                    is_front_matter=True,
                )
            )

    for i, match in enumerate(matches):
        start_idx = match.start()
        end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(markdown_content)
        heading_raw = match.group().strip()
        heading_first_line = heading_raw.splitlines()[0]
        clean_title = re.sub(r"^#+\s*", "", heading_first_line).strip()

        if len(re.findall(r"\bchapter\b", heading_raw, re.IGNORECASE)) > 3:
            continue

        raw_chapter_content = markdown_content[start_idx:end_idx]
        cleaned_content = clean_markdown_text(raw_chapter_content, keep_raw_artifacts=keep_raw_artifacts)

        is_epilogue = bool(re.search(r"epilogue|epílogo|خاتمه|مؤخره", clean_title, re.IGNORECASE))

        slug = sanitize_slug(clean_title, len(chapters))
        ch = Chapter(
            index=len(chapters),
            title=clean_title,
            slug=slug,
            content=cleaned_content,
            is_front_matter=False,
            is_epilogue=is_epilogue,
        )
        chapters.append(ch)

    final_chapters = consolidate_short_chapters(chapters, min_bytes=min_bytes)

    for ch in final_chapters:
        file_path = output_dir / f"{ch.slug}.md"
        file_path.write_text(ch.content, encoding="utf-8")

    return final_chapters


clean_text_artifacts = clean_markdown_text
