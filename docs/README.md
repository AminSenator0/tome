# Tome Documentation

Welcome to the Tome technical documentation index.

## Guides and References

| Document | Description |
|---|---|
| [System Architecture](architecture.md) | High-level system design, module clusters, pipeline stages, and end-to-end data flow. |
| [Project Structure](structure.md) | Repository directory tree, file organization, and module responsibilities. |
| [Configuration Reference](config.md) | Comprehensive specification for all settings and options in `tome.json`. |
| [Models & LLM Engine](models.md) | Frontier models catalog, AvalAI integration, request correlation, prompt caching, and error handling. |
| [GLiNER Setup & Caching](gliner.md) | Zero-shot named entity recognition setup, model caching, and offline environments. |
| [OfficeCLI Compilation Guide](officecli.md) | Cross-platform OfficeCLI setup, binary verification, typography, and headless servers. |
| [macOS Setup Guide](macos.md) | Comprehensive setup, Apple Silicon MPS acceleration, LibreOffice, and launchd services for macOS. |
| [REST API Reference](routes.md) | FastAPI endpoint reference, request/response schemas, and curl examples. |
| [Prompt Engineering & Variables](prompts.md) | Prompt structure, supported template variables, newline/tab formatting, and strict validation. |
| [Typography & Compilation](typography.md) | Word (.docx) manuscript assembly, font resolution, and styling standards. |
| [Core Features](features.md) | Multilingual metadata detection, character relationship modeling, and computational copyediting. |
| [VPS Deployment Checklist](deployment.md) | Production VPS checklist, systemd service configuration, proxies, and font assets. |
| [Developer Guide](development.md) | Developer setup, testing standards with pytest, linting with ruff, formatting with black, and typing with pyrefly. |

---

## Core Design Principles
1. **Simplicity First**: Minimal, robust solutions without speculative abstractions.
2. **Deterministic and Resilient**: Explicit network timeouts, exponential retry backoffs, and safe parameter fallbacks.
3. **Publication-Grade Quality**: Standards-compliant book layout, running headers, dynamic pagination, and typography.
4. **Cache-Friendly LLM Flow**: Static prompt prefixes to maximize upstream prompt caching and minimize latency and cost.
