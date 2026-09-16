import contextlib
import json
import logging
import re
import time
import uuid

logger = logging.getLogger(__name__)
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from pathlib import Path
from typing import Any

import httpx
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)

from tome.config import TomeConfig, normalize_prompt_escapes, validate_prompt_variables
from tome.core.avalai import (
    BookTranslationMetrics,
    ChapterMetrics,
    estimate_token_cost,
    get_avalai_credit,
    is_avalai_endpoint,
    is_wallet_empty,
    parse_retry_delay,
    resolve_exchange_rate,
)
from tome.core.glossary import ingest_chapter_delimiter_entities, write_glossary_markdown
from tome.core.logging import save_llm_response_cache
from tome.exceptions import TomeError
from tome.models import Entity


class TranslationError(TomeError):
    pass


MULTILINGUAL_REFUSAL_MARKERS = (
    "please tell me what you’d like",
    "please tell me what you'd like",
    "what would you like me to do",
    "how can i help",
    "how would you like to proceed",
    "i can help you with",
    "here is what i can do",
    "tell me what you would like",
    "i am ready to help",
    "i'm ready to help",
    "as an ai",
    "as a language model",
    "i cannot assist",
    "i'm sorry, but i cannot",
    "i am sorry, but i cannot",
    "sure, here are some options",
    "here are some options",
    "let me know how you'd like",
    "let me know how you’d like",
    "what format would you like",
    "would you like me to translate",
    "shall i translate",
    "لطفاً بفرمایید",
    "لطفا بفرمایید",
    "چگونه می‌توانم کمکتان کنم",
    "چگونه میتوانم کمکتان کنم",
    "چطور می‌توانم کمکتان کنم",
    "چطور میتوانم کمکتان کنم",
    "چه کمکی از دست من برمی‌آید",
    "چه کمکی از دست من برمی اید",
    "من می‌توانم این متن را",
    "من میتوانم این متن را",
    "به‌عنوان یک مدل زبانی",
    "به عنوان یک مدل زبانی",
    "من یک هوش مصنوعی هستم",
    "چه کاری مایلید انجام دهم",
    "لطفاً مشخص کنید که",
    "لطفا مشخص کنید که",
    "چه کاری می‌خواهید",
    "چه کاری میخواهید",
    "que souhaitez-vous",
    "comment puis-je vous aider",
    "dites-moi ce que vous aimeriez",
    "en tant qu'ia",
    "en tant que modèle de langue",
    "voici ce que je peux faire",
    "wie kann ich ihnen helfen",
    "bitte sagen sie mir",
    "was möchten sie",
    "als ki",
    "als sprachmodell",
    "ich kann ihnen dabei helfen",
    "en qué puedo ayudarte",
    "cómo puedo ayudarte",
    "por favor dime qué te gustaría",
    "como ia",
    "como modelo de lenguaje",
    "aquí hay algunas opciones",
    "كيف يمكنني مساعدتك",
    "يرجى إخباري بما تريد",
    "كنموذج لغوي",
    "أنا ذكاء اصطناعي",
    "ما الذي تود مني فعله",
    "size nasıl yardımcı olabilirim",
    "ne yapmamı istersiniz",
    "bir yapay zeka olarak",
    "чем я могу вам помочь",
    "что бы вы хотели",
    "как искусственный интеллект",
)

MULTILINGUAL_SAFETY_REFUSAL_TERMS = (
    "cannot fulfill",
    "unable to fulfill",
    "cannot assist",
    "unable to assist",
    "cannot translate",
    "unable to translate",
    "cannot comply",
    "unable to comply",
    "safety guidelines",
    "safety policy",
    "ethical guidelines",
    "ethical standards",
    "policy guidelines",
    "content policy",
    "terms of service",
    "content moderation",
    "inappropriate content",
    "harmful content",
    "sensitive content",
    "sexually explicit",
    "mature themes",
    "not able to assist",
    "not able to fulfill",
    "against my safety",
    "violates my safety",
    "violates our policy",
    "violates our terms",
    "refuse to translate",
    "نمی‌توانم این درخواست را انجام دهم",
    "نمی‌توانم کمک کنم",
    "امکان ترجمه این متن وجود ندارد",
    "دستورالعمل‌های اخلاقی",
    "دستورالعمل‌های ایمنی",
    "سیاست‌های محتوایی",
    "سیاست‌های ایمنی",
    "محتوای نامناسب",
    "محتوای حساس",
    "محتوای غیراخلاقی",
    "از انجام این کار معذورم",
    "قادر به انجام این درخواست نیستم",
    "لا يمكنني تلبية هذا الطلب",
    "لا يمكنني المساعدة",
    "لا أستطيع ترجمة",
    "سياسات الأمان",
    "الإرشادات الأخلاقية",
    "محتوى غير لائق",
    "محتوى حساس",
    "je ne peux pas satisfaire",
    "impossible de traduire",
    "politique de sécurité",
    "directives éthiques",
    "contenu inapproprié",
    "kann diese anfrage nicht erfüllen",
    "kann nicht übersetzen",
    "sicherheitsrichtlinien",
    "ethische richtlinien",
    "unangemessene inhalte",
    "no puedo cumplir con esta solicitud",
    "no puedo traducir",
    "política de seguridad",
    "directrices éticas",
    "contenido inapropiado",
    "я не могу выполнить этот запрос",
    "не могу перевести",
    "правила безопасности",
    "этические нормы",
    "bu isteği yerine getiremiyorum",
    "çeviri yapamam",
    "güvenlik yönergeleri",
    "etik kurallar",
)

SAFETY_INTENT_PATTERNS = (
    re.compile(
        r"\b(?:cannot|unable|can't|refuse|apologize|sorry)\s+(?:to\s+)?(?:\w+\s+){0,3}(?:fulfill|assist|translate|process|comply|generate|complete)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:against|violat\w+|breach\w+)\s+(?:our|my|the)?\s*(?:safety|policy|policies|guideline\w*|standard\w*|rule\w*|term\w*)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:as\s+an?\s+(?:ai|artificial\s+intelligence|language\s+model))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:نمی‌?توانم|معذورم|امکان\s*(?:پذیر)?\s*نیست|قادر\s*نیستم)\s+.*?(?:ترجمه|انجام|پاسخ|کمک)",
    ),
    re.compile(
        r"(?:سیاست‌?های\s*(?:محتوایی|ایمنی|اخلاقی)|دستورالعمل‌?های\s*(?:اخلاقی|ایمنی))",
    ),
    re.compile(
        r"(?:لا\s*أ?ستطيع|لا\s*يمكنني|أعتذر\s*عن)\s+.*?(?:مساعدتك|تلبية|ترجمة)",
    ),
    re.compile(
        r"(?:ne\s*peux\s*pas|impossible\s*de)\s+.*?(?:traduire|aider|satisfaire)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:kann\s*(?:ich)?\s*nicht|nicht\s*in\s*der\s*lage)\s+.*?(?:übersetzen|helfen|erfüllen)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:no\s*puedo|no\s*estoy\s*autorizado)\s+.*?(?:traducir|ayudar|cumplir)",
        re.IGNORECASE,
    ),
)


