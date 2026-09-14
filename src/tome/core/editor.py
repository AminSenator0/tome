import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shekar import Normalizer
from shekar.preprocessing import DiacriticRemover, EmojiRemover, RepeatedLetterNormalizer


@dataclass
class CopyeditStats:
    words_processed: int = 0
    words_modified: int = 0
    modifications: dict[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        return f"{self.words_modified}/{self.words_processed} words normalized"


_NORMALIZER: Normalizer | None = None
_EMOJI_REMOVER: EmojiRemover | None = None
_REPEATED_NORMALIZER: RepeatedLetterNormalizer | None = None
_DIACRITIC_REMOVER: DiacriticRemover | None = None


def get_persian_nlp_pipeline() -> tuple[Normalizer, EmojiRemover, RepeatedLetterNormalizer, DiacriticRemover]:
    global _NORMALIZER, _EMOJI_REMOVER, _REPEATED_NORMALIZER, _DIACRITIC_REMOVER
    if _NORMALIZER is None:
        _NORMALIZER = Normalizer()
    if _EMOJI_REMOVER is None:
        _EMOJI_REMOVER = EmojiRemover()
    if _REPEATED_NORMALIZER is None:
        _REPEATED_NORMALIZER = RepeatedLetterNormalizer()
    if _DIACRITIC_REMOVER is None:
        _DIACRITIC_REMOVER = DiacriticRemover()
    return _NORMALIZER, _EMOJI_REMOVER, _REPEATED_NORMALIZER, _DIACRITIC_REMOVER


def copyedit_persian_text(text: str, normalizer: Any | None = None) -> tuple[str, CopyeditStats]:
    norm, emoji_rem, rep_norm, diacritic_rem = get_persian_nlp_pipeline()
    if normalizer is not None:
        norm = normalizer

    entity_block = ""
    m = re.search(r"(<!--\s*ENTITIES_START.*?ENTITIES_END\s*-->)", text, flags=re.DOTALL)
    if m:
        entity_block = m.group(1)
        text = text[: m.start()] + text[m.end() :]

    lines = text.splitlines()
    out_lines: list[str] = []
    in_code_block = False

    total_words = 0
    words_mod = 0
    mod_dict: dict[str, int] = {}

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            out_lines.append(line)
            continue
        if in_code_block or not stripped:
            out_lines.append(line)
            continue

        prefix = ""
        m_prefix = re.match(r"^(\s*(?:#{1,6}\s+|>\s*|[-*+]\s+|\d+\.\s+|[—–-]\s*))", line)
        if m_prefix:
            prefix = m_prefix.group(1)
            content = line[len(prefix) :]
        else:
            content = line

        orig_words = content.split()
        total_words += len(orig_words)
        protected: list[str] = []

        def _make_replacer(acc: list[str]):
            def _repl(m: re.Match) -> str:
                idx = len(acc)
                acc.append(m.group(0))
                tag = "".join(chr(65 + int(d)) for d in str(idx))
                return f"TOMETOKEN{tag}XYZ"

            return _repl

        protected_content = re.sub(r"\[.*?\]\(.*?\)|\`.*?\`|<[^>\n]+>", _make_replacer(protected), content)

        clean_emojis = str(emoji_rem(protected_content))
        normalized = str(norm(clean_emojis))
        normalized = str(rep_norm(normalized))
        normalized = str(diacritic_rem(normalized))

        normalized = re.sub(r'"([^"]+)"', r"«\1»", normalized)
        normalized = normalized.replace(",", "،").replace("?", "؟").replace(";", "؛")
        normalized = re.sub(r"\.{3,}", "…", normalized)
        normalized = re.sub(r"\s+([،؛\.؟!…»\)])", r"\1", normalized)
        normalized = re.sub(r"([«\(])\s+", r"\1", normalized)
        normalized = re.sub(r"([،؛\.؟!…»])([^\s،؛\.؟!…»\)\d\n])", r"\1 \2", normalized)

        for i, val in enumerate(protected):
            tag = "".join(chr(65 + int(d)) for d in str(i))
            normalized = normalized.replace(f"TOMETOKEN{tag}XYZ", val)

        after_words = normalized.split()
        diff = sum(1 for w1, w2 in zip(orig_words, after_words) if w1 != w2) + abs(len(orig_words) - len(after_words))
        words_mod += diff

        if orig_words != after_words:
            sm = difflib.SequenceMatcher(None, orig_words, after_words)
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag != "equal":
                    w1 = " ".join(orig_words[i1:i2]).strip()
                    w2 = " ".join(after_words[j1:j2]).strip()
                    if w1 and w2 and w1 != w2:
                        pair = f"{w1} → {w2}"
                        mod_dict[pair] = mod_dict.get(pair, 0) + 1

        out_lines.append(prefix + normalized)

    result = "\n".join(out_lines)
    if entity_block:
        result = result.rstrip() + "\n\n" + entity_block

    stats = CopyeditStats(
        words_processed=total_words,
        words_modified=words_mod,
        modifications=mod_dict,
    )
    return result, stats


def save_persian_nlp_modifications(modifications: dict[str, int], target_path: Path) -> Path:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    sorted_items = sorted(modifications.items(), key=lambda x: (-x[1], x[0]))
    total_mods = sum(modifications.values())
    lines = [
        "# Persian NLP Modifications",
        f"Total Unique Corrections: {len(modifications)}",
        f"Total Modifications: {total_mods}",
        "",
    ]
    for pair, count in sorted_items:
        lines.append(f"{pair} (x{count})")
    lines.append("")
    target_path.write_text("\n".join(lines), encoding="utf-8")
    return target_path


def copyedit_persian_chapter(
    chapter_path: Path, output_path: Path | None = None, log_path: Path | None = None
) -> tuple[Path, CopyeditStats]:
    target_out = output_path or chapter_path
    content = chapter_path.read_text(encoding="utf-8")
    edited, stats = copyedit_persian_text(content)
    target_out.write_text(edited, encoding="utf-8")
    if log_path and stats.modifications:
        save_persian_nlp_modifications(stats.modifications, log_path)
    return target_out, stats
