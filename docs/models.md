# Models, LLM Engine & API Integration

This guide provides technical specifications for LLM providers, supported frontier models, request correlation, prompt caching economics, and error diagnostics within Tome.

---

## 1. Provider Infrastructure & Base Endpoint

Tome natively interfaces with **AvalAI** (`https://api.avalai.ir/v1`), utilizing standard OpenAI-compatible endpoints with support for real-time SSE streaming, reasoning token channels, and dynamic parameter validation.

- **Base URL**: `https://api.avalai.ir/v1`
- **Primary Endpoint**: `/v1/chat/completions`
- **Authentication**: `Authorization: Bearer <API_KEY>`

Configuration can be specified in `tome.json` or overridden through CLI flags (`-lm, --llm-model`) and API payloads:

```json
{
  "llm_base_url": "https://api.avalai.ir/v1",
  "llm_api_key": "aa-...",
  "llm_model": "qwen3.8-flash",
  "llm_temperature": 1.0,
  "llm_top_p": 0.95,
  "llm_max_tokens": 16384,
  "llm_thinking": true,
  "llm_reasoning_effort": "medium",
  "llm_timeout": 300,
  "stream_response": true
}
```

---

## 2. Supported Frontier Models

Tome offers out-of-the-box support for the following multi-provider frontier models:

| Model Identifier | Provider | Architecture | Thinking / Reasoning Notes |
|---|---|---|---|
| **`qwen3.8-flash`** (Default) | Alibaba | Fast Reasoning | Non-streaming requires `enable_thinking: False`. Streaming supports `enable_thinking: True`. |
| **`gemini-flash-latest`** | Google | High-Throughput | Fast multimodal translation and large context window. |
| **`glm-5.3-flash`** | ZAI / Zhipu | Deep Reasoning | Real-time reasoning tokens streamed via `delta.reasoning_content`. |
| **`deepseek-v4-flash`** | DeepSeek | Code & Prose | Efficient chain-of-thought reasoning for complex manuscripts. |
| **`deepseek-v4-pro`** | DeepSeek | Deep Reasoning | Multi-pass depth reasoning for scholarly and technical texts. |
| **`claude-sonnet-5`** | Anthropic | Literary Nuance | High prose eloquence, dialogue pacing, and voice differentiation. |
| **`gpt-5.6-luna`** | OpenAI | Frontier General | Strong long-context fidelity and structured output adherence. |
| **`custom`** | Any | Auto-Detected | Enter any arbitrary model ID. Family is detected automatically. |

---

## 3. Model Family Auto-Detection & Parameter Rules

When using custom models or third-party providers, Tome automatically inspects the model identifier to determine parameter compatibility:

- **Alibaba (`qwen`)**:
  - Non-streaming calls: Enforces `extra_body={"enable_thinking": False}` as required by AvalAI.
  - Streaming calls: Supports `extra_body={"enable_thinking": True}` and surfaces thought tokens via the observer system.
- **DeepSeek / GLM / OpenAI**:
  - Automatically maps `llm_reasoning_effort` (low, medium, high) into request bodies when enabled.
- **Anthropic / Meta (Llama, Muse) / xAI (Grok) / Moonshot (Kimi) / MiniMax**:
  - Standard chat completions with graceful argument passthrough.
- **Safe Fallback**: If an upstream model rejects reasoning arguments with an HTTP 400 response, Tome catches the exception, logs a diagnostic warning, and immediately retries the request cleanly without extra parameters.

---

## 4. Request Correlation & Observability

To guarantee traceability across proxies, network timeouts, and CDN layers, Tome adheres to the following request tracking conventions:

### AvalAI Request ID (`avalai-request-id`)
- Returned in the response headers of every request.
- Authoritative identifier used for cost lookup, log queries, and support tickets.
- Replaces the deprecated `x-request-id` header (which is subject to CDN modification and will be retired by AvalAI on 2026-10-15).

### Client Request ID (`X-Client-Request-Id`)
- Tome generates an idempotent UUIDv4 passed via the `X-Client-Request-Id` HTTP header on every outgoing call.
- Allows tracing requests that terminate prematurely due to client-side network disconnects or timeouts before server headers return.

