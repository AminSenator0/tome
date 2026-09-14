import logging
import os
import re
import warnings
from collections.abc import Callable
from typing import Any

import torch

from tome.core.downloader import ensure_gliner_model

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

warnings.filterwarnings("ignore", message=".*truncated to 384.*")
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*unauthenticated requests to the HF Hub.*")
warnings.filterwarnings("ignore", message=".*HF_TOKEN.*")
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)


def get_inference_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        try:
            _ = torch.zeros(1, device="mps")
            return torch.device("mps")
        except Exception as err:
            logging.getLogger(__name__).debug("MPS backend initialization failed, falling back to CPU: %s", err)
    return torch.device("cpu")


def is_dialogue_only_block(chunk: str) -> bool:
    internal_caps = re.findall(r"(?<!^)(?<!\.\s)(?<!\n)[A-Z][a-z]{2,}", chunk)
    if internal_caps:
        return False
    domain_indicators = (
        "prince",
        "princess",
        "lord",
        "lady",
        "king",
        "queen",
        "curse",
        "spell",
        "magic",
        "arch",
        "hall",
        "palace",
        "fate",
        "dragon",
        "beast",
        "relic",
        "signet",
        "blade",
        "witch",
        "vampire",
        "fae",
        "order",
        "clan",
        "guild",
    )
    lower = chunk.lower()
    return not any(ind in lower for ind in domain_indicators)


def chunk_text(
    text: str,
    chunk_size: int = 280,
    overlap: int = 20,
    fast_filter: bool = False,
) -> list[str]:
    raw_paras = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 10]
    if len(raw_paras) <= 1:
        words = re.findall(r"\S+|\n+", text)
        stride = max(1, chunk_size - overlap)
        return [" ".join(words[i : i + chunk_size]) for i in range(0, len(words), stride) if words[i : i + chunk_size]]

    chunks: list[str] = []
    current: list[str] = []
    current_words = 0

    for para in raw_paras:
        p_len = len(para.split())
        if current_words + p_len > chunk_size and current:
            combined = "\n\n".join(current)
            if not (fast_filter and is_dialogue_only_block(combined)):
                chunks.append(combined)
            current = [para]
            current_words = p_len
        else:
            current.append(para)
            current_words += p_len

    if current:
        combined = "\n\n".join(current)
        if not (fast_filter and is_dialogue_only_block(combined)):
            chunks.append(combined)

    return chunks


def extract_entities(
    text: str,
    model_identifier: str = "urchade/gliner_medium-v2.1",
    taxonomy: dict[str, list[str]] | None = None,
    batch_size: int = 16,
    chunk_size: int = 280,
    chunk_overlap: int = 20,
    fast_filter: bool = False,
    threshold: float = 0.45,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    if not text or not text.strip():
        return []

    torch.set_num_threads(max(1, os.cpu_count() or 4))
    model = ensure_gliner_model(model_identifier)
    device = get_inference_device()
    if device.type != "cpu":
        try:
            model = model.to(device)
        except Exception:
            device = torch.device("cpu")
    model.eval()

    if taxonomy is None:
        from tome.config import GENRE_TAXONOMIES

        taxonomy = GENRE_TAXONOMIES["fantasy"]

    label_to_category: dict[str, str] = {}
    active_labels: list[str] = []
    for cat, labels in taxonomy.items():
        if labels:
            primary_label = labels[0]
            label_to_category[primary_label.lower()] = cat
            active_labels.append(primary_label.lower())

    if not active_labels:
        return []

    chunks = chunk_text(text, chunk_size=chunk_size, overlap=chunk_overlap, fast_filter=fast_filter)
    total_chunks = len(chunks)
    all_extractions: list[dict[str, Any]] = []

    with torch.inference_mode():
        for idx in range(0, total_chunks, batch_size):
            batch = chunks[idx : idx + batch_size]
            try:
                batch_predictions = model.batch_predict_entities(batch, active_labels, threshold=threshold)
            except Exception:
                if device.type != "cpu":
                    device = torch.device("cpu")
                    model = model.to(device)
                    batch_predictions = model.batch_predict_entities(batch, active_labels, threshold=threshold)
                else:
                    raise

            for chunk_idx, entities in enumerate(batch_predictions):
                current_chunk = batch[chunk_idx]
                for ent in entities:
                    ent_text = ent["text"].strip()
                    ent_label = ent["label"].lower()
                    ent_score = float(ent["score"])
                    if ent_score < threshold:
                        continue
                    category = label_to_category.get(ent_label, "Domain Terms & Jargon")

                    sentence_match = re.search(
                        rf"(?:[^\.\n]+)?{re.escape(ent_text)}(?:[^\.\n]+)?",
                        current_chunk,
                    )
                    context_snippet = sentence_match.group().strip() if sentence_match else ent_text

                    all_extractions.append(
                        {
                            "text": ent_text,
                            "label": ent_label,
                            "category": category,
                            "score": ent_score,
                            "context": context_snippet,
                        }
                    )

            if progress_callback:
                progress_callback(min(idx + batch_size, total_chunks), total_chunks)

    return all_extractions
