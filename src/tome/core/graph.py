import re
from collections import defaultdict
from pathlib import Path

from tome.models import Chapter, Entity


def load_entities_from_glossary(glossary_path: Path) -> list[Entity]:
    entities: list[Entity] = []
    if not glossary_path.exists():
        return entities

    for line in glossary_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("|") and not line.startswith("| Canonical") and not line.startswith("|---"):
            cols = [c.strip() for c in line.split("|")[1:-1]]
            if len(cols) >= 2 and cols[0]:
                aliases = {a.strip() for a in cols[1].split(",") if a.strip() and a != "—"}
                ctx = cols[3] if len(cols) > 3 and cols[3] != "—" else ""
                entities.append(
                    Entity(canonical=cols[0], category="People & Characters", aliases=aliases, sample_context=ctx)
                )
    return entities


def extract_character_names(entities: list[Entity]) -> tuple[dict[str, set[str]], dict[str, Entity]]:
    character_map: dict[str, set[str]] = {}
    entity_by_canonical: dict[str, Entity] = {}
    for ent in entities:
        if ent.category in {"People & Characters", "Species, Races & Organisms"}:
            if len(ent.canonical) < 3 or ent.canonical.lower() in {"she", "he", "they", "it"}:
                continue
            all_variants = {ent.canonical} | set(ent.aliases)
            character_map[ent.canonical] = all_variants
            entity_by_canonical[ent.canonical] = ent
    return character_map, entity_by_canonical


