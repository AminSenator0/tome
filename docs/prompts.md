# Prompt Engineering & Template Validation

Tome implements a structured prompt engineering system designed to ensure high-fidelity literary translation, cultural localization, and narrative continuity.

---

## 1. Supported Prompt Template Variables

Tome supports dynamic variable substitution inside prompt templates. The supported placeholders depend on the prompt type:

### Chapter Translation Templates
- **`{target_language}`**: The designated target language (e.g. `Persian`, `Spanish`, `German`, `French`, `Arabic`).
- **`{user_style_rules}`**: Custom stylistic, tonal, or authorial guidelines (e.g. *"Maintain lyrical prose with gothic undertones"*).
- **`{graph}`**: Injected executive character and relationship dossier (`graph.md`), providing the model with character aliases, hierarchy, and interpersonal dialogue quotes.

### Specialized Fantasy Translation Guidelines
- **`fantasy_translation_guidelines`**: Specialized localization rules automatically appended to the main chapter translation prompt when the book genre is fantasy. Enforces the Dual-Voice engine (dignified literary narration vs living colloquial dialogue), creative Persian compounding (`-افزار`, `-آور`, `-زاد`, `-ساز`, `-ستان`), action velocity pacing, in-universe oaths, and lore consistency.

### Glossary Translation Templates
- **`glossary_translation_system_prompt`**: Translating canonical entity names and worldbuilding terminology tables.

### Metadata Refinement Templates
- **`{metadata}`**: Injected bibliographic manuscript intelligence containing source filename, extracted heuristic metadata JSON, raw front matter, and first chapter excerpt.

---

## 2. Escape Sequences & Multi-Line Formatting

Prompt templates and style rules fully support standard escape sequences for formatting:

- **Newlines (`\n`)**: Converted into actual line breaks. Use `\n\n` to establish distinct paragraph boundaries in prompts.
- **Tabs (`\t`)**: Converted into tab indents for lists, rubrics, or tabular prompt structures.
- **Carriage Returns (`\r\n`)**: Normalized into clean Unix newlines.

### Example in `tome.json`:
```json
{
  "user_style_rules": "1. Keep dialogue sharp and concise.\n2. Preserve melancholic atmosphere.\n\n3. Use archaic vocabulary for royal characters.",
  "prompts": {
    "chapter_translation_with_glossary_system_prompt": "You are a master literary translator.\n\nTranslate into {target_language}.\n\n### STYLE GUIDELINES\n{user_style_rules}\n\n### CHARACTER DOSSIER\n{graph}"
  }
}
```
Whether specified as escaped strings in JSON, passed via CLI arguments (`-s "Rule 1\nRule 2"`), or stored directly as multi-line strings, Tome normalizes them into proper whitespace before sending requests to the LLM.

---

## 3. Strict Variable Validation Against Typos

To prevent configuration errors and prompt corruption, Tome validates all prompt templates against a strict variable whitelist before initiating any LLM calls.

### Validation Rules
- Any single-bracket placeholder `{variable}` that is not in the whitelist raises an immediate `PromptValidationError`.
- Escaped brackets (e.g. `{{json}}` or double brackets) are ignored and permitted.
- If an invalid placeholder such as `{graphhh}`, `{target_languge}`, or `{custom_var}` is present, execution halts immediately with an informative message:

```
PromptValidationError: Invalid placeholder(s) {graphhh} found in chapter_translation_with_glossary_system_prompt. Allowed template variables are: {graph}, {target_language}, {user_style_rules}
```

Validation occurs:
1. When loading `tome.json` via `TomeConfig.load_config()`.
2. When instantiating `TomeConfig()`.
3. Before executing `translate_chapter()` or `translate_glossary()`.

---

## 4. First-Principles Prompt Architecture

Tome's default prompts are designed using a first-principles, outcome-first specification pattern focused on high signal-to-noise ratio, deterministic stop rules, and strict context isolation:

