from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tome.config import TomeConfig
from tome.core.translator import translate_book, translate_chapter, translate_glossary


def make_mock_stream(content: str = "", reasoning: str = ""):
    mock_delta = MagicMock()
    mock_delta.content = content
    mock_delta.reasoning = reasoning
    mock_delta.reasoning_content = reasoning
    mock_chunk = MagicMock()
    mock_chunk.choices = [MagicMock(delta=mock_delta)]
    return [mock_chunk]


def test_translate_glossary_mocked(tmp_path: Path):
    glossary_file = tmp_path / "glossary.md"
    glossary_file.write_text(
        "# Glossary\n\n| Canonical Term | Aliases / Variants | Term Translation | Sample Context | Context Translation |\n"
        "|---|---|---|---|---|\n"
        "| Jacks | Prince of Hearts | | Jacks looked at her | |\n",
        encoding="utf-8",
    )
    config = TomeConfig(log_dir=tmp_path / "logs")

    mock_client = MagicMock()
    translated_table = (
        "| Canonical Term | Aliases / Variants | Term Translation | Sample Context | Context Translation |\n"
        "|---|---|---|---|---|\n"
        "| Jacks | Prince of Hearts | جکس | Jacks looked at her | جکس به او نگاه کرد |\n"
    )
    mock_client.chat.completions.create.return_value = make_mock_stream(content=translated_table)

    with patch("tome.core.translator.get_openai_client", return_value=mock_client):
        res, dur = translate_glossary(glossary_file, config)
        text = res.read_text(encoding="utf-8")
        assert "جکس" in text
        assert "جکس به او نگاه کرد" in text
        assert dur >= 0.0


def test_translate_chapter_with_glossary_mocked(tmp_path: Path):
    chap = tmp_path / "01_chapter_1.md"
    chap.write_text("# Chapter 1\nJacks smiled.", encoding="utf-8")
    config = TomeConfig(log_dir=tmp_path / "logs")

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = make_mock_stream(content="# فصل ۱\nجکس لبخند زد.")

    text, entities = translate_chapter(
        chap,
        config,
        mock_client,
        glossary_content="Jacks -> جکس",
    )
    assert "فصل ۱" in text
    assert entities == []


def test_translate_chapter_no_gliner_mocked(tmp_path: Path):
    chap = tmp_path / "01_chapter_1.md"
    chap.write_text("# Chapter 1\nEva entered Wolf Hall.", encoding="utf-8")
    config = TomeConfig(log_dir=tmp_path / "logs")

    mock_client = MagicMock()
    content = (
        "# فصل ۱\nاوا وارد تالار گرگ شد.\n\n"
        "<!-- ENTITIES_START\n"
        "- [Category: People & Characters] Eva | Translation: اوا\n"
        "- [Category: Locations, Realms & Coordinates] Wolf Hall | Translation: تالار گرگ\n"
        "ENTITIES_END -->"
    )
    mock_client.chat.completions.create.return_value = make_mock_stream(content=content)

    clean_text, entities = translate_chapter(
        chap,
        config,
        mock_client,
        glossary_content="",
    )
    assert "ENTITIES_START" not in clean_text
    assert len(entities) == 2
    assert entities[0].canonical == "Eva"
    assert entities[1].canonical == "Wolf Hall"


def test_translate_book_pipeline(tmp_path: Path):
    book_dir = tmp_path / "Test_Book"
    chapters_dir = book_dir / "chapters"
    chapters_dir.mkdir(parents=True)
    ch1 = chapters_dir / "01_chapter_1.md"
    ch1.write_text("# Chapter 1\nHello world.", encoding="utf-8")

    config = TomeConfig(log_dir=tmp_path / "logs")
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = make_mock_stream(content="# فصل ۱\nسلام دنیا.")

    with patch("tome.core.translator.get_openai_client", return_value=mock_client):
        paths, timings = translate_book(book_dir, config)
        assert len(paths) == 1
        assert paths[0].name == "01_chapter_1.md"
        assert (book_dir / "translation" / "01_chapter_1.md").exists()
        assert "سلام دنیا" in paths[0].read_text(encoding="utf-8")
        assert "01_chapter_1.md" in timings
        assert "total" in timings


