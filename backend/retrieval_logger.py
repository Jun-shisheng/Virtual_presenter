"""检索日志与监控 — 每次检索记录结果，支持离线分析和指标计算

面试重点：
- 为什么需要检索日志：没有数据就没法优化，所有召回率提升都要基于日志
- 日志记录什么：query, retrieved_ids, scores, latency, reranker_applied
- 怎么用日志做改进：分析低召回 query → 补充知识库 / 调整 chunk 策略 / 调阈值
"""

import json
import time
import threading
from pathlib import Path
from datetime import datetime
from collections import defaultdict

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
_log_lock = threading.Lock()


class RetrievalLogger:
    """检索日志记录器 — JSONL 格式，每条检索一行"""

    def __init__(self, log_name: str = "retrieval"):
        self.log_path = LOG_DIR / f"{log_name}.jsonl"
        self.stats_path = LOG_DIR / f"{log_name}_stats.json"

    def log(self, query: str, results: list[dict], latency_ms: float,
            top_k: int = 5, use_rerank: bool = True,
            use_hybrid: bool = False, use_qe: bool = False):
        """记录一次检索"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "top_k": top_k,
            "results_count": len(results),
            "latency_ms": round(latency_ms, 2),
            "use_rerank": use_rerank,
            "use_hybrid": use_hybrid,
            "use_query_expansion": use_qe,
            "retrieved": [
                {
                    "id": r.get("id", ""),
                    "score": r.get("score", 0),
                    "title": r.get("metadata", {}).get("title", "") if r.get("metadata") else "",
                    "content_preview": r.get("content", "")[:80],
                }
                for r in results
            ],
        }

        with _log_lock:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_stats(self, last_n: int = 100) -> dict:
        """聚合最近的检索统计"""
        records = self._read_last_n(last_n)

        if not records:
            return {"total_queries": 0}

        latencies = [r["latency_ms"] for r in records]
        result_counts = [r["results_count"] for r in records]

        # 统计常见 query
        query_freq = defaultdict(int)
        for r in records:
            query_freq[r["query"][:50]] += 1

        # 统计零召回 query
        zero_recall_queries = [
            r["query"] for r in records if r["results_count"] == 0
        ]

        return {
            "total_queries_logged": len(records),
            "zero_recall_rate": round(
                len(zero_recall_queries) / len(records), 4
            ) if records else 0,
            "zero_recall_queries": zero_recall_queries[:10],
            "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
            "p50_latency_ms": round(_percentile(latencies, 50), 2),
            "p95_latency_ms": round(_percentile(latencies, 95), 2),
            "avg_results_count": round(sum(result_counts) / len(result_counts), 2),
            "top_queries": sorted(
                [{"query": q, "count": c} for q, c in query_freq.items()],
                key=lambda x: x["count"], reverse=True
            )[:10],
            "rerank_usage_rate": round(
                sum(1 for r in records if r["use_rerank"]) / len(records), 4
            ),
            "hybrid_usage_rate": round(
                sum(1 for r in records if r["use_hybrid"]) / len(records), 4
            ),
        }

    def get_recent_queries(self, limit: int = 50) -> list[dict]:
        """获取最近的检索记录"""
        return self._read_last_n(limit)

    def _read_last_n(self, n: int) -> list[dict]:
        """读取最近 n 条日志"""
        if not self.log_path.exists():
            return []

        with _log_lock:
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

        records = []
        for line in lines[-n:]:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        return records

    def clear(self):
        """清空日志（用于重置）"""
        with _log_lock:
            if self.log_path.exists():
                self.log_path.unlink()


def _percentile(data: list[float], pct: float) -> float:
    """计算百分位数"""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * pct / 100
    f = int(k)
    c = k - f
    if f + 1 < len(sorted_data):
        return sorted_data[f] + c * (sorted_data[f + 1] - sorted_data[f])
    return sorted_data[f]


# 全局单例
_global_logger: RetrievalLogger | None = None


def get_logger() -> RetrievalLogger:
    global _global_logger
    if _global_logger is None:
        _global_logger = RetrievalLogger()
    return _global_logger
