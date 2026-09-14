import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tome.exceptions import PromptValidationError

GENRE_TAXONOMIES: dict[str, dict[str, list[str]]] = {
    "fantasy": {
        "People & Characters": [
            "character",
            "protagonist",
            "person",
            "magician",
            "ruler",
            "witch",
            "vampire",
            "fate",
            "knight",
        ],
        "Titles, Roles & Positions": [
            "military rank",
            "royal title",
            "honorific",
            "epithet",
            "prince",
            "princess",
            "lord",
            "lady",
        ],
        "Locations, Realms & Coordinates": [
            "city",
            "kingdom",
            "realm",
            "fortress",
            "mountain",
            "inn",
            "castle",
            "hall",
            "palace",
            "sanctuary",
            "domain",
            "forest",
            "haven",
            "archipelago",
        ],
        "Organizations, Factions & Companies": ["squadron", "guild", "faction", "clan", "order", "house", "coven", "cult", "dynasty"],
        "Tech, Systems & Magic": [
            "spell",
            "magical ability",
            "curse",
            "signet",
            "rune",
            "combat technique",
            "enchantment",
            "magical reagent",
            "transformation stage",
            "incantation",
            "mana",
        ],
        "Species, Races & Organisms": ["dragon", "beast", "creature", "race", "species", "monster", "fae", "elf", "dwarf", "demon", "spirit", "mythical race"],
        "Artifacts, Products & Key Assets": [
            "relic",
            "enchanted weapon",
            "tome",
            "magical artifact",
            "stone",
            "arch",
            "blade",
            "talisman",
            "grimoire",
            "elixir",
        ],
        "Domain Terms & Jargon": ["lore term", "magical concept", "currency", "ritual", "prophecy", "bargain"],
    },
    "scifi": {
        "People & Characters": ["crew member", "commander", "scientist", "ai entity", "pilot", "clone", "cyborg"],
        "Titles, Roles & Positions": ["naval rank", "officer", "specialist", "governor", "captain", "admiral"],
        "Locations, Realms & Coordinates": [
            "planet",
            "star system",
            "space station",
            "quadrant",
            "colony",
            "galaxy",
            "orbit",
        ],
        "Organizations, Factions & Companies": [
            "federation",
            "corporation",
            "syndicate",
            "fleet",
            "coalition",
            "empire",
        ],
        "Tech, Systems & Magic": [
            "propulsion system",
            "algorithm",
            "weaponry",
            "cybernetic implant",
            "quantum drive",
            "shield",
        ],
        "Species, Races & Organisms": [
            "alien species",
            "synthetic life",
            "biome",
            "mutant",
            "extraterrestrial",
            "android",
        ],
        "Artifacts, Products & Key Assets": ["starship", "quantum device", "prototype", "beacon", "datalog", "ai core"],
        "Domain Terms & Jargon": [
            "scientific theory",
            "slang",
            "hyperdrive principle",
            "protocol",
            "hyperspace",
            "warp",
        ],
    },
    "romance": {
        "People & Characters": ["lover", "protagonist", "partner", "love interest", "confidante", "suitor"],
        "Titles, Roles & Positions": ["gentleman", "lady", "bachelor", "bride", "groom", "duchess", "earl"],
        "Locations, Realms & Coordinates": ["estate", "resort", "hometown", "ballroom", "cafe", "countryside"],
        "Organizations, Factions & Companies": ["society", "family estate", "club", "circle"],
        "Tech, Systems & Magic": [],
        "Species, Races & Organisms": [],
        "Artifacts, Products & Key Assets": ["keepsake", "letter", "jewelry", "heirloom", "ring"],
        "Domain Terms & Jargon": ["courtship", "engagement", "rendezvous", "vow", "scandal", "infatuation"],
    },
    "thriller_mystery": {
        "People & Characters": ["detective", "investigator", "suspect", "victim", "witness", "killer", "informant"],
        "Titles, Roles & Positions": ["inspector", "agent", "sergeant", "coroner", "attorney", "lieutenant"],
        "Locations, Realms & Coordinates": ["crime scene", "precinct", "hideout", "safehouse", "morgue", "alley"],
        "Organizations, Factions & Companies": ["police department", "agency", "syndicate", "cartel", "bureau"],
        "Tech, Systems & Magic": ["forensic technique", "ballistics", "surveillance method", "wiretap"],
        "Species, Races & Organisms": [],
        "Artifacts, Products & Key Assets": [
            "murder weapon",
            "clue",
            "alibi evidence",
            "encrypted file",
            "fingerprint",
        ],
        "Domain Terms & Jargon": ["motive", "modus operandi", "autopsy finding", "warrant", "subpoena"],
    },
    "horror": {
        "People & Characters": ["victim", "survivor", "cultist", "medium", "investigator", "harbinger"],
        "Titles, Roles & Positions": ["priest", "exorcist", "occultist", "caretaker", "inquisitor"],
        "Locations, Realms & Coordinates": ["asylum", "graveyard", "crypt", "haunted house", "woods", "basement"],
        "Organizations, Factions & Companies": ["cult", "coven", "secret society", "sect"],
        "Tech, Systems & Magic": ["ritual", "hex", "incantation", "possession", "manifestation"],
        "Species, Races & Organisms": ["demon", "entity", "ghoul", "fiend", "poltergeist", "apparition"],
        "Artifacts, Products & Key Assets": ["cursed object", "talisman", "grimoire", "effigy", "relic"],
        "Domain Terms & Jargon": ["manifestation", "seance", "omen", "abomination", "resurrection"],
    },
    "historical_fiction": {
        "People & Characters": ["historical figure", "monarch", "diplomat", "soldier", "rebel", "peasant"],
        "Titles, Roles & Positions": ["emperor", "chancellor", "earl", "cardinal", "general", "duke"],
        "Locations, Realms & Coordinates": ["province", "dynasty", "colony", "battlefield", "palace", "vassal"],
        "Organizations, Factions & Companies": ["regiment", "parliament", "treaty alliance", "aristocracy", "guild"],
        "Tech, Systems & Magic": ["period warfare", "naval strategy", "trade route", "siegecraft"],
        "Species, Races & Organisms": [],
        "Artifacts, Products & Key Assets": ["charter", "treaty", "crown jewels", "manuscript", "seal"],
        "Domain Terms & Jargon": ["insurgency", "succession", "rebellion", "feudal right", "armistice"],
    },
    "business": {
        "People & Characters": ["executive", "founder", "investor", "theorist", "leader", "customer", "shareholder"],
        "Titles, Roles & Positions": ["chief executive officer", "partner", "manager", "director", "chairperson"],
        "Locations, Realms & Coordinates": ["headquarters", "market region", "exchange", "economic zone", "hub"],
        "Organizations, Factions & Companies": [
            "corporation",
            "venture fund",
            "regulatory agency",
            "conglomerate",
            "startup",
        ],
        "Tech, Systems & Magic": ["business methodology", "operating system", "logistics model", "framework"],
        "Species, Races & Organisms": [],
        "Artifacts, Products & Key Assets": ["product line", "trademark", "patent", "financial instrument", "equity"],
        "Domain Terms & Jargon": ["metric", "kpi", "economic framework", "valuation multiple", "churn", "ebitda"],
    },
    "self_help_psychology": {
        "People & Characters": ["practitioner", "subject", "therapist", "author", "mentor", "patient"],
        "Titles, Roles & Positions": ["counselor", "coach", "psychologist", "trainer", "clinician"],
        "Locations, Realms & Coordinates": ["clinic", "retreat", "environment", "workspace"],
        "Organizations, Factions & Companies": ["institute", "association", "support group", "clinic"],
        "Tech, Systems & Magic": ["cognitive exercise", "behavioral technique", "mindfulness method", "protocol"],
        "Species, Races & Organisms": [],
        "Artifacts, Products & Key Assets": ["journal", "framework", "assessment", "tool", "diary"],
        "Domain Terms & Jargon": ["neuroplasticity", "habit loop", "dopamine", "mindset", "resilience", "cognition"],
    },
    "academic_textbook": {
        "People & Characters": ["researcher", "scholar", "theorist", "pioneer", "scientist", "academic"],
        "Titles, Roles & Positions": ["professor", "fellow", "principal investigator", "dean", "chair"],
        "Locations, Realms & Coordinates": ["laboratory", "observatory", "field site", "institution", "archive"],
        "Organizations, Factions & Companies": ["university", "department", "research foundation", "faculty"],
        "Tech, Systems & Magic": ["scientific methodology", "apparatus", "mathematical model", "simulation"],
        "Species, Races & Organisms": ["specimen", "classification", "taxa", "strain", "organism"],
        "Artifacts, Products & Key Assets": ["dataset", "instrument", "publication", "patent", "formula"],
        "Domain Terms & Jargon": ["hypothesis", "variable", "empirical evidence", "statistically significant", "proof"],
    },
    "biography_memoir": {
        "People & Characters": ["subject", "parent", "mentor", "companion", "contemporary", "ancestor"],
        "Titles, Roles & Positions": ["president", "statesman", "artist", "pioneer", "activist", "leader"],
        "Locations, Realms & Coordinates": ["birthplace", "childhood home", "capital", "exile", "homeland"],
        "Organizations, Factions & Companies": ["administration", "movement", "academy", "circle", "union"],
        "Tech, Systems & Magic": [],
        "Species, Races & Organisms": [],
        "Artifacts, Products & Key Assets": ["autobiography", "diary", "personal artifact", "archive", "letters"],
        "Domain Terms & Jargon": ["legacy", "upbringing", "watershed moment", "milestone", "memoir"],
    },
    "health_fitness": {
        "People & Characters": ["physician", "patient", "athlete", "nutritionist", "trainer", "clinician", "surgeon"],
        "Titles, Roles & Positions": ["doctor", "dietitian", "physiotherapist", "specialist", "coach", "nurse"],
        "Locations, Realms & Coordinates": ["clinic", "hospital", "gym", "wellness center", "laboratory", "pharmacy"],
        "Organizations, Factions & Companies": [
            "health organization",
            "medical association",
            "clinic",
            "athletic federation",
        ],
        "Tech, Systems & Magic": [
            "training regimen",
            "medical protocol",
            "diagnostic technique",
            "dietary plan",
            "therapy",
        ],
        "Species, Races & Organisms": ["pathogen", "microbiome", "cell", "tissue", "organism"],
        "Artifacts, Products & Key Assets": [
            "supplement",
            "pharmaceutical",
            "workout equipment",
            "medical device",
            "meal plan",
        ],
        "Domain Terms & Jargon": [
            "metabolism",
            "immune response",
            "hypertrophy",
            "cardiovascular",
            "biomarker",
            "longevity",
            "wellness",
            "symptom",
        ],
    },
    "psychology_communication": {
        "People & Characters": [
            "speaker",
            "listener",
            "subject",
            "psychologist",
            "observer",
            "negotiator",
            "interrogator",
        ],
        "Titles, Roles & Positions": ["analyst", "therapist", "counselor", "mediator", "coach", "specialist"],
        "Locations, Realms & Coordinates": [
            "interview room",
            "stage",
            "consulting room",
            "laboratory",
            "conference hall",
        ],
        "Organizations, Factions & Companies": ["institute", "psychological association", "behavioral lab", "society"],
        "Tech, Systems & Magic": [
            "behavioral analysis",
            "micro-expression reading",
            "active listening",
            "persuasion technique",
        ],
        "Species, Races & Organisms": [],
        "Artifacts, Products & Key Assets": [
            "assessment report",
            "body language guide",
            "interview transcript",
            "questionnaire",
        ],
        "Domain Terms & Jargon": [
            "body language",
            "nonverbal",
            "micro-expression",
            "posture",
            "eye contact",
            "gesture",
            "deception",
            "rapport",
            "subconscious",
        ],
    },
    "spirituality_mindset": {
        "People & Characters": ["practitioner", "seeker", "guide", "mystic", "master", "author", "healer"],
        "Titles, Roles & Positions": ["spiritual teacher", "mentor", "philosopher", "guide", "minister"],
        "Locations, Realms & Coordinates": ["sanctuary", "temple", "universe", "inner realm", "retreat", "altar"],
        "Organizations, Factions & Companies": ["fellowship", "spiritual society", "order", "community"],
        "Tech, Systems & Magic": [
            "affirmation",
            "manifestation",
            "visualization",
            "meditation",
            "prayer",
            "spiritual law",
        ],
        "Species, Races & Organisms": [],
        "Artifacts, Products & Key Assets": ["sacred text", "journal", "scroll", "heirloom", "scripture"],
        "Domain Terms & Jargon": [
            "law of attraction",
            "divine order",
            "abundance",
            "intuition",
            "karma",
            "grace",
            "subconscious mind",
            "faith",
            "blessing",
        ],
    },
    "academic_research": {
        "People & Characters": [
            "author",
            "investigator",
            "co-author",
            "participant",
            "reviewer",
            "editor",
            "researcher",
        ],
        "Titles, Roles & Positions": [
            "principal investigator",
            "corresponding author",
            "professor",
            "peer reviewer",
            "dean",
        ],
        "Locations, Realms & Coordinates": ["laboratory", "research institute", "archive", "field site", "department"],
        "Organizations, Factions & Companies": [
            "university",
            "academic publisher",
            "research council",
            "journal",
            "association",
        ],
        "Tech, Systems & Magic": [
            "methodology",
            "statistical model",
            "survey instrument",
            "experimental design",
            "measurement",
        ],
        "Species, Races & Organisms": ["control group", "cohort", "sample population", "specimen"],
        "Artifacts, Products & Key Assets": ["manuscript", "preprint", "dataset", "article", "bibliography", "doi"],
        "Domain Terms & Jargon": [
            "abstract",
            "literature review",
            "methodology",
            "findings",
            "conclusion",
            "references",
            "hypothesis",
            "empirical",
            "p-value",
            "citation",
        ],
    },
    "general": {
        "People & Characters": ["person", "author", "historical figure", "individual"],
        "Titles, Roles & Positions": ["title", "position", "office", "designation"],
        "Locations, Realms & Coordinates": ["city", "country", "region", "landmark"],
        "Organizations, Factions & Companies": ["organization", "institution", "company", "group"],
        "Tech, Systems & Magic": ["technology", "method", "system", "theory"],
        "Species, Races & Organisms": ["animal", "plant", "organism"],
        "Artifacts, Products & Key Assets": ["publication", "tool", "document", "artifact"],
        "Domain Terms & Jargon": ["concept", "term", "specialized vocabulary"],
    },
}