```
[System / Developer Message]
├── # Identity & Goal (Single-sentence functional role & objective)
├── # Contextual Inputs Specification
│   ├── <character_dossier> {graph} </character_dossier>
│   └── <style_guidelines> {user_style_rules} </style_guidelines>
├── # Core Translation & Copyediting Invariants
│   ├── 1. Book Integrity & Narrative Parity (strict 1:1 parity; no additions or omissions)
│   ├── 2. Watermark & Artifact Elimination (silently strip URLs, @channels, scan noise)
│   ├── 3. Terminology Conformance (strict adherence to glossary)
│   ├── 4. Syntactic & Idiomatic De-calquing (natural prose rhythm)
│   ├── 5. Orthography & Typographical Precision (locale punctuation & half-spaces)
│   ├── 6. Dialogue Calibration & Character Voice (register according to dossier)
│   └── 7. Structural Formatting Preservation (headers, italics, bold, breaks)
└── # Constraints & Stop Rules (Zero conversational preamble, 100% text coverage)

[User Message]
├── <glossary>...</glossary> (Pre-computed terminology; placed first for prompt caching)
└── <manuscript filename="...">...</manuscript> (Isolated source text)
```

---

## 5. Prompt Caching & Boundary Isolation

### Upstream Prompt Prefix Stability
Modern LLMs (Anthropic Claude, DeepSeek, Qwen, OpenAI) employ KV cache reuse on shared prompt prefixes. Tome maximizes cache hit rates by:
1. Keeping the system instructions, character dossier, and style guidelines static across all chapter translation calls.
2. Placing the shared bilingual `<glossary>` block before the chapter text in the user payload.
3. Placing the volatile, chapter-specific `<manuscript>` text at the very end of the payload.

### Context Boundary Isolation via XML Tags
Source manuscripts downloaded from web or channel distributors often contain dialogue, quotes, distributor watermarks (`https://`, `@channel`), or instructions that could confuse an LLM into following untrusted commands. Wrapping inputs in explicit XML-style tags (`<glossary>`, `<character_dossier>`, `<style_guidelines>`, `<manuscript filename="...">`) establishes impermeable semantic boundaries between compiler policy and raw manuscript data.

---

## 6. The 7 Core Invariant Editing Layers

1. **Book Integrity & Narrative Parity**: The output compiles into a publication edition. The model must preserve exact 1:1 narrative parity with the source text: no extraneous fabricated scenes, summaries, or translator notes, and zero omissions or condensation of canon text.
2. **Watermark & Artifact Elimination**: Silently identifies and discards distributor URLs (`http://`, `https://`, `www.`), channel handles (`@channel`), promotional stamps, and digitizing noise without translating or retaining them.
3. **Terminology Conformance**: Every entity defined in `<glossary>` must strictly use its assigned translation.
4. **De-Calquing & Syntax Restructuring**: Translates idioms and compound phrases into native literary expressions rather than rigid word-for-word calques; converts weak passives into active narrative verbs.
5. **Typographical & Orthographic Mechanics**: Enforces zero-width non-joiners (`\u200c`) for Persian verbal prefixes/suffixes, guillemets dialogue quotes (`« »`), Persian punctuation without leading whitespace, and locale-specific quote conventions for European targets.
6. **Dialogue & Relationship Voice**: Modulates character speech registers (formal, informal, intimate, defiant) according to interpersonal connections documented in `<character_dossier>`.
7. **Structural AST Preservation**: Preserves scene breaks, blockquotes, markdown headers, and emphasized thought sequences exactly as formatted in the original book.

---

## 7. Concrete Example: What the Model Sees

Below is a complete, real-world example of the exact prompt payload delivered to the LLM during chapter translation.

