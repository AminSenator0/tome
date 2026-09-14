# Core Features & Intelligence Modules

This document details Tome's linguistic detection, character relationship modeling, and computational copyediting engines.

---

## 1. Multilingual Metadata Detection & LLM Refinement

Tome combines heuristic extraction with an LLM bibliographic copyediting engine to produce publication-grade metadata records:

### 1.1 Heuristic Extraction
- **Languages Supported**: English, Persian, Arabic, Spanish, French, German.
- **Attributes Detected**:
  - **Title**: Identifies title indicators (`Title:`, `عنوان:`, `نام کتاب:`, `Título:`, `Titre:`, `Titel:`) and Markdown H1 headers.
  - **Authors**: Parses CIP catalog blocks (`Names: Author, First, author`), Eastern markers (`نویسنده:`, `پدیدآورنده:`, `مؤلف:`, `اثر:`), and European markers (`Autor:`, `Auteur:`, `Verfasser:`).
  - **Publication Year**: Recognizes Gregorian years and Solar Hijri years (`۱۳۱۵`, `۱۴۰۲`) with automatic Eastern Arabic numeral conversion.
  - **Publisher**: Extracts publisher credits across multilingual imprints.
  - **ISBN**: Identifies 10-digit and 13-digit ISBN identifiers with digit normalization.

### 1.2 LLM Bibliographic Refinement & Normalization
- **Refinement Prompting**: Configured via `metadata_refinement_system_prompt` using the standardized `{metadata}` variable containing manuscript filename, heuristic JSON, front matter, and first chapter excerpt.
- **Data Sanitization**: Strips distributor tags (Z-Library, OceanofPDF, Libgen), OCR artifacts, role noise (e.g. "by", ", author"), and numeric debris.
- **Synopsis & Keywords**: Synthesizes a concise, high-density 2-3 sentence executive synopsis and extracts 5-8 thematic indexing keywords.
- **Zero Redundancy**: Suppresses raw responses when identical or empty, ensuring predictable and cost-effective operation.
- **Strict JSON Contract**: Type-checked JSON parser with resilient fallback to heuristic metadata if the model response is malformed or offline.
- **CLI & TUI Control**: Toggleable with `--refine-metadata` / `-rm` or `--no-refine-metadata`, configured in `tome.json`, and accessible in the TUI Settings & Pipeline tabs.
- **Document Injection**: Embedded into Word OpenXML properties (`docProps/core.xml` and `docProps/custom.xml`) and forwarded to compiled PDFs.

---

## 2. Character Relationship Graph & LLM Dossier

To ensure narrative continuity and accurate interpersonal register across large novels, Tome compiles chapter co-occurrences into a structured intelligence dossier (`graph.md`):

### Executive Character Dossier
- **Character Profiles**: Aggregates aliases, appearance frequencies, chapter spans, and dynamic narrative roles (e.g. *Protagonist*, *Central Anchor*, *Supporting Cast*).
- **Pairwise Dynamics**: Tracks co-occurrence frequencies, relationship strength ratings, and exact paragraph-level interaction snippets that capture dialogue tone and character tension.
- **Prompt Injection**: Injected dynamically into translation prompts via the `{graph}` placeholder, allowing LLMs to reference relationship history when choosing dialogue formality and honorifics.

---

## 3. Computational Linguistic Copyediting Engine

Tome includes an automated linguistic copyediting layer that operates directly on translated text:

- **Orthographic Normalization**: Automatically inserts zero-width non-joiners (`\u200c`) for prefixes, suffixes, and compound words in complex scripts.
- **Punctuation Formatting**: Replaces ASCII quotes with localized typographic quotation marks (e.g. guillemets `« »`), regional commas, and dialogue dashes.
- **Artifact Stripping**: Cleans extraneous emojis, accidental OCR artifacts, and inconsistent diacritics.
- **Pre-Editor Raw Backup**: Preserves raw LLM responses in `logs/llm/<Book>_<timestamp>_<id>.txt` prior to copyediting for auditing and comparison.
- **Word Correction Audit Log**: Tracks all normalized word transformations via sequence diffing and generates an ordered audit log at `logs/<Book>_persian_nlp_changes.log` (e.g. `می شود → میشود (x14)`), sorted by frequency and pruned according to configured retention days.
- **Execution Metrics**: Reports processed word count, modified word count, and normalized entity rates in real time.

---

## 4. Generalized Multi-Source Watermark & Scraper Stripping

Tome features an aggressive, generalized heuristic cleaner that detects and purges scanning, archive, and distributor watermarks without relying on fragile hardcoded domain lists:

- **Universal Protocol & URL Pruning**: Automatically detects and eliminates all raw and parenthetical URLs (`https://...`, `http://...`, `www....`).
- **Generalized Domain TLD Matching**: Strips web domains ending in all common top-level domains (`.com`, `.org`, `.net`, `.ir`, `.co`, `.io`, `.is`, `.ai`, `.me`, `.gg`, `.site`, `.xyz`, `.online`, `.tech`, `.top`, etc.).
- **Social & Channel Handles**: Strips `@channel` and `@username` mentions across lines and within paragraphs, along with shortlinks (`t.me/...`, `telegram.me/...`, etc.).
- **Multilingual Download Markers**: Cleans download headers and footers across Persian (e.g. `دانلود شده از`, `کانال رسمی`, `عضویت در کانال`, `مرجع دانلود`, `ارائه‌شده در`, `اسکن اختصاصی`, `ترجمه اختصاصی`), English (`downloaded from`, `uploaded by`, `scanned by`, `retail epub`), French, German, Spanish, and Russian.
- **Inline Watermark Cleansing**: Removes embedded parenthetical and bracketed links and handles within narrative prose while strictly preserving genuine character dialogue.