def test_translate_chapter_persian_nlp_toggle(tmp_path: Path):
    chap = tmp_path / "01_chapter_1.md"
    chap.write_text("# Chapter 1\nHe goes.", encoding="utf-8")

    config_enabled = TomeConfig(log_dir=tmp_path / "logs_enabled", persian_nlp=True)
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = make_mock_stream(content="# فصل ۱\nاو ميرود.")

    text_enabled, _ = translate_chapter(chap, config_enabled, mock_client, glossary_content="He -> او")
    assert "می‌رود" in text_enabled
    raw_files = list((tmp_path / "logs_enabled" / "llm").glob("*raw_pre_editor*"))
    assert len(raw_files) >= 1
    assert "ميرود" in raw_files[0].read_text(encoding="utf-8")

    config_disabled = TomeConfig(log_dir=tmp_path / "logs_disabled", persian_nlp=False)
    mock_client.chat.completions.create.return_value = make_mock_stream(content="# فصل ۱\nاو ميرود.")
    text_disabled, _ = translate_chapter(chap, config_disabled, mock_client, glossary_content="He -> او")
    assert "ميرود" in text_disabled


def test_build_model_request_params_qwen():
    from tome.core.translator import build_model_request_params

    cfg_stream = TomeConfig(llm_model="qwen3.8-flash", llm_thinking=True, llm_reasoning_effort="medium")
    params_stream = build_model_request_params(cfg_stream, streaming=True)
    assert params_stream["model"] == "qwen3.8-flash"
    assert params_stream["extra_body"]["enable_thinking"] is True
    assert params_stream["extra_body"]["reasoning_effort"] == "medium"

    cfg_nostream = TomeConfig(llm_model="qwen3.8-flash", llm_thinking=True)
    params_nostream = build_model_request_params(cfg_nostream, streaming=False)
    assert params_nostream["extra_body"]["enable_thinking"] is False


def test_build_model_request_params_other_models():
    from tome.core.translator import build_model_request_params

    for m in [
        "gemini-flash-latest",
        "glm-5.3-flash",
        "deepseek-v4-flash",
        "claude-sonnet-5",
        "gpt-5.6-luna",
        "custom-model",
    ]:
        cfg = TomeConfig(llm_model=m, llm_thinking=True, llm_reasoning_effort="high")
        params = build_model_request_params(cfg, streaming=True)
        assert params["model"] == m
        assert params["extra_body"]["reasoning_effort"] == "high"
        assert "enable_thinking" not in params["extra_body"]


def test_detect_model_family():
    from tome.core.translator import detect_model_family

    assert detect_model_family("qwen3.8-flash") == "qwen"
    assert detect_model_family("deepseek-v4-pro") == "deepseek"
    assert detect_model_family("glm-5.3-flash") == "glm"
    assert detect_model_family("claude-sonnet-5") == "claude"
    assert detect_model_family("gemini-flash-latest") == "gemini"
    assert detect_model_family("gpt-5.6-luna") == "openai"
    assert detect_model_family("llama-3.3-70b-instruct") == "meta"
    assert detect_model_family("grok-4.5") == "xai"
    assert detect_model_family("kimi-k3") == "moonshot"
    assert detect_model_family("minimax-m3") == "minimax"
    assert detect_model_family("unknown-custom") == "general"


