"""Companion config defaults."""

from nanobot.config.schema import Config


def test_companion_defaults_enabled_with_random_trigger():
    config = Config()
    companion = config.gateway.companion
    assert companion.enabled is True
    assert companion.check_interval_s == 20 * 60
    assert 0.0 < companion.send_probability <= 1.0
    assert companion.min_interval_s >= 60