def validate_translation_response(
    raw_content: str,
    target_language: str,
    source_text: str,
) -> tuple[bool, str]:
    cleaned = raw_content.strip()
    if not cleaned:
        return False, "Empty response received from LLM."

    lower_text = cleaned.lower()
    is_short = len(cleaned) < 1500

    for term in MULTILINGUAL_SAFETY_REFUSAL_TERMS:
        if term in lower_text and (is_short or lower_text.startswith(term)):
            return False, f"Safety/policy refusal detected: '{term}'"

    if is_short or lower_text.startswith(("i ", "as ", "sorry", "نمی", "من ", "لا ", "je ", "wir ", "no ")):
        for pat in SAFETY_INTENT_PATTERNS:
            m = pat.search(lower_text)
            if m:
                return False, f"Safety/policy refusal pattern matched: '{m.group(0)}'"

    for marker in MULTILINGUAL_REFUSAL_MARKERS:
        if marker in lower_text and (is_short or lower_text.startswith(marker)):
            return False, f"Conversational refusal/prompt detected: '{marker}'"

    src_words = len(re.findall(r"\b\w+\b", source_text))
    out_words = len(re.findall(r"\b\w+\b", cleaned))

    if src_words >= 150:
        ratio = out_words / src_words
        if ratio < 0.35:
            return (
                False,
                f"Suspiciously low word count ({out_words} words vs source {src_words} words, ratio {ratio:.2f} < 0.35). Severe truncation or refusal likely.",
            )
        if ratio > 3.5:
            return (
                False,
                f"Suspiciously bloated word count ({out_words} words vs source {src_words} words, ratio {ratio:.2f} > 3.5). Hallucination or repetition loop likely.",
            )

    src_chars = len(source_text.strip())
    out_chars = len(cleaned)
    if src_chars >= 400:
        char_ratio = out_chars / src_chars
        if char_ratio < 0.30:
            return (
                False,
                f"Suspiciously low character length ({out_chars} chars vs source {src_chars} chars, ratio {char_ratio:.2f} < 0.30).",
            )
        if char_ratio > 4.0:
            return (
                False,
                f"Suspiciously bloated character length ({out_chars} chars vs source {src_chars} chars, ratio {char_ratio:.2f} > 4.0).",
            )

    lines = [line.strip() for line in cleaned.splitlines() if len(line.strip()) > 30]
    if len(lines) >= 8:
        counts = Counter(lines)
        most_common_line, freq = counts.most_common(1)[0]
        if freq >= 6 and (freq / len(lines)) > 0.4:
            return False, f"Degenerate repetition loop detected ('{most_common_line[:40]}' repeated {freq} times)."

    if len(source_text.strip()) > 500 and len(cleaned) < 80:
        return (
            False,
            f"Severe truncation: source text has {len(source_text)} chars, output has only {len(cleaned)} chars.",
        )

    return True, ""


