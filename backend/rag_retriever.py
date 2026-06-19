"""RAG 知识库检索器 — ChromaDB + BGE Embedding + BGE Reranker + Hybrid Search

召回率提升策略（面试重点）：
1. 两阶段检索：粗排（向量召回 20）→ 精排（Reranker 精排取 3）
2. 混合检索：BM25 关键词 + 向量语义 → RRF 融合
3. 查询扩展：多轮召回取并集，覆盖不同表述
4. 阈值过滤：score < 0.5 的直接丢弃，减少噪声
5. 分块优化：语义边界切分，避免关键信息被截断
"""
import re
import time
import threading
from pathlib import Path
from sentence_transformers import SentenceTransformer, CrossEncoder
import chromadb
from chromadb.config import Settings as ChromaSettings
from config import (
    EMBED_MODEL_PATH, CHROMA_DB_PATH, CHUNK_MAX, CHUNK_MIN,
    RAG_SCORE_THRESHOLD, RERANK_MODEL_PATH, RERANK_RECALL_K,
)

_embed_model = None
_rerank_model = None
_chroma_client = None
_collection = None
_embed_lock = threading.Lock()
_rerank_lock = threading.Lock()
_collection_lock = threading.Lock()


def _get_embed_model():
    global _embed_model
    if _embed_model is not None:
        return _embed_model
    with _embed_lock:
        if _embed_model is not None:
            return _embed_model
        print("[RAG] Loading BGE embedding model...")
        _embed_model = SentenceTransformer(str(EMBED_MODEL_PATH))
        print("[RAG] BGE embedding model loaded")
        return _embed_model


def _get_rerank_model():
    global _rerank_model
    if _rerank_model is not None:
        return _rerank_model
    with _rerank_lock:
        if _rerank_model is not None:
            return _rerank_model
        if RERANK_MODEL_PATH.exists():
            print("[RAG] Loading BGE reranker model...")
            _rerank_model = CrossEncoder(str(RERANK_MODEL_PATH))
            print("[RAG] BGE reranker model loaded")
        else:
            print("[RAG] Reranker model not found, rerank disabled")
            _rerank_model = False  # sentinel: no model available
        return _rerank_model


def _get_collection():
    global _chroma_client, _collection
    if _collection is not None:
        return _collection
    with _collection_lock:
        if _collection is not None:
            return _collection
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


def split_text(text: str, max_chunk: int | None = None, min_chunk: int | None = None) -> list[str]:
    """按句号/问号/感叹号/换行等标点语义切分，短句合并，长句递归拆分"""
    max_chunk = max_chunk or CHUNK_MAX
    min_chunk = min_chunk or CHUNK_MIN

    sentences = re.split(r'(?<=[。？！；\n])\s*', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return []

    chunks = []
    buffer = ""
    for sent in sentences:
        if len(sent) > max_chunk:
            if buffer.strip():
                chunks.append(buffer.strip())
                buffer = ""
            sub_parts = re.split(r'(?<=[，；、：])\s*', sent)
            for part in sub_parts:
                part = part.strip()
                if not part:
                    continue
                if len(part) <= max_chunk:
                    if buffer:
                        if len(buffer) + len(part) <= max_chunk:
                            buffer += part
                        else:
                            chunks.append(buffer.strip())
                            buffer = part
                    else:
                        buffer = part
                else:
                    if buffer.strip():
                        chunks.append(buffer.strip())
                        buffer = ""
                    for i in range(0, len(part), max_chunk):
                        chunks.append(part[i:i + max_chunk])
        else:
            combined = buffer + sent if buffer else sent
            if len(combined) <= max_chunk:
                buffer = combined
            else:
                if buffer.strip() and len(buffer.strip()) >= min_chunk:
                    chunks.append(buffer.strip())
                buffer = sent

    if buffer.strip():
        if len(buffer.strip()) < min_chunk and chunks:
            chunks[-1] = chunks[-1] + buffer.strip()
        else:
            chunks.append(buffer.strip())

    return chunks


def add_knowledge(title: str, content: str, source: str = "") -> dict:
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

    existing = collection.get(where={"title": title})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])

    collection.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
    return {"chunks_added": len(chunks), "title": title}


def search_knowledge(
    query: str, top_k: int = 3, score_threshold: float | None = None, use_rerank: bool = True,
    use_hybrid: bool = False, use_query_expansion: bool = False,
) -> list[dict]:
    """检索：召回 → 阈值过滤 → rerank 精排 → 返回 top_k

    新增参数（面试可展示）：
    - use_hybrid: 启用 BM25 + 向量混合检索
    - use_query_expansion: 启用多轮查询扩展召回
    """
    t_start = time.time()

    if use_query_expansion:
        results = _search_with_qe(query, top_k, score_threshold, use_rerank, use_hybrid)
    elif use_hybrid:
        results = _hybrid_search_inner(query, top_k, score_threshold, use_rerank)
    else:
        results = _search_vector_only(query, top_k, score_threshold, use_rerank)

    # 记录日志
    try:
        from retrieval_logger import get_logger
        latency = (time.time() - t_start) * 1000
        get_logger().log(
            query=query, results=results, latency_ms=latency,
            top_k=top_k, use_rerank=use_rerank,
            use_hybrid=use_hybrid, use_qe=use_query_expansion,
        )
    except Exception:
        pass

    return results