def build_character_graph(
    chapters: list[Chapter],
    entities: list[Entity],
    output_file: Path,
    book_title: str = "Book",
    top_n: int = 20,
) -> Path:
    char_variants, entity_meta = extract_character_names(entities)
    if not char_variants:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(
            f"# Executive Character & Relationship Dossier: {book_title}\n\n*No major characters extracted.*\n",
            encoding="utf-8",
        )
        return output_file

    chapter_character_counts: dict[str, dict[str, int]] = defaultdict(dict)
    character_totals: dict[str, int] = defaultdict(int)
    character_first_seen: dict[str, str] = {}
    character_chapters: dict[str, list[str]] = defaultdict(list)
    pair_interaction_snippets: dict[tuple[str, str], str] = {}

    for ch in chapters:
        ch_text = ch.content
        paragraphs = [p.strip() for p in ch_text.split("\n\n") if p.strip()]

        for canonical, variants in char_variants.items():
            count = 0
            for v in variants:
                count += len(re.findall(rf"\b{re.escape(v)}\b", ch_text, re.IGNORECASE))
            if count > 0:
                chapter_character_counts[ch.title][canonical] = count
                character_totals[canonical] += count
                character_chapters[canonical].append(ch.title)
                if canonical not in character_first_seen:
                    character_first_seen[canonical] = ch.title

        for para in paragraphs:
            present_in_para: list[str] = []
            for canonical, variants in char_variants.items():
                if any(re.search(rf"\b{re.escape(v)}\b", para, re.IGNORECASE) for v in variants):
                    present_in_para.append(canonical)

            if len(present_in_para) >= 2:
                for i in range(len(present_in_para)):
                    for j in range(i + 1, len(present_in_para)):
                        p1, p2 = sorted([present_in_para[i], present_in_para[j]])
                        pair_key = (p1, p2)
                        if pair_key not in pair_interaction_snippets:
                            cleaned_snippet = " ".join(para.split())
                            if len(cleaned_snippet) > 220:
                                cleaned_snippet = cleaned_snippet[:220].rstrip()
                            pair_interaction_snippets[pair_key] = cleaned_snippet

    sorted_characters = sorted(character_totals.items(), key=lambda x: x[1], reverse=True)[:top_n]
    top_char_names = [c[0] for c in sorted_characters]

    co_occurrences: dict[tuple[str, str], int] = defaultdict(int)
    co_occurring_chapters: dict[tuple[str, str], list[str]] = defaultdict(list)
    for ch in chapters:
        present_chars = chapter_character_counts.get(ch.title, {})
        present_top = [c for c in top_char_names if c in present_chars]
        for i in range(len(present_top)):
            for j in range(i + 1, len(present_top)):
                c1, c2 = sorted([present_top[i], present_top[j]])
                co_occurrences[(c1, c2)] += 1
                co_occurring_chapters[(c1, c2)].append(ch.title)

    lines: list[str] = [
        f"# Character Relationship & Narrative Dossier: {book_title}",
        "",
        "## Executive Character & Relationship Dossier (LLM Reference)",
        "",
        "### 1. Primary Character Profiles",
    ]

    for name, total in sorted_characters:
        active_count = len(character_chapters[name])
        first_app = character_first_seen.get(name, "—")
        ent = entity_meta.get(name)
        aliases_str = f" | Aliases: {', '.join(sorted(ent.aliases))}" if (ent and ent.aliases) else ""
        archetype = (
            "Protagonist / Leading Character"
            if total >= sorted_characters[0][1] * 0.5
            else "Major Supporting Character" if active_count >= max(2, len(chapters) // 4) else "Recurring Character"
        )
        ctx_snippet = f' | Sample Context: "{ent.sample_context}"' if (ent and ent.sample_context) else ""
        lines.append(
            f"- **{name}**{aliases_str}\n"
            f"  - Mentions: {total:,} across {active_count} chapter(s) | First Appearance: {first_app} | Role: {archetype}{ctx_snippet}"
        )

    lines.extend(["", "### 2. Semantic Interpersonal Dynamics"])
    sorted_pairs = sorted(co_occurrences.items(), key=lambda x: x[1], reverse=True)
    if not sorted_pairs:
        lines.append("- No explicit character co-occurrences detected.")
    else:
        for (c1, c2), shared_count in sorted_pairs:
            pair_key = (c1, c2)
            shared_ch_list = ", ".join(co_occurring_chapters[pair_key][:4])
            if len(co_occurring_chapters[pair_key]) > 4:
                shared_ch_list += f", +{len(co_occurring_chapters[pair_key]) - 4} more"

            strength = (
                "Central Bond / Constant Scene Partners"
                if shared_count >= 5
                else "Frequent Interaction" if shared_count >= 3 else "Occasional / Scene Contact"
            )
            snippet = pair_interaction_snippets.get(pair_key, "")
            snippet_str = f'\n    - Scene Interaction: "{snippet}"' if snippet else ""

            lines.append(
                f"- **{c1}** ⟷ **{c2}**:\n"
                f"  - Dynamic: {strength} ({shared_count} shared chapters: {shared_ch_list}){snippet_str}"
            )

    lines.extend(
        [
            "",
            "## Narrative Relationship Network",
            "```mermaid",
            "graph TD",
        ]
    )

    for name, total in sorted_characters:
        node_id = re.sub(r"\W+", "_", name)
        lines.append(f'    {node_id}["{name}<br/>({total:,} mentions)"]')

    for (c1, c2), shared_count in sorted(co_occurrences.items(), key=lambda x: x[1], reverse=True):
        if shared_count >= 2:
            id1 = re.sub(r"\W+", "_", c1)
            id2 = re.sub(r"\W+", "_", c2)
            lines.append(f'    {id1} ---|"{shared_count} chapters"| {id2}')

    lines.extend(
        [
            "```",
            "",
            "## Character Overview & Trajectory",
            "| Character | Total Mentions | Active Chapters | First Appearance | Major Associates |",
            "|---|---|---|---|---|",
        ]
    )

    for name, total in sorted_characters:
        active_count = len(character_chapters[name])
        first_app = character_first_seen.get(name, "—")
        associates = []
        for other in top_char_names:
            if other == name:
                continue
            o1, o2 = sorted([name, other])
            pair = (o1, o2)
            if pair in co_occurrences and co_occurrences[pair] >= 2:
                associates.append(f"{other} ({co_occurrences[pair]} ch)")
        associates_str = ", ".join(associates[:3]) if associates else "—"
        lines.append(f"| {name} | {total:,} | {active_count} | {first_app} | {associates_str} |")

    lines.extend(
        [
            "",
            "## Chapter Scene Presence Matrix",
            "| Chapter | Active Cast | Dominant Focus |",
            "|---|---|---|",
        ]
    )

    for ch in chapters:
        present = chapter_character_counts.get(ch.title, {})
        top_in_ch = sorted(
            [c for c in present.items() if c[0] in top_char_names],
            key=lambda x: x[1],
            reverse=True,
        )
        if not top_in_ch:
            continue
        dominant = top_in_ch[0][0]
        cast_list = ", ".join([f"{c[0]} ({c[1]})" for c in top_in_ch[:5]])
        lines.append(f"| {ch.title} | {cast_list} | {dominant} |")

    lines.append("")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("\n".join(lines), encoding="utf-8")
    return output_file