GENRE_KEYWORD_INDICATORS: dict[str, list[str]] = {
    "fantasy": [
        "magic",
        "curse",
        "spell",
        "dragon",
        "vampire",
        "prince",
        "princess",
        "fate",
        "arch",
        "castle",
        "sword",
        "witch",
        "fae",
        "enchanted",
        "sorcery",
        "wizard",
        "potion",
        "prophecy",
        "palace",
        "realm",
        "lord",
        "lady",
        "fairytale",
        "dagger",
        "kingdom",
        "oddity",
        "valory",
        "fates",
        "mythical",
    ],
    "scifi": [
        "alien",
        "starship",
        "space",
        "galaxy",
        "planet",
        "quantum",
        "cyber",
        "robot",
        "ai",
        "propulsion",
        "orbit",
        "hyperspace",
        "nanotech",
        "android",
        "laser",
        "warp",
        "teleport",
        "fleet",
        "colony",
        "shuttle",
    ],
    "romance": [
        "romance",
        "kiss",
        "heart",
        "darling",
        "flirt",
        "handsome",
        "marry",
        "marriage",
        "bride",
        "lover",
        "passion",
        "courtship",
        "embrace",
        "beloved",
        "attraction",
        "affair",
        "intimacy",
        "cherish",
    ],
    "thriller_mystery": [
        "detective",
        "murder",
        "police",
        "killer",
        "bullet",
        "crime",
        "investigation",
        "suspect",
        "victim",
        "forensic",
        "homicide",
        "alibi",
        "interrogation",
        "sheriff",
        "corpse",
        "fingerprint",
        "weapon",
    ],
    "horror": [
        "demon",
        "haunting",
        "terror",
        "ghost",
        "corpse",
        "evil",
        "ghoul",
        "nightmare",
        "possession",
        "macabre",
        "exorcism",
        "poltergeist",
        "sinister",
        "cursed",
        "graveyard",
        "crypt",
        "asylum",
        "dread",
    ],
    "historical_fiction": [
        "century",
        "empire",
        "reign",
        "emperor",
        "treaty",
        "revolution",
        "warfare",
        "regiment",
        "monarchy",
        "dynasty",
        "nob nobility",
        "aristocrat",
        "peasant",
        "feudal",
        "colonial",
        "battlefield",
        "parliament",
    ],
    "business": [
        "revenue",
        "profit",
        "market",
        "customer",
        "business",
        "growth",
        "stock",
        "investor",
        "corporate",
        "sales",
        "entrepreneur",
        "startup",
        "equity",
        "management",
        "strategy",
        "valuation",
        "brand",
    ],
    "self_help_psychology": [
        "habit",
        "habits",
        "compound",
        "discipline",
        "routine",
        "productivity",
        "goal",
        "goals",
        "consistency",
        "willpower",
        "mindset",
        "motivation",
        "success",
        "momentum",
        "focus",
        "procrastination",
        "time management",
        "self-improvement",
        "personal development",
        "resilience",
        "meditation",
        "mindfulness",
        "happiness",
        "behavior",
        "neuroscience",
        "reflection",
        "عادت",
        "عادات",
        "موفقیت",
        "انگیزه",
        "رشد فردی",
        "تمرکز",
        "پشتکار",
        "بهره‌وری",
        "انضباط",
        "هدف",
        "اهداف",
        "خودسازی",
        "توسعه فردی",
    ],
    "health_fitness": [
        "health",
        "fitness",
        "wellness",
        "nutrition",
        "diet",
        "workout",
        "exercise",
        "medicine",
        "medical",
        "disease",
        "immune",
        "muscle",
        "longevity",
        "doctor",
        "clinic",
        "symptom",
        "metabolic",
        "cardiovascular",
        "sleep",
        "therapy",
        "recovery",
        "physiology",
        "anatomy",
        "vitality",
        "سلامت",
        "سلامتی",
        "درمان",
        "تغذیه",
        "پزشک",
        "پزشکی",
        "بیماری",
        "رژیم",
        "دارو",
        "ورزش",
        "تندرستی",
        "بدنسازی",
    ],
    "psychology_communication": [
        "body language",
        "nonverbal",
        "non-verbal",
        "gesture",
        "gestures",
        "posture",
        "facial expression",
        "eye contact",
        "handshake",
        "deception",
        "lie detection",
        "persuasion",
        "communication",
        "interpersonal",
        "psychological",
        "subconscious",
        "empathy",
        "rapport",
        "microexpression",
        "arms crossed",
        "body signals",
        "زبان بدن",
        "حالات چهره",
        "حرکات بدن",
        "ارتباط غیرکلامی",
        "ارتباط موثر",
        "روانشناسی رفتار",
    ],
    "spirituality_mindset": [
        "spirituality",
        "spiritual",
        "universe",
        "divine",
        "faith",
        "prayer",
        "intuition",
        "abundance",
        "manifestation",
        "law of attraction",
        "karma",
        "affirmation",
        "spoken word",
        "blessing",
        "subconscious mind",
        "inner peace",
        "grace",
        "miracle",
        "destiny",
        "soul",
        "enlightenment",
        "معنویت",
        "معنوی",
        "کائنات",
        "قانون جذب",
        "دعا",
        "ایمان",
        "برکت",
        "فراوانی",
        "شکرگزاری",
        "ذهن نیمه هوشیار",
        "تجلی",
        "روح",
        "آگاهی",
    ],
    "academic_research": [
        "abstract",
        "introduction",
        "literature review",
        "methodology",
        "findings",
        "conclusion",
        "references",
        "hypothesis",
        "hypotheses",
        "p-value",
        "empirical",
        "peer-reviewed",
        "participant",
        "participants",
        "regression",
        "citation",
        "citations",
        "journal",
        "paper",
        "doi",
        "bibliography",
        "dataset",
        "dissertation",
        "thesis",
        "مقاله",
        "چکیده",
        "پیشینه تحقیق",
        "روش تحقیق",
        "یافته‌ها",
        "نتیجه‌گیری",
        "منابع",
        "فرضیه",
        "فرضیه‌ها",
        "متغیر",
        "جامعه آماری",
        "پژوهش",
    ],
    "academic_textbook": [
        "hypothesis",
        "methodology",
        "experiment",
        "analysis",
        "citation",
        "theoretical",
        "dataset",
        "theorem",
        "lemma",
        "pedagogical",
        "empirical",
        "curriculum",
        "definition",
        "literature review",
    ],
    "biography_memoir": [
        "childhood",
        "memoir",
        "autobiography",
        "upbringing",
        "recollection",
        "ancestors",
        "biography",
        "memoirs",
        "early years",
        "reminiscence",
        "parents",
        "born in",
        "youth",
    ],
}