### Rate Limit Headers
Responses include dynamic headers for concurrency and token budget tracking:
- `x-ratelimit-limit-requests`: Total allowed requests per minute.
- `x-ratelimit-remaining-requests`: Remaining requests in current window.
- `x-ratelimit-reset-requests`: Seconds until request count window resets.
- `x-ratelimit-limit-tokens`: Total token quota for current window.
- `x-ratelimit-remaining-tokens`: Remaining tokens available.
- `x-ratelimit-reset-tokens`: Seconds until token quota resets.

---

## 5. Error Diagnostics & Status Mapping

When API calls fail, Tome extracts error messages, error codes, and AvalAI `solution` recommendations into minimal, actionable notifications:

| HTTP Code | Error Classification | Behavior | Remediation |
|---|---|---|---|
| **401** | Unauthorized | Immediate failure | Check `llm_api_key` in configuration. |
| **402** | Insufficient Balance | Immediate abort | Wallet depleted; displays balance error and stops without wasting retries. |
| **403** | Forbidden / Sanction | Immediate failure | Verify account permissions or configure an egress proxy. |
| **404** | Model Not Found | Immediate failure | Verify model identifier spelling in the catalog. |
| **429** | Quota / Wallet Empty | Immediate abort | `insufficient_quota` detected; halts pipeline cleanly. |
| **429** | Rate Limit Exceeded | Dynamic backoff | Pauses according to `x-ratelimit-reset-requests` or `retry-after` header before retrying. |
| **500, 502, 503** | Server Overload | Retries with backoff | Upstream provider transient error; retried automatically. |
| **Timeout** | Connection Timeout | Retries with backoff | Check network connection or increase `llm_timeout`. |

---

## 6. AvalAI User API, Balance & Telemetry

When using AvalAI endpoints, Tome connects to the AvalAI User Management API (`https://api.avalai.ir/user/v1`):

### Account Balance Tracking (`/user/v1/credit`)
- Queries real-time wallet balance at the start and conclusion of translation.
- Tracks `remaining_irt` (in **Tomans**, 1 IRT = 1 Toman) and `remaining_unit` (USD).
- Computes actual credit consumed across the translation run, including percentage of wallet utilized.
- Emits real-time warning if wallet balance falls below threshold (50,000 Tomans or $1.00).

### Transaction Cost Lookup (`/user/v1/transactions/lookup`)
- Resolves chapter request IDs directly against AvalAI billing records for precise post-run accounting.

### Dynamic 429 Rate Limit Backoff
- When encountering HTTP 429 errors, Tome parses upstream `x-ratelimit-reset-requests`, `retry-after`, or `x-ratelimit-reset` headers.
- Automatically pauses execution for the exact server-requested seconds (capped safely at 300s) instead of blind exponential retry loops.

### Immediate Wallet Exhaustion Circuit Breaker
- If the endpoint returns HTTP 402 or error messages containing `insufficient_quota`, `insufficient_credit`, `wallet empty`, or Persian equivalents (`موجودی کافی نیست`, `اعتبار حساب شما به پایان رسیده`), Tome aborts immediately to protect user tokens and avoid useless retry attempts.

---

## 7. Token Economics & Cost Tracking

Tome measures token consumption for prompt, completion, and internal reasoning channels.

### Currency Standards
- **Toman**: Primary domestic billing currency for Iranian LLM gateways (1 IRT = 1 Iranian Toman).
- **USD**: Standard international reference unit.
- **Conversion Rate**: Standardized at 70,000 Tomans per USD for estimation across supported model tiers.

### Metrics Artifacts
Upon completion of a book or chapter batch, Tome produces:
- `output/<Book>/translation_metrics.json`: Full machine-readable breakdown of chapter durations, token breakdowns, costs in Toman and USD, and wallet credit delta.
- `logs/translation_<Book>_metrics.json`: Centralized archive copy subject to configured `log_retention_days`.
- **Console & TUI Panels**: Renders tabular metrics per chapter (Duration, Tokens, Cost in Toman, Cost in USD, NLP words fixed) alongside whole-manuscript averages.
