# Developer & Contributor Guide

This guide outlines standards, testing conventions, and tooling for contributing to Tome.

---

## 1. Environment Setup

```bash
git clone https://github.com/your-org/tome.git
cd tome
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## 2. Code Quality Standards

Tome enforces strict code quality through automated formatting, linting, and type checking:

### 2.1 Code Formatting (`black`)
Code must conform to the `black` code style with a line length of 120 characters:
```bash
.venv/bin/black src/ tests/
```

### 2.2 Linting (`ruff`)
Run `ruff` to detect code smells, unused imports, and formatting regressions:
```bash
.venv/bin/ruff check src/ tests/
```

### 2.3 Static Type Checking (`pyrefly`)
Run `pyrefly` to ensure complete type safety across all modules:
```bash
pyrefly check
```

---

## 3. Running the Test Suite

Tome includes comprehensive unit and integration tests under `tests/`:

```bash
# Run full test suite
.venv/bin/pytest tests/ -v

# Run specific test file
.venv/bin/pytest tests/test_translator.py -v

# Run with keyword filter
.venv/bin/pytest tests/ -k "test_prompt" -v
```

---

## 4. Architectural Conventions

- **Modular Configuration**: Settings are organized into dedicated blocks (`llm`, `proxy`, `typography`, `nlp`, `general`) in `tome.json`.
- **Pure Logging**: Application logs are stored under `logs/`, web server logs under `logs/web/` (`access.log`, `security.log`, `error.log`), and raw LLM responses under `logs/llm/`.
- **Stateless CLI & API**: Both CLI and Web interfaces invoke the same underlying engine methods in `tome.core`.

---

## 5. Web UI Development & Build

The Tome Web Platform frontend is located in `web/` and built with Bun, React 19, TypeScript, and Vite.

### 5.1 Installation & Dependencies
```bash
cd web
bun install
```

### 5.2 Running Local Development Server
```bash
# In web directory:
bun run dev

# In another terminal (or alone):
tome web --reload
```

### 5.3 Compiling Production Bundle
```bash
cd web
bun run build
```
The output is automatically generated in `src/tome/web/static/` and embedded into the Python package.

### 5.4 Running Frontend Unit Tests
```bash
cd web
bun test
```


1. **Surgical Edits**: Touch only the functions and classes required for the task. Preserve surrounding code, style, and comments.
2. **Prompt Template Validation**: When adding or updating prompt templates, always update `PROMPT_ALLOWED_VARIABLES` in `src/tome/config.py`. Never allow unverified `{placeholders}` into production templates.
3. **Model Family Registration**: When adding support for a new model family in `AVAILABLE_LLM_MODELS`, register its prefix in `detect_model_family()` within `src/tome/core/translator.py` and document its reasoning/thinking behavior in `docs/api_usage.md`.
4. **OfficeCLI Portability**: Always use `OfficeCLI` for DOCX compilation and ensure font paths fallback gracefully to system font families when local TTF files are not present.