DEFAULT_PROMPTS = {
    "user_style_rules": "",
    "glossary_translation_system_prompt": (
        "# Identity & Goal\n"
        "You are a terminology and localization compiler for novel worldbuilding. "
        "Translate the provided source glossary table into {target_language} with absolute lexical consistency, "
        "phonetic elegance, and creative compounding.\n\n"
        "# Input Specification\n"
        "A Markdown table with the following schema:\n"
        "| Canonical Term | Aliases / Variants | Term Translation | Sample Context | Context Translation |\n\n"
        "# Execution Invariants\n"
        "For each row where 'Term Translation' and 'Context Translation' are empty:\n"
        "1. Term Translation: Output an evocative, linguistically natural translation or transliteration in {target_language}. "
        "Avoid mechanical word-for-word calques. For proper nouns, preserve phonological beauty and authentic character identity. "
        "For fantasy entities, spells, and artifacts, utilize resonant morphological compounding (e.g. suffixes like -افزار, -آور, -زاد, -ساز, -ستان).\n"
        "2. Context Translation: Translate the sample context sentence into fluent, publication-grade {target_language}, "
        "illustrating the term in actual narrative flow.\n\n"
        "# Negative Constraints & Stop Rules\n"
        "- Strictly preserve the 5-column Markdown table structure: | Canonical Term | Aliases / Variants | Term Translation | Sample Context | Context Translation |\n"
        "- Do not modify, reorder, or delete existing values in 'Canonical Term', 'Aliases / Variants', or 'Sample Context'.\n"
        "- Filter non-narrative artifacts: If a term or context contains distributor watermarks, URLs, or channel handles, ignore the artifact.\n"
        "- Do not extrapolate or invent connotations unsupported by the context sentence.\n"
        "- Stop Rule: Output ONLY the completed Markdown table. No conversational preamble, greetings, or meta-commentary."
    ),
    "chapter_translation_with_glossary_system_prompt": (
        "# Identity & Goal\n"
        "You are an end-to-end literary translation and prose copyediting engine for publication-grade books. "
        "Translate English narrative prose into {target_language} with absolute semantic fidelity, vivid prose rhythm, "
        "captivating readability, and flawless orthography.\n\n"
        "# Contextual Inputs\n"
        "- <character_dossier>: Character relationship graph, archetypes, and narrative dynamics.\n"
        "- <style_guidelines>: Project-specific authorial and tonal constraints.\n"
        "- <glossary>: Authoritative bilingual term mappings.\n"
        "- <manuscript>: The source chapter to translate.\n\n"
        "<character_dossier>\n"
        "{graph}\n"
        "</character_dossier>\n\n"
        "<style_guidelines>\n"
        "{user_style_rules}\n"
        "</style_guidelines>\n\n"
        "# Core Translation & Copyediting Invariants\n"
        "1. Narrative Fidelity & Literary Fluency:\n"
        "   - Translate every scene, character interaction, and dialogue passage completely without omitting plot points or fabricating unrelated scenes.\n"
        "   - Prioritize natural, fluent, and captivating prose over rigid word-by-word literalism. The translated book must read as an authentic, high-caliber literary work that flows smoothly and grips the reader.\n"
        "   - Do NOT truncate, condense, or omit any sentences, paragraphs, or dialogue. Every source passage must be translated in full.\n"
        "2. Watermark & Artifact Elimination:\n"
        "   - Silently detect and eliminate all distributor watermarks, web URLs (e.g. http://, https://, www.), channel usernames/social tags (e.g. @name), scan artifacts, and promotional headers/footers found in the source text. Never translate or retain scraping noise.\n"
        "3. Terminology Conformance:\n"
        "   - Every named character, location, artifact, and realm found in <glossary> MUST strictly use its designated translation. Never invent conflicting variants.\n"
        "4. Syntactic & Idiomatic De-calquing:\n"
        "   - Avoid word-for-word literal translation. Restructure rigid English clauses into natural, fluid syntax authentic to {target_language}.\n"
        "   - Transform weak passive constructions into vivid active verbs where appropriate for narrative drive.\n"
        "   - Localize idioms, humor, and cultural metaphors to produce equivalent emotional resonance without changing story facts.\n"
        "5. Orthography & Typographical Precision:\n"
        "   - When target is Persian / Farsi:\n"
        "     * Strictly enforce zero-width non-joiners (ZWNJ / \\u200c) for verbal prefixes (mi- / nemi-), plural suffixes (-ha / -haye), comparative suffixes (-tar / -tarin), and possessive enclitics.\n"
        "     * Apply Persian punctuation: quotation guillemets (« ») for dialogue and direct thoughts, Persian commas (،), question marks (؟), and semicolons (؛). Never put whitespace before punctuation; place a single space after.\n"
        "     * Respect pro-drop grammar: eliminate repetitive subject pronouns (avoid repetitive leading 'ou').\n"
        "   - When target is European / Latin or other languages:\n"
        "     * Follow authentic locale conventions for quotes (e.g. curly quotes, chevrons, or em-dashes), punctuation, and diacritics.\n"
        "6. Dialogue Calibration & Dual-Voice Mandate (تفکیک بنیادین لحن روایت و دیالوگ):\n"
        "   - Modulate speech registers (formality, intimacy, defiance, social status) based on interpersonal dynamics documented in <character_dossier>.\n"
        "   - In Persian fiction, strictly enforce the Dual-Voice architecture:\n"
        "     * Narrative Prose (نثر روایت و توصیفات خارج از گیومه): Must be eloquent, publication-grade literary Persian (نثر کاملاً رسمی، فاخر، شیوا و آراسته). Verbs and grammatical structures must remain complete and formal (e.g. می‌دانست، می‌رفت، نمی‌خواست، خنجر را برداشت). NEVER use colloquial verbal contractions in descriptive narration.\n"
        "     * Direct Dialogue & Speech (گفتگوی شخصیت‌ها درون گیومه « »): MUST be 100% natural, living colloquial spoken Persian (محاوره‌ای زنده، تهرانی معیار و شکسته). Characters must sound authentic, emotional, and lifelike—NEVER stiff, robotic, or bookish.\n"
        "       - Mandatory Spoken Verbs: Use spoken contractions: می‌خوام/نمی‌خوام (NOT می‌خواهم)، می‌دونم/نمی‌دونم (NOT می‌دانم)، می‌تونی/نمی‌تونم (NOT می‌توانی)، می‌گه (NOT می‌گوید)، می‌ره (NOT می‌رود)، می‌شه/نمی‌شه (NOT می‌شود/نمی‌شود)، اومده/رفته/کرده (NOT آمده است/رفته است/کرده است).\n"
        "       - Banned «را» in Dialogue: The formal particle «را» is STRICTLY FORBIDDEN inside dialogue. Replace with «رو/ـو/ـرو» or attached clitics (e.g. «شوهرمو مسموم کردی!» NOT «شوهرم را زهر کردی!»; «ندیدمش / اونو ندیدم» NOT «او را ندیدم»; «اینو قبلاً گفتی» NOT «این را قبلاً گفتی»).\n"
        "       - Spoken Pronouns & Particles: Use اون/اونا (NOT او/ایشان)، واسه/واسه چی (NOT برای/برای چه)، آخه، مگه، چطور، چی، دیگه.\n"
        "       - Contrast Examples:\n"
        "         * WRONG (Stiff / Bookish): «از پیشم برو، جکس. می‌دانم چه کردی، و نمی‌خواهم ببینمت. تو شوهرم را زهر کردی!»\n"
        "         * CORRECT (Natural Spoken): «از پیشم برو جکس. می‌دونم چه غلطی کردی و اصلاً نمی‌خوام ببینمت! تو شوهرمو مسموم کردی!»\n"
        "7. Structural Formatting & Illustration Preservation:\n"
        "   - Preserve all Markdown structural elements: headings (#, ##), scene dividers (***, ---), blockquotes (>), italics (*thoughts/emphasis*), and bold text intact.\n"
        "   - Preserve all Markdown image links (e.g., ![Illustration](images/image_01_p003.png)) exactly in their contextual narrative position relative to the translated text. Do not omit, translate, or alter image paths.\n\n"
        "# Constraints & Stop Rules\n"
        "- Never ask the user what to do, offer editing options, or request clarification. "
        "Regardless of whether an excerpt begins mid-sentence, appears fragmented, or contains unusual dialogue, "
        "your SOLE and MANDATORY task is to translate and copyedit the entire content of <manuscript> into {target_language}.\n"
        "- Output Contract: Return ONLY the translated Markdown text.\n"
        "- Begin immediately with the translated manuscript content. No introductory conversational greetings, clarification questions, meta-explanations, or closing remarks."
    ),
    "chapter_translation_no_gliner_system_prompt": (
        "# Identity & Goal\n"
        "You are an end-to-end literary translation, prose copyediting, and inline entity-extraction engine for publication-grade books. "
        "Translate English narrative prose into {target_language} with absolute semantic fidelity, vivid prose rhythm, "
        "captivating readability, and flawless orthography, while tracking newly introduced worldbuilding lore.\n\n"
        "# Contextual Inputs\n"
        "- <character_dossier>: Character relationship graph, archetypes, and narrative dynamics.\n"
        "- <style_guidelines>: Project-specific authorial and tonal constraints.\n"
        "- <manuscript>: The source chapter to translate.\n\n"
        "<character_dossier>\n"
        "{graph}\n"
        "</character_dossier>\n\n"
        "<style_guidelines>\n"
        "{user_style_rules}\n"
        "</style_guidelines>\n\n"
        "# Core Translation & Copyediting Invariants\n"
        "1. Narrative Fidelity & Literary Fluency:\n"
        "   - Translate every scene, character interaction, and dialogue passage completely without omitting plot points or fabricating unrelated scenes.\n"
        "   - Prioritize natural, fluent, and captivating prose over rigid word-by-word literalism. The translated book must read as an authentic, high-caliber literary work that flows smoothly and grips the reader.\n"
        "   - Do NOT truncate, condense, or omit any sentences, paragraphs, or dialogue. Every source passage must be translated in full.\n"
        "2. Watermark & Artifact Elimination:\n"
        "   - Silently detect and eliminate all distributor watermarks, web URLs (e.g. http://, https://, www.), channel usernames/social tags (e.g. @name), scan artifacts, and promotional headers/footers found in the source text. Never translate or retain scraping noise.\n"
        "3. Lore Continuity:\n"
        "   - Maintain strict naming continuity for all recurring characters, realms, artifacts, and magical terms across chapters.\n"
        "4. Syntactic & Idiomatic De-calquing:\n"
        "   - Avoid word-for-word literal translation. Restructure rigid English clauses into natural, fluid syntax authentic to {target_language}.\n"
        "   - Transform weak passive constructions into vivid active verbs where appropriate for narrative drive.\n"
        "   - Localize idioms, humor, and cultural metaphors to produce equivalent emotional resonance without changing story facts.\n"
        "5. Orthography & Typographical Precision:\n"
        "   - When target is Persian / Farsi:\n"
        "     * Strictly enforce zero-width non-joiners (ZWNJ / \\u200c) for verbal prefixes (mi- / nemi-), plural suffixes (-ha / -haye), comparative suffixes (-tar / -tarin), and possessive enclitics.\n"
        "     * Apply Persian punctuation: quotation guillemets (« ») for dialogue and direct thoughts, Persian commas (،), question marks (؟), and semicolons (؛). Never put whitespace before punctuation; place a single space after.\n"
        "     * Respect pro-drop grammar: eliminate repetitive subject pronouns (avoid repetitive leading 'ou').\n"
        "   - When target is European / Latin or other languages:\n"
        "     * Follow authentic locale conventions for quotes (e.g. curly quotes, chevrons, or em-dashes), punctuation, and diacritics.\n"
        "6. Dialogue Calibration & Dual-Voice Mandate (تفکیک بنیادین لحن روایت و دیالوگ):\n"
        "   - Modulate speech registers (formality, intimacy, defiance, social status) based on interpersonal dynamics documented in <character_dossier>.\n"
        "   - In Persian fiction, strictly enforce the Dual-Voice architecture:\n"
        "     * Narrative Prose (نثر روایت و توصیفات خارج از گیومه): Must be eloquent, publication-grade literary Persian (نثر کاملاً رسمی، فاخر، شیوا و آراسته). Verbs and grammatical structures must remain complete and formal (e.g. می‌دانست، می‌رفت، نمی‌خواست، خنجر را برداشت). NEVER use colloquial verbal contractions in descriptive narration.\n"
        "     * Direct Dialogue & Speech (گفتگوی شخصیت‌ها درون گیومه « »): MUST be 100% natural, living colloquial spoken Persian (محاوره‌ای زنده، تهرانی معیار و شکسته). Characters must sound authentic, emotional, and lifelike—NEVER stiff, robotic, or bookish.\n"
        "       - Mandatory Spoken Verbs: Use spoken contractions: می‌خوام/نمی‌خوام (NOT می‌خواهم)، می‌دونم/نمی‌دونم (NOT می‌دانم)، می‌تونی/نمی‌تونم (NOT می‌توانی)، می‌گه (NOT می‌گوید)، می‌ره (NOT می‌رود)، می‌شه/نمی‌شه (NOT می‌شود/نمی‌شود)، اومده/رفته/کرده (NOT آمده است/رفته است/کرده است).\n"
        "       - Banned «را» in Dialogue: The formal particle «را» is STRICTLY FORBIDDEN inside dialogue. Replace with «رو/ـو/ـرو» or attached clitics (e.g. «شوهرمو مسموم کردی!» NOT «شوهرم را زهر کردی!»; «ندیدمش / اونو ندیدم» NOT «او را ندیدم»; «اینو قبلاً گفتی» NOT «این را قبلاً گفتی»).\n"
        "       - Spoken Pronouns & Particles: Use اون/اونا (NOT او/ایشان)، واسه/واسه چی (NOT برای/برای چه)، آخه، مگه، چطور، چی، دیگه.\n"
        "       - Contrast Examples:\n"
        "         * WRONG (Stiff / Bookish): «از پیشم برو، جکس. می‌دانم چه کردی، و نمی‌خواهم ببینمت. تو شوهرم را زهر کردی!»\n"
        "         * CORRECT (Natural Spoken): «از پیشم برو جکس. می‌دونم چه غلطی کردی و اصلاً نمی‌خوام ببینمت! تو شوهرمو مسموم کردی!»\n"
        "7. Structural Formatting & Illustration Preservation:\n"
        "   - Preserve all Markdown structural elements: headings (#, ##), scene dividers (***, ---), blockquotes (>), italics (*thoughts/emphasis*), and bold text intact.\n"
        "   - Preserve all Markdown image links (e.g., ![Illustration](images/image_01_p003.png)) exactly in their contextual narrative position relative to the translated text. Do not omit, translate, or alter image paths.\n\n"
        "# Dynamic Entity Extraction\n"
        "At the very end of your response, identify all newly introduced named entities in this chapter. Append them using this exact delimiter format:\n\n"
        "<!-- ENTITIES_START\n"
        "- [Category: People & Characters] English Name | Translation: Translation | Aliases: Alias1, Alias2\n"
        "- [Category: Locations, Realms & Coordinates] English Name | Translation: Translation\n"
        "- [Category: Tech, Systems & Magic] English Name | Translation: Translation\n"
        "ENTITIES_END -->\n\n"
        "# Constraints & Stop Rules\n"
        "- Never ask the user what to do, offer editing options, or request clarification. "
        "Regardless of whether an excerpt begins mid-sentence, appears fragmented, or contains unusual dialogue, "
        "your SOLE and MANDATORY task is to translate and copyedit the entire content of <manuscript> into {target_language}.\n"
        "- Output Contract: Return ONLY the translated Markdown text followed by the delimited entity extraction block.\n"
        "- Begin immediately with the translated manuscript content. No introductory conversational greetings, clarification questions, meta-explanations, or closing remarks."
    ),
    "fantasy_translation_guidelines": (
        "# Fantasy Localization Guidelines\n"
        "When localizing fantasy fiction into {target_language}, adhere strictly to these literary conventions:\n\n"
        "1. Absolute Dual-Voice Principle (قانون تفکیک قاطع دیالوگ محاوره‌ای از نثر فاخر):\n"
        "   - Narrative & Scene Descriptions (نثر و توصیفات صحنه - خارج از گیومه): Compose in eloquent, dignified, publication-grade literary Persian (نثر ادبی، فاخر، شیوا و روان). Verbs and grammatical structures must remain complete, formal, and rich (e.g. با پدرش ستاره‌ها را تماشا کرده بود، خنجر را در مشت فشرد). NEVER use broken colloquial verbal contractions or spoken slang in descriptive narration.\n"
        "   - Dialogue & Direct Speech (دیالوگ‌ها و گفتگوی شخصیت‌ها - درون گیومه « »): Render in 100% natural, living colloquial spoken Persian (محاوره‌ای زنده، روان، تهرانی معیار و شکسته). Characters must sound like real living individuals speaking to each other—dynamic, emotional, and sharp.\n"
        "     * STRICT PROHIBITION of bookish/formal speech in dialogue:\n"
        "       - WRONG (Stiff): «از پیشم برو، جکس. می‌دانم چه کردی، و نمی‌خواهم ببینمت.»\n"
        "       - CORRECT (Spoken): «از پیشم برو جکس. می‌دونم چه غلطی کردی و اصلاً نمی‌خوام ببینمت!»\n"
        "       - WRONG (Stiff): «تو شوهرم را زهر کردی!»\n"
        "       - CORRECT (Spoken): «تو به شوهرم زهر دادی!» یا «تو شوهرمو مسموم کردی!»\n"
        "       - WRONG (Stiff): «این چیزی نیست که بابتش امتیاز بگیری.»\n"
        "       - CORRECT (Spoken): «این چیزی نیست که بخوای بهش افتخار کنی / بابتش جایزه بگیری!»\n"
        "       - WRONG (Stiff): «باید از سنجیدن من با معیارهای انسانی دست برداری. من سرنوشت‌سازم.»\n"
        "       - CORRECT (Spoken): «باید دست از سنجیدن من با خط‌کش آدمی‌زاد برداری. من فِیتم / سرنوشت‌سازم.»\n"
        "       - WRONG (Stiff): «پس چرا من را خنجر نزدی، روباه کوچولو؟»\n"
        "       - CORRECT (Spoken): «پس چرا بهم خنجر نزدی، روباه کوچولو؟»\n"
        "       - WRONG (Stiff): «نمی‌خواهم بابت همان چیزی که هستم عذرخواهی کنم.»\n"
        "       - CORRECT (Spoken): «من واسه چیزی که هستم از کسی معذرت نمی‌خوام.»\n"
        "       - WRONG (Stiff): «اگر واقعاً باور داری این کار را می‌کنم، به‌کلی دیوانه‌ای.»\n"
        "       - CORRECT (Spoken): «اگه واقعاً فکر می‌کنی همچین کاری می‌کنم، پاک دیوونه شدی / رسماً عقلتو باختی!»\n"
        "     * Object Marker «را» is BANNED in dialogue: replace with «رو/ـو/ـرو» or attached pronouns (ندیدمش، کتابو بیار، شوهرمو زهر دادی).\n"
        "     * Contracted Spoken Verbs: All verbs in dialogue MUST be spoken (می‌خوام، نمی‌خوام، می‌دونم، نمی‌دونم، می‌تونی، نمی‌تونم، می‌ره، می‌گه، می‌شه، نمی‌شه، اومده، رفته، کرده).\n"
        "   - Telepathy & Mental Speech (ارتباط ذهنی و تله‌پاتی): Render in spoken colloquial Persian enclosed in Persian guillemets with bold styling: «**متن ارتباط ذهنی**».\n\n"
        "2. Creative Persian Word-Formation:\n"
        "   - For mythical creatures, magical ranks, artifacts, and spells, avoid rigid word-for-word calques.\n"
        "   - Employ natural, euphonic Persian morphological compounding with rich affixes (e.g. -افزار، -آور، -زاد، -ساز، -ستان، -بان، -پناه).\n\n"
        "3. World Lore & Conceptual Consistency:\n"
        "   - Treat magical mechanisms, reagent names, mana forms, and transformation stages as immutable physical laws. Terminology must remain uniform across all chapters.\n"
        "   - Avoid real-world cultural proverbs, modern street slang, or earthly religious expressions. Ground all oaths and expressions in the lore (e.g. oaths of blood, blade, ancient gods, and world mythos).\n\n"
        "4. Combat Dynamics & Narrative Velocity:\n"
        "   - In battle sequences and intense confrontations, use short, kinetic phrasing and dynamic active verbs to preserve momentum, tension, and speed."
    ),
    "metadata_refinement_system_prompt": (
        "# Identity & Goal\n"
        "You are a precise bibliographic metadata extraction and normalization engine.\n"
        "Analyze the raw book information provided in <metadata> and produce a canonical, cleaned JSON metadata record.\n\n"
        "# Contextual Inputs\n"
        "The <metadata> block provides:\n"
        "1. File name of the source manuscript.\n"
        "2. Internal document metadata (embedded PDF/EPUB attributes).\n"
        "3. Initial heuristically extracted metadata fields (may contain OCR artifacts, distributor watermarks, or missing keys).\n"
        "4. Raw front matter excerpt (cover, title page, copyright notice, cataloging data).\n"
        "5. Chapter 1 opening excerpt.\n\n"
        "<metadata>\n"
        "{metadata}\n"
        "</metadata>\n\n"
        "# Normalization Invariants & Rules\n"
        "1. Title & Authors:\n"
        "   - Identify the authentic authorial book title and author(s).\n"
        "   - Strictly distinguish the primary book title from in-universe fictional newspapers, fictional gazettes, letters, proclamations, or chapter headlines (e.g., in-universe fictional newspapers like 'The Whisper Gazette' must NOT be mistaken for the book title when the book is 'Spectacular').\n"
        "   - Cross-reference the attached cover illustration, document metadata, and manuscript filename as primary ground truth for the authentic book title.\n"
        "   - Strictly purge distributor tags, scanner watermarks, archive domain names (e.g., z-lib, oceanofpdf, libgen), and file extensions.\n"
        "   - Capitalize cleanly in title case.\n"
        "2. Authors:\n"
        "   - Extract individual author names as a clean list of strings.\n"
        "   - Remove role suffixes like ', author', 'by', 'written by', or editor credits unless primary.\n"
        "   - If unknown, return an empty list.\n"
        "3. Publication Details:\n"
        "   - Year: Extract the 4-digit original or edition publication year as a string, or null if absent.\n"
        "   - Publisher: Canonical imprint name, or null.\n"
        "   - ISBN: Valid 10 or 13-digit ISBN string with hyphens or digits only, or null.\n"
        "4. Genre Classification:\n"
        "   - Determine the most accurate manuscript category from: fantasy, scifi, romance, thriller_mystery, horror, historical_fiction, business, self_help_psychology, health_fitness, psychology_communication, spirituality_mindset, academic_research, biography_memoir, general.\n"
        "5. Synopsis & Keywords:\n"
        "   - Synopsis: Write a dense, high-signal 2-3 sentence executive synopsis capturing the premise, conflict, or core thesis of the book without hyperbole or spoiler endings.\n"
        "   - Keywords: List 5 to 8 specific thematic and subject keywords for document metadata indexing.\n\n"
        "# Output Contract\n"
        "Return ONLY a valid, parseable JSON object with no markdown fences, no conversational preambles, and no trailing commentary.\n\n"
        "Schema:\n"
        "{\n"
        '  "title": "string",\n'
        '  "authors": ["string"],\n'
        '  "year": "string | null",\n'
        '  "publisher": "string | null",\n'
        '  "isbn": "string | null",\n'
        '  "genre": "string",\n'
        '  "synopsis": "string",\n'
        '  "keywords": ["string"]\n'
        "}"
    ),
}


