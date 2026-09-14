from pathlib import Path
from unittest.mock import MagicMock

from textual.widgets import Input, Select, Switch

from tome.cli.tui import TomeApp
from tome.config import TomeConfig


def test_tui_switch_changed_gliner_auto_saves(tmp_path: Path):
    cfg_file = tmp_path / "tome.json"
    cfg = TomeConfig(config_path=cfg_file)
    cfg.skip_gliner = False
    cfg.save_config()

    app = TomeApp(config=cfg)
    app.notify = MagicMock()

    mock_switch = MagicMock(spec=Switch)
    mock_switch.id = "switch_gliner"
    mock_event = MagicMock(spec=Switch.Changed)
    mock_event.switch = mock_switch
    mock_event.value = False

    app.on_switch_changed(mock_event)

    assert app.config.skip_gliner is True
    reloaded = TomeConfig.load_config(cfg_file)
    assert reloaded.skip_gliner is True
    app.notify.assert_called_once()


def test_tui_switch_changed_persian_nlp_auto_saves(tmp_path: Path):
    cfg_file = tmp_path / "tome.json"
    cfg = TomeConfig(config_path=cfg_file)
    cfg.persian_nlp = True
    cfg.save_config()

    app = TomeApp(config=cfg)
    app.notify = MagicMock()

    mock_switch = MagicMock(spec=Switch)
    mock_switch.id = "switch_persian_nlp"
    mock_event = MagicMock(spec=Switch.Changed)
    mock_event.switch = mock_switch
    mock_event.value = False

    app.on_switch_changed(mock_event)

    assert app.config.persian_nlp is False
    reloaded = TomeConfig.load_config(cfg_file)
    assert reloaded.persian_nlp is False
    app.notify.assert_called_once()


def test_tui_switch_changed_keep_raw_auto_saves(tmp_path: Path):
    cfg_file = tmp_path / "tome.json"
    cfg = TomeConfig(config_path=cfg_file)
    cfg.keep_raw_artifacts = False
    cfg.save_config()

    app = TomeApp(config=cfg)
    app.notify = MagicMock()

    mock_switch = MagicMock(spec=Switch)
    mock_switch.id = "switch_keep_raw"
    mock_event = MagicMock(spec=Switch.Changed)
    mock_event.switch = mock_switch
    mock_event.value = True

    app.on_switch_changed(mock_event)

    assert app.config.keep_raw_artifacts is True
    reloaded = TomeConfig.load_config(cfg_file)
    assert reloaded.keep_raw_artifacts is True


def test_tui_switch_changed_fast_mode_auto_saves(tmp_path: Path):
    cfg_file = tmp_path / "tome.json"
    cfg = TomeConfig(config_path=cfg_file)
    cfg.fast_mode = False
    cfg.save_config()

    app = TomeApp(config=cfg)
    app.notify = MagicMock()

    mock_switch = MagicMock(spec=Switch)
    mock_switch.id = "switch_fast"
    mock_event = MagicMock(spec=Switch.Changed)
    mock_event.switch = mock_switch
    mock_event.value = True

    app.on_switch_changed(mock_event)

    assert app.config.fast_mode is True
    reloaded = TomeConfig.load_config(cfg_file)
    assert reloaded.fast_mode is True


def test_tui_select_changed_genre_auto_saves(tmp_path: Path):
    cfg_file = tmp_path / "tome.json"
    cfg = TomeConfig(config_path=cfg_file)
    cfg.genre = "auto"
    cfg.save_config()

    app = TomeApp(config=cfg)
    app.notify = MagicMock()

    mock_select = MagicMock(spec=Select)
    mock_select.id = "select_genre"
    mock_event = MagicMock(spec=Select.Changed)
    mock_event.select = mock_select
    mock_event.value = "fantasy"

    app.on_select_changed(mock_event)

    assert app.config.genre == "fantasy"
    reloaded = TomeConfig.load_config(cfg_file)
    assert reloaded.genre == "fantasy"
    app.notify.assert_called_once()


def test_tui_input_changed_output_dir_auto_saves(tmp_path: Path):
    cfg_file = tmp_path / "tome.json"
    cfg = TomeConfig(config_path=cfg_file)
    cfg.save_config()

    app = TomeApp(config=cfg)

    new_out = tmp_path / "custom_output"
    mock_input = MagicMock(spec=Input)
    mock_input.id = "input_output"
    mock_event = MagicMock(spec=Input.Changed)
    mock_event.input = mock_input
    mock_event.value = str(new_out)

    app.on_input_changed(mock_event)

    assert app.config.output_dir == new_out
    reloaded = TomeConfig.load_config(cfg_file)
    assert reloaded.output_dir == new_out


def test_tui_switch_changed_refine_metadata_auto_saves(tmp_path: Path):
    cfg_file = tmp_path / "tome.json"
    cfg = TomeConfig(config_path=cfg_file)
    cfg.refine_metadata = True
    cfg.save_config()

    app = TomeApp(config=cfg)
    app.notify = MagicMock()

    mock_switch = MagicMock(spec=Switch)
    mock_switch.id = "switch_refine_metadata"
    mock_event = MagicMock(spec=Switch.Changed)
    mock_event.switch = mock_switch
    mock_event.value = False

    app.on_switch_changed(mock_event)

    assert app.config.refine_metadata is False
    reloaded = TomeConfig.load_config(cfg_file)
    assert reloaded.refine_metadata is False
    app.notify.assert_called_once()
