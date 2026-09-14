import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from tome.core.avalai import (
    BookTranslationMetrics,
    ChapterMetrics,
    estimate_token_cost,
    get_avalai_credit,
    is_avalai_endpoint,
    is_wallet_empty,
    lookup_avalai_transactions,
    parse_retry_delay,
)


def test_is_avalai_endpoint():
    assert is_avalai_endpoint("https://api.avalai.ir/v1") is True
    assert is_avalai_endpoint("https://chat.avalai.ir/user") is True
    assert is_avalai_endpoint("https://api.openai.com/v1") is False
    assert is_avalai_endpoint("") is False


def test_parse_retry_delay():
    assert parse_retry_delay({"x-ratelimit-reset-requests": "12.5"}) == 12.5
    assert parse_retry_delay({"retry-after": "45"}) == 45.0
    assert parse_retry_delay({"x-ratelimit-reset": "15"}) == 15.0
    assert parse_retry_delay({"x-ratelimit-reset-requests": "999"}) == 300.0
    assert parse_retry_delay({"x-ratelimit-reset-requests": "-5"}) is None
    assert parse_retry_delay({"x-ratelimit-reset-requests": "invalid"}) is None
    assert parse_retry_delay({}) is None
    assert parse_retry_delay(None) is None


def test_is_wallet_empty():
    assert is_wallet_empty(402, "Payment required") is True
    assert is_wallet_empty(400, "insufficient_quota") is True
    assert is_wallet_empty(403, "credit limit reached") is True
    assert is_wallet_empty(400, "موجودی کافی نیست") is True
    assert is_wallet_empty(400, "اعتبار حساب شما به پایان رسیده است") is True
    assert is_wallet_empty(400, "اعتبار کافی نیست") is True
    assert is_wallet_empty(400, "wallet empty") is True
    assert is_wallet_empty(500, "Internal error") is False
    assert is_wallet_empty(200, "success") is False


def test_estimate_token_cost():
    toman, usd = estimate_token_cost(
        "qwen3.8-flash", prompt_tokens=100_000, completion_tokens=100_000, exchange_rate=70000.0
    )
    assert usd > 0
    assert toman > 0

    toman_zero, usd_zero = estimate_token_cost("unknown-model-xyz", 0, 0)
    assert toman_zero == 0.0
    assert usd_zero == 0.0

    toman_fallback, usd_fallback = estimate_token_cost("completely-custom-model", 1000, 1000)
    assert toman_fallback > 0
    assert usd_fallback > 0


def test_get_avalai_credit_mock():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "limit": 100000.0,
        "remaining_irt": 85400.0,
        "remaining_unit": 1.22,
        "account_tier": 2,
    }
    with patch("httpx.Client.get", return_value=mock_resp):
        credit = get_avalai_credit("fake_key")
        assert credit is not None
        assert credit["remaining_irt"] == 85400.0
        assert credit["account_tier"] == 2

    mock_err = MagicMock()
    mock_err.status_code = 500
    with patch("httpx.Client.get", return_value=mock_err):
        assert get_avalai_credit("fake_key") is None

    with patch("httpx.Client.get", side_effect=Exception("Network error")):
        assert get_avalai_credit("fake_key") is None


def test_lookup_avalai_transactions_mock():
    assert lookup_avalai_transactions("fake_key", []) == []

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"transactions": [{"transaction_id": "tx_1", "paid_irt": 150.0}]}
    with patch("httpx.Client.post", return_value=mock_resp):
        res = lookup_avalai_transactions("fake_key", ["tx_1"])
        assert len(res) == 1
        assert res[0]["paid_irt"] == 150.0

    with patch("httpx.Client.post", side_effect=Exception("Timeout")):
        assert lookup_avalai_transactions("fake_key", ["tx_1"]) == []


def test_book_translation_metrics_flow_and_retention(tmp_path: Path):
    metrics = BookTranslationMetrics(
        book_title="Test Book",
        model="qwen3.8-flash",
        initial_credit_toman=100000.0,
    )
    ch1 = ChapterMetrics(
        chapter_index=1,
        chapter_name="01_chapter_1.md",
        duration_seconds=10.0,
        prompt_tokens=1000,
        completion_tokens=500,
        reasoning_tokens=50,
        total_tokens=1500,
        cost_toman=120.0,
        cost_usd=0.0017,
        words_normalized=15,
    )
    ch2 = ChapterMetrics(
        chapter_index=2,
        chapter_name="02_chapter_2.md",
        duration_seconds=12.0,
        prompt_tokens=1200,
        completion_tokens=600,
        reasoning_tokens=60,
        total_tokens=1800,
        cost_toman=145.0,
        cost_usd=0.0020,
        words_normalized=20,
    )
    metrics.add_chapter(ch1)
    metrics.add_chapter(ch2)

    metrics.nlp_words_processed = 2000
    metrics.nlp_words_modified = 35
    metrics.persian_nlp_changes = {"می شود → میشود": 10, "مي → می": 25}
    metrics.nlp_unique_modifications_count = 2

    metrics.finalize(final_credit_toman=99735.0)

    assert metrics.total_tokens == 3300
    assert metrics.total_duration_seconds == 22.0
    assert metrics.average_duration_seconds == 11.0
    assert metrics.consumed_credit_toman == 265.0
    assert metrics.consumed_credit_percent > 0

    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    old_log = log_dir / "persian_nlp_OldBook_changes.log"
    old_log.write_text("old data", encoding="utf-8")
    old_mtime = time.time() - (15 * 86400)
    os.utime(old_log, (old_mtime, old_mtime))

    out_file = metrics.save(tmp_path / "output", log_dir=log_dir, max_age_days=7)
    assert out_file.exists()
    assert (log_dir / "Test_Book_metrics.json").exists()
    assert (log_dir / "Test_Book_persian_nlp_changes.log").exists()
    assert (log_dir / "translation_Test_Book_metrics.json").exists()
    assert (tmp_path / "output" / "metrics.json").exists()
    assert not (tmp_path / "output" / "translation_metrics.json").exists()
    assert not (tmp_path / "output" / "persian_nlp_changes.log").exists()
    assert not old_log.exists()

    log_content = (log_dir / "Test_Book_persian_nlp_changes.log").read_text(encoding="utf-8")
    assert "# Persian NLP Modifications" in log_content
    assert "می شود → میشود (x10)" in log_content
    assert "=>" not in log_content
    assert "Total Unique Corrections: 2" in log_content
