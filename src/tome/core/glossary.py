import re
from pathlib import Path

from rapidfuzz import distance, fuzz

from tome.models import Entity

DELIMITER_BLOCK_REGEX = re.compile(
    r"<!--\s*ENTITIES_START\s*(.*?)\s*ENTITIES_END\s*-->",
    re.DOTALL | re.IGNORECASE,
)

DELIMITER_LINE_REGEX = re.compile(
    r"-\s*\[(?:Category:\s*)?([^\]]+)\]\s*([^\|]+)\|\s*(?:Translation:\s*)?([^\|]*)(?:\|\s*(?:Aliases:\s*)?([^\|]*))?",
    re.IGNORECASE,
)


def cluster_entities(
    raw_extractions: list[dict],
    min_frequency: int = 2,
    high_confidence_threshold: float = 0.85,
    similarity_threshold: float = 0.88,
    max_edit_distance: int = 2,
) -> dict[str, list[Entity]]:
    category_grouped: dict[str, dict[str, dict]] = {}

    for item in raw_extractions:
        text = item["text"].strip()
        if len(text) <= 1 or text.isdigit():
            continue

        cat = item["category"]
        if cat not in category_grouped:
            category_grouped[cat] = {}

        key = text.lower()
        if key not in category_grouped[cat]:
            category_grouped[cat][key] = {
                "original": text,
                "count": 0,
                "highest_score": 0.0,
                "context": item.get("context", ""),
            }
        category_grouped[cat][key]["count"] += 1
        if item["score"] > category_grouped[cat][key]["highest_score"]:
            category_grouped[cat][key]["highest_score"] = item["score"]
            if item.get("context"):
                category_grouped[cat][key]["context"] = item["context"]

    results: dict[str, list[Entity]] = {}

    for cat, terms in category_grouped.items():
        candidates = [
            data
            for data in terms.values()
            if data["count"] >= min_frequency or data["highest_score"] >= high_confidence_threshold
        ]
        candidates.sort(key=lambda x: len(x["original"]), reverse=True)

        clustered_entities: list[Entity] = []

        for cand in candidates:
            cand_name = cand["original"]
            cand_count = cand["count"]
            cand_context = cand["context"]

            matched = False
            for entity in clustered_entities:
                is_substring = cand_name.lower() in entity.canonical.lower()
                sim_ratio = fuzz.ratio(cand_name.lower(), entity.canonical.lower()) / 100.0
                lev_dist = distance.Levenshtein.distance(cand_name.lower(), entity.canonical.lower())

                if is_substring or sim_ratio >= similarity_threshold or lev_dist <= max_edit_distance:
                    entity.merge_alias(cand_name, count=cand_count)
                    if not entity.sample_context and cand_context:
                        entity.sample_context = cand_context
                    matched = True
                    break

            if not matched:
                clustered_entities.append(
                    Entity(
                        canonical=cand_name,
                        category=cat,
                        count=cand_count,
                        sample_context=cand_context,
                    )
                )

        clustered_entities.sort(key=lambda x: x.count, reverse=True)
        if clustered_entities:
            results[cat] = clustered_entities

    return results


def write_glossary_markdown(
    clusters: dict[str, list[Entity]],
    output_file: Path,
    book_title: str = "Book",
) -> Path:
    lines: list[str] = [f"# Glossary: {book_title}", ""]

    for category, entities in clusters.items():
        lines.append(f"## {category}")
        lines.append(
            "| Canonical Term | Aliases / Variants | Term Translation | Sample Context | Context Translation |"
        )
        lines.append("|---|---|---|---|---|")

        for ent in entities:
            aliases_str = ", ".join(sorted(ent.aliases)) if ent.aliases else "—"
            clean_context = ent.sample_context.replace("|", "/").replace("\n", " ").strip()
            lines.append(f"| {ent.canonical} | {aliases_str} | | {clean_context} | |")

        lines.append("")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("\n".join(lines), encoding="utf-8")
    return output_file


def ingest_chapter_delimiter_entities(chapter_text: str) -> tuple[str, list[Entity]]:
    extracted_entities: list[Entity] = []
    match = DELIMITER_BLOCK_REGEX.search(chapter_text)

    if not match:
        return chapter_text, extracted_entities

    block_content = match.group(1)
    cleaned_chapter_text = DELIMITER_BLOCK_REGEX.sub("", chapter_text).strip() + "\n"

    for line in block_content.splitlines():
        line = line.strip()
        m = DELIMITER_LINE_REGEX.search(line)
        if m:
            cat = m.group(1).strip()
            canonical = m.group(2).strip()
            aliases_raw = m.group(4).strip() if m.group(4) else ""
            aliases = {a.strip() for a in aliases_raw.split(",") if a.strip()} if aliases_raw else set()

            extracted_entities.append(
                Entity(
                    canonical=canonical,
                    category=cat,
                    count=1,
                    aliases=aliases,
                )
            )

    return cleaned_chapter_text, extracted_entities