def detect_genre(text: str) -> str:
    sample = text[:120000].lower()
    scores: Counter[str] = Counter()

    for genre, keywords in GENRE_KEYWORD_INDICATORS.items():
        score = 0
        for kw in keywords:
            kw_clean = kw.lower()
            pattern = rf"(?:^|[\s\(\[\"\'«،؛.,!?:\-_]){re.escape(kw_clean)}(?:$|[\s\)\]\"\'»،؛.,!?:\-_])"
            matches = len(re.findall(pattern, sample))
            score += matches * (3 if " " in kw_clean else 1)
        if score > 0:
            scores[genre] = score

    if not scores:
        return "general"

    top_genre, top_score = scores.most_common(1)[0]
    if top_score < 3:
        return "general"

    return top_genre


AVAILABLE_LLM_MODELS: list[tuple[str, str]] = [
    ("qwen3.8-flash", "qwen3.8-flash (Alibaba) [Default]"),
    ("gemini-flash-latest", "gemini-flash-latest (Google)"),
    ("glm-5.3-flash", "glm-5.3-flash (ZAI / Zhipu)"),
    ("deepseek-v4-flash", "deepseek-v4-flash (DeepSeek)"),
    ("deepseek-v4-pro", "deepseek-v4-pro (DeepSeek)"),
    ("claude-sonnet-5", "claude-sonnet-5 (Anthropic)"),
    ("gpt-5.6-luna", "gpt-5.6-luna (OpenAI)"),
    ("custom", "Custom Model"),
]