def test_format_api_error():
    from openai import APITimeoutError, AuthenticationError, PermissionDeniedError, RateLimitError

    from tome.core.translator import format_api_error

    auth_err = AuthenticationError("Invalid key", response=MagicMock(status_code=401), body=None)
    assert "Authentication Error" in format_api_error(auth_err)

    perm_err = PermissionDeniedError("Country restricted", response=MagicMock(status_code=403), body=None)
    assert "Restricted" in format_api_error(perm_err)

    rate_err = RateLimitError("Rate limit exceeded", response=MagicMock(status_code=429), body=None)
    assert "Rate Limit" in format_api_error(rate_err)

    timeout_err = APITimeoutError(request=MagicMock())
    assert "Timeout" in format_api_error(timeout_err)


def test_prompt_graph_variable_substitution(tmp_path: Path):
    chap = tmp_path / "01_chap.md"
    chap.write_text("# Chapter 1\nContent.", encoding="utf-8")

    cfg = TomeConfig(
        log_dir=tmp_path / "logs",
        prompts={
            "chapter_translation_with_glossary_system_prompt": "Translate to {target_language}. Graph: {graph}. Rules: {user_style_rules}"
        },
    )

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = make_mock_stream(content="Translated text")

    graph_text = "Jacks <-> Evangeline"
    translate_chapter(
        chap,
        cfg,
        mock_client,
        glossary_content="Term -> ترجمه",
        graph_context=graph_text,
    )

    call_args = mock_client.chat.completions.create.call_args[1]
    system_msg = next(m["content"] for m in call_args["messages"] if m["role"] == "system")
    assert "Graph: Jacks <-> Evangeline" in system_msg


def test_prompt_validation_error_on_unknown_variable(tmp_path: Path):
    from tome.exceptions import PromptValidationError

    bad_prompts = {"chapter_translation_with_glossary_system_prompt": "Translate to {target_language} with {graphhh}."}
    with pytest.raises(PromptValidationError) as exc:
        TomeConfig(prompts=bad_prompts)
    assert "{graphhh}" in str(exc.value)
    assert "Allowed template variables" in str(exc.value)


def test_parse_chapter_selection():
    from tome.core.translator import parse_chapter_selection

    assert parse_chapter_selection(None) is None
    assert parse_chapter_selection("") is None
    assert parse_chapter_selection("5") == {5}
    assert parse_chapter_selection(5) == {5}
    assert parse_chapter_selection("5,6") == {5, 6}
    assert parse_chapter_selection("5 and 6") == {5, 6}
    assert parse_chapter_selection("5 & 6") == {5, 6}
    assert parse_chapter_selection("5 to 8") == {5, 6, 7, 8}
    assert parse_chapter_selection("5-8") == {5, 6, 7, 8}
    assert parse_chapter_selection("8 to 5") == {5, 6, 7, 8}
    assert parse_chapter_selection("1, 3, 5-7") == {1, 3, 5, 6, 7}


def test_normalize_prompt_escapes():
    from tome.config import TomeConfig, normalize_prompt_escapes

    assert normalize_prompt_escapes("Line 1\\nLine 2") == "Line 1\nLine 2"
    assert normalize_prompt_escapes("Col 1\\tCol 2") == "Col 1\tCol 2"
    assert normalize_prompt_escapes("P1\\n\\nP2") == "P1\n\nP2"

    cfg = TomeConfig(
        prompts={
            "chapter_translation_with_glossary_system_prompt": "Prompt line 1\\n\\nPrompt line 2 {target_language} {user_style_rules} {graph}"
        },
    )
    cfg.user_style_rules = "Rule 1\\nRule 2"
    assert "\n" in cfg.user_style_rules
    assert "\n\n" in cfg.prompts["chapter_translation_with_glossary_system_prompt"]


