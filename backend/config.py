"""统一配置管理 — 环境变量 + pydantic BaseSettings"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:123456@localhost:3306/ai_digital_db")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "anchor-secret-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "72"))

MODEL_PATH = PROJECT_ROOT / "models" / "llm" / "Qwen3-8B"
EMBED_MODEL_PATH = PROJECT_ROOT / "models" / "embedding" / "bge-small-zh-v1.5"
CHROMA_DB_PATH = PROJECT_ROOT / "database" / "chroma_db"

RERANK_MODEL_PATH = PROJECT_ROOT / "models" / "reranker" / "bge-reranker-base"
RERANK_RECALL_K = int(os.getenv("RERANK_RECALL_K", "20"))

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_CACHE_TTL = int(os.getenv("REDIS_CACHE_TTL", "3600"))

CHUNK_MAX = int(os.getenv("CHUNK_MAX", "512"))
CHUNK_MIN = int(os.getenv("CHUNK_MIN", "80"))
RAG_SCORE_THRESHOLD = float(os.getenv("RAG_SCORE_THRESHOLD", "0.5"))
