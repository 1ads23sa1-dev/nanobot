"""Bundled defaults for companion (human-like chat) configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nanobot.config.schema import Config

COMPANION_PRESET_NAME = "companion"

COMPANION_MODEL_PRESET: dict[str, Any] = {
    "label": "小祥聊天",
    "model": "anthropic/claude-sonnet-4-5",
    "temperature": 0.85,
    "maxTokens": 1024,
}

COMPANION_CONFIG_SNIPPET: dict[str, Any] = {
    "agents": {
        "defaults": {
            "modelPreset": COMPANION_PRESET_NAME,
            "timezone": "Asia/Shanghai",
        },
    },
    "modelPresets": {
        COMPANION_PRESET_NAME: COMPANION_MODEL_PRESET,
    },
    "gateway": {
        "companion": {
            "enabled": True,
            "channel": "weixin",
            "chatId": "",
            "sendProbability": 0.12,
            "minIntervalS": 7200,
            "checkIntervalS": 1200,
            "quietHoursStart": "23:00",
            "quietHoursEnd": "08:00",
            "followupEnabled": True,
            "lightweightChat": True,
            "recentChatSkipMinutes": 30,
            "sanitizeReply": True,
            "maxReplyChars": 300,
        },
        "messageBurst": {
            "enabled": True,
            "burstProbability": 0.35,
            "stumbleEnabled": True,
            "stumbleProbability": 0.10,
        },
        "selectiveDelay": {
            "enabled": True,
            "minDelayS": 2,
            "maxDelayS": 18,
            "longDelayMinS": 60,
            "longDelayMaxS": 120,
        },
        "mood": {
            "enabled": True,
            "decayHalfLifeHours": 8,
        },
    },
}


def ensure_companion_preset(config: Config) -> bool:
    """Add the bundled companion preset if missing. Returns True if config changed."""
    from nanobot.config.schema import ModelPresetConfig

    if COMPANION_PRESET_NAME in config.model_presets:
        return False
    config.model_presets[COMPANION_PRESET_NAME] = ModelPresetConfig.model_validate(
        COMPANION_MODEL_PRESET,
    )
    return True