PROMPT_ALLOWED_VARIABLES: dict[str, set[str]] = {
    "chapter_translation_with_glossary_system_prompt": {"target_language", "user_style_rules", "graph"},
    "chapter_translation_no_gliner_system_prompt": {"target_language", "user_style_rules", "graph"},
    "fantasy_translation_guidelines": {"target_language"},
    "glossary_translation_system_prompt": {"target_language"},
    "metadata_refinement_system_prompt": {"metadata"},
}


def normalize_prompt_escapes(text: str) -> str:
    """Decodes literal escape sequences such as \\n and \\t into real whitespace."""
    if not text:
        return text
    return text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t")


def validate_prompt_variables(template: str, allowed_vars: set[str], prompt_name: str = "prompt") -> None:
    found_vars = set(re.findall(r"(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*)\}(?!\})", template))
    invalid = found_vars - allowed_vars
    if invalid:
        invalid_str = ", ".join(f"{{{v}}}" for v in sorted(invalid))
        allowed_str = ", ".join(f"{{{v}}}" for v in sorted(allowed_vars))
        raise PromptValidationError(
            f"Invalid placeholder(s) {invalid_str} found in {prompt_name}. Allowed template variables are: {allowed_str}"
        )


@dataclass
class GeneralConfig:
    output_dir: Path = field(default_factory=lambda: Path("output"))
    log_dir: Path = field(default_factory=lambda: Path("logs"))
    log_retention_days: int = 7
    genre: str = "auto"
    keep_raw_artifacts: bool = False
    min_chapter_bytes: int = 512
    hf_mirror_endpoint: str = "https://hf-mirror.com"
    extract_images: bool = True


