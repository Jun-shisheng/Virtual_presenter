"""CosyVoice-300M TTS engine with sentence-level synthesis"""
import sys
import hashlib
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, Future

import torch
import torchaudio

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "third_party" / "CosyVoice" / "third_party" / "Matcha-TTS"))
sys.path.insert(0, str(ROOT / "third_party" / "CosyVoice"))

from cosyvoice.cli.cosyvoice import CosyVoice
from config import TTS_MODEL_PATH, TTS_PROMPT_WAV, TTS_PROMPT_TEXT, TTS_AUDIO_DIR

_engine: CosyVoice | None = None
_engine_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=1)


def _get_engine() -> CosyVoice:
    global _engine
    if _engine is not None:
        return _engine
    with _engine_lock:
        if _engine is not None:
            return _engine
        print("[TTS] Loading CosyVoice-300M...")
        use_fp16 = torch.cuda.is_available()
        _engine = CosyVoice(
            str(TTS_MODEL_PATH),
            load_jit=False,
            load_trt=False,
            fp16=use_fp16,
        )
        print(f"[TTS] CosyVoice-300M loaded, sample_rate={_engine.sample_rate}")
        return _engine


def synthesize(text: str) -> dict | None:
    """Generate audio for a single sentence. Returns {wav_url, duration, text} or None."""
    if not text.strip():
        return None

    engine = _get_engine()
    TTS_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    audio_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
    wav_path = TTS_AUDIO_DIR / f"tts_{audio_hash}.wav"

    if wav_path.exists():
        audio, sr = torchaudio.load(str(wav_path))
        duration = audio.shape[1] / sr
        return {
            "wav_url": f"/audio/tts_{audio_hash}.wav",
            "duration": round(duration, 2),
            "text": text,
        }

    try:
        outputs = list(engine.inference_zero_shot(
            text, TTS_PROMPT_TEXT, str(TTS_PROMPT_WAV), stream=False
        ))
    except Exception as e:
        print(f"[TTS] Synthesis failed: {e}")
        return None

    if not outputs:
        return None

    audio = outputs[0]["tts_speech"]
    duration = audio.shape[1] / engine.sample_rate
    torchaudio.save(str(wav_path), audio.cpu(), engine.sample_rate)

    return {
        "wav_url": f"/audio/tts_{audio_hash}.wav",
        "duration": round(duration, 2),
        "text": text,
    }


def synthesize_async(text: str) -> Future:
    """Submit TTS task to background thread, return Future"""
    return _executor.submit(synthesize, text)


def split_sentences(text: str) -> list[str]:
    """Split text into sentences at Chinese/English punctuation boundaries."""
    import re
    parts = re.split(r'(?<=[。！？~！？…\n])', text)
    result = []
    for p in parts:
        p = p.strip()
        if p:
            result.append(p)
    return result