def parse_chapter_selection(selection: str | int | set[int] | list[int] | None) -> set[int] | None:
    if selection is None:
        return None
    if isinstance(selection, (set, list)):
        return set(selection)
    if isinstance(selection, int):
        return {selection}
    s = str(selection).strip()
    if not s:
        return None

    s = re.sub(r"\s+(?:and|&)\s+", ",", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+(?:to|through)\s+", "-", s, flags=re.IGNORECASE)

    selected: set[int] = set()
    tokens = [t.strip() for t in re.split(r"[,;]+", s) if t.strip()]
    for token in tokens:
        range_match = re.match(r"^(\d+)\s*[-–—]\s*(\d+)$", token)
        if range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            if start <= end:
                selected.update(range(start, end + 1))
            else:
                selected.update(range(end, start + 1))
        elif token.isdigit():
            selected.add(int(token))
        else:
            subparts = token.split()
            for sp in subparts:
                if sp.isdigit():
                    selected.add(int(sp))
    return selected if selected else None


def extract_chapter_number(chap_path: Path, fallback_idx: int) -> int:
    match = re.search(r"(?:chapter|chap)[_\s-]*(\d+)", chap_path.stem, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+)", chap_path.stem)
    if match:
        return int(match.group(1))
    return fallback_idx


def detect_model_family(model_name: str) -> str:
    m = model_name.lower()
    if "qwen" in m:
        return "qwen"
    elif "deepseek" in m:
        return "deepseek"
    elif "glm" in m:
        return "glm"
    elif any(k in m for k in ("claude", "anthropic")):
        return "claude"
    elif any(k in m for k in ("gemini", "google")):
        return "gemini"
    elif any(k in m for k in ("gpt", "o1", "o3", "openai")):
        return "openai"
    elif any(k in m for k in ("llama", "muse", "meta")):
        return "meta"
    elif any(k in m for k in ("grok", "xai")):
        return "xai"
    elif any(k in m for k in ("kimi", "moonshot")):
        return "moonshot"
    elif "minimax" in m:
        return "minimax"
    return "general"


def format_api_error(err: Exception, model: str = "", client_request_id: str | None = None) -> str:
    err_text = str(err).lower()
    req_id = None
    solution = None
    resp = getattr(err, "response", None)
    if resp is not None:
        headers = getattr(resp, "headers", {})
        if hasattr(headers, "get"):
            req_id = headers.get("avalai-request-id") or headers.get("x-request-id")

    body = getattr(err, "body", None)
    if isinstance(body, dict):
        err_dict = body.get("error", {})
        if isinstance(err_dict, dict):
            req_id = req_id or err_dict.get("request_id")
            solution = err_dict.get("solution")

    base_msg = ""
    if isinstance(err, AuthenticationError) or "401" in err_text or "unauthorized" in err_text:
        base_msg = "API Authentication Error: Invalid or missing API key (401 Unauthorized)."
    elif (
        isinstance(err, PermissionDeniedError)
        or "403" in err_text
        or any(k in err_text for k in ("forbidden", "sanction", "restricted", "region", "country"))
    ):
        base_msg = (
            "API Access Restricted: Region, IP, or sanction restriction (403 Forbidden). "
            "Verify account permissions or proxy settings."
        )
    elif isinstance(err, NotFoundError) or "404" in err_text or "not_found" in err_text:
        model_part = f" for '{model}'" if model else ""
        base_msg = f"API Model Not Found: Model{model_part} does not exist or is unavailable on this provider (404)."
    elif isinstance(err, RateLimitError) or "429" in err_text or "rate limit" in err_text or "quota" in err_text:
        if "quota" in err_text or "credit" in err_text or "balance" in err_text:
            base_msg = "API Quota Depleted: Insufficient account credit or balance (429 Quota Exceeded)."
        else:
            base_msg = "API Rate Limit: Request frequency limit exceeded (429 Too Many Requests)."
    elif isinstance(err, APITimeoutError) or "timeout" in err_text or "timed out" in err_text:
        base_msg = "API Timeout: Server did not respond within configured timeout limit."
    elif isinstance(err, APIConnectionError) or "connection" in err_text or "network" in err_text:
        base_msg = "API Connection Error: Unable to reach endpoint. Check network or proxy settings."
    elif isinstance(err, InternalServerError) or any(code in err_text for code in ("500", "502", "503", "504")):
        base_msg = "API Server Overload: Upstream provider is experiencing temporary internal issues (5xx)."
    elif isinstance(err, BadRequestError) or "400" in err_text:
        base_msg = f"API Invalid Request: Parameter or format rejected by provider: {err}"
    else:
        base_msg = f"API Communication Error: {err}"

    parts = [base_msg]
    if solution:
        parts.append(f"Solution: {solution}")
    ref_id = req_id or client_request_id
    if ref_id:
        parts.append(f"[Ref: {ref_id}]")

    return " ".join(parts)


def get_openai_client(config: TomeConfig) -> OpenAI:
    timeout = httpx.Timeout(
        timeout=float(config.llm_timeout),
        connect=60.0,
        read=float(config.llm_timeout),
        write=60.0,
        pool=60.0,
    )
    if config.proxy_enabled:
        scheme = config.proxy_type.lower()
        if scheme in ("socks", "socks5", "socks5h"):
            proxy_url = f"socks5://{config.proxy_host}:{config.proxy_port}"
        else:
            proxy_url = f"http://{config.proxy_host}:{config.proxy_port}"
        http_client = httpx.Client(proxy=proxy_url, timeout=timeout)
    else:
        http_client = httpx.Client(timeout=timeout)

    return OpenAI(
        base_url=config.llm_base_url,
        api_key=config.llm_api_key,
        http_client=http_client,
    )


def build_model_request_params(config: TomeConfig, streaming: bool, include_reasoning: bool = True) -> dict[str, Any]:
    extra_body: dict[str, Any] = {}
    family = detect_model_family(config.llm_model)

    if family == "qwen":
        if streaming:
            extra_body["enable_thinking"] = bool(config.llm_thinking)
        else:
            extra_body["enable_thinking"] = False

        if include_reasoning and config.llm_thinking and config.llm_reasoning_effort:
            extra_body["reasoning_effort"] = config.llm_reasoning_effort
            extra_body["chat_template_kwargs"] = {
                "thinking": True,
                "reasoning_effort": config.llm_reasoning_effort,
            }
    elif include_reasoning and config.llm_thinking and config.llm_reasoning_effort:
        extra_body["reasoning_effort"] = config.llm_reasoning_effort

    kwargs: dict[str, Any] = {
        "model": config.llm_model,
        "temperature": config.llm_temperature,
        "top_p": config.llm_top_p,
        "max_tokens": config.llm_max_tokens,
        "timeout": config.llm_timeout,
    }
    if extra_body:
        kwargs["extra_body"] = extra_body
    return kwargs


def execute_llm_completion(
    client: OpenAI,
    config: TomeConfig,
    messages: Any,
    observer: Callable[[str, Any], None] | None = None,
    max_retries: int = 10,
    identifier: str = "llm_completion",
    metrics_out: dict[str, Any] | None = None,
    book_title: str | None = None,
) -> str:
    last_err: Exception | None = None
    captured_req_id = ""
    prompt_tokens = 0
    completion_tokens = 0
    reasoning_tokens = 0
    total_tokens = 0
    include_reasoning = True

    for attempt in range(1, max_retries + 1):
        client_request_id = str(uuid.uuid4())
        extra_headers = {"X-Client-Request-Id": client_request_id}
        try:
            req_params = build_model_request_params(
                config, streaming=config.stream_response, include_reasoning=include_reasoning
            )
            if config.stream_response:
                req_params["stream_options"] = {"include_usage": True}
                stream_obj: Any = client.chat.completions.create(
                    messages=messages,
                    stream=True,
                    extra_headers=extra_headers,
                    **req_params,
                )

                content_chunks: list[str] = []
                try:
                    for chunk in stream_obj:
                        chunk_req_id = getattr(chunk, "_request_id", None) or getattr(chunk, "id", None)
                        if chunk_req_id and not captured_req_id:
                            captured_req_id = str(chunk_req_id)
                        chunk_usage = getattr(chunk, "usage", None)
                        if chunk_usage:
                            prompt_tokens = getattr(chunk_usage, "prompt_tokens", 0) or prompt_tokens
                            completion_tokens = getattr(chunk_usage, "completion_tokens", 0) or completion_tokens
                            reasoning_tokens = (
                                getattr(getattr(chunk_usage, "completion_tokens_details", None), "reasoning_tokens", 0)
                                or reasoning_tokens
                            )
                            total_tokens = getattr(chunk_usage, "total_tokens", 0) or (
                                prompt_tokens + completion_tokens
                            )

                        if not hasattr(chunk, "choices") or not chunk.choices:
                            continue
                        delta = chunk.choices[0].delta
                        reasoning = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
                        if reasoning and observer:
                            observer("llm_reasoning_chunk", reasoning)
                        if delta.content:
                            content_chunks.append(delta.content)
                            if observer:
                                observer("llm_content_chunk", delta.content)
                except KeyboardInterrupt:
                    if hasattr(stream_obj, "response") and hasattr(stream_obj.response, "close"):
                        with contextlib.suppress(Exception):
                            stream_obj.response.close()
                    raise

                result_text = "".join(content_chunks)
            else:
                response = client.chat.completions.create(
                    messages=messages,
                    stream=False,
                    extra_headers=extra_headers,
                    **req_params,
                )
                captured_req_id = str(getattr(response, "_request_id", "") or getattr(response, "id", ""))
                usage_obj = getattr(response, "usage", None)
                if usage_obj:
                    prompt_tokens = getattr(usage_obj, "prompt_tokens", 0)
                    completion_tokens = getattr(usage_obj, "completion_tokens", 0)
                    reasoning_tokens = getattr(
                        getattr(usage_obj, "completion_tokens_details", None), "reasoning_tokens", 0
                    )
                    total_tokens = getattr(usage_obj, "total_tokens", 0) or (prompt_tokens + completion_tokens)

                if hasattr(response, "choices") and response.choices:
                    msg = response.choices[0].message
                    rc = getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None)
                    if rc and observer:
                        observer("llm_reasoning_chunk", rc)
                    result_text = msg.content or ""
                elif isinstance(response, list):
                    result_text = "".join(
                        c.choices[0].delta.content for c in response if c.choices and c.choices[0].delta.content
                    )
                else:
                    result_text = str(response)

            if total_tokens == 0:
                est_in = sum(len(str(m.get("content", "")).split()) for m in messages if isinstance(m, dict)) * 4 // 3
                est_out = len(result_text.split()) * 4 // 3
                prompt_tokens = est_in
                completion_tokens = est_out
                total_tokens = est_in + est_out

            if metrics_out is not None:
                metrics_out["prompt_tokens"] = prompt_tokens
                metrics_out["completion_tokens"] = completion_tokens
                metrics_out["reasoning_tokens"] = reasoning_tokens
                metrics_out["total_tokens"] = total_tokens
                metrics_out["request_id"] = captured_req_id

            save_llm_response_cache(
                log_dir=config.log_dir,
                identifier=identifier,
                raw_response=result_text,
                book_title=book_title,
                max_age_days=config.log_retention_days,
            )
            return result_text

        except BadRequestError as bad_err:
            err_str = str(bad_err).lower()
            if is_wallet_empty(getattr(bad_err, "status_code", 400), str(bad_err)) and observer:
                observer(
                    "wallet_empty",
                    {"error": "AvalAI wallet balance insufficient. Please recharge at chat.avalai.ir."},
                )
            if include_reasoning and any(
                k in err_str
                for k in (
                    "reasoning",
                    "thinking",
                    "extra_body",
                    "unrecognized",
                    "not supported",
                    "unknown parameter",
                    "invalid_request",
                )
            ):
                if observer:
                    observer(
                        "api_warning",
                        {
                            "warning": f"Model '{config.llm_model}' does not support reasoning parameters. Retrying without extra parameters."
                        },
                    )
                include_reasoning = False
                continue

            formatted_msg = format_api_error(bad_err, config.llm_model, client_request_id=client_request_id)
            if observer:
                observer("api_error", {"error": formatted_msg})
            raise TranslationError(formatted_msg) from bad_err

        except (AuthenticationError, PermissionDeniedError, NotFoundError) as fatal_err:
            status_code = getattr(fatal_err, "status_code", 0)
            if is_wallet_empty(status_code, str(fatal_err)) and observer:
                observer(
                    "wallet_empty",
                    {"error": "AvalAI wallet balance insufficient. Please recharge at chat.avalai.ir."},
                )
            formatted_msg = format_api_error(fatal_err, config.llm_model, client_request_id=client_request_id)
            if observer:
                observer("api_error", {"error": formatted_msg})
            raise TranslationError(formatted_msg) from fatal_err

        except (
            APIConnectionError,
            APITimeoutError,
            RateLimitError,
            InternalServerError,
            TimeoutError,
            ConnectionError,
            OSError,
        ) as err:
            last_err = err
            formatted_msg = format_api_error(err, config.llm_model, client_request_id=client_request_id)
            if observer:
                observer("api_retry", {"attempt": attempt, "max": max_retries, "error": formatted_msg})
            if attempt < max_retries:
                if isinstance(err, RateLimitError):
                    delay = parse_retry_delay(getattr(getattr(err, "response", None), "headers", None))
                    backoff = delay if delay else min(60, 15 * attempt)
                    if observer:
                        observer("rate_limit_wait", {"wait_seconds": backoff, "attempt": attempt})
                else:
                    backoff = min(45, 4 * attempt)
                time.sleep(backoff)
            else:
                raise TranslationError(f"{formatted_msg} (Failed after {max_retries} attempts)") from err

        except Exception as generic_err:
            err_str = str(generic_err).lower()
            if is_wallet_empty(0, str(generic_err)) and observer:
                observer(
                    "wallet_empty",
                    {"error": "AvalAI wallet balance insufficient. Please recharge at chat.avalai.ir."},
                )
            is_transient = any(
                k in err_str
                for k in (
                    "timeout",
                    "timed out",
                    "connection",
                    "network",
                    "proxy",
                    "reset",
                    "broken pipe",
                    "eof",
                    "handshake",
                    "502",
                    "503",
                    "504",
                    "stream",
                    "protocol",
                    "closed",
                )
            )
            if is_transient:
                last_err = generic_err
                formatted_msg = format_api_error(generic_err, config.llm_model, client_request_id=client_request_id)
                if observer:
                    observer("api_retry", {"attempt": attempt, "max": max_retries, "error": formatted_msg})
                if attempt < max_retries:
                    backoff = min(45, 4 * attempt)
                    time.sleep(backoff)
                    continue
                raise TranslationError(f"{formatted_msg} (Failed after {max_retries} attempts)") from generic_err

            raise TranslationError(f"LLM execution failed: {generic_err}") from generic_err

    raise TranslationError(f"Unexpected translation failure: {last_err}")