@dataclass
class LLMConfig:
    base_url: str = "https://api.avalai.ir/v1"
    api_key: str = "aa-G1AQIkYIIx3CGof0CalY9AvXJLdSChjeJPQQpGmwQNoXvpNe"
    model: str = "qwen3.8-flash"
    temperature: float = 1.0
    top_p: float = 0.95
    max_tokens: int = 16384
    thinking: bool = True
    reasoning_effort: str = "medium"
    timeout: int = 300
    stream_response: bool = True


@dataclass
class ProxyConfig:
    enabled: bool = False
    type: str = "socks5"
    host: str = "127.0.0.1"
    port: int = 10808


@dataclass
class GLiNERConfig:
    enabled: bool = True
    model: str = "urchade/gliner_medium-v2.1"
    batch_size: int = 16
    chunk_size_words: int = 280
    chunk_overlap_words: int = 20
    min_entity_frequency: int = 2
    high_confidence_threshold: float = 0.85
    fuzzy_similarity_threshold: float = 0.88
    max_levenshtein_distance: int = 2


@dataclass
class NLPConfig:
    refine_metadata: bool = True
    persian_nlp: bool = True
    fast_mode: bool = False
    gliner: GLiNERConfig = field(default_factory=GLiNERConfig)


@dataclass
class TranslationConfig:
    target_language: str = "Persian"
    batch_size: int = 1


@dataclass
class TypographyConfig:
    compile_docx: bool = True
    eastern_font: str = "B Nazanin"
    western_font: str = "Times New Roman"
    paragraph_indent: str = "0.4cm"
    line_spacing: str = "1.35x"
    body_font_size: str = "11"
    heading1_pagebreak: bool = True
    margin_cm: float = 2.5


