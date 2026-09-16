import contextlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

DEFAULT_AVALAI_USER_API = "https://api.avalai.ir/user/v1"

MODEL_PRICE_PER_1M_TOKENS: dict[str, tuple[float, float]] = {
    "qwen3.8-flash": (0.15, 0.60),
    "qwen": (0.15, 0.60),
    "gemini-flash-latest": (0.075, 0.30),
    "glm-5.3-flash": (0.10, 0.20),
    "deepseek-v4-flash": (0.14, 0.28),
    "deepseek-v4-pro": (0.55, 2.19),
    "claude-sonnet-5": (3.00, 15.00),
    "gpt-5.6-luna": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
}


def is_avalai_endpoint(base_url: str) -> bool:
    return "avalai.ir" in str(base_url).lower()


def get_avalai_credit(api_key: str, proxy_url: str | None = None, timeout: float = 10.0) -> dict[str, Any] | None:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    client_kwargs: dict[str, Any] = {"timeout": timeout}
    if proxy_url:
        client_kwargs["proxy"] = proxy_url

    with contextlib.suppress(Exception), httpx.Client(**client_kwargs) as client:
        resp = client.get(f"{DEFAULT_AVALAI_USER_API}/credit", headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                return data
    return None


def lookup_avalai_transactions(
    api_key: str, request_ids: list[str], proxy_url: str | None = None, timeout: float = 15.0
) -> list[dict[str, Any]]:
    if not request_ids:
        return []
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    client_kwargs: dict[str, Any] = {"timeout": timeout}
    if proxy_url:
        client_kwargs["proxy"] = proxy_url

    with contextlib.suppress(Exception), httpx.Client(**client_kwargs) as client:
        resp = client.post(
            f"{DEFAULT_AVALAI_USER_API}/transactions/lookup",
            headers=headers,
            json={"transaction_ids": request_ids},
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and "transactions" in data:
                return data.get("transactions", [])
    return []


def estimate_token_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    reasoning_tokens: int = 0,
    exchange_rate: float = 70000.0,
) -> tuple[float, float]:
    key = model.lower().strip()
    matched_pricing = MODEL_PRICE_PER_1M_TOKENS.get(key)
    if not matched_pricing:
        for k, v in MODEL_PRICE_PER_1M_TOKENS.items():
            if k in key or key in k:
                matched_pricing = v
                break
    if not matched_pricing:
        matched_pricing = (0.15, 0.60)

    in_price, out_price = matched_pricing
    total_out = completion_tokens + reasoning_tokens
    cost_usd = ((prompt_tokens / 1_000_000.0) * in_price) + ((total_out / 1_000_000.0) * out_price)
    cost_irt = cost_usd * exchange_rate
    return round(cost_irt, 2), round(cost_usd, 6)


import time

DEFAULT_EXCHANGE_RATE = 70000.0

AUTO_RATE_CACHE_SECONDS = 21600
DEFAULT_AUTO_RATE_URL = "https://api.brsapi.ir/Market/Gold_Currency.php?key=BTcbzt9hYhndeLvdDnDQxLRXGc8LTBh4"


def _extract_usd_rate(payload: Any) -> float | None:
    """Find the USD price (toman) in a market API payload, tolerating schema changes."""
    if isinstance(payload, dict):
        if isinstance(payload.get("currency"), list):
            for item in payload["currency"]:
                with contextlib.suppress(Exception):
                    name = str(item.get("name") or item.get("title") or "")
                    if "دلار" in name or name.strip().upper() in {"USD", "US DOLLAR", "DOLLAR"}:
                        for key in ("price", "sell", "buy", "value"):
                            with contextlib.suppress(Exception):
                                return float(item[key])
        for key, value in payload.items():
            if isinstance(key, str) and key.strip().upper() in {"USD", "DOLLAR"} and isinstance(value, dict):
                for k in ("price", "sell", "buy", "value"):
                    with contextlib.suppress(Exception):
                        return float(value[k])
        for value in payload.values():
            found = _extract_usd_rate(value)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                name = str(item.get("name") or item.get("title") or item.get("symbol") or "")
                if "دلار" in name or name.strip().upper() in {"USD", "US DOLLAR", "DOLLAR"}:
                    for k in ("price", "sell", "buy", "value"):
                        with contextlib.suppress(Exception):
                            return float(item[k])
        for item in payload:
            found = _extract_usd_rate(item)
            if found:
                return found
    return None


def fetch_auto_exchange_rate(config: Any = None) -> tuple[float, float] | None:
    """Fetch USD/toman from the configured market API. Returns (rate, fetched_at) or None."""
    import urllib.request

    url = None
    with contextlib.suppress(Exception):
        url = getattr(config, "exchange_rate_auto_url", None)
    if not url:
        url = DEFAULT_AUTO_RATE_URL
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "tome/1.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
        rate = _extract_usd_rate(payload)
        if rate and 1000 < rate < 10_000_000:
            return float(rate), time.time()
    except Exception as err:
        logger.warning("Auto exchange rate fetch failed: %s", err)
    return None


def resolve_exchange_rate(config: Any = None) -> float:
    """Toman per USD. Priority: auto mode (cached/fetched) -> manual tome.json -> default."""
    try:
        data = json.loads(Path("tome.json").read_text(encoding="utf-8"))
    except Exception:
        data = {}

    if data.get("exchange_rate_auto"):
        with contextlib.suppress(Exception):
            cached = float(data.get("exchange_rate_auto_value") or 0)
            fetched_at = float(data.get("exchange_rate_auto_at") or 0)
            if cached and time.time() - fetched_at < AUTO_RATE_CACHE_SECONDS:
                return cached
        got = fetch_auto_exchange_rate(config)
        if got:
            rate, at = got
            data["exchange_rate_auto_value"] = rate
            data["exchange_rate_auto_at"] = at
            with contextlib.suppress(Exception):
                Path("tome.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            return rate

    manual = data.get("exchange_rate")
    if manual:
        return float(manual)
    return DEFAULT_EXCHANGE_RATE


def parse_retry_delay(headers: Any) -> float | None:
    if not headers:
        return None
    for k in ("x-ratelimit-reset-requests", "retry-after", "x-ratelimit-reset"):
        val = None
        if hasattr(headers, "get"):
            val = headers.get(k) or headers.get(k.lower())
        if val is not None:
            with contextlib.suppress(ValueError, TypeError):
                secs = float(val)
                if secs > 0:
                    return min(secs, 300.0)
    return None


def is_wallet_empty(status_code: int, error_text: str) -> bool:
    if status_code == 402:
        return True
    lowered = error_text.lower()
    return any(
        kw in lowered
        for kw in (
            "insufficient_quota",
            "insufficient_credit",
            "credit limit reached",
            "wallet empty",
            "موجودی کافی نیست",
            "اعتبار حساب شما به پایان رسیده",
            "اعتبار کافی نیست",
        )
    )


@dataclass
class ChapterMetrics:
    chapter_index: int
    chapter_name: str
    duration_seconds: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    cost_toman: float = 0.0
    cost_irt: float = 0.0
    cost_usd: float = 0.0
    request_id: str = ""
    words_normalized: int = 0
    exchange_rate: float = 70000.0

    def __post_init__(self) -> None:
        if self.cost_toman and not self.cost_irt:
            self.cost_irt = self.cost_toman
        elif self.cost_irt and not self.cost_toman:
            self.cost_toman = self.cost_irt
        if self.cost_toman and not self.cost_usd:
            self.cost_usd = round(self.cost_toman / (self.exchange_rate or 70000.0), 6)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chapter_index": self.chapter_index,
            "chapter_name": self.chapter_name,
            "duration_seconds": self.duration_seconds,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "total_tokens": self.total_tokens,
            "cost_toman": self.cost_toman,
            "exchange_rate": self.exchange_rate,
            "request_id": self.request_id,
            "words_normalized": self.words_normalized,
        }


@dataclass
class BookTranslationMetrics:
    book_title: str
    model: str
    initial_credit_toman: float | None = None
    initial_credit_irt: float | None = None
    final_credit_toman: float | None = None
    final_credit_irt: float | None = None
    consumed_credit_toman: float = 0.0
    consumed_credit_irt: float = 0.0
    consumed_credit_percent: float = 0.0
    total_duration_seconds: float = 0.0
    average_duration_seconds: float = 0.0
    total_tokens: int = 0
    average_tokens_per_chapter: float = 0.0
    total_cost_toman: float = 0.0
    total_cost_irt: float = 0.0
    total_cost_usd: float = 0.0
    average_cost_toman_per_chapter: float = 0.0
    average_cost_irt_per_chapter: float = 0.0
    chapters: list[ChapterMetrics] = field(default_factory=list)
    nlp_words_processed: int = 0
    nlp_words_modified: int = 0
    nlp_unique_modifications_count: int = 0
    persian_nlp_changes: dict[str, int] = field(default_factory=dict)
    exchange_rate: float = 70000.0

    def __post_init__(self) -> None:
        if self.initial_credit_toman is not None and self.initial_credit_irt is None:
            self.initial_credit_irt = self.initial_credit_toman
        elif self.initial_credit_irt is not None and self.initial_credit_toman is None:
            self.initial_credit_toman = self.initial_credit_irt

    def add_chapter(self, metrics: ChapterMetrics) -> None:
        self.chapters.append(metrics)
        self.total_duration_seconds = round(self.total_duration_seconds + metrics.duration_seconds, 2)
        self.total_tokens += metrics.total_tokens
        val_toman = metrics.cost_toman or metrics.cost_irt
        self.total_cost_toman = round(self.total_cost_toman + val_toman, 2)
        self.total_cost_irt = self.total_cost_toman
        self.total_cost_usd = round(self.total_cost_usd + (metrics.cost_usd or round(val_toman / (metrics.exchange_rate or 70000.0), 6)), 6)

        count = len(self.chapters)
        if count > 0:
            self.average_duration_seconds = round(self.total_duration_seconds / count, 2)
            self.average_tokens_per_chapter = round(self.total_tokens / count, 1)
            self.average_cost_toman_per_chapter = round(self.total_cost_toman / count, 2)
            self.average_cost_irt_per_chapter = self.average_cost_toman_per_chapter

    def finalize(self, final_credit_toman: float | None = None) -> None:
        if final_credit_toman is not None:
            self.final_credit_toman = final_credit_toman
            self.final_credit_irt = final_credit_toman
        init_val = self.initial_credit_toman or self.initial_credit_irt
        fin_val = self.final_credit_toman or self.final_credit_irt
        if init_val is not None and fin_val is not None:
            diff = init_val - fin_val
            if diff >= 0:
                self.consumed_credit_toman = round(diff, 2)
                self.consumed_credit_irt = self.consumed_credit_toman
                if init_val > 0:
                    self.consumed_credit_percent = round((self.consumed_credit_toman / init_val) * 100, 2)
            else:
                self.consumed_credit_toman = self.total_cost_toman
                self.consumed_credit_irt = self.total_cost_toman
        elif self.total_cost_toman > 0:
            self.consumed_credit_toman = self.total_cost_toman
            self.consumed_credit_irt = self.total_cost_toman

    def to_dict(self) -> dict[str, Any]:
        return {
            "book_title": self.book_title,
            "model": self.model,
            "initial_credit_toman": self.initial_credit_toman,
            "final_credit_toman": self.final_credit_toman,
            "consumed_credit_toman": self.consumed_credit_toman,
            "consumed_credit_percent": self.consumed_credit_percent,
            "total_duration_seconds": self.total_duration_seconds,
            "average_duration_seconds": self.average_duration_seconds,
            "total_tokens": self.total_tokens,
            "average_tokens_per_chapter": self.average_tokens_per_chapter,
            "total_cost_toman": self.total_cost_toman,
            "exchange_rate": self.exchange_rate,
            "average_cost_toman_per_chapter": self.average_cost_toman_per_chapter,
            "chapters": [c.to_dict() for c in self.chapters],
            "nlp_words_processed": self.nlp_words_processed,
            "nlp_words_modified": self.nlp_words_modified,
            "nlp_unique_modifications_count": self.nlp_unique_modifications_count,
        }

    def save(self, output_dir: Path, log_dir: Path | None = None, max_age_days: int = 7) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        data_json = json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
        book_metrics_file = output_dir / "metrics.json"
        book_metrics_file.write_text(data_json, encoding="utf-8")

        active_log = log_dir or output_dir
        active_log.mkdir(parents=True, exist_ok=True)
        clean_title = re.sub(r"[^\w\.-]", "_", self.book_title)
        out_file = active_log / f"{clean_title}_metrics.json"
        out_file.write_text(data_json, encoding="utf-8")
        compat_log = active_log / f"translation_{clean_title}_metrics.json"
        compat_log.write_text(data_json, encoding="utf-8")

        if self.persian_nlp_changes:
            from tome.core.editor import save_persian_nlp_modifications

            nlp_log = active_log / f"{clean_title}_persian_nlp_changes.log"
            save_persian_nlp_modifications(self.persian_nlp_changes, nlp_log)
            compat_nlp = active_log / f"persian_nlp_{clean_title}_changes.log"
            save_persian_nlp_modifications(self.persian_nlp_changes, compat_nlp)

        from tome.core.logging import prune_old_metrics_and_nlp_logs

        prune_old_metrics_and_nlp_logs(active_log, max_age_days=max_age_days)

        return out_file
