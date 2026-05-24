"""Virtual streamer soul engine — stub for Phase 5+ implementation.

Design reference: https://github.com/... (virtual life engine)
Full spec: docs/phase3-live2d-tts-design.md#灵魂引擎预留接口

This module is intentionally a no-op placeholder. It ensures the frontend
and TTS pipeline have stable interfaces to consume when the soul engine
is implemented later.
"""


def get_agent_state() -> dict:
    """Return current internal state for TTS expression and frontend display.

    Future: driven by biorhythm engine, PAD emotion model, narrative self.
    """
    return {
        "energy": 0.8,
        "mood_valence": 0.6,
        "mood_arousal": 0.5,
        "mood_dominance": 0.7,
        "expression": "happy",
    }


def on_message_sent(user_msg: str) -> None:
    """Notify soul engine that the user sent a message."""
    pass


def on_reply_generated(reply: str) -> None:
    """Notify soul engine that the AI generated a reply."""
    pass