class TomeConfig:
    def __init__(
        self,
        general: GeneralConfig | None = None,
        llm: LLMConfig | None = None,
        proxy: ProxyConfig | None = None,
        nlp: NLPConfig | None = None,
        translation: TranslationConfig | None = None,
        typography: TypographyConfig | None = None,
        config_path: Path | None = None,
        prompts: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        self.general = general or GeneralConfig()
        self.llm = llm or LLMConfig()
        self.proxy = proxy or ProxyConfig()
        self.nlp = nlp or NLPConfig()
        self.translation = translation or TranslationConfig()
        self.typography = typography or TypographyConfig()
        self.config_path = config_path or Path("tome.json")
        self.prompts = dict(DEFAULT_PROMPTS) if prompts is None else dict(prompts)

        for k, v in kwargs.items():
            setattr(self, k, v)

        for k, v in list(self.prompts.items()):
            if isinstance(v, str):
                self.prompts[k] = normalize_prompt_escapes(v)
        self.validate()

    @property
    def output_dir(self) -> Path:
        return self.general.output_dir

    @output_dir.setter
    def output_dir(self, val: Any) -> None:
        self.general.output_dir = Path(val)

    @property
    def log_dir(self) -> Path:
        return self.general.log_dir

    @log_dir.setter
    def log_dir(self, val: Any) -> None:
        self.general.log_dir = Path(val)

    @property
    def log_retention_days(self) -> int:
        return self.general.log_retention_days

    @log_retention_days.setter
    def log_retention_days(self, val: int) -> None:
        self.general.log_retention_days = int(val)

    @property
    def genre(self) -> str:
        return self.general.genre

    @genre.setter
    def genre(self, val: str) -> None:
        self.general.genre = str(val)

    @property
    def keep_raw_artifacts(self) -> bool:
        return self.general.keep_raw_artifacts

    @keep_raw_artifacts.setter
    def keep_raw_artifacts(self, val: bool) -> None:
        self.general.keep_raw_artifacts = bool(val)

    @property
    def min_chapter_bytes(self) -> int:
        return self.general.min_chapter_bytes

    @min_chapter_bytes.setter
    def min_chapter_bytes(self, val: int) -> None:
        self.general.min_chapter_bytes = int(val)

    @property
    def hf_mirror_endpoint(self) -> str:
        return self.general.hf_mirror_endpoint

    @hf_mirror_endpoint.setter
    def hf_mirror_endpoint(self, val: str) -> None:
        self.general.hf_mirror_endpoint = str(val)

    @property
    def extract_images(self) -> bool:
        return self.general.extract_images

    @extract_images.setter
    def extract_images(self, val: bool) -> None:
        self.general.extract_images = bool(val)

    @property
    def llm_base_url(self) -> str:
        return self.llm.base_url

    @llm_base_url.setter
    def llm_base_url(self, val: str) -> None:
        self.llm.base_url = str(val)

    @property
    def llm_api_key(self) -> str:
        return self.llm.api_key

    @llm_api_key.setter
    def llm_api_key(self, val: str) -> None:
        self.llm.api_key = str(val)

    @property
    def llm_model(self) -> str:
        return self.llm.model

    @llm_model.setter
    def llm_model(self, val: str) -> None:
        self.llm.model = str(val)

    @property
    def llm_temperature(self) -> float:
        return self.llm.temperature

    @llm_temperature.setter
    def llm_temperature(self, val: float) -> None:
        self.llm.temperature = float(val)

    @property
    def llm_top_p(self) -> float:
        return self.llm.top_p

    @llm_top_p.setter
    def llm_top_p(self, val: float) -> None:
        self.llm.top_p = float(val)

    @property
    def llm_max_tokens(self) -> int:
        return self.llm.max_tokens

    @llm_max_tokens.setter
    def llm_max_tokens(self, val: int) -> None:
        self.llm.max_tokens = int(val)

    @property
    def llm_thinking(self) -> bool:
        return self.llm.thinking

    @llm_thinking.setter
    def llm_thinking(self, val: bool) -> None:
        self.llm.thinking = bool(val)

    @property
    def llm_reasoning_effort(self) -> str:
        return self.llm.reasoning_effort

    @llm_reasoning_effort.setter
    def llm_reasoning_effort(self, val: str) -> None:
        self.llm.reasoning_effort = str(val)

    @property
    def llm_timeout(self) -> int:
        return self.llm.timeout

    @llm_timeout.setter
    def llm_timeout(self, val: int) -> None:
        self.llm.timeout = int(val)

    @property
    def stream_response(self) -> bool:
        return self.llm.stream_response

    @stream_response.setter
    def stream_response(self, val: bool) -> None:
        self.llm.stream_response = bool(val)

    @property
    def proxy_enabled(self) -> bool:
        return self.proxy.enabled

    @proxy_enabled.setter
    def proxy_enabled(self, val: bool) -> None:
        self.proxy.enabled = bool(val)

    @property
    def proxy_type(self) -> str:
        return self.proxy.type

    @proxy_type.setter
    def proxy_type(self, val: str) -> None:
        self.proxy.type = str(val)

    @property
    def proxy_host(self) -> str:
        return self.proxy.host

    @proxy_host.setter
    def proxy_host(self, val: str) -> None:
        self.proxy.host = str(val)

    @property
    def proxy_port(self) -> int:
        return self.proxy.port

    @proxy_port.setter
    def proxy_port(self, val: int) -> None:
        self.proxy.port = int(val)

    @property
    def refine_metadata(self) -> bool:
        return self.nlp.refine_metadata

    @refine_metadata.setter
    def refine_metadata(self, val: bool) -> None:
        self.nlp.refine_metadata = bool(val)

    @property
    def persian_nlp(self) -> bool:
        return self.nlp.persian_nlp

    @persian_nlp.setter
    def persian_nlp(self, val: bool) -> None:
        self.nlp.persian_nlp = bool(val)

    @property
    def fast_mode(self) -> bool:
        return self.nlp.fast_mode

    @fast_mode.setter
    def fast_mode(self, val: bool) -> None:
        self.nlp.fast_mode = bool(val)

    @property
    def skip_gliner(self) -> bool:
        return not self.nlp.gliner.enabled

    @skip_gliner.setter
    def skip_gliner(self, val: bool) -> None:
        self.nlp.gliner.enabled = not bool(val)

    @property
    def default_model(self) -> str:
        return self.nlp.gliner.model

    @default_model.setter
    def default_model(self, val: str) -> None:
        self.nlp.gliner.model = str(val)

    @property
    def gliner_model(self) -> str:
        return self.nlp.gliner.model

    @gliner_model.setter
    def gliner_model(self, val: str) -> None:
        self.nlp.gliner.model = str(val)

    @property
    def batch_size(self) -> int:
        return self.nlp.gliner.batch_size

    @batch_size.setter
    def batch_size(self, val: int) -> None:
        self.nlp.gliner.batch_size = int(val)

    @property
    def chunk_size_words(self) -> int:
        return self.nlp.gliner.chunk_size_words

    @chunk_size_words.setter
    def chunk_size_words(self, val: int) -> None:
        self.nlp.gliner.chunk_size_words = int(val)

    @property
    def chunk_overlap_words(self) -> int:
        return self.nlp.gliner.chunk_overlap_words

    @chunk_overlap_words.setter
    def chunk_overlap_words(self, val: int) -> None:
        self.nlp.gliner.chunk_overlap_words = int(val)

    @property
    def min_entity_frequency(self) -> int:
        return self.nlp.gliner.min_entity_frequency

    @min_entity_frequency.setter
    def min_entity_frequency(self, val: int) -> None:
        self.nlp.gliner.min_entity_frequency = int(val)

    @property
    def high_confidence_threshold(self) -> float:
        return self.nlp.gliner.high_confidence_threshold

    @high_confidence_threshold.setter
    def high_confidence_threshold(self, val: float) -> None:
        self.nlp.gliner.high_confidence_threshold = float(val)

    @property
    def fuzzy_similarity_threshold(self) -> float:
        return self.nlp.gliner.fuzzy_similarity_threshold

    @fuzzy_similarity_threshold.setter
    def fuzzy_similarity_threshold(self, val: float) -> None:
        self.nlp.gliner.fuzzy_similarity_threshold = float(val)

    @property
    def max_levenshtein_distance(self) -> int:
        return self.nlp.gliner.max_levenshtein_distance

    @max_levenshtein_distance.setter
    def max_levenshtein_distance(self, val: int) -> None:
        self.nlp.gliner.max_levenshtein_distance = int(val)

    @property
    def target_language(self) -> str:
        return self.translation.target_language

    @target_language.setter
    def target_language(self, val: str) -> None:
        self.translation.target_language = str(val)

    @property
    def translation_batch_size(self) -> int:
        return self.translation.batch_size

    @translation_batch_size.setter
    def translation_batch_size(self, val: int) -> None:
        self.translation.batch_size = int(val)

    @property
    def compile_docx(self) -> bool:
        return self.typography.compile_docx

    @compile_docx.setter
    def compile_docx(self, val: bool) -> None:
        self.typography.compile_docx = bool(val)

    @property
    def eastern_font(self) -> str:
        return self.typography.eastern_font

    @eastern_font.setter
    def eastern_font(self, val: str) -> None:
        self.typography.eastern_font = str(val)

    @property
    def western_font(self) -> str:
        return self.typography.western_font

    @western_font.setter
    def western_font(self, val: str) -> None:
        self.typography.western_font = str(val)

    @property
    def persian_font(self) -> str:
        return self.typography.eastern_font

    @persian_font.setter
    def persian_font(self, val: str) -> None:
        self.typography.eastern_font = str(val)

    @property
    def paragraph_indent(self) -> str:
        return self.typography.paragraph_indent

    @paragraph_indent.setter
    def paragraph_indent(self, val: str) -> None:
        self.typography.paragraph_indent = str(val)

    @property
    def line_spacing(self) -> str:
        return self.typography.line_spacing

    @line_spacing.setter
    def line_spacing(self, val: str) -> None:
        self.typography.line_spacing = str(val)

    @property
    def body_font_size(self) -> str:
        return self.typography.body_font_size

    @body_font_size.setter
    def body_font_size(self, val: str) -> None:
        self.typography.body_font_size = str(val)

    @property
    def heading1_pagebreak(self) -> bool:
        return self.typography.heading1_pagebreak

    @heading1_pagebreak.setter
    def heading1_pagebreak(self, val: bool) -> None:
        self.typography.heading1_pagebreak = bool(val)

    @property
    def margin_cm(self) -> float:
        return self.typography.margin_cm

    @margin_cm.setter
    def margin_cm(self, val: float) -> None:
        self.typography.margin_cm = float(val)

    @property
    def user_style_rules(self) -> str:
        return self.prompts.get("user_style_rules", "")

    @user_style_rules.setter
    def user_style_rules(self, val: str) -> None:
        self.prompts["user_style_rules"] = normalize_prompt_escapes(val)

    def resolve_genre(self, text: str = "") -> str:
        if self.genre.lower() != "auto":
            return self.genre.lower()
        if text:
            return detect_genre(text)
        return "fantasy"

    def get_taxonomy(self, resolved_genre: str | None = None) -> dict[str, list[str]]:
        genre_key = resolved_genre or (self.genre.lower() if self.genre.lower() != "auto" else "fantasy")
        return GENRE_TAXONOMIES.get(genre_key, GENRE_TAXONOMIES["general"])

    def get_chapter_prompt_name(self, has_glossary: bool = True) -> str:
        return (
            "chapter_translation_with_glossary_system_prompt"
            if has_glossary
            else "chapter_translation_no_gliner_system_prompt"
        )

    def get_glossary_prompt_name(self) -> str:
        return "glossary_translation_system_prompt"

    def is_fantasy_genre(self, genre: str | None = None) -> bool:
        resolved = (genre or self.genre or "general").lower().strip()
        return "fantasy" in resolved

    def validate_prompts(self) -> None:
        for prompt_name, allowed_vars in PROMPT_ALLOWED_VARIABLES.items():
            template = self.prompts.get(prompt_name)
            if template:
                validate_prompt_variables(template, allowed_vars, prompt_name=prompt_name)

    def validate(self) -> None:
        if self.proxy.enabled:
            ptype = self.proxy.type.lower()
            if ptype not in ("socks5", "socks", "socks5h", "http", "https"):
                raise ValueError(
                    f"Invalid proxy type '{self.proxy.type}'. Supported types: socks5, socks, http, https."
                )
            if not (1 <= self.proxy.port <= 65535):
                raise ValueError(f"Invalid proxy port '{self.proxy.port}'. Must be between 1 and 65535.")
            if not self.proxy.host or not self.proxy.host.strip():
                raise ValueError("Proxy host cannot be empty when proxy is enabled.")

        if not (0.0 <= self.llm.temperature <= 2.0):
            raise ValueError(f"Invalid llm temperature '{self.llm.temperature}'. Must be between 0.0 and 2.0.")
        if not (0.0 <= self.llm.top_p <= 1.0):
            raise ValueError(f"Invalid llm top_p '{self.llm.top_p}'. Must be between 0.0 and 1.0.")
        if self.llm.max_tokens <= 0:
            raise ValueError(f"Invalid llm max_tokens '{self.llm.max_tokens}'. Must be a positive integer.")
        if self.llm.timeout <= 0:
            raise ValueError(f"Invalid llm timeout '{self.llm.timeout}'. Must be a positive integer.")
        if self.llm.reasoning_effort and self.llm.reasoning_effort.lower() not in ("low", "medium", "high"):
            raise ValueError(
                f"Invalid reasoning_effort '{self.llm.reasoning_effort}'. Allowed values: low, medium, high."
            )

        if self.nlp.gliner.batch_size <= 0:
            raise ValueError(f"Invalid GLiNER batch_size '{self.nlp.gliner.batch_size}'. Must be positive.")
        if not (0.0 <= self.nlp.gliner.high_confidence_threshold <= 1.0):
            raise ValueError("Invalid GLiNER high_confidence_threshold. Must be between 0.0 and 1.0.")
        if not (0.0 <= self.nlp.gliner.fuzzy_similarity_threshold <= 1.0):
            raise ValueError("Invalid GLiNER fuzzy_similarity_threshold. Must be between 0.0 and 1.0.")
        if self.nlp.gliner.max_levenshtein_distance < 0:
            raise ValueError("Invalid GLiNER max_levenshtein_distance. Must be non-negative.")

        if self.translation.batch_size < 1:
            raise ValueError(f"Invalid translation batch_size '{self.translation.batch_size}'. Must be >= 1.")
        if self.general.log_retention_days < 1:
            raise ValueError(f"Invalid log_retention_days '{self.general.log_retention_days}'. Must be >= 1.")
        if self.general.min_chapter_bytes < 0:
            raise ValueError("min_chapter_bytes cannot be negative.")
        if self.typography.margin_cm <= 0:
            raise ValueError("margin_cm must be positive.")

        self.validate_prompts()

    def to_dict(self) -> dict[str, Any]:
        return {
            "general": {
                "output_dir": str(self.general.output_dir),
                "log_dir": str(self.general.log_dir),
                "log_retention_days": self.general.log_retention_days,
                "genre": self.general.genre,
                "keep_raw_artifacts": self.general.keep_raw_artifacts,
                "min_chapter_bytes": self.general.min_chapter_bytes,
                "hf_mirror_endpoint": self.general.hf_mirror_endpoint,
                "extract_images": self.general.extract_images,
            },
            "llm": {
                "base_url": self.llm.base_url,
                "api_key": self.llm.api_key,
                "model": self.llm.model,
                "temperature": self.llm.temperature,
                "top_p": self.llm.top_p,
                "max_tokens": self.llm.max_tokens,
                "thinking": self.llm.thinking,
                "reasoning_effort": self.llm.reasoning_effort,
                "timeout": self.llm.timeout,
                "stream_response": self.llm.stream_response,
            },
            "proxy": {
                "enabled": self.proxy.enabled,
                "type": self.proxy.type,
                "host": self.proxy.host,
                "port": self.proxy.port,
            },
            "nlp": {
                "refine_metadata": self.nlp.refine_metadata,
                "persian_nlp": self.nlp.persian_nlp,
                "fast_mode": self.nlp.fast_mode,
                "gliner": {
                    "enabled": self.nlp.gliner.enabled,
                    "model": self.nlp.gliner.model,
                    "batch_size": self.nlp.gliner.batch_size,
                    "chunk_size_words": self.nlp.gliner.chunk_size_words,
                    "chunk_overlap_words": self.nlp.gliner.chunk_overlap_words,
                    "min_entity_frequency": self.nlp.gliner.min_entity_frequency,
                    "high_confidence_threshold": self.nlp.gliner.high_confidence_threshold,
                    "fuzzy_similarity_threshold": self.nlp.gliner.fuzzy_similarity_threshold,
                    "max_levenshtein_distance": self.nlp.gliner.max_levenshtein_distance,
                },
            },
            "translation": {
                "target_language": self.translation.target_language,
                "batch_size": self.translation.batch_size,
            },
            "typography": {
                "compile_docx": self.typography.compile_docx,
                "eastern_font": self.typography.eastern_font,
                "western_font": self.typography.western_font,
                "paragraph_indent": self.typography.paragraph_indent,
                "line_spacing": self.typography.line_spacing,
                "body_font_size": self.typography.body_font_size,
                "heading1_pagebreak": self.typography.heading1_pagebreak,
                "margin_cm": self.typography.margin_cm,
            },
            "prompts": self.prompts,
        }

    @classmethod
    def load_config(cls, path: Path | None = None) -> "TomeConfig":
        config_path = path or Path("tome.json")
        if not config_path.exists():
            cfg = cls(config_path=config_path)
            cfg.save_config(config_path)
            return cfg

        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return cls(config_path=config_path)

            general_data = data.get("general", {})
            llm_data = data.get("llm", {})
            proxy_data = data.get("proxy", {})
            nlp_data = data.get("nlp", {})
            gliner_data = nlp_data.get("gliner", {}) if isinstance(nlp_data, dict) else {}
            translation_data = data.get("translation", {})
            typography_data = data.get("typography", {})

            out_dir = general_data.get("output_dir", data.get("output_dir", "output"))
            log_dir = general_data.get("log_dir", data.get("log_dir", "logs"))
            retention = int(general_data.get("log_retention_days", data.get("log_retention_days", 7)))
            genre = str(general_data.get("genre", data.get("genre", "auto")))
            keep_raw = bool(general_data.get("keep_raw_artifacts", data.get("keep_raw_artifacts", False)))
            min_ch = int(general_data.get("min_chapter_bytes", data.get("min_chapter_bytes", 512)))
            hf_mirror = str(
                general_data.get("hf_mirror_endpoint", data.get("hf_mirror_endpoint", "https://hf-mirror.com"))
            )
            extract_img = bool(general_data.get("extract_images", data.get("extract_images", True)))

            general = GeneralConfig(
                output_dir=Path(out_dir),
                log_dir=Path(log_dir),
                log_retention_days=retention,
                genre=genre,
                keep_raw_artifacts=keep_raw,
                min_chapter_bytes=min_ch,
                hf_mirror_endpoint=hf_mirror,
                extract_images=extract_img,
            )

            llm = LLMConfig(
                base_url=str(llm_data.get("base_url", data.get("llm_base_url", "https://api.avalai.ir/v1"))),
                api_key=str(llm_data.get("api_key", data.get("llm_api_key", ""))),
                model=str(llm_data.get("model", data.get("llm_model", "qwen3.8-flash"))),
                temperature=float(llm_data.get("temperature", data.get("llm_temperature", 1.0))),
                top_p=float(llm_data.get("top_p", data.get("llm_top_p", 0.95))),
                max_tokens=int(llm_data.get("max_tokens", data.get("llm_max_tokens", 16384))),
                thinking=bool(llm_data.get("thinking", data.get("llm_thinking", True))),
                reasoning_effort=str(llm_data.get("reasoning_effort", data.get("llm_reasoning_effort", "medium"))),
                timeout=int(llm_data.get("timeout", data.get("llm_timeout", 300))),
                stream_response=bool(llm_data.get("stream_response", data.get("stream_response", True))),
            )

            proxy = ProxyConfig(
                enabled=bool(proxy_data.get("enabled", data.get("proxy_enabled", False))),
                type=str(proxy_data.get("type", data.get("proxy_type", "socks5"))),
                host=str(proxy_data.get("host", data.get("proxy_host", "127.0.0.1"))),
                port=int(proxy_data.get("port", data.get("proxy_port", 10808))),
            )

            gliner_enabled = bool(
                gliner_data.get("enabled", not data.get("skip_gliner", False))
                if ("enabled" in gliner_data or "skip_gliner" in data)
                else True
            )
            gliner_model = str(gliner_data.get("model", data.get("default_model", "urchade/gliner_medium-v2.1")))
            gliner = GLiNERConfig(
                enabled=gliner_enabled,
                model=gliner_model,
                batch_size=int(gliner_data.get("batch_size") or data.get("batch_size") or 16),
                chunk_size_words=int(gliner_data.get("chunk_size_words") or data.get("chunk_size_words") or 280),
                chunk_overlap_words=int(
                    gliner_data.get("chunk_overlap_words") or data.get("chunk_overlap_words") or 20
                ),
                min_entity_frequency=int(
                    gliner_data.get("min_entity_frequency") or data.get("min_entity_frequency") or 2
                ),
                high_confidence_threshold=float(
                    gliner_data.get("high_confidence_threshold") or data.get("high_confidence_threshold") or 0.85
                ),
                fuzzy_similarity_threshold=float(
                    gliner_data.get("fuzzy_similarity_threshold") or data.get("fuzzy_similarity_threshold") or 0.88
                ),
                max_levenshtein_distance=int(
                    gliner_data.get("max_levenshtein_distance") or data.get("max_levenshtein_distance") or 2
                ),
            )

            nlp = NLPConfig(
                refine_metadata=bool(nlp_data.get("refine_metadata", data.get("refine_metadata", True))),
                persian_nlp=bool(nlp_data.get("persian_nlp", data.get("persian_nlp", True))),
                fast_mode=bool(nlp_data.get("fast_mode", data.get("fast_mode", False))),
                gliner=gliner,
            )

            translation = TranslationConfig(
                target_language=str(translation_data.get("target_language", data.get("target_language", "Persian"))),
                batch_size=int(translation_data.get("batch_size", data.get("translation_batch_size", 1))),
            )

            eastern = str(
                typography_data.get(
                    "eastern_font",
                    data.get("eastern_font", data.get("persian_font", "B Nazanin")),
                )
            )
            typography = TypographyConfig(
                compile_docx=bool(typography_data.get("compile_docx", data.get("compile_docx", True))),
                eastern_font=eastern,
                western_font=str(typography_data.get("western_font", data.get("western_font", "Times New Roman"))),
                paragraph_indent=str(typography_data.get("paragraph_indent", data.get("paragraph_indent", "0.4cm"))),
                line_spacing=str(typography_data.get("line_spacing", data.get("line_spacing", "1.35x"))),
                body_font_size=str(typography_data.get("body_font_size", data.get("body_font_size", "11"))),
                heading1_pagebreak=bool(
                    typography_data.get("heading1_pagebreak", data.get("heading1_pagebreak", True))
                ),
                margin_cm=float(typography_data.get("margin_cm", data.get("margin_cm", 2.5))),
            )

            merged_prompts = dict(DEFAULT_PROMPTS)
            if "prompts" in data and isinstance(data["prompts"], dict):
                merged_prompts.update(data["prompts"])
            if "user_style_rules" in data and not merged_prompts.get("user_style_rules"):
                merged_prompts["user_style_rules"] = data["user_style_rules"]

            cfg = cls(
                general=general,
                llm=llm,
                proxy=proxy,
                nlp=nlp,
                translation=translation,
                typography=typography,
                config_path=config_path,
                prompts=merged_prompts,
            )
            cfg.validate()
            return cfg
        except json.JSONDecodeError:
            return cls(config_path=config_path)
        except (PromptValidationError, ValueError):
            raise
        except Exception:
            return cls(config_path=config_path)

    def save_config(self, path: Path | None = None) -> None:
        config_path = path or getattr(self, "config_path", Path("tome.json"))
        config_dict = self.to_dict()
        config_path.write_text(json.dumps(config_dict, indent=2, ensure_ascii=False), encoding="utf-8")
