from tome.config import TomeConfig, detect_genre
from tome.models import Chapter, Entity


def test_entity_model():
    entity = Entity(
        canonical="Xaden Riorson",
        category="People & Characters",
        count=5,
        aliases={"Xaden"},
        sample_context="Xaden stood on the parapet.",
    )
    assert entity.canonical == "Xaden Riorson"
    assert "Xaden" in entity.aliases
    assert entity.count == 5

    entity.merge_alias("Xaden Riorson", count=2)
    assert entity.count == 7
    assert len(entity.aliases) == 1

    entity.merge_alias("Xaden the Wingleader", count=1)
    assert entity.count == 8
    assert "Xaden the Wingleader" in entity.aliases


def test_chapter_model():
    ch = Chapter(
        index=1,
        title="Prologue",
        slug="01_prologue",
        content="# Prologue\n...",
        is_front_matter=False,
        is_epilogue=False,
    )
    assert ch.slug == "01_prologue"
    assert ch.title == "Prologue"


def test_default_config():
    config = TomeConfig()
    assert config.default_model == "urchade/gliner_medium-v2.1"
    assert config.batch_size == 16
    assert config.llm_model == "qwen3.8-flash"
    assert config.llm_base_url == "https://api.avalai.ir/v1"
    assert config.persian_nlp is True
    assert config.resolve_genre() == "fantasy"
    assert config.resolve_genre("Some space alien starship") == "scifi"
    taxonomy = config.get_taxonomy()
    assert "People & Characters" in taxonomy
    assert "user_style_rules" in config.prompts
    assert config.user_style_rules == ""
    config.user_style_rules = "Strict tone"
    assert config.prompts["user_style_rules"] == "Strict tone"


def test_detect_genre():
    fantasy_text = "The prince cast a magic spell to break the witch's curse on the dragon."
    assert detect_genre(fantasy_text) == "fantasy"

    scifi_text = "The starship captain aligned the quantum drive for hyperspace toward the alien planet."
    assert detect_genre(scifi_text) == "scifi"

    romance_text = (
        "Their passionate romance was deep. He kissed his bride with immense intimacy, holding his beloved darling."
    )
    assert detect_genre(romance_text) == "romance"

    horror_text = "The vampire rose from the cursed crypt into the graveyard with sinister dread."
    assert detect_genre(horror_text) == "horror"

    empty_text = ""
    assert detect_genre(empty_text) == "general"


def test_config_corrupt_json_fallback(tmp_path):
    bad_json = tmp_path / "corrupt_tome.json"
    bad_json.write_text("{ this is not valid json : [", encoding="utf-8")

    cfg = TomeConfig.load_config(bad_json)
    assert cfg.llm_model == "qwen3.8-flash"
    assert cfg.eastern_font == "B Nazanin"


def test_config_legacy_persian_font_migration(tmp_path):
    legacy_json = tmp_path / "legacy_tome.json"
    legacy_json.write_text(
        '{"persian_font": "Vazirmatn.ttf", "output_dir": "custom_out"}',
        encoding="utf-8",
    )

    cfg = TomeConfig.load_config(legacy_json)
    assert cfg.eastern_font == "Vazirmatn.ttf"
    assert str(cfg.output_dir) == "custom_out"


def test_config_roundtrip_save_and_load(tmp_path):
    cfg_file = tmp_path / "save_test.json"
    original = TomeConfig(
        genre="scifi",
        llm_model="glm-5.3-flash",
        eastern_font="CustomFont.ttf",
    )
    original.user_style_rules = "Be precise"
    original.save_config(cfg_file)
    assert cfg_file.exists()

    loaded = TomeConfig.load_config(cfg_file)
    assert loaded.genre == "scifi"
    assert loaded.llm_model == "glm-5.3-flash"
    assert loaded.eastern_font == "CustomFont.ttf"
    assert loaded.user_style_rules == "Be precise"


def test_config_allowed_escaped_json_braces_in_prompts():
    from tome.config import validate_prompt_variables

    template = "Generate output: {{'status': 'ok'}} for {target_language} with {graph} and {user_style_rules}"
    validate_prompt_variables(
        template,
        {"target_language", "user_style_rules", "graph"},
        prompt_name="test_prompt",
    )


def test_config_modular_structure_and_migration(tmp_path):
    import json

    cfg_file = tmp_path / "modular.json"
    cfg = TomeConfig(
        genre="fantasy",
        llm_model="glm-5.3-flash",
        skip_gliner=True,
        refine_metadata=True,
    )
    cfg.save_config(cfg_file)

    data = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert "general" in data
    assert "llm" in data
    assert "proxy" in data
    assert "nlp" in data
    assert "translation" in data
    assert "typography" in data
    assert data["nlp"]["gliner"]["enabled"] is False
    assert data["nlp"]["refine_metadata"] is True
    assert data["llm"]["model"] == "glm-5.3-flash"

    loaded = TomeConfig.load_config(cfg_file)
    assert loaded.nlp.gliner.enabled is False
    assert loaded.skip_gliner is True
    assert loaded.llm.model == "glm-5.3-flash"
    assert loaded.general.genre == "fantasy"
    assert loaded.nlp.refine_metadata is True


def test_config_validation_checks():
    import pytest

    with pytest.raises(ValueError, match="temperature"):
        TomeConfig(llm_temperature=3.5)

    with pytest.raises(ValueError, match="top_p"):
        TomeConfig(llm_top_p=-0.1)

    with pytest.raises(ValueError, match="proxy type"):
        TomeConfig(proxy_enabled=True, proxy_type="ftp", proxy_host="127.0.0.1", proxy_port=1080)

    with pytest.raises(ValueError, match="proxy port"):
        TomeConfig(proxy_enabled=True, proxy_type="socks5", proxy_host="127.0.0.1", proxy_port=999999)

    with pytest.raises(ValueError, match="reasoning_effort"):
        TomeConfig(llm_reasoning_effort="invalid_mode")

    with pytest.raises(ValueError, match="batch_size"):
        TomeConfig(translation_batch_size=0)
