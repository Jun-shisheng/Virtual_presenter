"""下载项目所需模型到 models/ 目录"""
from huggingface_hub import snapshot_download
import os

MODELS_DIR = os.path.dirname(os.path.abspath(__file__))

models_to_download = [
    {
        "repo_id": "Qwen/Qwen3-8B",
        "local_dir": os.path.join(MODELS_DIR, "models", "llm", "Qwen3-8B"),
        "description": "Qwen3-8B LLM 对话模型"
    },
    # 后续阶段下载
    # {
    #     "repo_id": "BAAI/bge-small-zh-v1.5",
    #     "local_dir": os.path.join(MODELS_DIR, "models", "embedding", "bge-small-zh-v1.5"),
    #     "description": "BGE Embedding 向量模型"
    # },
    # {
    #     "repo_id": "FunAudioLLM/CosyVoice-300M",
    #     "local_dir": os.path.join(MODELS_DIR, "models", "tts", "CosyVoice-300M"),
    #     "description": "CosyVoice TTS 语音合成"
    # },
]

for model in models_to_download:
    print(f"\n{'='*60}")
    print(f"开始下载: {model['description']}")
    print(f"模型仓库: {model['repo_id']}")
    print(f"保存路径: {model['local_dir']}")
    print(f"{'='*60}\n")

    snapshot_download(
        repo_id=model["repo_id"],
        local_dir=model["local_dir"],
        resume_download=True,
        local_dir_use_symlinks=False,
        ignore_patterns=["*.msgpack", "*.h5"],  # 跳过旧格式，只要 safetensors
    )
    print(f"✅ {model['description']} 下载完成！")

print("\n🎉 所有模型下载完成！")
