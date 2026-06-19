"""RAG 检索评估框架 — Recall@k, Precision@k, MRR, NDCG

面试可展示：
- 评估指标原理与计算公式
- 自动生成测试集（基于已有知识库构造问答对）
- 离线评估 vs 在线评估的差异
"""

import math
import random
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class EvalResult:
    """单次检索评估结果"""
    query: str
    retrieved_ids: list[str]
    relevant_ids: list[str]
    recall_at_k: dict[int, float] = field(default_factory=dict)
    precision_at_k: dict[int, float] = field(default_factory=dict)
    mrr: float = 0.0
    ndcg_at_k: dict[int, float] = field(default_factory=dict)


def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """召回率 = 前k个结果中相关文档数 / 总相关文档数

    recall@k 越低说明漏检越多。面试常问：召回率 vs 精确率的 trade-off。
    """
    if not relevant_ids:
        return 1.0
    retrieved_k = set(retrieved_ids[:k])
    relevant_set = set(relevant_ids)
    return len(retrieved_k & relevant_set) / len(relevant_set)


def precision_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """精确率 = 前k个结果中相关文档数 / k

    精确率高但召回率低 → 返回的都对但漏了很多；
    召回率高但精确率低 → 覆盖面广但噪声大。
    """
    if k <= 0:
        return 0.0
    retrieved_k = set(retrieved_ids[:k])
    relevant_set = set(relevant_ids)
    return len(retrieved_k & relevant_set) / k


def mrr(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
    """MRR (Mean Reciprocal Rank): 第一个相关文档的排名的倒数

    值域 [0, 1]，越接近 1 越好。衡量的是「第一个正确答案排在第几名」。
    面试重点：MRR 对第一个相关文档的位置极其敏感，适用于 QA 场景。
    """
    relevant_set = set(relevant_ids)
    for i, doc_id in enumerate(retrieved_ids):
        if doc_id in relevant_set:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int,
              relevance_scores: dict[str, float] | None = None) -> float:
    """NDCG@k: 归一化折损累积增益

    考虑两个因素：
    1. 相关文档排得越靠前分数越高（位置折损）
    2. 相关程度越高分数越高（分级相关性）

    对比 recall 只看「相关与否」，NDCG 能区分「高度相关」和「部分相关」。
    面试重点：解释 DCG → IDCG → NDCG 的推导过程。
    """
    if k <= 0 or not relevant_ids:
        return 0.0

    # 构造分级相关性：人工标注的可以给高分，自动生成的默认 1.0
    if relevance_scores is None:
        relevance_scores = {rid: 1.0 for rid in relevant_ids}

    def dcg(ids: list[str]) -> float:
        score = 0.0
        for i, doc_id in enumerate(ids[:k]):
            rel = relevance_scores.get(doc_id, 0.0)
            if i == 0:
                score += rel
            else:
                score += rel / math.log2(i + 2)  # position discount from 2
        return score

    actual_dcg = dcg(retrieved_ids)
    ideal_ids = sorted(relevant_ids, key=lambda x: relevance_scores.get(x, 0.0), reverse=True)
    ideal_dcg = dcg(ideal_ids)

    if ideal_dcg == 0:
        return 0.0
    return actual_dcg / ideal_dcg


def evaluate_single(retrieved_ids: list[str], relevant_ids: list[str],
                    k_values: list[int] | None = None,
                    relevance_scores: dict[str, float] | None = None) -> EvalResult:
    """对单次检索计算所有指标"""
    if k_values is None:
        k_values = [1, 3, 5, 10]

    result = EvalResult(
        query="",
        retrieved_ids=retrieved_ids,
        relevant_ids=relevant_ids,
    )

    for k in k_values:
        result.recall_at_k[k] = round(recall_at_k(retrieved_ids, relevant_ids, k), 4)
        result.precision_at_k[k] = round(precision_at_k(retrieved_ids, relevant_ids, k), 4)
        result.ndcg_at_k[k] = round(ndcg_at_k(retrieved_ids, relevant_ids, k, relevance_scores), 4)

    result.mrr = round(mrr(retrieved_ids, relevant_ids), 4)

    return result


def evaluate_batch(results: list[EvalResult], k_values: list[int] | None = None) -> dict:
    """批量评估，返回平均指标"""
    if k_values is None:
        k_values = [1, 3, 5, 10]

    if not results:
        return {"error": "No results to evaluate"}

    summary = {"num_queries": len(results), "metrics": {}}

    for k in k_values:
        summary["metrics"][f"recall@{k}"] = round(
            sum(r.recall_at_k.get(k, 0) for r in results) / len(results), 4
        )
        summary["metrics"][f"precision@{k}"] = round(
            sum(r.precision_at_k.get(k, 0) for r in results) / len(results), 4
        )
        summary["metrics"][f"ndcg@{k}"] = round(
            sum(r.ndcg_at_k.get(k, 0) for r in results) / len(results), 4
        )

    summary["metrics"]["mrr"] = round(
        sum(r.mrr for r in results) / len(results), 4
    )

    return summary


def generate_test_set(knowledge_chunks: list[dict]) -> list[dict]:
    """基于已有知识库自动生成测试集

    对每个 chunk：
    1. 取 chunk 内容作为 ground truth 相关文档
    2. 用 chunk 中的关键词构造查询
    3. 随机采样不相关的 chunk 作负例

    面试可讲：自动测试集节省人力，但需要人工抽检质量。
    """
    test_queries = []

    for chunk in knowledge_chunks:
        content = chunk.get("content", "")
        chunk_id = chunk.get("id", "")

        if len(content) < 20:
            continue

        # 从 chunk 中提取关键句作为查询
        sentences = content.replace("。", "。\n").replace("！", "！\n").replace("？", "？\n").split("\n")
        candidates = [s.strip() for s in sentences if 10 <= len(s.strip()) <= 50]

        if not candidates:
            # 取前 40 个字符
            query = content[:40]
        else:
            query = random.choice(candidates)

        test_queries.append({
            "query": query,
            "relevant_ids": [chunk_id],
            "title": chunk.get("metadata", {}).get("title", ""),
        })

    return test_queries


def run_evaluation(rag_module, test_queries: list[dict],
                   top_k: int = 10, use_hybrid: bool = False) -> dict:
    """对 RAG 模块跑完整评估

    Args:
        rag_module: rag_retriever 模块
        test_queries: generate_test_set 的输出
        top_k: 检索返回数量
        use_hybrid: 是否使用混合检索

    Returns:
        包含逐条结果和汇总指标的 dict
    """
    eval_results = []

    for tq in test_queries:
        query = tq["query"]
        relevant = tq["relevant_ids"]

        # 检索
        if use_hybrid and hasattr(rag_module, 'hybrid_search'):
            retrieved = rag_module.hybrid_search(query, top_k=top_k)
        else:
            retrieved = rag_module.search_knowledge(query, top_k=top_k, use_rerank=True)

        retrieved_ids = [r.get("id", "") for r in retrieved]

        eval_result = evaluate_single(retrieved_ids, relevant)
        eval_result.query = query
        eval_results.append(eval_result)

    summary = evaluate_batch(eval_results)

    return {
        "summary": summary,
        "details": [
            {
                "query": r.query,
                "recall@3": r.recall_at_k.get(3, 0),
                "recall@5": r.recall_at_k.get(5, 0),
                "mrr": r.mrr,
            }
            for r in eval_results
        ],
        "total_queries": len(eval_results),
    }