---

## 5. OpenXML DOCX Metadata Injection

Tome automatically embeds rich bibliographic and manuscript analysis data directly into the compiled Word (`.docx`) file's standard OpenXML properties:

- **Core Properties (`docProps/core.xml`)**: Maps book title, author(s), genre, keywords, and description synopsis directly into document metadata.
- **Custom Properties (`docProps/custom.xml`)**: Injects exact manuscript metrics including `PageCount`, `WordCount`, `CharacterCount`, `ReadingTime`, `Year`, `Publisher`, and `ISBN`.

---

## 6. Automated Headless PDF Compilation

Following Word compilation, Tome automatically converts the generated DOCX manuscript into a PDF document via headless LibreOffice:

- **Automatic Pipeline Execution**: Runs directly after DOCX styling without requiring user intervention.
- **Preserved Styling**: Retains page numbering, headers, margins, and bidirectional typography.

---

## 7. Granular Metrics & Balance Tracking

Tome monitors API utilization, execution timings, and cost metrics:

- **Toman Balance Auditing**: Tracks initial, final, and consumed wallet credit.
- **Minimal Metric Schema**: Exports clean, deduplicated statistics to `logs/<Book>_metrics.json`.
- **Per-Chapter Telemetry**: Logs token usage (prompt, completion, reasoning) and duration for every translated section.

---

## 8. Enterprise Structured Logging (Google Cloud Standard)

All logs associated with a manuscript are strictly prefixed with `<Book>_` for effortless filtering and retention auditing:

- **Human-Readable Logs (`logs/<Book>_execution.log`)**: Standard ISO 8601 UTC timestamps, log levels, component tags, and contextual chapter milestones.
- **Google Cloud JSON Lines (`logs/<Book>_execution.jsonl`)**: Universal cloud-native structured format conforming to Google Cloud Logging specification (`time`, `severity`, `logging.googleapis.com/sourceLocation`, `book`, `message`).
- **Word Transformation Logs (`logs/<Book>_persian_nlp_changes.log`)**: Full audit record of zero-width non-joiner insertions, typo corrections, and orthographical cleanups.
- **Raw LLM Audit Snapshots (`logs/llm/<Book>_<timestamp>_<id>.txt`)**: Pre-copyedited raw LLM inference responses preserved for audit trails.

---

## 9. Intelligent Illustration & Image Extraction

Tome automatically inspects and extracts genuine illustrations from PDF and EPUB manuscripts into `output/<Book>/images`, seamlessly resolving formatting complexities:

- **Alpha Transparency & Soft Masks (`smask`)**: Combines PDF soft masks (`smask`) with RGB pixel streams via PIL to avoid black background artifacts on transparent PNGs.
- **Scanner Tile Clip Stitching**: Detects multi-strip scanner artifacts (adjacent vertical or horizontal image slices) and renders them as unified whole illustrations via viewport rasterization.
- **Repeated Logo & Header Deduplication**: Identifies recurring publisher logos, running headers, and decorative page flourishes by frequency tracking and content hashing, omitting them from the illustrations folder.
- **Vector Graphics Detection**: Renders complex vector path illustrations and diagrams into high-resolution images when raster XObjects are not present.
- **Preserved Placement Signatures**: Deterministically names images (`image_01_p003.png`, `image_02_p015.png`) and embeds contextual Markdown markers (`![Illustration](images/image_01_p003.png)`) directly into chapter prose and compiled Word documents.
- **Zero-Artifact Guarantee**: If no genuine illustrations exist, the `images` directory is omitted entirely.

---

## 10. Specialized Fantasy Localization Engine

Tome includes dedicated fantasy translation rules that replace rigid word-for-word translation with immersive worldbuilding and literary fluency:

- **Dual-Voice Engine**: Automatically bifurcates narrative exposition (`نثر ادبی، فخیم و شیوا`) from character dialogue (`محاوره‌ای زنده، روزمره و شکسته`), ensuring reading pleasure without losing character authenticity.
- **Creative Morphological Compounding**: Replaces stiff calques with evocative Persian affixes (`-افزار`, `-آور`, `-زاد`, `-ساز`, `-ستان`, `-بان`, `-پناه`) for unlisted monsters, magic ranks, and spells.
- **Dynamic Action Pacing**: Tightens sentence length and utilizes explosive kinetic verbs in battle sequences.
- **Worldbuilding Consistency**: Enforces magic rules as immutable physics and replaces earthly real-world idioms with authentic in-universe mythological oaths.
- **Automated Genre Routing**: Automatically appends the specialized fantasy guidelines when a book's genre is resolved or configured as `fantasy`.


