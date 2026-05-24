"""Pre-generated audio cache for high-frequency TTS phrases"""
import hashlib
from pathlib import Path

from config import TTS_AUDIO_DIR

COMMON_PHRASES = [
    "欢迎来到直播间~",
    "谢谢大家的支持！",
    "喜欢的话记得点个关注哦~",
    "这个话题不适合在直播间讨论哦~我们聊点开心的吧！",
    "大家好！我是小安，欢迎来到我的直播间~",
    "那我们下次再见啦~拜拜！",
]


def wav_url(text: str) -> str:
    key = hashlib.sha256(text.strip().encode()).hexdigest()[:16]
    return f"/audio/tts_{key}.wav"


def pregenerate_all(tts_engine):
    """Pre-generate cached audio for common phrases on startup"""
    print("[Cache] Pre-generating common phrase audio...")
    for phrase in COMMON_PHRASES:
        wav_path = TTS_AUDIO_DIR / f"tts_{hashlib.sha256(phrase.strip().encode()).hexdigest()[:16]}.wav"
        if wav_path.exists():
            continue
        result = tts_engine.synthesize(phrase)
        if result:
            print(f"[Cache] Cached: {phrase}")
        else:
            print(f"[Cache] Failed: {phrase}")