def translate_glossary(
    glossary_path: Path,
    config: TomeConfig,
    observer: Callable[[str, Any], None] | None = None,
) -> tuple[Path, float]:
    t0 = time.perf_counter()
    if not glossary_path.exists():
        return glossary_path, 0.0

    content = glossary_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    is_legacy_schema = False
    for line in lines:
        if line.startswith("| Canonical") and "Occurrences" in line:
            is_legacy_schema = True
            break

    data_rows: list[tuple[int, list[str]]] = []
    for idx, line in enumerate(lines):
        if line.startswith("|") and not line.startswith("|---"):
            cols = [c.strip() for c in line.split("|")[1:-1]]
            if len(cols) >= 5 and cols[0] != "Canonical Term":
                if is_legacy_schema:
                    data_rows.append((idx, [cols[0], cols[1], cols[3], cols[4], ""]))
                else:
                    data_rows.append((idx, cols))

    untranslated = [row for row in data_rows if not row[1][2]]
    if not untranslated:
        return glossary_path, 0.0

    if observer:
        observer("stage_start", {"stage": "glossary_translation", "count": len(untranslated)})

    client = get_openai_client(config)

    from tome.config import DEFAULT_PROMPTS

    prompt_name = config.get_glossary_prompt_name()
    system_prompt_template = config.prompts.get(prompt_name, DEFAULT_PROMPTS.get(prompt_name, ""))
    validate_prompt_variables(
        system_prompt_template, {"target_language"}, prompt_name=prompt_name
    )
    system_prompt = system_prompt_template.replace("{target_language}", config.target_language)

    table_lines = [
        "| Canonical Term | Aliases / Variants | Term Translation | Sample Context | Context Translation |",
        "|---|---|---|---|---|",
    ]
    for _, cols in untranslated:
        ctx = cols[3] if len(cols) > 3 else ""
        table_lines.append(f"| {cols[0]} | {cols[1]} | | {ctx} | |")

    full_table_input = "\n".join(table_lines)
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"<glossary_table>\n{full_table_input}\n</glossary_table>",
        },
    ]

    translated_table = execute_llm_completion(
        client,
        config,
        messages,
        observer=observer,
        identifier="glossary_translation",
        book_title=glossary_path.parent.name,
    )

    translated_map: dict[str, tuple[str, str]] = {}
    for line in translated_table.splitlines():
        if line.startswith("|") and not line.startswith("| Canonical") and not line.startswith("|---"):
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 5 and parts[0]:
                canon_key = parts[0].strip().lower()
                translated_map[canon_key] = (parts[2].strip(), parts[4].strip())

    for orig_idx, orig_cols in untranslated:
        canon_key = orig_cols[0].strip().lower()
        if canon_key in translated_map:
            term_trans, ctx_trans = translated_map[canon_key]
            lines[orig_idx] = f"| {orig_cols[0]} | {orig_cols[1]} | {term_trans} | {orig_cols[3]} | {ctx_trans} |"

    if is_legacy_schema:
        for idx, line in enumerate(lines):
            if line.startswith("| Canonical") and "Occurrences" in line:
                lines[idx] = (
                    "| Canonical Term | Aliases / Variants | Term Translation | Sample Context | Context Translation |"
                )

    glossary_path.write_text("\n".join(lines), encoding="utf-8")
    duration = round(time.perf_counter() - t0, 2)
    if observer:
        observer("glossary_translation_complete", {"path": str(glossary_path), "duration": duration})
    return glossary_path, duration


