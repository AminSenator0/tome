import json
import logging
import re
import time
from datetime import UTC, datetime
from pathlib import Path


class GoogleStructuredFormatter(logging.Formatter):
    def __init__(self, book_title: str | None = None) -> None:
        super().__init__()
        self.book_title = book_title

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=UTC).isoformat()
        payload = {
            "time": ts,
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "logging.googleapis.com/sourceLocation": {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            },
        }
        if self.book_title:
            payload["book"] = self.book_title
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class StandardTextFormatter(logging.Formatter):
    def __init__(self, book_title: str | None = None) -> None:
        super().__init__()
        self.book_title = book_title

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=UTC).isoformat()
        book_tag = f"[{self.book_title}] " if self.book_title else ""
        exc_str = f"\n{self.formatException(record.exc_info)}" if record.exc_info else ""
        return f"{ts} | {record.levelname:<8} | {record.name} | {book_tag}{record.getMessage()}{exc_str}"


def setup_logger(
    log_dir: Path,
    book_title: str | None = None,
    level: int = logging.INFO,
) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    clean_title = re.sub(r"[^\w\.-]", "_", book_title) if book_title else ""
    logger_name = f"tome.{clean_title}" if clean_title else "tome"
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.propagate = False

    if clean_title:
        log_file = log_dir / f"{clean_title}_execution.log"
        json_file = log_dir / f"{clean_title}_execution.jsonl"
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_file = log_dir / f"tome_{timestamp}.log"
        json_file = None

    if not logger.handlers:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(StandardTextFormatter(book_title=book_title))
        logger.addHandler(file_handler)

        if json_file:
            json_handler = logging.FileHandler(json_file, encoding="utf-8")
            json_handler.setFormatter(GoogleStructuredFormatter(book_title=book_title))
            logger.addHandler(json_handler)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(StandardTextFormatter(book_title=book_title))
        stream_handler.setLevel(logging.WARNING)
        logger.addHandler(stream_handler)

    prune_old_metrics_and_nlp_logs(log_dir, max_age_days=7)
    return logger


def prune_old_logs(log_dir: Path, max_age_days: int = 7) -> int:
    if not log_dir.exists():
        return 0

    cutoff_seconds = time.time() - (max_age_days * 86400)
    pruned_count = 0

    for log_path in log_dir.glob("tome_*.log"):
        try:
            if log_path.stat().st_mtime < cutoff_seconds:
                log_path.unlink()
                pruned_count += 1
        except OSError:
            continue

    return pruned_count


def save_llm_response_cache(
    log_dir: Path,
    identifier: str,
    raw_response: str,
    book_title: str | None = None,
    max_age_days: int = 7,
) -> Path:
    if not raw_response or not raw_response.strip():
        return log_dir / "llm"
    responses_dir = log_dir / "llm"
    responses_dir.mkdir(parents=True, exist_ok=True)
    prune_old_llm_responses(responses_dir, max_age_days=max_age_days)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    clean_id = re.sub(r"[^\w\.-]", "_", identifier)
    prefix = ""
    if book_title:
        clean_book = re.sub(r"[^\w\.-]", "_", book_title)
        prefix = f"{clean_book}_"
    cache_file = responses_dir / f"{prefix}{timestamp}_{clean_id}.txt"
    cache_file.write_text(raw_response, encoding="utf-8")
    return cache_file


def prune_old_llm_responses(responses_dir: Path, max_age_days: int = 7) -> int:
    if not responses_dir.exists():
        return 0
    cutoff_seconds = time.time() - (max_age_days * 86400)
    pruned_count = 0
    for file_path in responses_dir.glob("*.txt"):
        try:
            if file_path.stat().st_mtime < cutoff_seconds:
                file_path.unlink()
                pruned_count += 1
        except OSError:
            continue
    return pruned_count


def prune_old_metrics_and_nlp_logs(log_dir: Path, max_age_days: int = 7) -> int:
    if not log_dir.exists():
        return 0
    cutoff_seconds = time.time() - (max_age_days * 86400)
    pruned_count = 0
    patterns = (
        "*_persian_nlp_changes.log",
        "persian_nlp_*_changes.log",
        "*_metrics.json",
        "translation_*_metrics.json",
        "*_execution.log",
        "*_execution.jsonl",
        "tome_*.log",
    )
    for pattern in patterns:
        for file_path in log_dir.glob(pattern):
            try:
                if file_path.stat().st_mtime < cutoff_seconds:
                    file_path.unlink()
                    pruned_count += 1
            except OSError:
                continue
    return pruned_count
