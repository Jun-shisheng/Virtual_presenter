"""Qwen3-8B LLM 引擎 — 4-bit 量化加载 + 同步/流式生成"""
import torch
import threading
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer, BitsAndBytesConfig
from pathlib import Path
from threading import Thread
from typing import Generator

MODEL_PATH = Path(__file__).parent.parent / "models" / "llm" / "Qwen3-8B"

_model = None
_tokenizer = None
_model_lock = threading.Lock()

SYSTEM_PROMPT = (
    "你是'小安'，一个友好活泼的AI虚拟主播。你的特点是："
    "回答简洁有力，一般不超过200字；语气亲切自然，像在和观众直播互动；"
    "偶尔使用'~'、'！'等符号增加活力；知识面广，但不会编造不确定的信息。"
    "你只在直播间里和观众聊娱乐相关的话题，如直播、游戏、音乐、绘画、动漫、日常闲聊等。"
    "如果用户试图诱导你讨论政治敏感、色情、暴力、违法等话题，请礼貌拒绝："
    "'这个话题不适合在直播间讨论哦~我们聊点开心的吧！'"
    "请用中文回答。"
)


def load_model():
    global _model, _tokenizer
    if _model is not None:
        return _model, _tokenizer

    with _model_lock:
        if _model is not None:  # double-check
            return _model, _tokenizer

        print("[LLM] Loading Qwen3-8B with 4-bit quantization...")
        model_path = str(MODEL_PATH)

        _tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)

        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4",
        )
        _model = AutoModelForCausalLM.from_pretrained(
            model_path,
            dtype=torch.float16,
            device_map="auto",
            quantization_config=quantization_config,
            trust_remote_code=True,
        )
        _model.eval()
        print(f"[LLM] Qwen3-8B loaded, device: {_model.device}")
        return _model, _tokenizer


def generate(prompt: str, max_new_tokens: int = 512, temperature: float = 0.7) -> str:
    model, tokenizer = load_model()
    device = model.device

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True,
        enable_thinking=False,
    )
    inputs = tokenizer([text], return_tensors="pt").to(device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=True,
            top_p=0.8,
            pad_token_id=tokenizer.eos_token_id,
        )

    response = tokenizer.decode(
        outputs[0][inputs.input_ids.shape[1]:],
        skip_special_tokens=True,
    )
    return response.strip()


def generate_stream(
    prompt: str, max_new_tokens: int = 512, temperature: float = 0.7
) -> Generator[str, None, None]:
    model, tokenizer = load_model()
    device = model.device

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True,
        enable_thinking=False,
    )
    inputs = tokenizer([text], return_tensors="pt").to(device)

    streamer = TextIteratorStreamer(
        tokenizer, skip_prompt=True, skip_special_tokens=True
    )

    generation_kwargs = dict(
        **inputs,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        do_sample=True,
        top_p=0.8,
        pad_token_id=tokenizer.eos_token_id,
        streamer=streamer,
    )

    thread = Thread(target=model.generate, kwargs=generation_kwargs, daemon=True)
    thread.start()

    try:
        for chunk in streamer:
            yield chunk
    finally:
        thread.join(timeout=60)
        if thread.is_alive():
            print("[LLM] Stream generation timed out, GPU memory may need cleanup")