### System Message
```markdown
# Identity & Goal
You are an end-to-end literary translation and prose copyediting engine for publication-grade books. Translate English narrative prose into Persian with absolute semantic fidelity, vivid prose rhythm, and flawless orthography.

# Contextual Inputs
- <character_dossier>: Character relationship graph, archetypes, and narrative dynamics.
- <style_guidelines>: Project-specific authorial and tonal constraints.
- <glossary>: Authoritative bilingual term mappings.
- <manuscript>: The source chapter to translate.

<character_dossier>
# Executive Character & Relationship Dossier: Once Upon a Broken Heart

## Character Index & Core Personas
- **Evangeline Fox** (Curiosity, naive optimism; protagonist)
- **Jacks** (Prince of Hearts; immortal Fate; sardonic, predatory, morally gray)

## Key Narrative Dynamics & Dialogue Directives
- **Evangeline Fox & Jacks**: High emotional tension. Jacks treats Evangeline with cruel, mocking intimacy. Evangeline is guarded and desperate.
</character_dossier>

<style_guidelines>
Maintain lyrical gothic atmosphere with lush prose rhythm.
</style_guidelines>

# Core Translation & Copyediting Invariants
1. Book Integrity & Narrative Parity:
   - This translation compiles directly into a book edition. Maintain strict 1:1 narrative parity with the source text.
   - Do NOT add extraneous content, fabricated scenes, summaries, or explanatory translator notes.
   - Do NOT truncate, condense, or omit any sentences, paragraphs, or dialogue. Every source passage must be translated in full.
2. Watermark & Artifact Elimination:
   - Silently detect and eliminate all distributor watermarks, web URLs (e.g. http://, https://, www.), channel usernames/social tags (e.g. @name), scan artifacts, and promotional headers/footers found in the source text. Never translate or retain scraping noise.
3. Terminology Conformance:
   - Every named character, location, artifact, and realm found in <glossary> MUST strictly use its designated translation. Never invent conflicting variants.
4. Syntactic & Idiomatic De-calquing:
   - Avoid word-for-word literal translation. Restructure rigid English clauses into natural, fluid syntax authentic to Persian.
   - Transform weak passive constructions into vivid active verbs where appropriate for narrative drive.
   - Localize idioms, humor, and cultural metaphors to produce equivalent emotional resonance without changing story facts.
5. Orthography & Typographical Precision:
   - When target is Persian / Farsi:
     * Strictly enforce zero-width non-joiners (ZWNJ / \u200c) for verbal prefixes (mi- / nemi-), plural suffixes (-ha / -haye), comparative suffixes (-tar / -tarin), and possessive enclitics.
     * Apply Persian punctuation: quotation guillemets (« ») for dialogue and direct thoughts, Persian commas (،), question marks (؟), and semicolons (؛). Never put whitespace before punctuation; place a single space after.
     * Respect pro-drop grammar: eliminate repetitive subject pronouns (avoid repetitive leading 'ou').
   - When target is European / Latin or other languages:
     * Follow authentic locale conventions for quotes (e.g. curly quotes, chevrons, or em-dashes), punctuation, and diacritics.
6. Dialogue Calibration & Character Voice:
   - Modulate speech registers (formality, intimacy, defiance, social status) based on interpersonal dynamics documented in <character_dossier>.
7. Structural Formatting Preservation:
   - Preserve all Markdown structural elements: headings (#, ##), scene dividers (***, ---), blockquotes (>), italics (*thoughts/emphasis*), and bold text intact.

# Constraints & Stop Rules
- Output Contract: Return ONLY the translated Markdown text.
- Begin immediately with the translated manuscript content. No introductory conversational greetings, meta-explanations, or closing remarks.
```

### User Message
```markdown
<glossary>
| Canonical Term | Aliases / Variants | Term Translation | Sample Context | Context Translation |
|---|---|---|---|---|
| Evangeline Fox | Evangeline | اوانجلین فاکس | Evangeline pulled her cloak tight. | اوانجلین شنلش را محکم دور خود پیچید. |
| Jacks | Prince of Hearts | جکس | Jacks bit into the poisoned apple. | جکس سیب زهرآلود را گاز زد. |
| The Fates | Immortals | سرنوشت‌ها | Beware the bargains of the Fates. | از معامله با سرنوشت‌ها برحذر باش. |
</glossary>

<manuscript filename="02_chapter_2.md">
# Chapter 2

Downloaded from https://t.me/free_fantasy_books @FreeBooks
Evangeline took a hesitant step forward into the church. The air tasted of bitter apples and cold incense.

"You're late, Little Fox," a voice purred from the rafters.

Jacks dropped to the marble floor without a sound, a blood-red apple turning lazily between his pale fingers. Visit www.z-lib.org for more books.

*He really is one of the Fates,* she thought, her heart hammering against her ribs.
</manuscript>
```

