"""Companion config defaults."""

from nanobot.config.companion_defaults import COMPANION_PRESET_NAME, ensure_companion_preset
from nanobot.config.loader import load_config
from nanobot.config.schema import Config


def test_companion_defaults_enabled_with_random_trigger():
    config = Config()
    companion = config.gateway.companion
    assert companion.enabled is True
    assert companion.check_interval_s == 20 * 60
    assert companion.send_probability == 0.12
    assert companion.min_interval_s == 7200
    assert companion.lightweight_chat is True
    assert companion.recent_chat_skip_minutes == 30
    assert companion.sanitize_reply is True
    assert config.gateway.message_burst.burst_probability == 0.35


def test_ensure_companion_preset_adds_bundled_preset():
    config = Config()
    assert COMPANION_PRESET_NAME not in config.model_presets
    changed = ensure_companion_preset(config)
    assert changed is True
    assert COMPANION_PRESET_NAME in config.model_presets
    assert config.model_presets[COMPANION_PRESET_NAME].temperature == 0.85


def test_load_config_injects_companion_preset(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text('{"gateway": {"companion": {"enabled": true}}}', encoding="utf-8")
    config = load_config(cfg_path)
    assert COMPANION_PRESET_NAME in config.model_presets
