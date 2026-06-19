"""查询扩展 — 多策略改写提升召回率

面试重点：
- 查询扩展 (Query Expansion) vs 查询改写 (Query Rewriting)
- 多轮召回取并集：为什么能提升召回？因为不同表述方向互补
- 生成式扩展 vs 规则扩展：成本/效果 trade-off

提升召回的三种策略：
1. 关键词提取：从查询中提取关键实体，构造多条检索
2. 同义改写：LLM 生成 2-3 个语义等价但表述不同的查询
3. 子问题拆分：复杂问题拆解为多个子问题分别检索
"""

import re
import logging

logger = logging.getLogger("query_expansion")


def extract_keywords(query: str, max_keywords: int = 3) -> list[str]:
    """规则提取关键词

    思路：去掉停用词/语气词，提取核心名词/NER 实体。
    对中文简历/直播间场景的常见词做了针对性过滤。
    """
    stopwords = {
        "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一",
        "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
        "没有", "看", "好", "自己", "这", "他", "她", "它", "们", "那", "些",
        "什么", "怎么", "怎样", "哪", "吗", "呢", "吧", "啊", "哦", "嗯",
        "可以", "能", "应该", "可能", "一定", "需要", "想", "觉得", "知道",
        "请问", "问一下", "问问", "帮", "让", "给",
    }

    # 中文分词简化
    tokens = list(query)

    # 提取连续的非停用词片段作为关键词
    keywords = []
    current = ""

    for char in tokens:
        if char in stopwords or char in "，。！？、：；""''（）【】《》 \t\n":
            if current and len(current) >= 2:
                keywords.append(current)
            current = ""
        else:
            current += char

    if current and len(current) >= 2:
        keywords.append(current)

    # 去重 + 限制数量
    seen = set()
    unique = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)

    return unique[:max_keywords]


def generate_expanded_queries(query: str, llm_generate_fn=None) -> list[str]:
    """生成式查询扩展 — 使用 LLM 生成同义改写

    Args:
        query: 原始查询
        llm_generate_fn: LLM 生成函数 (可选)，不提供则只用规则

    Returns:
        扩展后的查询列表（包含原查询）
    """
    expanded = [query]

    # 策略 1: 规则提取关键词构造子查询
    keywords = extract_keywords(query)
    for kw in keywords:
        if kw not in query:
            # 用关键词构造一个精简查询
            expanded.append(kw)

    # 策略 2: LLM 同义改写
    if llm_generate_fn is not None:
        rewrite_prompt = (
            f"请将以下问题改写为2个表达不同但意思相同的查询，用于提升搜索引擎召回率。\n"
            f"只需返回改写后的查询，每行一个，不要编号和解释。\n"
            f"原问题：{query}"
        )
        try:
            rewrites = llm_generate_fn(rewrite_prompt, max_new_tokens=128, temperature=0.3)
            for line in rewrites.strip().split("\n"):
                line = line.strip()
                if line and line != query and len(line) >= 3:
                    expanded.append(line)
        except Exception as e:
            logger.warning(f"LLM query expansion failed: {e}")

    return expanded


def multi_round_recall(
    query: str,
    search_fn,
    top_k: int = 5,
    llm_generate_fn=None,
    fusion: str = "union",
) -> list[dict]:
    """多轮召回：扩展查询 → 每轮独立检索 → 融合

    Args:
        query: 原始查询
        search_fn: 检索函数 (query, top_k) → list[dict]
        top_k: 每轮检索返回数量
        llm_generate_fn: LLM 生成函数 (可选)
        fusion: "union" (取并集) 或 "rrf" (排名融合)

    Returns:
        融合后的 top_k 结果

    面试重点：
    - union: 简单取并集去重，提升 coverage 但可能引入噪声
    - 适合「宁可多检不可漏检」的场景（如 QA）
    - trade-off: 召回率 ↑ 但精确率可能 ↓，需要 reranker 兜底
    """
    queries = generate_expanded_queries(query, llm_generate_fn)

    all_results: dict[str, dict] = {}
    result_ranks: dict[str, list[int]] = {}  # doc_id -> [rank in each round]

    for q_idx, q in enumerate(queries):
        try:
            round_results = search_fn(q, top_k=top_k)
        except Exception as e:
            logger.warning(f"Recall round {q_idx} failed for '{q[:30]}': {e}")
            continue

        for rank, r in enumerate(round_results):
            doc_id = r.get("id", "")
            if doc_id not in all_results:
                all_results[doc_id] = r
                result_ranks[doc_id] = []
            result_ranks[doc_id].append(rank)

    if fusion == "union":
        # 按各轮最优排名排序
        scored = []
        for doc_id, ranks in result_ranks.items():
            # 多轮中出现次数越多 + 排名越靠前 = 越相关
            bonus = min(ranks)  # 最好排名
            frequency = len(ranks)  # 出现次数
            score = frequency * 10 - bonus  # 出现次数权重大于排名
            scored.append((score, doc_id))

        scored.sort(reverse=True)
        result = []
        for _, doc_id in scored[:top_k]:
            result.append(all_results[doc_id])
        return result

    else:
        # 简单并集
        return list(all_results.values())[:top_k]