def test_translate_book_chapter_selection_filter(tmp_path: Path):
    from tome.core.translator import translate_book

    book_dir = tmp_path / "Book"
    chapters_dir = book_dir / "chapters"
    chapters_dir.mkdir(parents=True)

    for i in range(1, 6):
        (chapters_dir / f"0{i}_chapter_{i}.md").write_text(
            f"# Chapter {i}\nContent for chapter {i} " * 50, encoding="utf-8"
        )

    cfg = TomeConfig(log_dir=tmp_path / "logs", persian_nlp=False)

    mock_translation = "متن ترجمه شده برای این فصل از کتاب داستان به صورت کامل. " * 40
    with (
        patch("tome.core.translator.execute_llm_completion", return_value=mock_translation),
        patch("tome.core.translator.get_openai_client"),
    ):
        paths, _ = translate_book(book_dir, cfg, chapters="2, 4")
        translated_names = [p.name for p in paths]
        assert "02_chapter_2.md" in translated_names
        assert "04_chapter_4.md" in translated_names
        assert "01_chapter_1.md" not in translated_names
        assert "03_chapter_3.md" not in translated_names
        assert "05_chapter_5.md" not in translated_names

        unmatched_paths, _ = translate_book(book_dir, cfg, chapters="99")
        assert len(unmatched_paths) == 0


def test_format_api_error_all_variants():
    from unittest.mock import MagicMock

    from tome.core.translator import format_api_error

    err_401 = Exception("HTTP 401 Unauthorized: Invalid API key")
    msg = format_api_error(err_401)
    assert "401 Unauthorized" in msg

    err_403 = Exception("Access denied: sanction policy applies to your region")
    msg = format_api_error(err_403)
    assert "403 Forbidden" in msg
    assert "sanction" in msg.lower()

    err_404 = Exception("404 not_found")
    msg = format_api_error(err_404, model="non-existent-model")
    assert "404" in msg
    assert "non-existent-model" in msg

    err_quota = Exception("429 Insufficient credit balance or quota exhausted")
    msg = format_api_error(err_quota)
    assert "Quota Depleted" in msg

    err_rate = Exception("429 rate limit exceeded")
    msg = format_api_error(err_rate)
    assert "Rate Limit" in msg

    err_timeout = TimeoutError("Request timed out after 300s")
    msg = format_api_error(err_timeout)
    assert "Timeout" in msg

    class MockAPIError(Exception):
        def __init__(self, msg: str, response=None, body=None):
            super().__init__(msg)
            self.response = response
            self.body = body

    mock_resp = MagicMock()
    mock_resp.headers = {"avalai-request-id": "req-avalai-777"}
    err_with_headers = MockAPIError(
        "General failure",
        response=mock_resp,
        body={"error": {"solution": "Contact support at https://avalai.ir"}},
    )
    msg = format_api_error(err_with_headers)
    assert "req-avalai-777" in msg
    assert "Contact support" in msg

    msg_cli = format_api_error(Exception("Network dropout"), client_request_id="cli-123")
    assert "cli-123" in msg_cli


def test_validate_translation_response_universal_proportionality():
    from tome.core.translator import validate_translation_response

    source = "This is a detailed paragraph of a novel chapter. " * 30
    valid_output = "Esta es una traducción detallada del capítulo de una novela. " * 30
    ok, _ = validate_translation_response(valid_output, "Spanish", source)
    assert ok

    truncated = "Esta es una traducción corta."
    ok, reason = validate_translation_response(truncated, "Spanish", source)
    assert not ok
    assert "Suspiciously low word count" in reason

    bloated = "Palabra repetida muchas veces en bucle infinito. " * 300
    ok, reason = validate_translation_response(bloated, "Spanish", source)
    assert not ok
    assert "Suspiciously bloated" in reason


def test_validate_translation_response_safety_refusal():
    from tome.core.translator import validate_translation_response

    source = "Chapter text about battle and emotional conflict in fantasy realm. " * 20

    refusal = "I apologize, but I cannot fulfill this request due to safety guidelines regarding mature themes."
    ok, reason = validate_translation_response(refusal, "French", source)
    assert not ok
    assert "Safety/policy refusal" in reason

    question = "Please tell me what you'd like me to do with this excerpt."
    ok, reason = validate_translation_response(question, "German", source)
    assert not ok
    assert "Conversational refusal" in reason


