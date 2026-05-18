"""RAG 知识库检索器 — ChromaDB + BGE Embedding"""
from pathlib import Path
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings as ChromaSettings

EMBED_MODEL_PATH = Path(__file__).parent.parent / "models" / "embedding" / "bge-small-zh-v1.5"
CHROMA_DB_PATH = Path(__file__).parent.parent / "database" / "chroma_db"

_embed_model = None
_chroma_client = None
_collection = None


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        print("[RAG] Loading BGE embedding model...")
        _embed_model = SentenceTransformer(str(EMBED_MODEL_PATH))
        print("[RAG] BGE embedding model loaded")
    return _embed_model


def _get_collection():
    global _chroma_client, _collection
    if _collection is None:
        CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(
            path=str(CHROMA_DB_PATH),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        _collection = _chroma_client.get_or_create_collection(
            name="anchor_knowledge",
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def split_text(text: str, chunk_size: int = 300, overlap: int = 50) -> list[str]:
    """简单分块：按段落优先，长段落再按字数切分"""
    paragraphs = text.split("\n")
    chunks = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(para) <= chunk_size:
            chunks.append(para)
        else:
            for i in range(0, len(para), chunk_size - overlap):
                chunks.append(para[i:i + chunk_size])
    return chunks


def add_knowledge(title: str, content: str, source: str = "") -> dict:
    """添加知识文档，自动分块并向量化存储"""
    collection = _get_collection()
    model = _get_embed_model()

    chunks = split_text(content)
    if not chunks:
        return {"chunks_added": 0}

    embeddings = model.encode(chunks, normalize_embeddings=True).tolist()
    metadatas = [
        {"title": title, "source": source, "chunk_index": i, "chunk_total": len(chunks)}
        for i in range(len(chunks))
    ]
    ids = [f"{title}_{i}" for i in range(len(chunks))]

    # 如果已存在同 title 的文档，先删除再添加（覆盖更新）
    existing = collection.get(where={"title": title})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])

    collection.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
    return {"chunks_added": len(chunks), "title": title}


def search_knowledge(query: str, top_k: int = 3) -> list[dict]:
    """检索最相关的知识片段"""
    collection = _get_collection()
    model = _get_embed_model()

    query_embedding = model.encode([query], normalize_embeddings=True).tolist()
    results = collection.query(query_embeddings=query_embedding, n_results=top_k)

    items = []
    if results["ids"] and results["ids"][0]:
        for i, doc_id in enumerate(results["ids"][0]):
            items.append({
                "id": doc_id,
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "score": 1 - results["distances"][0][i] if results.get("distances") else None,
            })
    return items


def delete_knowledge(title: str) -> int:
    """按标题删除知识文档的所有分块"""
    collection = _get_collection()
    existing = collection.get(where={"title": title})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])
        return len(existing["ids"])
    return 0


def list_knowledge() -> list[dict]:
    """列出所有已存储的知识文档标题"""
    collection = _get_collection()
    results = collection.get()
    titles = {}
    if results["metadatas"]:
        for meta in results["metadatas"]:
            t = meta["title"]
            if t not in titles:
                titles[t] = {"title": t, "source": meta["source"], "chunks": 0}
            titles[t]["chunks"] += 1
    return list(titles.values())


def build_rag_prompt(user_message: str, contexts: list[dict]) -> str:
    """构建带知识上下文的增强 prompt"""
    if not contexts:
        return user_message

    knowledge_parts = []
    for i, ctx in enumerate(contexts):
        knowledge_parts.append(f"[参考{i + 1}] {ctx['content']}")

    knowledge_text = "\n".join(knowledge_parts)
    return f"请根据以下参考知识回答用户问题。如果参考知识与问题无关，请忽略并按正常方式回答。\n\n## 参考知识\n{knowledge_text}\n\n## 用户问题\n{user_message}"
