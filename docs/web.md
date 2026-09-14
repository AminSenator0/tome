# Tome Web Platform Documentation

## Overview
The Tome Web Platform is a production-ready, responsive, aesthetic web application and unified REST API designed for literary translation, zero-shot entity extraction, and manuscript compilation. It provides complete parity with the `tome` CLI and TUI harnesses, allowing users to process manuscripts on mobile, tablet, and desktop devices without requiring terminal access.

## Architecture & Communication Model

### How WebUI Runs the Backend
A common question is whether the WebUI shells out to CLI commands or calls Python backend APIs directly:
- **Direct Engine API**: The WebUI communicates with FastAPI backend endpoints (`/api/*`) via standard JSON and multipart payloads.
- **Unified Engine Execution**: When a pipeline run is triggered (`/api/pipeline/run`), the backend executes the exact same underlying pipeline function (`tome.core.pipeline.run_pipeline`) and translator (`tome.core.translator.translate_book`) that power the `tome run` CLI command.
- **Asynchronous Thread Worker**: Pipeline jobs run within background worker threads with an event observer that streams real-time status, stage transitions, and chapter completion metrics to the client via Server-Sent Events (SSE at `/api/pipeline/events/{task_id}`).
- **Auto-Compilation**: When automatic translation is enabled, the pipeline completes by compiling styled Word (`.docx`) and print-ready PDF volumes just like `tome run --translate`.

### Tech Stack
- **Backend Runtime**: FastAPI + Python 3.11 with Uvicorn ASGI server.
- **Frontend Stack**: React 19 + TypeScript + Vite + Tailwind CSS styled with flat iOS-inspired design system.
- **Engine Capabilities**: PyMuPDF, GLiNER, Shekar NLP, AvalAI/OpenAI API streaming, LibreOffice compilation.
- **Authentication Database**: Embedded SQLite database located in `.tome/web_users.db` with salted PBKDF2 SHA-256 password hashing.
- **Security**:
  - Global right-click context menu prevention.
  - Strict IP-based brute-force protection (max 5 failed attempts per 5 minutes before temporary lockout).
  - Secure HTTP-only session cookies and Bearer tokens.
  - Security headers: `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`.

## Getting Started

### Single-Command Launch
Start the platform locally or on a remote VPS:
```bash
# Default binding: 0.0.0.0:8000
tome web

# Custom host and port
tome web --host 0.0.0.0 --port 8080
```

### Pre-Configured Administrator Accounts
Default seeded accounts in `.tome/web_users.db`:
- `aren` : `0009`
- `mobina` : `1383`
- `khorshid` : `1382`

## Features & Navigation

### 1. Library & Download Center (`/bookshelf`)
- Displays all processed books from the `output/` directory.
- Quantitative metrics: total books, translated chapters, tokens consumed, and estimated cost in Toman.
- Responsive search bar strictly aligned to grid columns.
- Direct artifact downloads:
  - `.docx` styled Word manuscript
  - `.pdf` compiled volume
  - `.zip` archive of extracted illustrations
  - `metadata.json` bibliographic metadata
  - `metrics.json` execution performance & cost metrics
  - Source manuscript (`original/`)

### 2. Manuscript Studio (`/books/{title}`)
- **Overview & Volume Metadata**:
  - Top row: Narrative abstract synopsis and keywords alongside Volume Metadata.
  - Bottom row: Full-width Chapter Index with chapter selection, word counts, and batch translation triggers.
  - Height-matched action buttons (`Select All`, `Translate Selected`).
- **Chapter Reader**: Bilingual source vs Persian translation with full HTML formatting support (`<u>`, `<i>`, `<b>`, `<p>`).
- **Entity Glossary**:
  - `Preview` mode: Tabular visualization of character, location, and concept mappings.
  - `Raw Data` mode: Preformatted Markdown data block with consistent code iconography (`<Code />`).
- **Character Relationship Graph**: Visualized character co-occurrence and scene presence network, with both interactive graph and raw data modes.
- **Illustration Lightbox**: Lazy-loaded thumbnails with full-screen lightbox modal for single illustration preview and download.
- **Compilation**: One-click regeneration of `.docx` and `.pdf` files.

### 3. Pipeline Studio (`/pipeline`)
- Full manuscript ingestion for `.pdf`, `.epub`, `.mobi`, `.md`, and `.txt`.
- Real-time animated progress stepper tracking pipeline phases:
  - Conversion ➔ Extraction ➔ Genre Detection ➔ Metadata Refinement ➔ Chapter Segmentation ➔ Translation ➔ Document Compilation.

### 4. Standalone Tool Lab (`/tools`)
Every internal module can be executed standalone:
- **Genre Detector**: Keyword and contextual classification.
- **Image Extractor**: Extracts illustrations with resolution and page numbers using PyMuPDF.
- **Metadata Refiner**: Bibliographic analysis with vision and LLM refinement.
- **Manuscript Converter**: Converts PDF/EPUB/MOBI into clean Markdown.
- **Chapter Segmenter**: Splits raw text into structured chapters.
- **Entity Extractor**: Zero-shot NER extraction into Characters, Locations, Organizations, and Artifacts.
- **Character Graph Builder**: Synthesizes entity co-occurrence into relationship Markdown.
- **Single Translator**: Translates custom text or single chapters with style and glossary adherence.
- **Persian NLP Copyeditor**: Normalizes half-spaces (ZWNJ), prefixes, suffixes, diacritics, and punctuation.
- **Word & PDF Compiler**: Assembles Markdown chapters into formatted `.docx` and `.pdf` files.

### 5. Prompt Studio (`/prompts`)
- Responsive two-tier layout separating title and controls.
- Fluid sliding physics switch between `Preview` and `Edit Raw`.
- Live Markdown rendering with highlighted dynamic variable tokens (displayed cleanly without curly braces).
- Intelligent change tracking: `Save Prompts` button is disabled until actual edits are made in `Edit Raw` mode.
- Full-width touch-friendly actions on mobile.

### 6. System Configuration (`/settings`)
- Modular settings editor covering `general`, `llm`, `proxy`, `nlp`, `translation`, and `typography`.
- Automatic system theme detection (prefers dark/light matching user device on first visit) with persistent local storage.
