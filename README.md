<div align="center">

# Tome

[![Python](https://img.shields.io/badge/Python-3.11+-18181b?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-18181b?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-18181b?style=flat-square&logo=pytorch&logoColor=white)](https://pytorch.org)
[![Textual](https://img.shields.io/badge/TUI-Textual-18181b?style=flat-square&logo=gnometerminal&logoColor=white)](https://textual.textualize.io)
[![OfficeCLI](https://img.shields.io/badge/Engine-OfficeCLI-18181b?style=flat-square&logo=microsoftword&logoColor=white)](https://github.com/iOfficeAI/OfficeCLI)
[![License](https://img.shields.io/badge/License-MIT-18181b?style=flat-square)](LICENSE)

*Autonomous multilingual manuscript processing, localization, and book production harness.*

</div>

---

Tome turns raw books into polished, published volumes. Feed it a PDF, EPUB, or text file, and it handles everything from chapter segmentation and character tracking to translation, linguistic copyediting, and Word (.docx) book compilation.

Whether translating fantasy epics, historical sagas, or non-fiction across Right-to-Left (RTL) and Left-to-Right (LTR) languages, Tome keeps character voices consistent, preserves worldbuilding terminology, and outputs a formatted book ready to read or print.

---

## Documentation

Comprehensive guides, specifications, and architecture references are available in the [`docs/`](docs/README.md) directory:

| Document | Focus Area |
|---|---|
| [System Architecture](docs/architecture.md) | High-level system design, module clusters, and pipeline flow. |
| [Project Structure](docs/structure.md) | Repository directory tree, file organization, and component roles. |
| [Configuration Reference](docs/config.md) | Full guide to `tome.json` settings, defaults, and override options. |
| [Models & LLM Engine](docs/models.md) | Frontier model catalog, AvalAI integration, request correlation, prompt caching, and error handling. |
| [GLiNER Setup & Caching](docs/gliner.md) | Local zero-shot entity extraction setup, offline weights, and memory management. |
| [OfficeCLI Compilation Guide](docs/officecli.md) | Document compilation setup, binary management, and headless servers. |
| [macOS Setup Guide](docs/macos.md) | macOS installation, Apple Silicon MPS acceleration, LibreOffice, and launchd services. |
| [REST API Reference](docs/routes.md) | FastAPI endpoints, request and response schemas, and curl examples. |
| [Prompt Engineering & Variables](docs/prompts.md) | 3-layer literary prompts, supported variables, newline/tab formatting, and strict validation. |
| [Typography & Compilation](docs/typography.md) | Word (.docx) manuscript assembly, font resolution, and styling standards. |
| [Core Features](docs/features.md) | Multilingual metadata detection, character relationship modeling, and computational copyediting. |
| [Web Platform & Studio](docs/web.md) | Full responsive web application, authentication, standalone tools lab, and SSE pipeline streaming. |
| [VPS Deployment Checklist](docs/deployment.md) | Production VPS deployment, systemd configuration, network proxies, and font assets. |
| [Developer Guide](docs/development.md) | Development setup, test suite execution (pytest), code formatting (black), linting (ruff), and type checking (pyrefly). |

---

## Quick Start

### Installation

```bash
git clone https://github.com/your-username/tome.git
cd tome

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate
uv pip install -e .
```

### Interactive Studio (TUI)

Launch the full-screen interactive terminal interface:

```bash
tome
# or
python -m tome.cli.main
```

### Web Platform & Studio

Launch the responsive web application and unified REST API with a single command:

```bash
tome web
# or custom host/port
tome web --host 0.0.0.0 --port 8080
```

### REST API Server

Start the headless FastAPI service:

```bash
uvicorn tome.api.routes:app --host 0.0.0.0 --port 8000 --reload
```

---

## Command Line Interface

### Run Full End-to-End Pipeline
Processes document ingestion, cleaning, chapter segmentation, entity extraction, character dossier compilation, translation, copyediting, and Word manuscript assembly in one command:

```bash
tome run book.pdf -g fantasy -lm qwen3.8-flash
```

### Universal Document Conversion (`tome convert`)
Converts EPUB or PDF directly into standardized Markdown:

```bash
tome convert book.epub -o output/book.md
tome convert book.pdf -o output/book.md
```

### Chapter Segmentation (`tome chapterize`)
Splits a raw Markdown manuscript into ordered chapter files:

```bash
tome chapterize output/book.md -o output/Book_Title/chapters
```

### Bibliographic Metadata & Refinement (`tome metadata`)
Extracts, cleans, and refines manuscript metadata (title, authors, genre, synopsis, keywords):

```bash
# Extract and refine metadata using LLM
tome metadata book.pdf -rm

# Heuristic extraction without LLM
tome metadata book.epub --no-refine -o metadata.json
```

### Illustration & Image Extraction (`tome images`)
Extracts, orders, and embeds illustrations from any PDF or EPUB manuscript into `output/<Book>/images`:

```bash
# Extract illustrations to default book folder
tome images book.pdf

# Extract illustrations to custom directory
tome images book.epub -o output/CustomDir
```

### Entity Extraction (`tome extract`)
Extracts characters, locations, and lore using local GLiNER zero-shot models:

```bash
tome extract output/Book_Title/chapters -g fantasy -o output/Book_Title/glossary.md
```

### Character Relationship Dossier (`tome graph`)
Builds a character intelligence dossier and interaction graph for LLM context:

```bash
tome graph output/Book_Title/chapters -g output/Book_Title/glossary.md -o output/Book_Title/graph.md
```

### Sequential Translation (`tome translate`)
Translates chapters sequentially with relationship context and glossary enforcement:

```bash
# Translate specific chapter
tome translate output/Book_Title/chapters -c 5

# Translate multiple chapters or ranges
tome translate output/Book_Title/chapters -c "5,6"
tome translate output/Book_Title/chapters -c "5 to 10"

# Translate all chapters (default when -c is omitted)
tome translate output/Book_Title/chapters
```

### Standalone Word Manuscript Compilation (`tome docx`)
Compiles Markdown chapters into a unified Word book with headers, footers, and margins:

```bash
# Compile with Eastern font
tome docx output/Book_Title/translation -o output/Book_Title/Book.docx -ef B-Nazanin.ttf

# Compile English manuscript with Western font
tome docx output/Book_Title/chapters -o output/Book_Title/Manuscript.docx -l English -wf Times.ttf
```

### Computational Copyediting (`tome edit`)
Applies linguistic normalization, zero-width non-joiners, quote conversions, and cleanup:

```bash
tome edit output/Book_Title/translation/01_chapter_1.md
```

---

## Output Folder Hierarchy

When processing a book manuscript, Tome organizes all generated artifacts in a collision-free structure:

```text
output/<Book_Title>/
├── original/              # Untouched source manuscript and raw extracted markdown
│   ├── <Book_Title>.pdf   # Original source file (safeguarded against overwrite)
│   └── book.md            # Cleaned, consolidated Markdown manuscript
├── chapters/              # Segmented source chapters (00_front_matter.md, 01_chapter_1.md, ...)
├── images/                # Extracted and indexed illustrations (image_01_p003.png, ...)
├── glossary.md            # Clustered entity dictionary and canonical translations
├── graph.md               # Character dossiers and social interaction relationship graph
├── translation/           # Translated chapter files and consolidated translation.md
├── <Book_Title>.docx      # Compiled, typographically styled Word publication
├── <Book_Title>.pdf       # Compiled publication PDF (converted from Word edition)
├── metadata.json          # Machine-readable bibliographic analysis record
└── metrics.json           # Token usage, API costs (IRT/USD), execution timings, and NLP stats
```

---

## Global Flags Reference

| Flag | Long Flag | Description |
|---|---|---|
| `-o` | `--output` | Destination directory or file path for generated artifacts |
| `-g` | `--genre` | Genre preset (`auto`, `fantasy`, `scifi`, `romance`, `horror`, `general`) |
| `-m` | `--model` | GLiNER model identifier or local model path |
| `-lm` | `--llm-model` | LLM translation model override (e.g. `qwen3.8-flash`, `gemini-flash-latest`, `glm-5.3-flash`) |
| `-b` | `--batch-size` | Batch size for CPU inference (default: 16) |
| `-n` | `--no-gliner` | Skip local NER extraction; use LLM inline extraction |
| `-np` | `--no-persian-nlp` | Disable Persian linguistic copyediting post-processor |
| `-f` | `--fast` | Fast mode with dialogue filtering for low-spec hosts |
| `-k` | `--keep-raw` | Preserve raw layout artifacts, page numbers, and headers |
| `-rm` | `--refine-metadata` | Refine bibliographic metadata via LLM and computer vision |
| `-ni` | `--no-images` | Disable illustration and figure extraction |
| `-l` | `--lang` | Target language override (e.g. `Persian`, `Spanish`, `German`, `French`) |
| `-s` | `--style` | Custom authorial or editorial tone guidelines (supports `\n` and `\t`) |
| `-c` | `--chapters` | Specific chapters to process (e.g. `5`, `'5 and 6'`, `'5 to 10'`, `'1,3,5-7'`). Default: all |
| | `--font` | Font override (accepts font family, TTF filename, or font path) |
| `-ef` | `--eastern-font` | Eastern font override for RTL text (e.g. `B-Nazanin.ttf`, `Vazirmatn.ttf`) |
| `-wf` | `--western-font` | Western font override for Latin text (e.g. `Times.ttf`, `Times New Roman`) |

---

## Configuration

All pipeline settings, LLM parameters, typography options, and prompt templates can be configured in `tome.json`. For detailed descriptions of each option, see the [Configuration Reference](docs/config.md).

---

## License

MIT License. See [LICENSE](LICENSE) for details.
