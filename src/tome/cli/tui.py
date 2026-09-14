import re
from pathlib import Path
from typing import Any, ClassVar

from rich.segment import Segment
from rich.style import Style
from textual.app import App, ComposeResult
from textual.containers import Container, Grid, Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.strip import Strip
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Select,
    Switch,
    TabbedContent,
    TabPane,
    TextArea,
)

from tome.config import AVAILABLE_LLM_MODELS, GENRE_TAXONOMIES, TomeConfig


class PromptEditor(TextArea):
    VAR_STYLE = Style.parse("bold #facc15")

    def _render_line(self, y: int) -> Strip:
        strip = super()._render_line(y)
        new_segments = []
        for seg in strip._segments:
            if not seg.text or "{" not in seg.text:
                new_segments.append(seg)
                continue
            matches = list(re.finditer(r"\{[^}\n]+\}", seg.text))
            if not matches:
                new_segments.append(seg)
                continue
            last_end = 0
            for m in matches:
                if m.start() > last_end:
                    new_segments.append(Segment(seg.text[last_end : m.start()], seg.style))
                combined = seg.style + self.VAR_STYLE if seg.style else self.VAR_STYLE
                new_segments.append(Segment(seg.text[m.start() : m.end()], combined))
                last_end = m.end()
            if last_end < len(seg.text):
                new_segments.append(Segment(seg.text[last_end:], seg.style))
        return Strip(new_segments, cell_length=strip.cell_length)


