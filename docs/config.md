# Configuration Reference (tome.json)

Tome is configured via a JSON file named `tome.json` placed in the root project directory. If the file does not exist, Tome generates a default template on its first execution.

---

### Configuration Schema

```json
{
  "general": {
    "output_dir": "output",
    "log_dir": "logs",
    "log_retention_days": 7,
    "genre": "auto",
    "keep_raw_artifacts": false,
    "min_chapter_bytes": 512,
    "hf_mirror_endpoint": "https://hf-mirror.com",
    "extract_images": true
  },
  "llm": {
    "base_url": "https://api.avalai.ir/v1",
    "api_key": "aa-...",
    "model": "qwen3.8-flash",
    "temperature": 1.0,
    "top_p": 0.95,
    "max_tokens": 16384,
    "thinking": true,
    "reasoning_effort": "medium",
    "timeout": 300,
    "stream_response": true
  },
  "proxy": {
    "enabled": false,
    "type": "socks5",
    "host": "127.0.0.1",
    "port": 10808
  },
  "nlp": {
    "refine_metadata": true,
    "persian_nlp": true,
    "fast_mode": false,
    "gliner": {
      "enabled": true,
      "model": "urchade/gliner_medium-v2.1",
      "batch_size": 16,
      "chunk_size_words": 280,
      "chunk_overlap_words": 20,
      "min_entity_frequency": 2,
      "high_confidence_threshold": 0.85,
      "fuzzy_similarity_threshold": 0.88,
      "max_levenshtein_distance": 2
    }
  },
  "translation": {
    "target_language": "Persian",
    "batch_size": 1
  },
  "typography": {
    "compile_docx": true,
    "eastern_font": "B Nazanin",
    "western_font": "Times New Roman",
    "paragraph_indent": "0.4cm",
    "line_spacing": "1.35x",
    "body_font_size": "11",
    "heading1_pagebreak": true,
    "margin_cm": 2.5
  },
  "prompts": {
    "user_style_rules": "",
    "glossary_translation_system_prompt": "...",
    "chapter_translation_with_glossary_system_prompt": "...",
    "chapter_translation_no_gliner_system_prompt": "...",
    "metadata_refinement_system_prompt": "..."
  }
}
```

---

## Detailed Setting Explanations

### 1. General Settings (`general`)

| Setting | Type | Default | Description |
|---|---|---|---|
| `output_dir` | string | `output` | Root directory for processed manuscripts, chapters, and compiled books. |
| `log_dir` | string | `logs` | Directory for execution logs, translation metrics, Persian NLP audit logs, and LLM response backups. |
| `log_retention_days` | integer | `7` | Days to keep execution logs, metrics, and response archives before pruning. |
| `genre` | string | `auto` | Genre taxonomy preset (`auto`, `fantasy`, `scifi`, `romance`, `horror`, `general`). |
| `keep_raw_artifacts` | boolean | `false` | When true, preserves raw OCR running headers/footers without stripping. |
| `min_chapter_bytes` | integer | `512` | Minimum byte size for an isolated chapter before automatic consolidation. |
| `hf_mirror_endpoint` | string | `https://hf-mirror.com` | Hugging Face mirror endpoint for downloading model weights in restricted regions. |
| `extract_images` | boolean | `true` | When true, automatically extracts illustrations into `output/<Book>/images` and embeds markdown signs. |

### 2. LLM & Provider Settings (`llm`)

| Setting | Type | Default | Description |
|---|---|---|---|
| `base_url` | string | `https://api.avalai.ir/v1` | Base URL for OpenAI-compatible endpoint. |
| `api_key` | string | `""` | Bearer authorization token. |
| `model` | string | `qwen3.8-flash` | LLM model identifier. |
| `temperature` | float | `1.0` | Sampling temperature (range: `0.0` - `2.0`). |
| `top_p` | float | `0.95` | Nucleus sampling probability (range: `0.0` - `1.0`). |
| `max_tokens` | integer | `16384` | Maximum completion tokens per request. |
| `thinking` | boolean | `true` | Enables reasoning/thinking mode for supporting models (e.g. Qwen, GLM). |
| `reasoning_effort` | string | `medium` | Reasoning depth: `low`, `medium`, or `high`. |
| `timeout` | integer | `300` | HTTP request timeout in seconds. |
| `stream_response` | boolean | `true` | Enables real-time streaming of translation tokens. |

