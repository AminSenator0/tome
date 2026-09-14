import os
import time
from pathlib import Path

from tome.core.logging import (
    prune_old_llm_responses,
    prune_old_logs,
    save_llm_response_cache,
    setup_logger,
)


def test_logger_setup_and_prune(tmp_path: Path):
    logger = setup_logger(tmp_path)
    logger.info("Test execution log entry")
    log_files = list(tmp_path.glob("tome_*.log"))
    assert len(log_files) == 1

    old_log = tmp_path / "tome_2020-01-01_00-00-00.log"
    old_log.write_text("old log content", encoding="utf-8")
    stale_time = time.time() - (8 * 86400)
    os.utime(old_log, (stale_time, stale_time))

    pruned = prune_old_logs(tmp_path, max_age_days=7)
    assert pruned == 1
    assert not old_log.exists()
    assert log_files[0].exists()


def test_save_and_prune_llm_response_cache(tmp_path: Path):
    cache_file = save_llm_response_cache(
        log_dir=tmp_path,
        identifier="chapter_01",
        raw_response="Raw translated markdown content",
        max_age_days=7,
    )
    assert cache_file.exists()
    assert "chapter_01" in cache_file.name
    assert cache_file.read_text(encoding="utf-8") == "Raw translated markdown content"

    responses_dir = tmp_path / "llm"
    old_file = responses_dir / "2020-01-01_00-00-00_old_ch.txt"
    old_file.write_text("very old response", encoding="utf-8")
    stale_time = time.time() - (8 * 86400)
    os.utime(old_file, (stale_time, stale_time))

    pruned = prune_old_llm_responses(responses_dir, max_age_days=7)
    assert pruned == 1
    assert not old_file.exists()
    assert cache_file.exists()


def test_prune_nonexistent_directory(tmp_path: Path):
    non_existent = tmp_path / "phantom_dir"
    assert prune_old_logs(non_existent) == 0
    assert prune_old_llm_responses(non_existent) == 0


def test_save_llm_response_cache_sanitized_identifier(tmp_path: Path):
    cache_file = save_llm_response_cache(
        log_dir=tmp_path,
        identifier="dangerous/../path\\test:chapter?name",
        raw_response="Safe content",
        max_age_days=7,
    )
    assert cache_file.exists()
    assert cache_file.parent == tmp_path / "llm"


def test_prune_old_metrics_and_nlp_logs(tmp_path: Path):
    from tome.core.logging import prune_old_metrics_and_nlp_logs

    old_nlp = tmp_path / "persian_nlp_book_changes.log"
    old_nlp.write_text("old nlp", encoding="utf-8")
    new_nlp = tmp_path / "persian_nlp_fresh_changes.log"
    new_nlp.write_text("fresh nlp", encoding="utf-8")

    stale_time = time.time() - (10 * 86400)
    os.utime(old_nlp, (stale_time, stale_time))

    pruned = prune_old_metrics_and_nlp_logs(tmp_path, max_age_days=7)
    assert pruned == 1
    assert not old_nlp.exists()
    assert new_nlp.exists()


def test_book_scoped_logger_and_structured_json(tmp_path: Path):
    import json

    logger = setup_logger(tmp_path, book_title="Atomic Habits")
    logger.info("Starting segmentation for Atomic Habits")

    log_file = tmp_path / "Atomic_Habits_execution.log"
    json_file = tmp_path / "Atomic_Habits_execution.jsonl"

    assert log_file.exists()
    assert json_file.exists()

    log_text = log_file.read_text(encoding="utf-8")
    assert "[Atomic Habits]" in log_text
    assert "Starting segmentation for Atomic Habits" in log_text

    json_lines = json_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(json_lines) >= 1
    record = json.loads(json_lines[-1])
    assert record["severity"] == "INFO"
    assert record["book"] == "Atomic Habits"
    assert "Atomic Habits" in record["message"]
    assert "logging.googleapis.com/sourceLocation" in record


def test_save_llm_response_cache_with_book_title(tmp_path: Path):
    cache = save_llm_response_cache(
        log_dir=tmp_path,
        identifier="chapter_01",
        raw_response="Translated Chapter",
        book_title="The Compound Effect",
    )
    assert cache.exists()
    assert cache.name.startswith("The_Compound_Effect_")
    assert "chapter_01" in cache.name