def test_translate_chapter_recovery_capped_at_3_attempts(tmp_path: Path):
    from tome.core.translator import TranslationError, translate_chapter

    chap = tmp_path / "01_chap.md"
    chap.write_text("Source text for chapter with substantial narrative content. " * 30, encoding="utf-8")

    cfg = TomeConfig(log_dir=tmp_path / "logs")
    mock_client = MagicMock()

    refusal_stream = make_mock_stream(content="I cannot fulfill this request due to content policy.")
    mock_client.chat.completions.create.return_value = refusal_stream

    with pytest.raises(TranslationError) as exc_info:
        translate_chapter(
            chap,
            cfg,
            mock_client,
            glossary_content="",
            graph_context="",
        )

    assert "failed validation after 3 attempts" in str(exc_info.value)
    assert mock_client.chat.completions.create.call_count == 3


def test_validate_translation_response_multilingual_refusal():
    from tome.core.translator import validate_translation_response

    source = "Chapter content about ancient realms and kings. " * 30

    ok_fa, r_fa = validate_translation_response("متأسفانه نمی‌توانم این درخواست را انجام دهم.", "Persian", source)
    assert not ok_fa
    assert "refusal" in r_fa

    ok_ar, r_ar = validate_translation_response(
        "أعتذر، لا يمكنني تلبية هذا الطلب وفقاً لسياسات الأمان.", "Arabic", source
    )
    assert not ok_ar
    assert "refusal" in r_ar

    ok_fr, r_fr = validate_translation_response("Je ne peux pas traduire ce contenu sensible.", "French", source)
    assert not ok_fr
    assert "refusal" in r_fr

    ok_fuzzy, r_fuzzy = validate_translation_response(
        "I am unable to assist with translating this text due to our strict safety guidelines.", "English", source
    )
    assert not ok_fuzzy
    assert "refusal" in r_fuzzy


def test_translate_chapter_attempt_observer_logging(tmp_path: Path):
    from tome.core.translator import translate_chapter

    chap = tmp_path / "01_chap.md"
    chap.write_text("Source text of a novel chapter. " * 30, encoding="utf-8")

    cfg = TomeConfig(log_dir=tmp_path / "logs")
    mock_client = MagicMock()

    bad_stream = make_mock_stream(content="Please tell me what you'd like me to do with this.")
    good_stream = make_mock_stream(content="متن ترجمه شده برای این فصل از کتاب رمان به صورت کامل و دقیق. " * 30)
    mock_client.chat.completions.create.side_effect = [bad_stream, good_stream]

    events: list[tuple[str, dict]] = []

    def obs(event: str, data: dict):
        events.append((event, data))

    translate_chapter(chap, cfg, mock_client, glossary_content="", graph_context="", observer=obs)

    attempt_events = [data for ev, data in events if ev == "translation_attempt"]
    assert len(attempt_events) == 2
    assert attempt_events[0]["attempt"] == 1
    assert attempt_events[0]["strategy"] == "initial"
    assert attempt_events[1]["attempt"] == 2
    assert attempt_events[1]["strategy"] == "recovery"


def test_execute_llm_completion_keyboard_interrupt_closes_stream():
    from tome.core.translator import execute_llm_completion

    cfg = TomeConfig(stream_response=True)
    mock_client = MagicMock()

    class InterruptingStream:
        def __init__(self):
            self.closed = False
            self.response = MagicMock()
            self.response.close = self.close

        def close(self):
            self.closed = True

        def __iter__(self):
            raise KeyboardInterrupt()

    mock_stream = InterruptingStream()
    mock_client.chat.completions.create.return_value = mock_stream

    with pytest.raises(KeyboardInterrupt):
        execute_llm_completion(mock_client, cfg, [{"role": "user", "content": "hello"}])

    assert mock_stream.closed is True