def translate_chapter(
    chapter_path: Path,
    config: TomeConfig,
    client: OpenAI,
    glossary_content: str = "",
    graph_context: str = "",
    observer: Callable[[str, Any], None] | None = None,
    content_override: str | None = None,
    metrics_out: dict[str, Any] | None = None,
    genre: str | None = None,
    rolling_summary: str = "",
) -> tuple[str, list[Entity]]:
    chapter_text = content_override if content_override is not None else chapter_path.read_text(encoding="utf-8")

    has_glossary = bool(glossary_content.strip())
    resolved_genre = (genre or "").lower().strip()
    if not resolved_genre:
        for cand_dir in [chapter_path.parent, chapter_path.parent.parent]:
            cand_meta = cand_dir / "metadata.json"
            if cand_meta.exists():
                with contextlib.suppress(Exception):
                    m_data = json.loads(cand_meta.read_text(encoding="utf-8"))
                    if m_data.get("genre"):
                        resolved_genre = str(m_data.get("genre")).lower().strip()
                        break
        if not resolved_genre:
            resolved_genre = config.resolve_genre(chapter_text)

    from tome.config import DEFAULT_PROMPTS

    prompt_name = config.get_chapter_prompt_name(has_glossary=has_glossary)
    system_template = config.prompts.get(prompt_name, DEFAULT_PROMPTS.get(prompt_name, ""))
    validate_prompt_variables(
        system_template,
        {"target_language", "user_style_rules", "graph"},
        prompt_name=prompt_name,
    )

    if not graph_context:
        candidate_dirs = [chapter_path.parent, chapter_path.parent.parent]
        for c_dir in candidate_dirs:
            candidate_graph = c_dir / "graph.md"
            if candidate_graph.exists():
                graph_context = extract_focused_graph_context(candidate_graph)
                break
            candidate_legacy = c_dir / "character_graph.md"
            if candidate_legacy.exists():
                graph_context = extract_focused_graph_context(candidate_legacy)
                break

    has_graph_var = "{graph}" in system_template
    formatted_graph = graph_context.strip() if graph_context.strip() else "No relationship graph available."

    system_prompt = normalize_prompt_escapes(
        system_template.replace("{target_language}", config.target_language)
        .replace("{user_style_rules}", config.user_style_rules or "Maintain natural literary prose.")
        .replace("{graph}", formatted_graph)
    )

    if "fantasy" in resolved_genre:
        fantasy_rules = config.prompts.get(
            "fantasy_translation_guidelines",
            DEFAULT_PROMPTS.get("fantasy_translation_guidelines", ""),
        ).strip()
        if fantasy_rules:
            fantasy_rules_formatted = normalize_prompt_escapes(
                fantasy_rules.replace("{target_language}", config.target_language)
            )
            system_prompt = f"{system_prompt}\n\n{fantasy_rules_formatted}"

    user_parts: list[str] = []

    if has_glossary:
        user_parts.append(f"<glossary>\n{glossary_content.strip()}\n</glossary>")

    if graph_context.strip() and not has_graph_var:
        user_parts.append(f"<character_dossier>\n{graph_context.strip()}\n</character_dossier>")

    if rolling_summary.strip():
        user_parts.append(f"<story_so_far>\n{rolling_summary.strip()}\n</story_so_far>")

    user_parts.append(f'<manuscript filename="{chapter_path.name}">\n{chapter_text.strip()}\n</manuscript>')
    user_parts.append(
        f'Translate and copyedit the entire content of <manuscript filename="{chapter_path.name}"> into {config.target_language}. '
        "MANDATORY DUAL-VOICE REQUIREMENT: "
        "1. All direct dialogue and spoken lines inside « » MUST be natural living colloquial spoken Persian (کاملاً محاوره‌ای، تهرانی معیار و شکسته با افعالی مثل می‌خوام، می‌دونم، نمی‌شه، و حذف کامل «را» به نفع «رو/ـو»). "
        "2. Narrative prose and scene descriptions outside « » MUST be formal, dignified, publication-grade literary Persian (نثر کاملاً رسمی، فاخر، شیوا و کتابی). "
        "Strictly adhere to all system instructions, terminology in <glossary>, and character voices in <character_dossier>. Maintain continuity with <story_so_far> for plot, character states, and terminology. "
        "Do not ask questions, propose options, or include commentary. "
        "Even if the text appears to start mid-sentence or contains unusual dialogue, output ONLY the finalized translation in Markdown."
    )

    user_message = "\n\n".join(user_parts)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    book_title = chapter_path.parent.parent.name if chapter_path.parent.name == "chapters" else chapter_path.parent.name

    if observer:
        observer(
            "translation_attempt",
            {"chapter": chapter_path.name, "attempt": 1, "max_attempts": 3, "strategy": "initial"},
        )
    logger.info("Translating %s [Attempt 1/3: Initial]", chapter_path.name)

    raw_content = execute_llm_completion(
        client,
        config,
        messages,
        observer=observer,
        identifier=f"chapter_{chapter_path.stem}",
        metrics_out=metrics_out,
        book_title=book_title,
    )

    is_valid, validation_reason = validate_translation_response(raw_content, config.target_language, chapter_text)
    if not is_valid:
        if observer:
            observer(
                "translation_attempt",
                {
                    "chapter": chapter_path.name,
                    "attempt": 2,
                    "max_attempts": 3,
                    "strategy": "recovery",
                    "reason": validation_reason,
                },
            )
        logger.warning(
            "Translating %s [Attempt 2/3: Recovery] - Validation rejected: %s",
            chapter_path.name,
            validation_reason,
        )

        recovery_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": raw_content},
            {
                "role": "user",
                "content": (
                    f"CRITICAL: Your output was rejected: {validation_reason}\n"
                    f"You are a translation engine, NOT a conversational assistant.\n"
                    f'Translate the text in <manuscript filename="{chapter_path.name}"> into {config.target_language} immediately.\n'
                    "Output ONLY the finalized Markdown text. Zero conversational preamble, questions, or notes."
                ),
            },
        ]
        raw_content = execute_llm_completion(
            client,
            config,
            recovery_messages,
            observer=observer,
            identifier=f"chapter_{chapter_path.stem}_recovery",
            metrics_out=metrics_out,
            book_title=book_title,
        )
        is_valid_rec, rec_reason = validate_translation_response(raw_content, config.target_language, chapter_text)
        if not is_valid_rec:
            if observer:
                observer(
                    "translation_attempt",
                    {
                        "chapter": chapter_path.name,
                        "attempt": 3,
                        "max_attempts": 3,
                        "strategy": "fallback",
                        "reason": rec_reason,
                    },
                )
            logger.warning(
                "Translating %s [Attempt 3/3: Fallback] - Validation rejected: %s",
                chapter_path.name,
                rec_reason,
            )

            fresh_prompt = (
                f"Translate this book chapter into publication-grade {config.target_language} Markdown now. "
                "Output ONLY the translated text without commentary or questions:\n\n"
                f"{chapter_text.strip()}"
            )
            fallback_messages = [
                {
                    "role": "system",
                    "content": f"You are an expert literary translator. Output ONLY the {config.target_language} translation in Markdown.",
                },
                {"role": "user", "content": fresh_prompt},
            ]
            raw_content = execute_llm_completion(
                client,
                config,
                fallback_messages,
                observer=observer,
                identifier=f"chapter_{chapter_path.stem}_fresh_fallback",
                metrics_out=metrics_out,
                book_title=book_title,
            )
            is_valid_final, final_reason = validate_translation_response(
                raw_content, config.target_language, chapter_text
            )
            if not is_valid_final:
                raise TranslationError(
                    f"Chapter translation for {chapter_path.name} failed validation after 3 attempts ({final_reason}). "
                    "Halting to prevent token exhaustion."
                )

    glossary_markers = [
        "### واژه‌نامه دزبانه",
        "### واژه‌نامه دو زبانه",
        "### واژه‌نامه دوزبانه",
        "## واژه‌نامه",
        "# واژه‌نامه",
        "## اصطلاحات تخصصی حوزه",
        "### BILINGUAL GLOSSARY",
        "## BILINGUAL GLOSSARY",
        "| Canonical Term |",
    ]
    for marker in glossary_markers:
        if marker in raw_content:
            raw_content = raw_content.split(marker)[0].rstrip()
            raw_content = re.sub(r"\n\s*---\s*$", "", raw_content).rstrip()

    if config.persian_nlp and config.target_language.lower() in ("persian", "farsi"):
        save_llm_response_cache(
            log_dir=config.log_dir,
            identifier=f"raw_pre_editor_{chapter_path.stem}",
            raw_response=raw_content,
            book_title=book_title,
            max_age_days=config.log_retention_days,
        )
        from tome.core.editor import copyedit_persian_text

        raw_content, stats = copyedit_persian_text(raw_content)
        if metrics_out is not None:
            metrics_out["words_processed"] = stats.words_processed
            metrics_out["words_modified"] = stats.words_modified
            metrics_out["persian_nlp_changes"] = stats.modifications
        if observer:
            observer(
                "persian_nlp_complete",
                {
                    "chapter": chapter_path.name,
                    "stats": stats.summary(),
                    "words_modified": stats.words_modified,
                    "words_processed": stats.words_processed,
                },
            )

    if not has_glossary:
        clean_content, extracted_entities = ingest_chapter_delimiter_entities(raw_content)
        return clean_content, extracted_entities

    return raw_content, []


def extract_focused_graph_context(graph_path: Path) -> str:
    if not graph_path.exists():
        return ""
    content = graph_path.read_text(encoding="utf-8")
    if "## Executive Character & Relationship Dossier (LLM Reference)" in content:
        parts = content.split("## Executive Character & Relationship Dossier (LLM Reference)")
        if len(parts) > 1:
            dossier = parts[1].split("## Narrative Relationship Network")[0].strip()
            return f"### CHARACTER LORE & RELATIONSHIP DOSSIER\n{dossier}"

    lines = content.splitlines()
    focused: list[str] = []
    for idx, line in enumerate(lines):
        if line.startswith(
            (
                "## Executive Character Dossier",
                "## Character Profiles",
                "## Character Interactions & Dynamics",
            )
        ):
            focused.append(line)
            focused.extend(lines[idx + 1 : idx + 25])
        elif line.startswith("## ") and focused:
            focused.extend(lines[len(focused) : len(focused) + 25])
            break
    return "\n".join(focused[:40])


