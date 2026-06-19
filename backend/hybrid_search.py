"""混合检索 — BM25 关键词 + 向量语义双路召回 + RRF 融合

面试重点：
- 为什么需要混合检索：向量检索对专有名词/数字不敏感，BM25 补关键词短板
- RRF (Reciprocal Rank Fusion): 无需调参，对排名取倒数求和，数学上等价于对排名分布的概率融合
- score = sum(1 / (k + rank_i)) for each retriever i
"""

import re
import math
from collections import defaultdict
from sentence_transformers import SentenceTransformer


class BM25Retriever:
    """BM25 关键词检索

    BM25 核心公式:
    score(D, Q) = sum( IDF(qi) * f(qi,D) * (k1+1) / (f(qi,D) + k1*(1-b + b*|D|/avgdl)) )

    关键参数:
    - k1: 词频饱和参数 (默认 1.5)，控制词频对分数的影响上限
    - b:  文档长度归一化 (默认 0.75)，b=1 完全归一化，b=0 不归一化
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: list[dict] = []
        self.doc_freqs: dict[str, int] = defaultdict(int)
        self.doc_lengths: list[int] = []
        self.avgdl: float = 0.0
        self.N: int = 0

    def index(self, documents: list[dict]):
        """构建 BM25 索引"""
        self.documents = documents
        self.N = len(documents)

        for doc in documents:
            tokens = self._tokenize(doc.get("content", ""))
            self.doc_lengths.append(len(tokens))

            # 文档内去重统计 DF
            seen = set()
            for token in tokens:
                if token not in seen:
                    self.doc_freqs[token] += 1
                    seen.add(token)

        self.avgdl = sum(self.doc_lengths) / max(1, self.N)

    def _tokenize(self, text: str) -> list[str]:
        """中文分词简化版：按字/词切分 + 英文按空格"""
        tokens = []
        # 中文按 1-2 gram 切分
        chinese_chars = re.findall(r'[一-鿿]+', text)
        for chunk in chinese_chars:
            # unigram
            tokens.extend(list(chunk))
            # bigram
            tokens.extend(chunk[i:i + 2] for i in range(len(chunk) - 1))

        # 英文和数字
        english_words = re.findall(r'[a-zA-Z0-9]+', text)
        tokens.extend(w.lower() for w in english_words)

        return tokens

    def _idf(self, term: str) -> float:
        """IDF = log((N - df + 0.5) / (df + 0.5) + 1)"""
        df = self.doc_freqs.get(term, 0)
        return math.log((self.N - df + 0.5) / (df + 0.5) + 1.0)

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """BM25 检索，返回带有 bm25_score 的结果"""
        if self.N == 0:
            return []

        query_tokens = self._tokenize(query)
        scores = []

        for i, doc in enumerate(self.documents):
            doc_len = self.doc_lengths[i]
            doc_tokens = self._tokenize(doc.get("content", ""))

            term_freqs = defaultdict(int)
            for t in doc_tokens:
                term_freqs[t] += 1

            score = 0.0
            for token in query_tokens:
                tf = term_freqs.get(token, 0)
                if tf == 0:
                    continue
                idf = self._idf(token)
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
                score += idf * numerator / denominator

            if score > 0:
                scores.append({
                    **doc,
                    "bm25_score": round(score, 4),
                })

        scores.sort(key=lambda x: x["bm25_score"], reverse=True)
        return scores[:top_k]


def reciprocal_rank_fusion(
    vector_results: list[dict],
    bm25_results: list[dict],
    k: int = 60,
    weight_vector: float = 0.6,
    weight_bm25: float = 0.4,
) -> list[dict]:
    """RRF 融合两路检索结果

    核心公式:
    RRF_score(doc) = sum( w_i / (k + rank_i(doc)) )

    - k=60 是经验值，防止排名 1 的文档权重过大
    - 权重可调：向量更适合语义匹配，BM25 更适合精确关键词

    面试重点：为什么用 RRF 而不是直接加权分数？
    答：两路检索的分数分布不同（cosine∈[0,1], BM25无上限），不可直接比较。
    RRF 只依赖排名，天然无量纲，无需做分数归一化。
    """
    score_map: dict[str, dict] = {}
    doc_store: dict[str, dict] = {}

    # 向量路
    for rank, doc in enumerate(vector_results):
        doc_id = doc.get("id", "")
        if doc_id not in score_map:
            score_map[doc_id] = {"rrf": 0.0, "doc": doc}
            doc_store[doc_id] = doc
        score_map[doc_id]["rrf"] += weight_vector / (k + rank + 1)

    # BM25 路
    for rank, doc in enumerate(bm25_results):
        doc_id = doc.get("id", "")
        if doc_id not in score_map:
            score_map[doc_id] = {"rrf": 0.0, "doc": doc}
            doc_store[doc_id] = doc
        score_map[doc_id]["rrf"] += weight_bm25 / (k + rank + 1)

    # 按 RRF 分数排序
    fused = sorted(score_map.values(), key=lambda x: x["rrf"], reverse=True)

    results = []
    for item in fused:
        doc = item["doc"]
        doc["rrf_score"] = round(item["rrf"], 6)
        results.append(doc)

    return results


def hybrid_search(
    query: str,
    collection,
    embed_model: SentenceTransformer,
    bm25: BM25Retriever,
    top_k: int = 5,
    recall_k: int = 20,
    weight_vector: float = 0.6,
    weight_bm25: float = 0.4,
) -> list[dict]:
    """完整的混合检索流程

    1. 向量召回 recall_k 个候选
    2. BM25 关键词召回 recall_k 个候选
    3. RRF 融合 + 排序
    4. 返回 top_k
    """
    # 向量检索
    query_embedding = embed_model.encode([query], normalize_embeddings=True).tolist()
    vec_results_raw = collection.query(query_embeddings=query_embedding, n_results=recall_k)

    vector_results = []
    if vec_results_raw.get("ids") and vec_results_raw["ids"][0]:
        for i, doc_id in enumerate(vec_results_raw["ids"][0]):
            distance = vec_results_raw["distances"][0][i] if vec_results_raw.get("distances") else 0
            vector_results.append({
                "id": doc_id,
                "content": vec_results_raw["documents"][0][i],
                "metadata": vec_results_raw["metadatas"][0][i] if vec_results_raw.get("metadatas") else {},
                "vector_score": round(max(0.0, 1.0 - distance), 4),
            })

    # BM25 检索
    bm25_docs = [{"id": "", "content": d} for d in vec_results_raw.get("documents", [[]])[0]] if vec_results_raw.get("documents") else []
    if bm25_docs:
        bm25.index([{"id": v["id"], "content": v["content"]} for v in vector_results])
    else:
        # Fallback: index from collection
        all_docs = collection.get()
        if all_docs.get("documents"):
            docs_for_bm25 = []
            for i, doc_id in enumerate(all_docs.get("ids", [])):
                docs_for_bm25.append({
                    "id": doc_id,
                    "content": all_docs["documents"][i],
                    "metadata": all_docs["metadatas"][i] if all_docs.get("metadatas") else {},
                })
            bm25.index(docs_for_bm25)

    bm25_results = bm25.search(query, top_k=recall_k)

    # 格式统一
    bm25_formatted = []
    for r in bm25_results:
        bm25_formatted.append({
            "id": r.get("id", ""),
            "content": r.get("content", ""),
            "metadata": r.get("metadata", {}),
            "bm25_score": r.get("bm25_score", 0),
        })

    # RRF 融合
    fused = reciprocal_rank_fusion(
        vector_results, bm25_formatted,
        weight_vector=weight_vector, weight_bm25=weight_bm25,
    )

    return fused[:top_k]