class TomeApp(App):
    TITLE = "Tome"
    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+q", "quit", "Quit"),
    ]

    CSS = """
    Screen {
        layout: vertical;
        background: #101010;
        color: #d4d4d4;
        scrollbar-background: #101010;
        scrollbar-background-hover: #141414;
        scrollbar-background-active: #181818;
        scrollbar-color: #242424;
        scrollbar-color-hover: #363636;
        scrollbar-color-active: #4a4a4a;
        scrollbar-corner-color: #101010;
    }
    * {
        scrollbar-background: #101010;
        scrollbar-background-hover: #141414;
        scrollbar-background-active: #181818;
        scrollbar-color: #242424;
        scrollbar-color-hover: #363636;
        scrollbar-color-active: #4a4a4a;
        scrollbar-corner-color: #101010;
    }
    Tooltip {
        background: #161616;
        color: #d0d0d0;
        border: solid #262626;
        padding: 0 1;
        max-width: 50;
    }
    Toast {
        background: #181818;
        color: #d4d4d4;
        border: solid #2a2a2a;
    }
    Toast .toast--title {
        color: #ffffff;
        text-style: bold;
    }
    Toast.-information {
        background: #181818;
        color: #d4d4d4;
        border: solid #2a2a2a;
        border-left: outer #555555;
    }
    Toast.-information .toast--title {
        color: #ffffff;
    }
    Toast.-warning {
        background: #181818;
        color: #d4d4d4;
        border: solid #2a2a2a;
        border-left: outer #d97706;
    }
    Toast.-warning .toast--title {
        color: #fbbf24;
    }
    Toast.-error {
        background: #181818;
        color: #d4d4d4;
        border: solid #2a2a2a;
        border-left: outer #dc2626;
    }
    Toast.-error .toast--title {
        color: #f87171;
    }
    Header {
        background: #101010;
        color: #b0b0b0;
    }
    Footer {
        background: #101010;
        color: #606060;
    }
    Tabs {
        background: #101010;
        border-bottom: solid #1e1e1e;
    }
    Tabs #tabs-list {
        align: center middle;
        width: 100%;
        background: #101010;
    }
    Tabs:focus .underline--bar {
        background: #4a4a4a;
    }
    .underline--bar {
        background: #333333;
    }
    Tab {
        color: #606060;
        background: #101010;
        padding: 0 3;
        margin: 0 1;
        min-width: 18;
    }
    Tab:hover {
        color: #a0a0a0;
        background: #101010;
    }
    Tab.-active {
        color: #e5e5e5;
        background: #101010;
        text-style: bold;
    }
    Switch {
        background: #101010;
        border: none;
        padding: 0;
        height: auto;
        width: auto;
    }
    Switch:focus {
        border: none;
        background: #101010;
    }
    Switch .switch--slider {
        color: #363636;
        background: #181818;
    }
    Switch:hover > .switch--slider {
        color: #444444;
    }
    Switch.-on .switch--slider {
        color: #c0c0c0;
        background: #242424;
    }
    Switch:hover.-on > .switch--slider {
        color: #d4d4d4;
        background: #2a2a2a;
    }
    #pipeline_scroll {
        height: 1fr;
        padding: 1 2;
        background: #101010;
    }
    #settings_scroll {
        height: 1fr;
        padding: 1 2;
        background: #101010;
    }
    #prompts_scroll {
        height: 1fr;
        padding: 1 2;
        background: #101010;
    }
    .section_title {
        color: #e0e0e0;
        text-style: bold;
        margin: 1 0;
    }
    .full_run_row {
        height: auto;
        margin-bottom: 1;
        background: #101010;
    }
    #btn_run_pipeline {
        width: 100%;
        text-style: bold;
        height: 3;
        background: #101010;
        border: solid #242424;
        color: #d4d4d4;
    }
    #btn_run_pipeline:hover {
        background: #141414;
        border: solid #2e2e2e;
        color: #e5e5e5;
    }
    #btn_run_pipeline:focus {
        border: solid #3e3e3e;
    }
    #tools_grid {
        grid-size: 4 2;
        grid-gutter: 1;
        height: auto;
        margin: 0 0 1 0;
        background: #101010;
    }
    .tool_btn {
        width: 100%;
        background: #101010;
        border: solid #202020;
        color: #a8a8a8;
    }
    .tool_btn:hover {
        background: #141414;
        border: solid #2a2a2a;
        color: #d4d4d4;
    }
    .tool_btn:focus {
        border: solid #3e3e3e;
    }
    #dashboard_box {
        layout: horizontal;
        height: 22;
        margin-top: 1;
        margin-bottom: 1;
        background: #101010;
    }
    #left_panel {
        width: 35%;
        border: solid #1e1e1e;
        background: #101010;
        padding: 1;
        height: 100%;
    }
    #right_panel {
        width: 65%;
        border: solid #1e1e1e;
        background: #101010;
        padding: 1;
        height: 100%;
    }
    .field_row {
        height: auto;
        margin-bottom: 1;
        background: #101010;
        align-vertical: middle;
    }
    .field_label {
        width: 24;
        color: #b5b5b5;
        text-style: bold;
    }
    .toggle_label {
        margin-left: 1;
        margin-right: 4;
        color: #b5b5b5;
        text-style: bold;
    }
    .prompt_label {
        width: 100%;
        color: #d4d4d4;
        text-style: bold;
        margin-top: 1;
        margin-bottom: 0;
    }
    .config_input {
        width: 1fr;
        background: #101010;
        border: solid #202020;
        color: #d4d4d4;
    }
    .config_input:focus {
        border: solid #3e3e3e;
        background: #101010;
    }
    Select {
        border: none;
        background: #101010;
        padding: 0;
        height: auto;
    }
    Select:focus {
        border: none;
        background: #101010;
    }
    SelectCurrent {
        background: #101010;
        border: solid #202020;
        color: #d4d4d4;
    }
    SelectCurrent:focus {
        border: solid #3e3e3e;
    }
    SelectOverlay {
        background: #141414;
        border: solid #262626;
    }
    OptionList {
        background: #141414;
    }
    OptionList:focus {
        background: #141414;
    }
    .config_select {
        width: 1fr;
        background: #101010;
    }
    .prompt_area {
        height: 7;
        margin: 0 0 1 0;
        background: #101010;
        border: solid #202020;
        color: #d4d4d4;
    }
    .prompt_area:focus {
        border: solid #3e3e3e;
    }
    .save_btn {
        width: 100%;
        margin-top: 1;
        margin-bottom: 1;
        text-style: bold;
        height: 3;
        background: #101010;
        border: solid #242424;
        color: #d4d4d4;
    }
    .save_btn:hover {
        background: #141414;
        border: solid #2e2e2e;
        color: #e5e5e5;
    }
    .save_btn:focus {
        border: solid #3e3e3e;
    }
    #chapters_log {
        height: 1fr;
        background: #101010;
    }
    #live_logs {
        height: 1fr;
        background: #101010;
    }
    """

    def __init__(self, initial_path: str = "", config: TomeConfig | None = None) -> None:
        super().__init__()
        self.initial_path = initial_path
        self.config = config or TomeConfig.load_config()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent():
            with TabPane("Pipeline & Tools", id="tab_pipeline"), VerticalScroll(id="pipeline_scroll"):
                yield Label("Book Configuration", classes="section_title")
                with Horizontal(classes="field_row"):
                    yield Label("Target Manuscript:", classes="field_label")
                    yield Input(
                        value=self.initial_path,
                        placeholder="Path to PDF, EPUB, MOBI, MD, or TXT",
                        id="input_path",
                        classes="config_input",
                        tooltip="Path to input book manuscript (PDF, EPUB, MOBI, MD, TXT)",
                    )
                with Horizontal(classes="field_row"):
                    yield Label("Output Directory:", classes="field_label")
                    yield Input(
                        value=str(self.config.output_dir),
                        id="input_output",
                        classes="config_input",
                        tooltip="Directory where extracted chapters, graphs, and translations are saved",
                    )
                with Horizontal(classes="field_row"):
                    yield Label("Genre Taxonomy:", classes="field_label")
                    genre_options = [("Auto Detect", "auto")] + [
                        (g.replace("_", " ").capitalize(), g) for g in GENRE_TAXONOMIES
                    ]
                    yield Select(
                        options=genre_options,
                        value=self.config.genre,
                        id="select_genre",
                        classes="config_select",
                        tooltip="Preset genre taxonomy used for NER entity extraction",
                    )
                with Horizontal(classes="field_row"):
                    yield Switch(
                        value=not self.config.skip_gliner,
                        id="switch_gliner",
                        tooltip="Extract entities (characters, places, items) using local GLiNER model",
                    )
                    yield Label("English NLP (GLiNER)", classes="toggle_label")
                    yield Switch(
                        value=self.config.persian_nlp,
                        id="switch_persian_nlp",
                        tooltip="Run Persian NLP copyeditor (Shekar normalizer, half-spaces, quotes, and typography)",
                    )
                    yield Label("Persian NLP (Shekar)", classes="toggle_label")
                    yield Switch(
                        value=self.config.refine_metadata,
                        id="switch_refine_metadata",
                        tooltip="Refine and clean book metadata via LLM",
                    )
                    yield Label("Refine Metadata (LLM)", classes="toggle_label")
                    yield Switch(
                        value=self.config.extract_images,
                        id="switch_extract_images",
                        tooltip="Extract illustrations and figures from PDF/EPUB manuscripts",
                    )
                    yield Label("Extract Illustrations", classes="toggle_label")
                    yield Switch(
                        value=self.config.keep_raw_artifacts,
                        id="switch_keep_raw",
                        tooltip="Preserve raw page numbers, running headers, and footers without stripping",
                    )
                    yield Label("Keep Raw Artifacts", classes="toggle_label")
                    yield Switch(
                        value=self.config.fast_mode,
                        id="switch_fast",
                        tooltip="Enable fast mode with dialogue filtering to reduce CPU load",
                    )
                    yield Label("Fast Mode", classes="toggle_label")

                yield Label("Operations & Execution", classes="section_title")
                with Horizontal(classes="full_run_row"):
                    yield Button(
                        "Run Full Pipeline",
                        variant="default",
                        id="btn_run_pipeline",
                        tooltip="Ingest, sanitize, chapterize, extract entities, and build relationship graph",
                    )
                with Grid(id="tools_grid"):
                    yield Button(
                        "1. Convert to Markdown",
                        variant="default",
                        id="btn_convert",
                        classes="tool_btn",
                        tooltip="Convert any input (PDF, EPUB, MOBI, TXT) to full clean Markdown",
                    )
                    yield Button(
                        "2. Detect Genre",
                        variant="default",
                        id="btn_detect_genre",
                        classes="tool_btn",
                        tooltip="Detect literary genre from manuscript content automatically",
                    )
                    yield Button(
                        "3. Segment Chapters",
                        variant="default",
                        id="btn_chapterize",
                        classes="tool_btn",
                        tooltip="Split Markdown into individual chapters and consolidate fragments under 512 bytes",
                    )
                    yield Button(
                        "4. Setup GLiNER Model",
                        variant="default",
                        id="btn_setup_model",
                        classes="tool_btn",
                        tooltip="Pre-download and cache the GLiNER model locally",
                    )
                    yield Button(
                        "5. Build Character Graph",
                        variant="default",
                        id="btn_graph",
                        classes="tool_btn",
                        tooltip="Generate Mermaid narrative relationship network and scene presence matrix",
                    )
                    yield Button(
                        "6. Ingest Entities",
                        variant="default",
                        id="btn_ingest",
                        classes="tool_btn",
                        tooltip="Ingest LLM entity delimiter blocks and merge new entities into glossary.md",
                    )
                    yield Button(
                        "7. Translate Chapters",
                        variant="default",
                        id="btn_translate",
                        classes="tool_btn",
                        tooltip="Translate segmented chapters into target language using bilingual glossary",
                    )
                    yield Button(
                        "8. Persian NLP (Shekar)",
                        variant="default",
                        id="btn_persian_nlp",
                        classes="tool_btn",
                        tooltip="Run Persian NLP copyeditor (Shekar normalizer, half-spaces, typography) on target",
                    )

                with Container(id="dashboard_box"):
                    with Vertical(id="left_panel"):
                        yield Label("Discovered Chapters:", classes="field_label")
                        yield RichLog(id="chapters_log", highlight=True, markup=True)
                    with Vertical(id="right_panel"):
                        yield Label("Live Execution Log:", classes="field_label")
                        yield RichLog(id="live_logs", highlight=True, markup=True)

            with TabPane("Settings & LLM", id="tab_settings"), VerticalScroll(id="settings_scroll"):
                yield Label("API & Model Credentials", classes="section_title")
                with Horizontal(classes="field_row"):
                    yield Label("LLM Endpoint:", classes="field_label")
                    yield Input(
                        value=self.config.llm_base_url,
                        id="cfg_llm_url",
                        classes="config_input",
                        tooltip="Base URL for OpenAI-compatible LLM endpoint",
                    )
                with Horizontal(classes="field_row"):
                    yield Label("API Key:", classes="field_label")
                    yield Input(
                        value=self.config.llm_api_key,
                        password=True,
                        id="cfg_llm_key",
                        classes="config_input",
                        tooltip="Authorization Bearer API Key",
                    )
                with Horizontal(classes="field_row"):
                    yield Label("Model Name:", classes="field_label")
                    known_models = {val for val, _ in AVAILABLE_LLM_MODELS if val != "custom"}
                    initial_model_val = self.config.llm_model if self.config.llm_model in known_models else "custom"
                    model_options = [(label, val) for val, label in AVAILABLE_LLM_MODELS]
                    yield Select(
                        options=model_options,
                        value=initial_model_val,
                        id="select_llm_model",
                        classes="config_select",
                        tooltip="Select pre-configured AvalAI model or Custom Model",
                    )
                with Horizontal(classes="field_row", id="row_custom_model"):
                    yield Label("Custom Model:", classes="field_label")
                    yield Input(
                        value=self.config.llm_model if initial_model_val == "custom" else "",
                        id="cfg_custom_model",
                        classes="config_input",
                        tooltip="Custom model identifier (e.g. qwen3-8b, mistral-large)",
                    )
                with Horizontal(classes="field_row"):
                    yield Label("Target Language:", classes="field_label")
                    yield Input(
                        value=self.config.target_language,
                        id="cfg_target_lang",
                        classes="config_input",
                        tooltip="Destination language for translation (e.g. Persian, Spanish, French)",
                    )

                yield Label("Typography & Word (.docx) Export", classes="section_title")
                with Horizontal(classes="field_row"):
                    yield Switch(
                        value=self.config.compile_docx,
                        id="cfg_compile_docx",
                        tooltip="Automatically compile translated chapters into a unified Word (.docx) book",
                    )
                    yield Label("Auto-Compile Word (.docx)", classes="toggle_label")
                with Horizontal(classes="field_row"):
                    yield Label("Eastern Font:", classes="field_label")
                    yield Input(
                        value=self.config.eastern_font,
                        id="cfg_eastern_font",
                        classes="config_input",
                        tooltip="Eastern typeface name, TTF filename, or path (e.g. B-Nazanin.ttf or Vazirmatn)",
                    )
                with Horizontal(classes="field_row"):
                    yield Label("Western Font:", classes="field_label")
                    yield Input(
                        value=self.config.western_font,
                        id="cfg_western_font",
                        classes="config_input",
                        tooltip="Western typeface name, TTF filename, or path (e.g. Times.ttf or Times New Roman)",
                    )

                yield Label("Inference & Performance", classes="section_title")
                with Horizontal(classes="field_row"):
                    yield Label("Batch Size:", classes="field_label")
                    yield Input(
                        value=str(self.config.translation_batch_size),
                        id="cfg_trans_batch",
                        classes="config_input",
                        tooltip="Concurrency batch size for translation requests",
                    )
                with Horizontal(classes="field_row"):
                    yield Label("Timeout (Seconds):", classes="field_label")
                    yield Input(
                        value=str(self.config.llm_timeout),
                        id="cfg_llm_timeout",
                        classes="config_input",
                        tooltip="Socket timeout in seconds for long completions",
                    )
                with Horizontal(classes="field_row"):
                    yield Label("Reasoning Effort:", classes="field_label")
                    yield Select(
                        [("Max", "max"), ("High", "high"), ("Medium", "medium"), ("Low", "low")],
                        value=self.config.llm_reasoning_effort,
                        id="cfg_reasoning_effort",
                        classes="config_select",
                        tooltip="Select reasoning effort depth for thinking models",
                    )
                with Horizontal(classes="field_row"):
                    yield Switch(
                        value=self.config.llm_thinking,
                        id="cfg_llm_thinking",
                        tooltip="Enable deep reasoning and internal thought tokens before generating output",
                    )
                    yield Label("Enable Thinking", classes="toggle_label")
                    yield Switch(
                        value=self.config.stream_response,
                        id="cfg_stream_response",
                        tooltip="Stream response chunks live as tokens are generated",
                    )
                    yield Label("Stream LLM Response", classes="toggle_label")

                yield Label("Network & Proxy Configuration", classes="section_title")
                with Horizontal(classes="field_row"):
                    yield Switch(
                        value=self.config.proxy_enabled,
                        id="cfg_proxy_enabled",
                        tooltip="Route API requests through the configured SOCKS5 or HTTP proxy",
                    )
                    yield Label("Enable Proxy", classes="toggle_label")
                with Horizontal(classes="field_row"):
                    yield Label("Proxy Type:", classes="field_label")
                    yield Select(
                        [("SOCKS5", "socks5"), ("HTTP", "http")],
                        value=self.config.proxy_type,
                        id="cfg_proxy_type",
                        classes="config_select",
                        tooltip="Proxy protocol type",
                    )
                with Horizontal(classes="field_row"):
                    yield Label("Proxy Host:", classes="field_label")
                    yield Input(
                        value=self.config.proxy_host,
                        id="cfg_proxy_host",
                        classes="config_input",
                        tooltip="Proxy IP address or hostname",
                    )
                with Horizontal(classes="field_row"):
                    yield Label("Proxy Port:", classes="field_label")
                    yield Input(
                        value=str(self.config.proxy_port),
                        id="cfg_proxy_port",
                        classes="config_input",
                        tooltip="Proxy connection port",
                    )

                yield Button(
                    "Save Settings to tome.json",
                    variant="default",
                    id="btn_save_settings",
                    classes="save_btn",
                    tooltip="Persist settings to tome.json",
                )

            with TabPane("System Prompts", id="tab_prompts"), VerticalScroll(id="prompts_scroll"):
                yield Label("System & Localization Prompts", classes="section_title")
                yield Label("User Style Guide & Translation Rules:", classes="prompt_label")
                yield PromptEditor(self.config.user_style_rules, id="prompt_style_rules", classes="prompt_area")
                yield Label("Glossary Translation System Prompt:", classes="prompt_label")
                yield PromptEditor(
                    self.config.prompts.get("glossary_translation_system_prompt", ""),
                    id="prompt_glossary",
                    classes="prompt_area",
                )
                yield Label("Chapter Translation with Glossary Prompt:", classes="prompt_label")
                yield PromptEditor(
                    self.config.prompts.get("chapter_translation_with_glossary_system_prompt", ""),
                    id="prompt_chapter_glossary",
                    classes="prompt_area",
                )
                yield Label("Chapter Translation without GLiNER Prompt:", classes="prompt_label")
                yield PromptEditor(
                    self.config.prompts.get("chapter_translation_no_gliner_system_prompt", ""),
                    id="prompt_chapter_nogliner",
                    classes="prompt_area",
                )
                yield Label("Fantasy Localization Guidelines (Applied when genre is fantasy):", classes="prompt_label")
                yield PromptEditor(
                    self.config.prompts.get("fantasy_translation_guidelines", ""),
                    id="prompt_fantasy_guidelines",
                    classes="prompt_area",
                )
                yield Label("Metadata Refinement & Cleaning System Prompt:", classes="prompt_label")
                yield PromptEditor(
                    self.config.prompts.get("metadata_refinement_system_prompt", ""),
                    id="prompt_metadata_refinement",
                    classes="prompt_area",
                )
                yield Button(
                    "Save Prompts & Rules to tome.json",
                    variant="default",
                    id="btn_save_prompts",
                    classes="save_btn",
                    tooltip="Persist system prompts and style rules to tome.json",
                )

        yield Footer()

    def on_mount(self) -> None:
        known_models = {val for val, _ in AVAILABLE_LLM_MODELS if val != "custom"}
        is_custom = self.config.llm_model not in known_models
        try:
            self.query_one("#row_custom_model").display = is_custom
        except NoMatches:
            pass

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "select_llm_model":
            is_custom = event.value == "custom"
            try:
                self.query_one("#row_custom_model").display = is_custom
            except NoMatches:
                pass
        elif event.select.id == "select_genre":
            self.config.genre = str(event.value)
            self.config.save_config()
            self.notify("Genre setting saved.", title="Saved", timeout=1.5)

    def on_switch_changed(self, event: Switch.Changed) -> None:
        sid = event.switch.id
        if sid == "switch_gliner":
            self.config.skip_gliner = not event.value
            self.config.save_config()
            self.notify("GLiNER setting saved.", title="Saved", timeout=1.5)
        elif sid == "switch_persian_nlp":
            self.config.persian_nlp = bool(event.value)
            self.config.save_config()
            self.notify("Persian NLP setting saved.", title="Saved", timeout=1.5)
        elif sid == "switch_keep_raw":
            self.config.keep_raw_artifacts = bool(event.value)
            self.config.save_config()
            self.notify("Artifacts setting saved.", title="Saved", timeout=1.5)
        elif sid == "switch_fast":
            self.config.fast_mode = bool(event.value)
            self.config.save_config()
            self.notify("Fast mode setting saved.", title="Saved", timeout=1.5)
        elif sid == "switch_refine_metadata":
            self.config.refine_metadata = bool(event.value)
            self.config.save_config()
            self.notify("Metadata refinement setting saved.", title="Saved", timeout=1.5)
        elif sid == "switch_extract_images":
            self.config.extract_images = bool(event.value)
            self.config.save_config()
            self.notify("Image extraction setting saved.", title="Saved", timeout=1.5)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "input_output":
            val = event.value.strip()
            if val:
                self.config.output_dir = Path(val)
                self.config.save_config()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        logs = self.query_one("#live_logs", RichLog)

        if event.button.id == "btn_save_settings":
            self.config.llm_base_url = self.query_one("#cfg_llm_url", Input).value.strip()
            self.config.llm_api_key = self.query_one("#cfg_llm_key", Input).value.strip()
            selected_model = str(self.query_one("#select_llm_model", Select).value)
            if selected_model == "custom":
                custom_name = self.query_one("#cfg_custom_model", Input).value.strip()
                self.config.llm_model = custom_name or "qwen3.8-flash"
            else:
                self.config.llm_model = selected_model
            self.config.target_language = self.query_one("#cfg_target_lang", Input).value.strip()
            self.config.compile_docx = self.query_one("#cfg_compile_docx", Switch).value
            e_font_val = self.query_one("#cfg_eastern_font", Input).value.strip() or "B Nazanin"
            w_font_val = self.query_one("#cfg_western_font", Input).value.strip() or "Times New Roman"
            self.config.eastern_font = e_font_val
            self.config.western_font = w_font_val

            from tome.core.docx import resolve_font

            font_warns: list[str] = []
            resolve_font(e_font_val, default_name="B Nazanin", warning_handler=font_warns.append)
            resolve_font(w_font_val, default_name="Times New Roman", warning_handler=font_warns.append)
            for fw in font_warns:
                self.notify(fw, title="Font Notice", severity="warning")

            self.config.llm_thinking = self.query_one("#cfg_llm_thinking", Switch).value
            self.config.llm_reasoning_effort = str(self.query_one("#cfg_reasoning_effort", Select).value)
            try:
                self.config.translation_batch_size = int(self.query_one("#cfg_trans_batch", Input).value.strip())
            except ValueError:
                pass
            try:
                self.config.llm_timeout = int(self.query_one("#cfg_llm_timeout", Input).value.strip())
            except ValueError:
                pass
            self.config.stream_response = self.query_one("#cfg_stream_response", Switch).value
            self.config.proxy_enabled = self.query_one("#cfg_proxy_enabled", Switch).value
            self.config.proxy_type = str(self.query_one("#cfg_proxy_type", Select).value)
            self.config.proxy_host = self.query_one("#cfg_proxy_host", Input).value.strip()
            try:
                self.config.proxy_port = int(self.query_one("#cfg_proxy_port", Input).value.strip())
            except ValueError:
                pass
            self.config.save_config()
            self.notify("Configuration saved to tome.json!", title="Saved")

        elif event.button.id == "btn_save_prompts":
            self.config.user_style_rules = self.query_one("#prompt_style_rules", PromptEditor).text
            self.config.prompts["glossary_translation_system_prompt"] = self.query_one(
                "#prompt_glossary", PromptEditor
            ).text
            self.config.prompts["chapter_translation_with_glossary_system_prompt"] = self.query_one(
                "#prompt_chapter_glossary", PromptEditor
            ).text
            self.config.prompts["chapter_translation_no_gliner_system_prompt"] = self.query_one(
                "#prompt_chapter_nogliner", PromptEditor
            ).text
            self.config.prompts["fantasy_translation_guidelines"] = self.query_one(
                "#prompt_fantasy_guidelines", PromptEditor
            ).text
            self.config.prompts["metadata_refinement_system_prompt"] = self.query_one(
                "#prompt_metadata_refinement", PromptEditor
            ).text
            self.config.save_config()
            self.notify("System prompts and style rules saved to tome.json!", title="Saved")

        elif event.button.id == "btn_run_pipeline":
            path_str = self.query_one("#input_path", Input).value.strip()
            if not path_str:
                logs.write("[bold red]Please specify an input book file or directory.[/]")
                return
            if not Path(path_str).exists():
                logs.write(f"[bold red]File or directory not found: {path_str}[/]")
                return
            self._sync_pipeline_config()
            self.run_worker(lambda: self._execute_pipeline(Path(path_str)), thread=True)

        elif event.button.id == "btn_translate":
            path_str = self.query_one("#input_path", Input).value.strip()
            if not path_str:
                logs.write("[bold red]Please specify a book directory or file to translate.[/]")
                return
            book_dir = Path(path_str)
            if not book_dir.is_dir():
                book_dir = self.config.output_dir / book_dir.stem
            if not book_dir.exists():
                logs.write(f"[bold red]Target directory not found: {book_dir}[/]")
                return
            chapters_dir = book_dir / "chapters"
            if not chapters_dir.exists() or not list(chapters_dir.glob("*.md")):
                logs.write(f"[bold red]No chapters found in {chapters_dir}[/]")
                return
            self._sync_pipeline_config()
            self.run_worker(lambda: self._execute_translation(book_dir), thread=True)

        elif event.button.id == "btn_detect_genre":
            path_str = self.query_one("#input_path", Input).value.strip()
            if not path_str:
                logs.write("[bold red]Please specify a book file path for genre detection.[/]")
                return
            self.run_worker(lambda: self._execute_genre_detect(Path(path_str)), thread=True)

        elif event.button.id == "btn_convert":
            path_str = self.query_one("#input_path", Input).value.strip()
            if not path_str:
                logs.write("[bold red]Please specify an input manuscript path (PDF, EPUB, MOBI, TXT).[/]")
                return
            self.run_worker(lambda: self._execute_convert_to_markdown(Path(path_str)), thread=True)

        elif event.button.id == "btn_chapterize":
            path_str = self.query_one("#input_path", Input).value.strip()
            if not path_str:
                logs.write("[bold red]Please specify a Markdown file path.[/]")
                return
            self.run_worker(lambda: self._execute_chapterize(Path(path_str)), thread=True)

        elif event.button.id == "btn_persian_nlp":
            path_str = self.query_one("#input_path", Input).value.strip()
            if not path_str:
                logs.write("[bold red]Please specify a chapter file or directory for Persian NLP.[/]")
                return
            self.run_worker(lambda: self._execute_persian_nlp(Path(path_str)), thread=True)

        elif event.button.id == "btn_graph":
            path_str = self.query_one("#input_path", Input).value.strip()
            if not path_str:
                logs.write("[bold red]Please specify a book directory or chapters folder.[/]")
                return
            self.run_worker(lambda: self._execute_build_graph(Path(path_str)), thread=True)

        elif event.button.id == "btn_ingest":
            path_str = self.query_one("#input_path", Input).value.strip()
            if not path_str:
                logs.write("[bold red]Please specify a translated chapter file path.[/]")
                return
            self.run_worker(lambda: self._execute_ingest(Path(path_str)), thread=True)

        elif event.button.id == "btn_setup_model":
            self.run_worker(self._execute_setup_model, thread=True)

    def _sync_pipeline_config(self) -> None:
        out_val = self.query_one("#input_output", Input).value.strip()
        if out_val:
            self.config.output_dir = Path(out_val)
        self.config.genre = str(self.query_one("#select_genre", Select).value)
        self.config.skip_gliner = not self.query_one("#switch_gliner", Switch).value
        self.config.persian_nlp = self.query_one("#switch_persian_nlp", Switch).value
        self.config.fast_mode = self.query_one("#switch_fast", Switch).value
        self.config.keep_raw_artifacts = self.query_one("#switch_keep_raw", Switch).value
        self.config.refine_metadata = self.query_one("#switch_refine_metadata", Switch).value
        self.config.extract_images = self.query_one("#switch_extract_images", Switch).value
        self.config.save_config()

    def _execute_pipeline(self, book_path: Path) -> None:
        from tome.core.pipeline import run_pipeline

        logs = self.query_one("#live_logs", RichLog)
        chapters_log = self.query_one("#chapters_log", RichLog)

        def observer(event_type: str, data: Any) -> None:
            if event_type == "stage_start":
                logs.write(f"[bold cyan]Starting {data.get('stage')}[/]")
            elif event_type == "conversion_complete":
                logs.write(f"[green]Manuscript converted ({data.get('page_count')} pages) [Progress: 25%][/]")
            elif event_type == "images_extracted":
                cnt = data.get("image_count", 0)
                dur = data.get("duration", 0)
                if cnt > 0:
                    logs.write(f"[green]Extracted {cnt} illustrations in {dur}s[/]")
                else:
                    logs.write(f"[dim]No illustrations found ({dur}s)[/]")
            elif event_type == "genre_detected":
                logs.write(f"[magenta]Detected Genre: {data.get('genre')}[/]")
            elif event_type == "chapterization_complete":
                logs.write(f"[green]Found {data.get('chapter_count')} chapters [Progress: 50%][/]")
                for ch in data.get("chapters", []):
                    chapters_log.write(f"- {ch.title}")
            elif event_type == "extraction_progress":
                pct = int(50 + (data["current"] / max(data["total"], 1)) * 45)
                logs.write(f"GLiNER chunk {data['current']}/{data['total']} [Progress: {pct}%]")
            elif event_type == "extraction_complete":
                logs.write(
                    f"[green]Extracted {data.get('entity_count')} entities in {data.get('duration')}s [Progress: 95%][/]"
                )
            elif event_type == "pipeline_complete":
                logs.write("[bold green]Book processing complete! [Progress: 100%][/]")

        try:
            run_pipeline(book_path, self.config, observer=observer)
        except Exception as err:
            logs.write(f"[bold red]Execution error: {err}[/]")

    def _execute_translation(self, book_dir: Path) -> None:
        from tome.core.translator import translate_book

        logs = self.query_one("#live_logs", RichLog)

        def observer(event_type: str, data: Any) -> None:
            if event_type == "stage_start" and data.get("stage") == "glossary_translation":
                logs.write(f"[magenta]Translating bilingual glossary ({data.get('count')} entries)[/]")
            elif event_type == "glossary_translation_complete":
                logs.write(f"[green]Glossary translated and saved to {data.get('path')} in {data.get('duration')}s[/]")
            elif event_type == "chapter_translation_start":
                idx = data.get("index", 1)
                total = max(data.get("total", 1), 1)
                pct = int(((idx - 1) / total) * 100)
                logs.write(f"[cyan]Translating chapter [{idx}/{total}]: {data.get('chapter')} [Progress: {pct}%][/]")
            elif event_type == "glossary_translation_complete":
                logs.write(f"[bold green]• Bilingual glossary translated in {data.get('duration')}s[/]")
            elif event_type == "persian_nlp_complete":
                logs.write(f"[bold cyan]• NLP Processing:[/] {data.get('chapter')} -> [dim]{data.get('stats')}[/dim]")
            elif event_type == "docx_compilation_start":
                logs.write(f"[bold magenta]‣ Compiling {data.get('file_count')} chapters into Word (.docx)[/]")
            elif event_type == "docx_compilation_complete":
                logs.write(f"[bold green]• Word manuscript compiled and saved to: {data.get('path')}[/]")
            elif event_type == "pdf_compilation_complete":
                logs.write(f"[bold green]• PDF manuscript compiled and saved to: {data.get('path')}[/]")
            elif event_type == "docx_compilation_error":
                logs.write(f"[bold red]Word compilation error: {data.get('error')}[/]")
            elif event_type == "officecli_download_start":
                logs.write(f"[yellow]‣ Downloading OfficeCLI from {data.get('url')}[/]")
            elif event_type == "officecli_download_complete":
                logs.write(f"[bold green]• OfficeCLI installed to {data.get('path')}[/]")
            elif event_type == "docx_warning":
                logs.write(f"[bold yellow]{data.get('warning')}[/]")
            elif event_type == "avalai_credit_info":
                rem_toman = data.get("remaining_irt", data.get("remaining_toman", 0))
                logs.write(f"[bold cyan]• Account Connected:[/] Balance: {rem_toman:,.0f} Toman")
            elif event_type == "wallet_warning":
                logs.write(f"[bold yellow]• {data.get('warning')}[/]")
            elif event_type == "wallet_empty":
                logs.write(f"[bold red]• {data.get('error')}[/]")
            elif event_type == "rate_limit_wait":
                logs.write(f"[yellow]• Rate limit reached. Backing off for {data.get('wait_seconds', 15):.1f}s[/]")
            elif event_type == "chapter_translation_complete":
                idx = data.get("index", 1)
                total = max(data.get("total", 1), 1)
                pct = int((idx / total) * 100)
                toks_info = ""
                if data.get("tokens"):
                    val_toman = data.get("cost_toman", data.get("cost_irt", 0))
                    toks_info = f" | {data.get('tokens', 0):,} toks | ~{val_toman:,.0f} Toman"
                logs.write(
                    f"[green]• Chapter {data.get('chapter')} translated in {data.get('duration')}s{toks_info} [Progress: {pct}%][/]"
                )
            elif event_type == "translation_metrics":
                tot_toman = data.get("total_cost_toman", data.get("total_cost_irt", 0))
                logs.write(
                    f"[bold green]• Total Cost: {tot_toman:,.0f} Toman | Tokens: {data.get('total_tokens', 0):,} | Avg: {data.get('average_duration_seconds', 0):.1f}s/ch[/]"
                )
                used_toman = data.get("consumed_credit_toman", data.get("consumed_credit_irt", 0))
                if used_toman:
                    logs.write(
                        f"[bold magenta]• Wallet Credit Used: {used_toman:,.0f} Toman ({data.get('consumed_credit_percent', 0):.2f}%)[/]"
                    )
            elif event_type == "llm_reasoning_chunk":
                logs.write(f"[dim]{data}[/dim]")

        try:
            outputs, _timings = translate_book(book_dir, self.config, observer=observer)
            logs.write(f"[bold green]Translation complete! {len(outputs)} chapters translated [Progress: 100%][/]")
        except Exception as err:
            logs.write(f"[bold red]Translation error: {err}[/]")

    def _execute_genre_detect(self, file_path: Path) -> None:
        from tome.config import detect_genre

        logs = self.query_one("#live_logs", RichLog)
        if not file_path.exists():
            logs.write(f"[bold red]File not found: {file_path}[/]")
            return

        try:
            if file_path.suffix.lower() == ".pdf":
                import pdf_inspector

                res = pdf_inspector.process_pdf(str(file_path))
                text = res.markdown or ""
            else:
                text = file_path.read_text(encoding="utf-8", errors="ignore")

            detected = detect_genre(text)
            logs.write(f"[bold green]Detected Genre: {detected.replace('_', ' ').title()}[/]")
            self.query_one("#select_genre", Select).value = detected
        except Exception as err:
            logs.write(f"[bold red]Genre detection failed: {err}[/]")

    def _execute_convert_to_markdown(self, input_path: Path) -> None:
        from tome.core.cleaner import clean_markdown_text
        from tome.core.converter import convert_pdf_to_markdown
        from tome.core.epub_converter import convert_epub_to_pdf, convert_mobi_to_pdf

        logs = self.query_one("#live_logs", RichLog)
        if not input_path.exists():
            logs.write(f"[bold red]File not found: {input_path}[/]")
            return

        out_dir = Path(self.query_one("#input_output", Input).value.strip())
        keep_raw = self.query_one("#switch_keep_raw", Switch).value
        try:
            pdf_path = input_path
            suffix = input_path.suffix.lower()
            if suffix in (".epub", ".mobi", ".azw3", ".cbz", ".cbr"):
                logs.write(f"[cyan]Converting {input_path.name} to PDF intermediate[/]")
                if suffix == ".mobi":
                    pdf_path = convert_mobi_to_pdf(input_path, out_dir / "converted_intermediate.pdf")
                else:
                    pdf_path = convert_epub_to_pdf(input_path, out_dir / "converted_intermediate.pdf")

            if pdf_path.suffix.lower() == ".pdf":
                logs.write(f"[cyan]Extracting Markdown from: {pdf_path.name}[/]")
                md_path, meta = convert_pdf_to_markdown(pdf_path, out_dir)
                if not keep_raw:
                    cleaned = clean_markdown_text(md_path.read_text(encoding="utf-8"))
                    md_path.write_text(cleaned, encoding="utf-8")
                logs.write(f"[bold green]Saved Markdown to {md_path} ({meta.get('page_count', 0)} pages)[/]")
            else:
                out_dir.mkdir(parents=True, exist_ok=True)
                md_path = out_dir / "book.md"
                content = input_path.read_text(encoding="utf-8")
                if not keep_raw:
                    content = clean_markdown_text(content)
                md_path.write_text(content, encoding="utf-8")
                logs.write(f"[bold green]Saved Markdown manuscript to {md_path}[/]")
        except Exception as err:
            logs.write(f"[bold red]Conversion to Markdown failed: {err}[/]")

    def _execute_chapterize(self, md_path: Path) -> None:
        from tome.core.chapterizer import segment_chapters

        logs = self.query_one("#live_logs", RichLog)
        chapters_log = self.query_one("#chapters_log", RichLog)
        if not md_path.exists():
            logs.write(f"[bold red]File not found: {md_path}[/]")
            return

        out_dir = Path(self.query_one("#input_output", Input).value.strip()) / "chapters"
        keep_raw = self.query_one("#switch_keep_raw", Switch).value
        try:
            logs.write(f"[cyan]Segmenting chapters from {md_path.name}[/]")
            text = md_path.read_text(encoding="utf-8")
            chapters = segment_chapters(text, out_dir, keep_raw_artifacts=keep_raw)
            chapters_log.clear()
            for ch in chapters:
                chapters_log.write(f"- {ch.title}")
            logs.write(f"[bold green]Segmented {len(chapters)} chapters into {out_dir}[/]")
        except Exception as err:
            logs.write(f"[bold red]Chapterization failed: {err}[/]")

    def _execute_persian_nlp(self, target_path: Path) -> None:
        from tome.core.editor import copyedit_persian_chapter

        logs = self.query_one("#live_logs", RichLog)
        if not target_path.exists():
            logs.write(f"[bold red]File or directory not found: {target_path}[/]")
            return

        try:
            if target_path.is_file():
                logs.write(f"[cyan]Running Persian NLP (Shekar) on {target_path.name}[/]")
                res_path, stats = copyedit_persian_chapter(target_path)
                logs.write(f"[bold green]Persian NLP complete for {res_path.name}: {stats.summary()}[/]")
            elif target_path.is_dir():
                md_files = sorted(target_path.glob("*.md"))
                if not md_files:
                    logs.write(f"[bold red]No Markdown files found in {target_path}[/]")
                    return
                logs.write(f"[cyan]Running Persian NLP (Shekar) on {len(md_files)} chapters[/]")
                for f in md_files:
                    _, stats = copyedit_persian_chapter(f)
                    logs.write(f"[green]• {f.name}: {stats.summary()}[/]")
                logs.write(f"[bold green]Persian NLP complete for {len(md_files)} chapters in {target_path}[/]")
        except Exception as err:
            logs.write(f"[bold red]Persian NLP execution failed: {err}[/]")

    def _execute_build_graph(self, book_dir: Path) -> None:
        from tome.core.graph import build_character_graph
        from tome.models import Chapter, Entity

        logs = self.query_one("#live_logs", RichLog)
        chapters_dir = book_dir / "chapters" if (book_dir / "chapters").exists() else book_dir
        if not chapters_dir.exists():
            logs.write(f"[bold red]Chapters directory not found: {chapters_dir}[/]")
            return

        gloss_path = (
            book_dir / "glossary.md" if (book_dir / "glossary.md").exists() else chapters_dir.parent / "glossary.md"
        )
        out_path = book_dir / "graph.md"
        try:
            logs.write(f"[cyan]Generating Character Relationship Graph for {book_dir.name}[/]")
            chapters = []
            for f in sorted(chapters_dir.glob("*.md")):
                if f.name != "book.md":
                    chapters.append(
                        Chapter(index=len(chapters), title=f.stem, slug=f.stem, content=f.read_text(encoding="utf-8"))
                    )

            entities = []
            if gloss_path.exists():
                for line in gloss_path.read_text(encoding="utf-8").splitlines():
                    if line.startswith("|") and not line.startswith("| Canonical") and not line.startswith("|---"):
                        cols = [c.strip() for c in line.split("|")[1:-1]]
                        if len(cols) >= 2 and cols[0]:
                            aliases = {
                                a.strip() for a in cols[1].split(",") if a.strip() and a not in ("-", "--", "\u2014")
                            }
                            entities.append(Entity(canonical=cols[0], category="People & Characters", aliases=aliases))

            build_character_graph(chapters, entities, out_path)
            logs.write(f"[bold green]Character Relationship Graph saved to {out_path}[/]")
        except Exception as err:
            logs.write(f"[bold red]Graph generation failed: {err}[/]")

    def _execute_ingest(self, chapter_path: Path) -> None:
        from tome.core.glossary import ingest_chapter_delimiter_entities, write_glossary_markdown

        logs = self.query_one("#live_logs", RichLog)
        if not chapter_path.exists():
            logs.write(f"[bold red]Chapter file not found: {chapter_path}[/]")
            return

        gloss_path = chapter_path.parent.parent / "glossary.md"
        try:
            logs.write(f"[cyan]Ingesting delimiter entities from {chapter_path.name}[/]")
            cleaned, entities = ingest_chapter_delimiter_entities(chapter_path.read_text(encoding="utf-8"))
            chapter_path.write_text(cleaned, encoding="utf-8")
            if entities:
                grouped = {e.category: [e] for e in entities}
                write_glossary_markdown(grouped, gloss_path)
                logs.write(f"[bold green]Ingested {len(entities)} entities into {gloss_path}[/]")
            else:
                logs.write("[yellow]No delimiter entity block found in file.[/]")
        except Exception as err:
            logs.write(f"[bold red]Entity ingestion failed: {err}[/]")

    def _execute_setup_model(self) -> None:
        from tome.core.downloader import ensure_gliner_model

        logs = self.query_one("#live_logs", RichLog)
        try:
            logs.write(f"[cyan]Pre-caching GLiNER model: {self.config.default_model}[/]")
            ensure_gliner_model(self.config.default_model)
            logs.write(f"[bold green]GLiNER model ready: {self.config.default_model}[/]")
        except Exception as err:
            logs.write(f"[bold red]Model setup failed: {err}[/]")