### 3. Proxy Configuration (`proxy`)

| Setting | Type | Default | Description |
|---|---|---|---|
| `enabled` | boolean | `false` | When true, routes all outbound LLM, metadata, and API calls through the configured proxy. |
| `type` | string | `socks5` | Proxy protocol (`socks5`, `socks`, `http`, `https`). |
| `host` | string | `127.0.0.1` | Proxy server hostname or IP address. |
| `port` | integer | `10808` | Proxy port number (`1` - `65535`). |

### 4. NLP & Entity Extraction (`nlp`)

| Setting | Type | Default | Description |
|---|---|---|---|
| `refine_metadata` | boolean | `true` | Cleans, verifies, and extracts bibliographic metadata (title, author, genre, synopsis, keywords) via LLM. |
| `persian_nlp` | boolean | `true` | Enables Persian computational copyediting (Shekar normalizer, half-spaces, guillemets, punctuation). |
| `fast_mode` | boolean | `false` | Filters non-dialogue blocks prior to entity extraction to conserve CPU memory. |
| `gliner.enabled` | boolean | `true` | When true, extracts entities using local GLiNER zero-shot model. Replaces legacy `skip_gliner`. |
| `gliner.model` | string | `urchade/gliner_medium-v2.1` | Local path or Hugging Face model identifier. Replaces legacy `default_model`. |
| `gliner.batch_size` | integer | `16` | Text chunks processed concurrently during GLiNER CPU inference. |
| `gliner.chunk_size_words` | integer | `280` | Window size in words per entity extraction chunk. |
| `gliner.chunk_overlap_words` | integer | `20` | Overlap word count between consecutive extraction chunks. |
| `gliner.min_entity_frequency` | integer | `2` | Minimum occurrences required to include an entity in the glossary. |
| `gliner.high_confidence_threshold` | float | `0.85` | Confidence threshold for automatically accepting entity detections. |
| `gliner.fuzzy_similarity_threshold` | float | `0.88` | Similarity threshold for entity clustering and alias matching. |
| `gliner.max_levenshtein_distance` | integer | `2` | Maximum character edit distance for name variation merging. |

### 5. Translation (`translation`)

| Setting | Type | Default | Description |
|---|---|---|---|
| `target_language` | string | `Persian` | Target language for manuscript translation. |
| `batch_size` | integer | `1` | Number of concurrent chapter translation tasks. |

### 6. Typography & Word Book Compilation (`typography`)

| Setting | Type | Default | Description |
|---|---|---|---|
| `compile_docx` | boolean | `true` | Compiles translated Markdown chapters into a styled `.docx` book and PDF. |
| `eastern_font` | string | `B Nazanin` | Font family name or TTF file in `fonts/` for RTL scripts. |
| `western_font` | string | `Times New Roman` | Font family name or TTF file in `fonts/` for LTR scripts. |
| `paragraph_indent` | string | `0.4cm` | First-line paragraph indentation applied to body prose. |
| `line_spacing` | string | `1.35x` | Interline spacing multiplier for body text. |
| `body_font_size` | string | `11` | Font size in points for main body paragraphs. |
| `heading1_pagebreak` | boolean | `true` | Inserts a page break before each top-level chapter heading (`#`). |
| `margin_cm` | float | `2.5` | Document page margins in centimeters. |

### 7. Prompts (`prompts`)

The `prompts` object contains system prompt templates for chapter translation, glossary translation, and metadata refinement. Prompts support dynamic placeholders (`{target_language}`, `{user_style_rules}`, `{graph}`, `{metadata}`) as well as literal escape sequences like `\n` and `\t`.

---

## Semantic Type Validation & Safety

Tome enforces strict validation via `TomeConfig.validate()` upon initialization and loading:
- **Port Ranges**: Proxy port must be within `1` - `65535`.
- **Proxy Types**: Must be one of `socks5`, `socks`, `http`, `https`.
- **Sampling Bounds**: Temperature must be in `0.0` - `2.0`; top-p must be in `0.0` - `1.0`.
- **Token Ceilings**: Max tokens and timeouts must be positive integers.
- **Reasoning Effort**: Must be `low`, `medium`, or `high`.
- **Backward Compatibility**: Flat legacy configurations are automatically parsed and migrated to the modular structure.
