# REST API Reference

Tome provides a complete REST API built on FastAPI for automated processing, webhook integration, and remote pipeline execution.

- **Base URL**: `http://localhost:8000`
- **Swagger Documentation**: `http://localhost:8000/docs`
- **OpenAPI Specification**: `http://localhost:8000/openapi.json`

---

## Health Check
`GET /api/v1/health`

Verifies server status.

```bash
curl http://localhost:8000/api/v1/health
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "service": "tome"
}
```

---

## Full Pipeline Execution
`POST /api/v1/process`

Executes the entire workflow from raw document conversion to final Word book compilation.

**Request Body:**
```json
{
  "pdf_path": "path/to/manuscript.pdf",
  "output_dir": "output",
  "genre": "fantasy",
  "skip_gliner": false,
  "model": "urchade/gliner_medium-v2.1",
  "batch_size": 16,
  "fast_mode": false,
  "keep_raw": false,
  "persian_nlp": true,
  "llm_model": "qwen3.8-flash",
  "translate": true,
  "target_language": "Persian",
  "chapters": "5 to 10"
}
```

```bash
curl -X POST http://localhost:8000/api/v1/process \
  -H "Content-Type: application/json" \
  -d '{
    "pdf_path": "books/NeverAfter.pdf",
    "output_dir": "output",
    "llm_model": "qwen3.8-flash",
    "translate": true,
    "chapters": "5 to 10"
  }'
```

**Response (200 OK):**
```json
{
  "book_title": "The Ballad of Never After",
  "full_markdown_path": "output/The Ballad of Never After/original/book.md",
  "chapter_paths": [
    "output/The Ballad of Never After/chapters/01_chapter_1.md",
    "output/The Ballad of Never After/chapters/02_chapter_2.md"
  ],
  "glossary_path": "output/The Ballad of Never After/glossary.md",
  "total_pages": 340,
  "total_chapters": 28,
  "entity_count": 86,
  "timings": {
    "conversion": 4.12,
    "chapterization": 0.18,
    "extraction": 18.4,
    "total": 22.7
  }
}
```

---

## Character Relationship Graph & Dossier
`POST /api/v1/graph`

Analyzes chapter co-occurrences and outputs an executive character intelligence dossier (`graph.md`).

**Request Body:**
```json
{
  "chapters_dir": "output/Book/chapters",
  "glossary_path": "output/Book/glossary.md",
  "output_path": "output/Book/graph.md",
  "book_title": "The Ballad of Never After",
  "top_n": 15
}
```

```bash
curl -X POST http://localhost:8000/api/v1/graph \
  -H "Content-Type: application/json" \
  -d '{
    "chapters_dir": "output/NeverAfter/chapters",
    "book_title": "The Ballad of Never After"
  }'
```

**Response (200 OK):**
```json
{
  "graph_path": "output/NeverAfter/graph.md",
  "top_characters": ["Jacks", "Evangeline", "Apollo", "Castor"]
}
```

---

## Chapter Translation
`POST /api/v1/translate`

Translates chapters sequentially, injecting relationship graph context and enforcing glossary consistency.

**Request Body:**
```json
{
  "book_dir": "output/NeverAfter",
  "target_language": "Persian",
  "user_style_rules": "Maintain fairy-tale prose.",
  "chapters": "5 to 10",
  "persian_nlp": true,
  "llm_model": "gemini-flash-latest"
}
```

```bash
# Translate specific chapter range (e.g. chapters 5 through 10)
curl -X POST http://localhost:8000/api/v1/translate \
  -H "Content-Type: application/json" \
  -d '{
    "book_dir": "output/NeverAfter",
    "chapters": "5 to 10",
    "llm_model": "gemini-flash-latest"
  }'

# Translate all chapters (omit chapters parameter)
curl -X POST http://localhost:8000/api/v1/translate \
  -H "Content-Type: application/json" \
  -d '{
    "book_dir": "output/NeverAfter",
    "llm_model": "gemini-flash-latest"
  }'
```