def _translation_flag(config: TomeConfig, key: str, default: bool) -> bool:
    """Read a translation feature flag: config attr -> tome.json translation section -> default."""
    with contextlib.suppress(Exception):
        val = getattr(config, key, None)
        if val is not None:
            return bool(val)
    with contextlib.suppress(Exception):
        data = json.loads(Path("tome.json").read_text(encoding="utf-8"))
        sect = data.get("translation") or {}
        if key in sect:
            return bool(sect[key])
    return default


def update_rolling_summary(
    config: TomeConfig,
    client: OpenAI,
    previous_summary: str,
    chapter_name: str,
    translated_text: str,
    observer: Callable[[str, Any], None] | None = None,
) -> str:
    """Return an updated rolling story summary. Falls back to previous on any failure."""
    prompt = (
        f"Previous story summary:\n{previous_summary.strip() or '(none - this is the first chapter)'}\n\n"
        f"New translated chapter ({chapter_name}):\n{translated_text.strip()[:12000]}\n\n"
        f"Write an updated running summary in {config.target_language} (maximum 180 words) preserving "
        "all important continuity facts: plot progress, character names and their current states, locations, "
        "open questions and unresolved threads. Output ONLY the summary text."
    )
    try:
        result = execute_llm_completion(
            client,
            config,
            [{"role": "user", "content": prompt}],
            observer=None,
            identifier=f"rolling_summary_{Path(chapter_name).stem}",
            book_title=None,
        )
        cleaned = result.strip()
        if len(cleaned) < 40:
            return previous_summary
        if observer:
            observer("context_rolling_updated", {"chapter": chapter_name, "summary_words": len(cleaned.split())})
        return cleaned[:4000]
    except Exception as err:
        logger.warning("Rolling summary update failed for %s: %s", chapter_name, err)
        return previous_summary


def check_chapter_consistency(
    config: TomeConfig,
    client: OpenAI,
    glossary_content: str,
    chapter_name: str,
    translated_text: str,
    observer: Callable[[str, Any], None] | None = None,
) -> tuple[str, int, int]:
    """Detect glossary deviations in a translated chapter and fix them with one LLM pass.

    Returns (final_text, issues_found, fixes_applied). Never raises.
    """
    issues: list[str] = []
    try:
        for line in glossary_content.splitlines():
            if not line.startswith("|") or line.startswith("|---"):
                continue
            cols = [c.strip() for c in line.split("|")[1:-1]]
            if len(cols) < 3 or not cols[0] or cols[0] == "Canonical Term":
                continue
            canonical, aliases, term_translation = cols[0], cols[1], cols[2]
            target = term_translation.strip()
            if len(target) < 2:
                continue
            source_forms = [canonical.strip()] + [a.strip() for a in aliases.split(",") if a.strip()]
            lower_text = translated_text.lower()
            leaked = [
                f for f in source_forms
                if len(f) >= 4 and re.search(rf"(?<!\w){re.escape(f.lower())}(?!\w)", lower_text)
            ]
            missing = target.lower() not in lower_text
            if leaked or missing:
                issues.append(
                    f"{canonical} -> {target}" + (f" (source leaked: {', '.join(leaked)})" if leaked else " (target missing)")
                )
    except Exception as err:
        logger.warning("Consistency scan failed for %s: %s", chapter_name, err)
        return translated_text, 0, 0

    if not issues:
        return translated_text, 0, 0

    if observer:
        observer("consistency_issues", {"chapter": chapter_name, "count": len(issues), "issues": issues[:20]})

    relevant_rows = "\n".join(
        line for line in glossary_content.splitlines() if line.startswith("|")
    )[:6000]
    prompt = (
        f"You are a terminology enforcer for a literary translation into {config.target_language}.\n"
        f"Glossary (authoritative):\n{relevant_rows}\n\n"
        f"Translated chapter ({chapter_name}):\n{translated_text.strip()[:14000]}\n\n"
        "Some entity names in the chapter deviate from the glossary. Rewrite the chapter so that EVERY "
        "entity name exactly matches its 'Term Translation' in the glossary. Change names only; do not alter "
        "style, dialogue, or anything else. Output ONLY the full corrected chapter."
    )
    try:
        fixed = execute_llm_completion(
            client,
            config,
            [{"role": "user", "content": prompt}],
            observer=None,
            identifier=f"consistency_{Path(chapter_name).stem}",
            book_title=None,
        ).strip()
        src_len = max(1, len(translated_text))
        if fixed and 0.6 <= len(fixed) / src_len <= 1.6:
            if observer:
                observer("consistency_fixed", {"chapter": chapter_name, "issues": len(issues)})
            return fixed, len(issues), 1
        logger.warning("Consistency fix rejected for %s (length ratio out of range)", chapter_name)
    except Exception as err:
        logger.warning("Consistency fix failed for %s: %s", chapter_name, err)
    return translated_text, len(issues), 0


def score_chapter_quality(
    config: TomeConfig,
    client: OpenAI,
    chapter_name: str,
    translated_text: str,
    observer: Callable[[str, Any], None] | None = None,
) -> tuple[int, str]:
    """Grade translation quality 1-10. Returns (score, reason); (0, '') on failure."""
    prompt = (
        f"You are a strict literary translation grader. The target language is {config.target_language}.\n"
        f"Chapter ({chapter_name}):\n{translated_text.strip()[:12000]}\n\n"
        "Grade the translation quality: fidelity to meaning, fluency, and internal consistency. "
        "Reply in exactly this format:\nSCORE: <integer 1-10>\nREASON: <one short sentence>"
    )
    try:
        raw = execute_llm_completion(
            client,
            config,
            [{"role": "user", "content": prompt}],
            observer=None,
            identifier=f"quality_{Path(chapter_name).stem}",
            book_title=None,
        )
        m = re.search(r"SCORE:\s*(\d+)", raw)
        score = int(m.group(1)) if m else 0
        if score:
            score = max(1, min(10, score))
        rm = re.search(r"REASON:\s*(.+)", raw)
        reason = rm.group(1).strip()[:300] if rm else ""
        if score and observer:
            observer("chapter_quality_scored", {"chapter": chapter_name, "score": score, "reason": reason})
        return score, reason
    except Exception as err:
        logger.warning("Quality scoring failed for %s: %s", chapter_name, err)
        return 0, ""