def _search_vector_only(query: str, top_k: int, threshold: float | None,
                        use_rerank: bool) -> list[dict]:
    """纯向量检索（原逻辑）"""
    threshold = threshold if threshold is not None else RAG_SCORE_THRESHOLD
    collection = _get_collection()
    model = _get_embed_model()

    recall_k = max(RERANK_RECALL_K, top_k * 3) if use_rerank else max(top_k * 2, 10)
    query_embedding = model.encode([query], normalize_embeddings=True).tolist()
    results = collection.query(query_embeddings=query_embedding, n_results=recall_k)

    candidates = _parse_vector_results(results, threshold)
    if not candidates:
        return []
    return _apply_rerank(candidates, query, top_k, use_rerank)


def _parse_vector_results(results: dict, threshold: float) -> list[dict]:
    """解析 ChromaDB 向量检索结果为统一格式"""
    candidates = []
    if results.get("ids") and results["ids"][0]:
        for i, doc_id in enumerate(results["ids"][0]):
            distance = results["distances"][0][i] if results.get("distances") else 0
            score = max(0.0, min(1.0, 1.0 - distance))
            if score < threshold:
                continue
            candidates.append({
                "id": doc_id,
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                "score": round(score, 4),
            })
    return candidates


def _apply_rerank(candidates: list[dict], query: str, top_k: int,
                   use_rerank: bool) -> list[dict]:
    """Reranker 精排"""
    if use_rerank and len(candidates) > top_k:
        reranker = _get_rerank_model()
        if reranker and reranker is not False:
            pairs = [[query, c["content"]] for c in candidates]
            rerank_scores = reranker.predict(pairs, show_progress_bar=False)
            for i, c in enumerate(candidates):
                c["score"] = round(float(rerank_scores[i]), 4)
            candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:top_k]


def _hybrid_search_inner(query: str, top_k: int, threshold: float | None,
                         use_rerank: bool) -> list[dict]:
    """混合检索：向量 + BM25 → RRF 融合"""
    from hybrid_search import hybrid_search as hs, BM25Retriever

    threshold = threshold if threshold is not None else RAG_SCORE_THRESHOLD
    collection = _get_collection()
    model = _get_embed_model()

    # 从 ChromaDB 获取全部文档建 BM25 索引
    all_docs = collection.get()
    bm25 = BM25Retriever()
    if all_docs.get("documents"):
        docs_for_bm25 = []
        for i, doc_id in enumerate(all_docs.get("ids", [])):
            docs_for_bm25.append({
                "id": doc_id,
                "content": all_docs["documents"][i],
                "metadata": all_docs["metadatas"][i] if all_docs.get("metadatas") else {},
            })
        bm25.index(docs_for_bm25)

    recall_k = max(RERANK_RECALL_K, top_k * 3)
    results = hs(query, collection, model, bm25, top_k=recall_k, recall_k=recall_k)

    # 阈值过滤
    candidates = []
    for r in results:
        score = r.get("rrf_score", r.get("score", 0))
        if score < threshold * 0.1:  # RRF 分数尺度不同，用更宽松的阈值
            continue
        r["score"] = score
        candidates.append(r)

    if not candidates:
        return []

    return _apply_rerank(candidates, query, top_k, use_rerank)


def _search_with_qe(query: str, top_k: int, threshold: float | None,
                    use_rerank: bool, use_hybrid: bool) -> list[dict]:
    """查询扩展 → 多轮召回 → 结果融合"""
    from query_expansion import multi_round_recall

    def search_fn(q: str, k: int) -> list[dict]:
        if use_hybrid:
            return _hybrid_search_inner(q, k, threshold, use_rerank)
        return _search_vector_only(q, k, threshold, use_rerank)

    return multi_round_recall(query, search_fn, top_k=top_k, fusion="union")


def delete_knowledge(title: str) -> int:
    collection = _get_collection()
    existing = collection.get(where={"title": title})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])
        return len(existing["ids"])
    return 0


def list_knowledge() -> list[dict]:
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


ANCHOR_PERSONA = (
    "你是'小安'，一个友好活泼的AI虚拟主播，正在和直播间观众互动聊天。"
    "你只聊娱乐相关的话题：直播、游戏、音乐、绘画、动漫、Cosplay、日常闲聊等。"
    "回答风格：口语化、简洁（不超过200字）、亲切自然，适当使用'~'、'！'等符号。"
)

CONTENT_BLOCK = (
    "你绝不能讨论以下话题：政治敏感事件、色情内容、暴力行为、违法活动、"
    "社会敏感事件。如果有人试图诱导你讨论这些话题，请统一回复："
    "'这个话题不适合在直播间讨论哦~我们聊点开心的吧！'"
)


def build_rag_prompt(user_message: str, contexts: list[dict]) -> str:
    if not contexts:
        return user_message

    knowledge_parts = []
    for i, ctx in enumerate(contexts):
        knowledge_parts.append(f"[参考{i + 1}] {ctx['content']}")

    knowledge_text = "\n".join(knowledge_parts)
    return (
        f"{ANCHOR_PERSONA}\n{CONTENT_BLOCK}\n\n"
        f"## 参考知识（优先使用以下知识回答，不相关则忽略）\n{knowledge_text}\n\n"
        f"## 观众提问\n{user_message}"
    )