### Expected Output
```markdown
# فصل ۲

اوانجلین گامی مردد به درون کلیسا برداشت. هوا طعم سیب‌های تلخ و عود سرد می‌داد.

صدایی از میان تیرچه‌های سقف نجوا کرد: «دیر کردی، روباه کوچولو.»

جکس بی‌صدا روی کف مرمرین فرود آمد؛ سیبی سرخ‌فام میان انگشتان رنگ‌پریده‌اش با طمأنینه می‌چرخید.

با خود اندیشید: «او واقعاً یکی از سرنوشت‌هاست.» و قلبش دیوانه‌وار به قفسهٔ سینه‌اش می‌کوبید.
```
*(Notice how distributor URLs and `@FreeBooks` handles were silently pruned, guillemets were applied to dialogue, ZWNJ was enforced, terminology from `<glossary>` was adhered to, and natural literary flow was preserved).*

---

## 8. Specialized Fantasy Localization Architecture
 
Tome includes dedicated, high-signal translation rules designed specifically for fantasy novels to solve the stiffness and artificiality of generic machine translation:
 
### 1. The Dual-Voice Engine
- **Narration & World Lore**: Fluent, eloquent, dignified, literary Persian (`نثر ادبیِ روان، شیوا و فاخر`). Employs complete grammatical verbs and evocative imagery. Slang and broken word contractions are strictly prohibited in narrative exposition.
- **Dialogue & Direct Speech**: Natural, authentic, spoken colloquial Persian (`کاملاً محاوره‌ای، روان و شکسته`). Characters sound like living people having authentic conversations, matching their background and social standing.
- **Telepathic Communications & Internal Projections**: Formatted in bold markdown inside Persian quotation guillemets (`«**متن تله‌پاتی**»`).
 
### 2. Worldbuilding & Creative Compounding
- **No Literal Calquing**: Fantasy names, magical ranks, beasts, and spells are never translated mechanically.
- **Morphological Compounding**: Utilizes euphonic Persian affixes:
  - `-افزار` (e.g. `نبرد‌افزار`, `طلسم‌افزار`)
  - `-آور` (e.g. `مرگ‌آور`, `شفاآور`)
  - `-زاد` (e.g. `سایه‌زاد`, `بادزاد`)
  - `-ساز` (e.g. `وهم‌ساز`, `روح‌ساز`)
  - `-ستان` (e.g. `اخگرستان`, `کهن‌ستان`)
  - `-بان` / `-پناه` (e.g. `دژبان`, `سایه‌پناه`)
- **Phonetic Harmony**: Respects the sonic identity of the source world and forbids jarring real-world cultural or modern expressions.
- **Magic Laws as Hard Physics**: Magical mechanics, mana forms, transformation tiers, and runic stages remain 100% immutable across all chapters.
 
### 3. Combat Pacing & Narrative Velocity
- In moments of close combat and sudden peril, sentence structure tightens into rapid, sequential beats.
- Sluggish auxiliary verbs (e.g. "شروع به حرکت به سمت او کرد") are replaced by explosive kinetic verbs (e.g. "به سویش جهید", "تیغه کشید", "فرو نشست").
 
### 4. Cultural Oath & Expletive Adaptation
- **Ban on Real-World Idioms**: Forbids real-world localized idioms or religious phrases (no "شاهنامه آخرش خوشه" or "یا خدا").
- **In-Universe Oaths**: Recreated from world mythos ("قسم به خدایان کهن", oaths of blood, blade, and ancestors).
- **Controlled Wrath**: Modern street profanities are eliminated in favor of fantasy curses focused on dishonor, spilled blood, broken oaths, and ancestral damnation.
 
### 5. Automatic Genre Routing
When a book's genre is detected as `fantasy` or configured as `fantasy`:
- Tome automatically appends the `fantasy_translation_guidelines` to the active chapter translation prompt.
- GLiNER entity extraction uses the expanded fantasy taxonomy spanning realms, magical reagents, transformation stages, and ancient relics.