---

## Word Manuscript Compilation
`POST /api/v1/compile-docx`

Compiles Markdown chapters into a styled `.docx` book with running headers, footers, and typography.

**Request Body:**
```json
{
  "input_path": "output/NeverAfter/translation",
  "output_docx": "output/NeverAfter/Manuscript.docx",
  "title": "The Ballad of Never After",
  "target_language": "Persian",
  "eastern_font": "B-Nazanin.ttf",
  "western_font": "Times.ttf"
}
```

```bash
curl -X POST http://localhost:8000/api/v1/compile-docx \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "output/NeverAfter/translation",
    "output_docx": "output/NeverAfter/Manuscript.docx",
    "title": "The Ballad of Never After"
  }'
```

**Response (200 OK):**
```json
{
  "output_docx": "output/NeverAfter/Manuscript.docx",
  "output_pdf": "output/NeverAfter/Manuscript.pdf",
  "status": "success"
}
```

> [!NOTE]
> When LibreOffice is available, the DOCX is automatically converted into a publication-ready PDF with preserved layout, font styling, and OpenXML document properties.


---

## Document Conversion
`POST /api/v1/convert`

Converts a PDF or EPUB document into Markdown.

```bash
curl -X POST http://localhost:8000/api/v1/convert \
  -H "Content-Type: application/json" \
  -d '{"pdf_path": "book.pdf", "output_dir": "output"}'
```

---

## Chapter Segmentation
`POST /api/v1/chapterize`

Splits a single Markdown manuscript into individual numbered chapter files.

```bash
curl -X POST http://localhost:8000/api/v1/chapterize \
  -H "Content-Type: application/json" \
  -d '{"markdown_path": "output/book.md", "output_dir": "output/chapters"}'
```

---

## Computational Copyediting
`POST /api/v1/copyedit`

Applies linguistic normalization to text or Markdown files.

```bash
curl -X POST http://localhost:8000/api/v1/copyedit \
  -H "Content-Type: application/json" \
  -d '{"text": "او ميرود و كتاب ها را ديد."}'
```

---

## Bibliographic Metadata Extraction & Refinement
`POST /api/v1/metadata`

Extracts, cleans, and refines manuscript metadata (title, author, publisher, ISBN, year, genre, synopsis, and keywords).

```bash
curl -X POST http://localhost:8000/api/v1/metadata \
  -H "Content-Type: application/json" \
  -d '{"input_file": "manuscript.pdf", "refine": true}'
```

**Response Schema:**
```json
{
  "title": "The Way of Kings",
  "authors": ["Brandon Sanderson"],
  "year": "2010",
  "publisher": "Tor Books",
  "isbn": "978-0765326355",
  "page_count": 1007,
  "word_count": 384000,
  "char_count": 2150000,
  "reading_time": "1280m",
  "genre": "fantasy",
  "synopsis": "On the shattered plains of Roshar, highprince Dalinar Kholin seeks to unite the fractured kingdoms while Kaladin must survive the brutal frontline bridge runs.",
  "keywords": ["epic fantasy", "roshar", "spren", "shardblade", "stormlight"]
}
```

---

## Illustration & Image Extraction
`POST /api/v1/images`

Extracts illustrations and images from a PDF or EPUB document, handling alpha masks, scanner tile stitching, repeated logo deduplication, and vector diagrams into `output/<Book>/images`.

```bash
curl -X POST http://localhost:8000/api/v1/images \
  -H "Content-Type: application/json" \
  -d '{"input_file": "manuscript.pdf", "output_dir": "output/MyBook"}'
```

**Response Schema:**
```json
{
  "image_count": 4,
  "images": [
    "image_01_p003.png",
    "image_02_p015.png",
    "image_03_p042.png",
    "image_04_p108.png"
  ],
  "images_dir": "output/MyBook/images"
}
```