def test_translate_chapter_with_persian_nlp_disabled(tmp_path: Path):
    from tome.core.translator import translate_chapter

    chap = tmp_path / "01_chap.md"
    chap.write_text("Original chapter content for test. " * 30, encoding="utf-8")

    cfg = TomeConfig(log_dir=tmp_path / "logs", persian_nlp=False)
    mock_client = MagicMock()
    mock_stream = make_mock_stream(content="متن ترجمه شده بدون نرمال‌سازی فارسی برای این فصل. " * 30)
    mock_client.chat.completions.create.return_value = mock_stream

    obs_events = []
    content, _ = translate_chapter(
        chap,
        cfg,
        mock_client,
        glossary_content="",
        graph_context="",
        observer=lambda ev, d: obs_events.append(ev),
    )
    assert len(content) > 50
    assert "persian_nlp_complete" not in obs_events


def test_fantasy_prompt_routing_and_config_helpers():
    cfg = TomeConfig()
    # Chapter prompts remain universal
    assert (
        cfg.get_chapter_prompt_name(has_glossary=True)
        == "chapter_translation_with_glossary_system_prompt"
    )
    assert (
        cfg.get_chapter_prompt_name(has_glossary=False)
        == "chapter_translation_no_gliner_system_prompt"
    )

    # Glossary prompt is universal
    assert cfg.get_glossary_prompt_name() == "glossary_translation_system_prompt"

    # Fantasy genre detection
    assert cfg.is_fantasy_genre("fantasy") is True
    assert cfg.is_fantasy_genre("Epic Fantasy") is True
    assert cfg.is_fantasy_genre("High Fantasy") is True
    assert cfg.is_fantasy_genre("general") is False
    assert cfg.is_fantasy_genre("sci-fi") is False

    # Fantasy taxonomy terms check
    from tome.config import GENRE_TAXONOMIES
    all_fantasy_terms = [
        term
        for terms in GENRE_TAXONOMIES["fantasy"].values()
        for term in terms
    ]
    for expected in [
        "sanctuary",
        "domain",
        "magical reagent",
        "transformation stage",
        "incantation",
        "mana",
        "dwarf",
        "demon",
        "talisman",
        "grimoire",
        "elixir",
    ]:
        assert expected in all_fantasy_terms


def test_translate_chapter_fantasy_prompt_selection(tmp_path: Path):
    chap = tmp_path / "01_fantasy.md"
    chap.write_text("The high elf drew his runeblade in Wolf Hall.", encoding="utf-8")

    cfg = TomeConfig(log_dir=tmp_path / "logs")
    mock_client = MagicMock()

    captured_messages = []

    def mock_create(*args, **kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        return make_mock_stream(content="الف بلندمرتبه تیغهٔ نشان‌دارش را کشید.")

    mock_client.chat.completions.create.side_effect = mock_create

    # 1. Fantasy translation: fantasy guidelines MUST be appended
    content, _ = translate_chapter(
        chap,
        cfg,
        mock_client,
        glossary_content="runeblade -> تیغهٔ نشان‌دار",
        genre="fantasy",
    )
    assert "الف بلندمرتبه" in content
    system_msg = next((m["content"] for m in captured_messages if m["role"] == "system"), "")
    assert "Fantasy Localization Guidelines" in system_msg
    assert "Dual-Voice Principle" in system_msg
    assert "Creative Persian Word-Formation" in system_msg

    # 2. General / non-fantasy translation: fantasy guidelines must NOT be appended
    captured_messages.clear()
    translate_chapter(
        chap,
        cfg,
        mock_client,
        glossary_content="runeblade -> تیغهٔ نشان‌دار",
        genre="general",
    )
    system_msg_general = next((m["content"] for m in captured_messages if m["role"] == "system"), "")
    assert "Fantasy Localization Guidelines" not in system_msg_general

