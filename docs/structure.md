# Project Structure

This document outlines the codebase layout, file organization, and modular boundaries of Tome.

```text
book/
├── bin/
│   └── officecli                  # OfficeCLI binary (downloaded automatically if missing)
├── docs/
│   ├── README.md                  # Documentation index
│   ├── architecture.md            # System architecture and pipeline flow
│   ├── config.md                  # Configuration options and defaults for tome.json
│   ├── deployment.md              # Production VPS deployment checklist
│   ├── development.md             # Contributor guidelines and testing setup
│   ├── features.md                # Metadata detection, character graphs, and copyediting
│   ├── gliner.md                  # GLiNER model setup, local caching, and memory optimization
│   ├── models.md                  # LLM models, AvalAI integration, caching, and error handling
│   ├── officecli.md               # OfficeCLI compilation setup and platform binary management
│   ├── prompts.md                 # Prompt framework and template variable validation
│   ├── routes.md                  # FastAPI REST endpoints reference
│   ├── structure.md               # Repository file tree and module index
│   └── typography.md              # Word compilation and typography standards
├── fonts/
│   ├── B-Nazanin.ttf              # Eastern serif book typeface (Persian/Arabic)
│   ├── Vazirmatn.ttf              # Eastern sans-serif typeface (Persian/Arabic)
│   └── Times.ttf                  # Western serif typeface (Latin)
├── src/
│   └── tome/
│       ├── __init__.py            # Package root and version definition
│       ├── api/
│       │   ├── __init__.py
│       │   └── routes.py          # FastAPI application routes and request/response models
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── main.py            # CLI argument parser and command dispatcher
│       │   └── tui.py             # Textual full-screen interactive terminal interface
│       ├── core/
│       │   ├── __init__.py
│       │   ├── docx.py            # OfficeCLI bridge for Word (.docx) book compilation & PDF conversion
│       │   ├── chapterizer.py     # Manuscript segmentation into numbered chapter files
│       │   ├── cleaner.py         # Removal of page headers, footers, and scanning artifacts
│       │   ├── converter.py       # PDF/EPUB to Markdown extraction router
│       │   ├── downloader.py      # Binary and asset auto-download utilities
│       │   ├── editor.py          # Computational linguistics copyediting layer
│       │   ├── extractor.py       # GLiNER zero-shot named entity recognition engine
│       │   ├── glossary.py        # Entity clustering, coreference, and Markdown tables
│       │   ├── graph.py           # Character relationship graph and LLM executive dossier
│       │   ├── logging.py         # Rotating logger setup and LLM response caching
│       │   ├── metadata.py        # Multilingual book metadata detector (EN, FA, ES, FR, DE, AR)
│       │   ├── pipeline.py        # End-to-end orchestration coordinator
│       │   └── translator.py      # LLM translation client, SSE streaming, and error handling
│       ├── config.py              # Configuration dataclass, model registries, and prompt validators
│       ├── exceptions.py          # Custom domain exception hierarchy
│       └── models.py              # Pydantic and dataclass models (Chapter, Entity, Metadata)
├── tests/
│   ├── test_api.py                # FastAPI endpoint integration tests
│   ├── test_docx.py               # Typography, OfficeCLI, and PDF conversion tests
│   ├── test_chapterizer.py        # Segmentation and fragment consolidation tests
│   ├── test_cleaner.py            # Artifact and running header removal tests
│   ├── test_cli.py                # Command-line argument parsing and flag tests
│   ├── test_converter.py          # Document conversion tests
│   ├── test_editor.py             # Linguistic copyediting unit tests
│   ├── test_epub_converter.py     # EPUB and image container conversion tests
│   ├── test_extractor.py          # Text chunking and entity extraction tests
│   ├── test_glossary.py           # Clustering, coreference, and ingestion tests
│   ├── test_graph.py              # Co-occurrence analysis and dossier tests
│   ├── test_logging.py            # Cache rotation and retention tests
│   ├── test_metadata.py           # Multilingual metadata parsing tests
│   ├── test_models.py             # Data model and genre taxonomy tests
│   ├── test_pipeline.py           # Full pipeline execution tests
│   └── test_translator.py         # LLM parameters, prompt validation, and error formatting tests
├── pyproject.toml                 # Build configuration, dependencies, and tooling settings
├── tome.json                      # Local runtime configuration overrides
└── README.md                      # Primary project overview and quickstart
```

---

## Component Responsibilities

### `src/tome/api`
Provides the FastAPI application layer. Endpoints wrap internal core services and return strongly-typed Pydantic responses. Designed for headless operations, background worker queues, and external integrations.

### `src/tome/cli`
Supplies dual user interfaces:
- An argument-driven CLI (`main.py`) with intuitive flags for shell scripting and automation.
- An interactive terminal user interface (`tui.py`) built on Textual with real-time log monitors, model selection dropdowns, and progress visualizers.

### `src/tome/core`
The primary computational engine. Houses layout analysis, linguistic cleanup, zero-shot entity extraction, glossary compilation, character graph intelligence, API client execution, copyediting normalization, and book compilation.

### `src/tome/config.py`
Defines `TomeConfig`, runtime defaults, font resolution logic, model family mappings, and validation checks for prompt template variables.
