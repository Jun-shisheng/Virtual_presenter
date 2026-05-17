"""下载项目所需模型到 models/ 目录

使用方式:
    python download_models.py           # 下载所有模型
    python download_models.py --llm     # 仅下载 LLM
    python download_models.py --embed   # 仅下载 Embedding
    python download_models.py --tts     # 仅下载 TTS
"""
import subprocess
import sys
import os

MODELS_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(MODELS_DIR, "venv")
HF_BIN = os.path.join(VENV_DIR, "Scripts", "hf.exe")

models = {
    "llm": {
        "repo_id": "Qwen/Qwen3-8B",
        "local_dir": os.path.join(MODELS_DIR, "models", "llm", "Qwen3-8B"),
        "description": "Qwen3-8B LLM 对话模型 (~16GB)",
    },
    "embedding": {
        "repo_id": "BAAI/bge-small-zh-v1.5",
        "local_dir": os.path.join(MODELS_DIR, "models", "embedding", "bge-small-zh-v1.5"),
        "description": "BGE-small-zh-v1.5 Embedding 向量模型 (~480MB)",
    },
    "tts": {
        "repo_id": "FunAudioLLM/CosyVoice-300M",
        "local_dir": os.path.join(MODELS_DIR, "models", "tts", "CosyVoice-300M"),
        "description": "CosyVoice-300M TTS 语音合成模型 (~310MB)",
    },
}

def download(repo_id: str, local_dir: str, description: str):
    print(f"\n{'='*60}")
    print(f"开始下载: {description}")
    print(f"模型仓库: {repo_id}")
    print(f"保存路径: {local_dir}")
    print(f"{'='*60}\n")

    result = subprocess.run(
        [HF_BIN, "download", repo_id, "--local-dir", local_dir, "--max-workers", "4"],
        cwd=MODELS_DIR,
    )
    if result.returncode == 0:
        print(f"✅ {description} 下载完成！")
    else:
        print(f"❌ {description} 下载失败（退出码: {result.returncode}）")
        sys.exit(1)

if __name__ == "__main__":
    # 根据命令行参数过滤
    if len(sys.argv) > 1:
        selected = [k for k in models if f"--{k}" in sys.argv]
    else:
        selected = list(models.keys())

    print(f"将下载 {len(selected)} 个模型: {[models[k]['description'] for k in selected]}")
    print("提示: 可以使用 --llm / --embedding / --tts 分别下载\n")

    for key in selected:
        m = models[key]
        # 检查是否已存在
        if os.path.exists(m["local_dir"]) and os.listdir(m["local_dir"]):
            print(f"⏭️  {m['description']} 已存在，跳过（如需重新下载请删除 {m['local_dir']}）")
            continue
        download(m["repo_id"], m["local_dir"], m["description"])

    print("\n🎉 所有模型下载完成！")
