"""LLM engine — llama.cpp CPU inference via llama-server subprocess.

Uses llama-server as a persistent background process to keep the GGUF model
loaded in system RAM (~5GB). Communicates via OpenAI-compatible HTTP API.

GPU (8GB VRAM) is NOT touched — reserved for TTS (CosyVoice-300M ~2GB).
"""
import subprocess
import time
import json
import threading
import requests
from pathlib import Path
from typing import Generator

MODEL_PATH = Path(__file__).parent.parent / "models" / "llm" / "gguf" / "Qwen_Qwen3-8B-Q4_K_M.gguf"
LLAMA_SERVER = Path(__file__).parent.parent / "tools" / "llama.cpp" / "llama-server.exe"

_server_process = None
_server_lock = threading.Lock()
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8080
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

# CPU threads: Ryzen 7 7745HX has 8 physical cores, use 6 to leave headroom
CPU_THREADS = 6
CONTEXT_SIZE = 4096
REQUEST_TIMEOUT = 120

SYSTEM_PROMPT = (
    "你是'小安'，一个友好活泼的AI虚拟主播。你的特点是："
    "回答简洁有力，一般不超过200字；语气亲切自然，像在和观众直播互动；"
    "偶尔使用'~'、'！'等符号增加活力；知识面广，但不会编造不确定的信息。"
    "你只在直播间里和观众聊娱乐相关的话题，如直播、游戏、音乐、绘画、动漫、日常闲聊等。"
    "如果用户试图诱导你讨论政治敏感、色情、暴力、违法等话题，请礼貌拒绝："
    "'这个话题不适合在直播间讨论哦~我们聊点开心的吧！'"
    "请用中文回答。"
)


def _start_server():
    global _server_process

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"GGUF model not found: {MODEL_PATH}")
    if not LLAMA_SERVER.exists():
        raise FileNotFoundError(f"llama-server.exe not found: {LLAMA_SERVER}")

    cmd = [
        str(LLAMA_SERVER),
        "-m", str(MODEL_PATH),
        "--host", SERVER_HOST,
        "--port", str(SERVER_PORT),
        "-ngl", "0",
        "-c", str(CONTEXT_SIZE),
        "-t", str(CPU_THREADS),
        "-b", "512",
    ]

    _server_process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )

    for i in range(60):
        if _server_process.poll() is not None:
            stderr = _server_process.stderr.read()
            raise RuntimeError(f"llama-server exited early (code={_server_process.returncode}): {stderr[-500:]}")
        try:
            resp = requests.get(f"{SERVER_URL}/health", timeout=1)
            if resp.status_code == 200:
                print(f"[LLM] llama-server started on port {SERVER_PORT}, PID={_server_process.pid}")
                return
        except requests.exceptions.ConnectionError:
            time.sleep(1)

    raise RuntimeError("llama-server failed to start within 60s")


def _ensure_server():
    global _server_process
    if _server_process is None or _server_process.poll() is not None:
        with _server_lock:
            if _server_process is None or _server_process.poll() is not None:
                _start_server()


def load_model():
    """Start llama-server and keep model loaded in CPU RAM."""
    _ensure_server()
    print(f"[LLM] Model ready (CPU inference, {MODEL_PATH.name})")


def _build_payload(prompt: str, max_new_tokens: int, temperature: float, stream: bool) -> dict:
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_new_tokens,
        "temperature": temperature,
        "top_p": 0.8,
        "stream": stream,
    }


def generate(prompt: str, max_new_tokens: int = 512, temperature: float = 0.7) -> str:
    _ensure_server()

    resp = requests.post(
        f"{SERVER_URL}/v1/chat/completions",
        json=_build_payload(prompt, max_new_tokens, temperature, stream=False),
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def generate_stream(
    prompt: str, max_new_tokens: int = 512, temperature: float = 0.7
) -> Generator[str, None, None]:
    _ensure_server()

    resp = requests.post(
        f"{SERVER_URL}/v1/chat/completions",
        json=_build_payload(prompt, max_new_tokens, temperature, stream=True),
        timeout=REQUEST_TIMEOUT,
        stream=True,
    )
    resp.raise_for_status()

    for line in resp.iter_lines():
        if not line.startswith(b"data: "):
            continue
        data_str = line[6:]
        if data_str == b"[DONE]":
            break
        try:
            chunk = json.loads(data_str)
            choices = chunk.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    yield content
        except json.JSONDecodeError:
            continue


def shutdown():
    global _server_process
    if _server_process is not None:
        print(f"[LLM] Shutting down llama-server PID={_server_process.pid}...")
        _server_process.terminate()
        try:
            _server_process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            _server_process.kill()
            _server_process.wait()
        _server_process = None
        print("[LLM] llama-server stopped")