def _save_quality(path: Path, lock: threading.Lock, chapter_name: str, score: int, reason: str) -> None:
    """Append/overwrite a chapter quality record in <book>/quality_scores.json (thread-safe)."""
    with lock:
        data: dict[str, Any] = {}
        if path.exists():
            with contextlib.suppress(Exception):
                data = json.loads(path.read_text(encoding="utf-8"))
        data[chapter_name] = {"score": score, "reason": reason}
        with contextlib.suppress(Exception):
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def translate_book(
    book_dir: Path,
    config: TomeConfig | None = None,
    chapters: str | int | set[int] | list[int] | None = None,
    max_chapters: int | None = None,
    observer: Callable[[str, Any], None] | None = None,
) -> tuple[list[Path], dict[str, float]]:
    start_total = time.perf_counter()
    timings: dict[str, float] = {}

    if config is None:
        config = TomeConfig.load_config()

    rate = resolve_exchange_rate(config)

    if not book_dir.exists():
        raise FileNotFoundError(f"Book directory not found: {book_dir}")

    chapters_dir = book_dir / "chapters"
    if not chapters_dir.exists():
        if (book_dir / "original" / "book.md").exists() or (book_dir / "book.md").exists():
            chapters_dir = book_dir
        else:
            raise FileNotFoundError(f"No chapters directory found in: {book_dir}")

    translation_dir = book_dir / "translation"
    translation_dir.mkdir(parents=True, exist_ok=True)

    glossary_path = book_dir / "glossary.md"
    if glossary_path.exists():
        _, dur = translate_glossary(glossary_path, config, observer=observer)
        if dur > 0:
            timings["glossary"] = dur

    glossary_content = glossary_path.read_text(encoding="utf-8") if glossary_path.exists() else ""
    graph_path = book_dir / "graph.md"
    graph_context = extract_focused_graph_context(graph_path)

    raw_files = sorted([f for f in chapters_dir.glob("*.md") if f.is_file() and f.name != "book.md"])
    consolidated_items: list[tuple[Path, str]] = []
    pending_prefix = ""
    for idx, f in enumerate(raw_files):
        text = f.read_text(encoding="utf-8")
        current_content = (f"{pending_prefix}\n\n{text}").strip() if pending_prefix else text.strip()
        pending_prefix = ""
        if len(current_content.encode("utf-8")) < 512:
            if idx + 1 < len(raw_files):
                pending_prefix = current_content
                continue
            elif consolidated_items:
                prev_path, prev_text = consolidated_items[-1]
                consolidated_items[-1] = (prev_path, f"{prev_text}\n\n{current_content}".strip())
                continue
        consolidated_items.append((f, current_content))

    if pending_prefix and consolidated_items:
        prev_path, prev_text = consolidated_items[-1]
        consolidated_items[-1] = (prev_path, f"{prev_text}\n\n{pending_prefix}".strip())

    if chapters is not None:
        if isinstance(chapters, (list, set)):
            slug_tokens = {str(t).strip().lower() for t in chapters}
        else:
            slug_tokens = {t.strip().lower() for t in re.split(r"[,;]+", str(chapters)) if t.strip()}
        int_selection = parse_chapter_selection(chapters)

        filtered_items: list[tuple[Path, str]] = []
        for idx, (chap_path, content) in enumerate(consolidated_items, start=1):
            chap_num = extract_chapter_number(chap_path, idx)
            stem_clean = chap_path.stem.lower()
            if (
                stem_clean in slug_tokens
                or chap_path.name.lower() in slug_tokens
                or (int_selection and (chap_num in int_selection or idx in int_selection))
            ):
                filtered_items.append((chap_path, content))
        consolidated_items = filtered_items
    elif max_chapters is not None and max_chapters > 0:
        consolidated_items = consolidated_items[:max_chapters]

    if not consolidated_items:
        return [], timings

    from tome.core.logging import setup_logger

    setup_logger(config.log_dir, book_title=book_dir.name)

    book_meta_file = book_dir / "metadata.json"
    book_genre = None
    if book_meta_file.exists():
        with contextlib.suppress(Exception):
            book_genre = json.loads(book_meta_file.read_text(encoding="utf-8")).get("genre")

    is_avalai = is_avalai_endpoint(config.llm_base_url)
    proxy_url = None
    if config.proxy_enabled:
        scheme = config.proxy_type.lower()
        if scheme in ("socks", "socks5", "socks5h"):
            proxy_url = f"socks5://{config.proxy_host}:{config.proxy_port}"
        else:
            proxy_url = f"http://{config.proxy_host}:{config.proxy_port}"

    credit_info = get_avalai_credit(config.llm_api_key, proxy_url=proxy_url) if is_avalai else None
    init_credit = None
    if credit_info and "remaining_irt" in credit_info:
        with contextlib.suppress(ValueError, TypeError):
            init_credit = float(credit_info["remaining_irt"])

    if is_avalai and credit_info and observer:
        observer("avalai_credit_info", credit_info)
        if init_credit is not None and init_credit < 5000:
            observer("wallet_warning", {"warning": f"AvalAI credit is low: {init_credit:,.0f} IRT remaining."})

    book_metrics = BookTranslationMetrics(
        book_title=book_dir.name,
        model=config.llm_model,
        initial_credit_irt=init_credit,
        exchange_rate=rate,
    )

    client = get_openai_client(config)
    translated_paths: list[Path] = []
    running_entities: list[Entity] = []

    rolling_enabled = _translation_flag(config, "context_rolling", True)
    rolling_path = book_dir / "context_rolling.md"
    rolling_summary = rolling_path.read_text(encoding="utf-8").strip() if rolling_path.exists() else ""
    rolling_lock = threading.Lock()
    consistency_enabled = _translation_flag(config, "consistency_check", True) and bool(glossary_content)
    quality_enabled = _translation_flag(config, "quality_score", True)
    quality_path = book_dir / "quality_scores.json"
    quality_lock = threading.Lock()

    total_chapters = len(consolidated_items)
    batch_size = max(1, config.translation_batch_size)

    if batch_size > 1 and bool(glossary_content):
        pending_items: list[tuple[int, Path, str]] = []
        for idx, (chap_file, chap_content) in enumerate(consolidated_items, start=1):
            out_file = translation_dir / chap_file.name
            if out_file.exists() and out_file.stat().st_size > 50:
                translated_paths.append(out_file)
                if observer:
                    observer("chapter_cached", {"chapter": chap_file.name, "index": idx, "total": total_chapters})
            else:
                pending_items.append((idx, chap_file, chap_content))

        if pending_items:

            def _worker(item: tuple[int, Path, str]) -> tuple[str, float, dict[str, Any]]:
                c_idx, c_file, c_content = item
                t0 = time.perf_counter()
                if observer:
                    observer(
                        "chapter_translation_start",
                        {"chapter": c_file.name, "index": c_idx, "total": total_chapters},
                    )
                worker_metrics: dict[str, Any] = {}
                t_text, _ = translate_chapter(
                    chapter_path=c_file,
                    config=config,
                    client=client,
                    glossary_content=glossary_content,
                    graph_context=graph_context,
                    observer=observer,
                    content_override=c_content,
                    metrics_out=worker_metrics,
                    genre=book_genre,
                    rolling_summary=rolling_summary,
                )
                if consistency_enabled:
                    t_text, _cons_issues, _cons_fixed = check_chapter_consistency(config, client, glossary_content, c_file.name, t_text, observer)
                if quality_enabled:
                    _q_score, _q_reason = score_chapter_quality(config, client, c_file.name, t_text, observer)
                    if _q_score:
                        _save_quality(quality_path, quality_lock, c_file.name, _q_score, _q_reason)
                c_out = translation_dir / c_file.name
                c_out.write_text(t_text, encoding="utf-8")
                if rolling_enabled:
                    with rolling_lock:
                        prev_sum = rolling_path.read_text(encoding="utf-8").strip() if rolling_path.exists() else ""
                        new_sum = update_rolling_summary(config, client, prev_sum, c_file.name, t_text, observer)
                        if new_sum and new_sum != prev_sum:
                            rolling_path.write_text(new_sum, encoding="utf-8")
                dur = round(time.perf_counter() - t0, 2)
                return c_file.name, dur, worker_metrics

            workers = min(batch_size, len(pending_items))
            executor = ThreadPoolExecutor(max_workers=workers)
            try:
                futures = [executor.submit(_worker, item) for item in pending_items]
                for fut in as_completed(futures):
                    chap_name, dur, w_metrics = fut.result()
                    timings[chap_name] = dur
                    p_toks = int(w_metrics.get("prompt_tokens", 0))
                    c_toks = int(w_metrics.get("completion_tokens", 0))
                    r_toks = int(w_metrics.get("reasoning_tokens", 0))
                    t_toks = int(w_metrics.get("total_tokens", p_toks + c_toks))
                    c_irt, _ = estimate_token_cost(
                        config.llm_model, prompt_tokens=p_toks, completion_tokens=c_toks, reasoning_tokens=r_toks,
                        exchange_rate=rate,
                    )
                    w_mod = int(w_metrics.get("words_modified", 0))
                    w_proc = int(w_metrics.get("words_processed", 0))
                    nlp_changes = w_metrics.get("persian_nlp_changes", {})

                    cm = ChapterMetrics(
                        chapter_index=len(book_metrics.chapters) + 1,
                        chapter_name=chap_name,
                        duration_seconds=dur,
                        prompt_tokens=p_toks,
                        completion_tokens=c_toks,
                        reasoning_tokens=r_toks,
                        total_tokens=t_toks,
                        cost_toman=c_irt,
                        exchange_rate=rate,
                        request_id=str(w_metrics.get("request_id", "")),
                        words_normalized=w_mod,
                    )
                    book_metrics.add_chapter(cm)
                    book_metrics.nlp_words_processed += w_proc
                    book_metrics.nlp_words_modified += w_mod
                    for km, vm in nlp_changes.items():
                        book_metrics.persian_nlp_changes[km] = book_metrics.persian_nlp_changes.get(km, 0) + vm
                    book_metrics.nlp_unique_modifications_count = len(book_metrics.persian_nlp_changes)

                    if observer:
                        observer(
                            "chapter_translation_complete",
                            {
                                "chapter": chap_name,
                                "output": str(translation_dir / chap_name),
                                "duration": dur,
                                "tokens": t_toks,
                                "prompt_tokens": p_toks,
                                "completion_tokens": c_toks,
                                "cost_toman": c_irt,
                                "words_normalized": w_mod,
                                "avg_duration": book_metrics.average_duration_seconds,
                                "avg_cost_toman": book_metrics.average_cost_toman_per_chapter,
                            },
                        )
            except KeyboardInterrupt:
                executor.shutdown(wait=False, cancel_futures=True)
                raise
            finally:
                executor.shutdown(wait=False, cancel_futures=True)

        translated_paths = [
            translation_dir / f.name
            for f, _ in consolidated_items
            if (translation_dir / f.name).exists() and (translation_dir / f.name).stat().st_size > 50
        ]
    else:
        for idx, (chap_file, chap_content) in enumerate(consolidated_items, start=1):
            out_file = translation_dir / chap_file.name
            if out_file.exists() and out_file.stat().st_size > 50:
                translated_paths.append(out_file)
                if observer:
                    observer("chapter_cached", {"chapter": chap_file.name, "index": idx, "total": total_chapters})
                continue

            t0 = time.perf_counter()
            if observer:
                observer(
                    "chapter_translation_start", {"chapter": chap_file.name, "index": idx, "total": total_chapters}
                )

            seq_metrics: dict[str, Any] = {}
            translated_text, new_entities = translate_chapter(
                chapter_path=chap_file,
                config=config,
                client=client,
                glossary_content=glossary_content,
                graph_context=graph_context,
                observer=observer,
                content_override=chap_content,
                metrics_out=seq_metrics,
                genre=book_genre,
                rolling_summary=rolling_summary,
            )

            if consistency_enabled:
                translated_text, _cons_issues, _cons_fixed = check_chapter_consistency(config, client, glossary_content, chap_file.name, translated_text, observer)

            if quality_enabled:
                _q_score, _q_reason = score_chapter_quality(config, client, chap_file.name, translated_text, observer)
                if _q_score:
                    _save_quality(quality_path, quality_lock, chap_file.name, _q_score, _q_reason)

            out_file.write_text(translated_text, encoding="utf-8")
            translated_paths.append(out_file)

            if rolling_enabled:
                updated_summary = update_rolling_summary(config, client, rolling_summary, chap_file.name, translated_text, observer)
                if updated_summary and updated_summary != rolling_summary:
                    rolling_summary = updated_summary
                    with contextlib.suppress(Exception):
                        rolling_path.write_text(rolling_summary, encoding="utf-8")

            duration = round(time.perf_counter() - t0, 2)
            timings[chap_file.name] = duration

            p_toks = int(seq_metrics.get("prompt_tokens", 0))
            c_toks = int(seq_metrics.get("completion_tokens", 0))
            r_toks = int(seq_metrics.get("reasoning_tokens", 0))
            t_toks = int(seq_metrics.get("total_tokens", p_toks + c_toks))
            c_irt, _ = estimate_token_cost(
                config.llm_model, prompt_tokens=p_toks, completion_tokens=c_toks, reasoning_tokens=r_toks,
                exchange_rate=rate,
            )
            w_mod = int(seq_metrics.get("words_modified", 0))
            w_proc = int(seq_metrics.get("words_processed", 0))
            nlp_changes = seq_metrics.get("persian_nlp_changes", {})

            cm = ChapterMetrics(
                chapter_index=idx,
                chapter_name=chap_file.name,
                duration_seconds=duration,
                prompt_tokens=p_toks,
                completion_tokens=c_toks,
                reasoning_tokens=r_toks,
                total_tokens=t_toks,
                cost_toman=c_irt,
                exchange_rate=rate,
                request_id=str(seq_metrics.get("request_id", "")),
                words_normalized=w_mod,
            )
            book_metrics.add_chapter(cm)
            book_metrics.nlp_words_processed += w_proc
            book_metrics.nlp_words_modified += w_mod
            for km, vm in nlp_changes.items():
                book_metrics.persian_nlp_changes[km] = book_metrics.persian_nlp_changes.get(km, 0) + vm
            book_metrics.nlp_unique_modifications_count = len(book_metrics.persian_nlp_changes)

            if observer:
                observer(
                    "chapter_translation_complete",
                    {
                        "chapter": chap_file.name,
                        "output": str(out_file),
                        "duration": duration,
                        "index": idx,
                        "total": total_chapters,
                        "tokens": t_toks,
                        "prompt_tokens": p_toks,
                        "completion_tokens": c_toks,
                        "cost_toman": c_irt,
                        "words_normalized": w_mod,
                        "avg_duration": book_metrics.average_duration_seconds,
                        "avg_cost_toman": book_metrics.average_cost_toman_per_chapter,
                    },
                )
            time.sleep(1.0)

            if new_entities:
                existing_canon = {e.canonical.lower() for e in running_entities}
                fresh = [e for e in new_entities if e.canonical.lower() not in existing_canon]
                if fresh:
                    running_entities.extend(fresh)
                    grouped: dict[str, list[Entity]] = {}
                    for e in running_entities:
                        grouped.setdefault(e.category, []).append(e)
                    write_glossary_markdown(grouped, glossary_path)
                    glossary_content = glossary_path.read_text(encoding="utf-8")

    final_credit_info = get_avalai_credit(config.llm_api_key, proxy_url=proxy_url) if is_avalai else None
    final_credit = None
    if final_credit_info and "remaining_irt" in final_credit_info:
        with contextlib.suppress(ValueError, TypeError):
            final_credit = float(final_credit_info["remaining_irt"])

    book_metrics.finalize(final_credit_toman=final_credit)
    book_metrics.save(book_dir, log_dir=config.log_dir, max_age_days=config.log_retention_days)

    if observer:
        observer("translation_metrics", book_metrics.to_dict())

    if config.compile_docx and translated_paths:
        try:
            from tome.core.docx import compile_book_to_docx

            meta_obj = None
            meta_json = book_dir / "metadata.json"
            if meta_json.exists():
                with contextlib.suppress(Exception):
                    meta_obj = json.loads(meta_json.read_text(encoding="utf-8"))

            docx_out = book_dir / f"{book_dir.name}.docx"
            compile_book_to_docx(
                input_path=translation_dir,
                output_docx=docx_out,
                config=config,
                title=book_dir.name,
                observer=observer,
                metadata=meta_obj,
            )
        except Exception as err:
            if observer:
                observer("docx_compilation_error", {"error": str(err)})

    timings["total"] = round(time.perf_counter() - start_total, 2)
    return translated_paths, timings
