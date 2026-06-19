"""文档分块策略 — 多种可切换的分块方法

面试重点：
- 分块大小对检索的影响：太大 → 噪声多 + 超出 LLM context；太小 → 语义不完整
- 不同场景选不同策略：FAQ 用语义分块，文档用递归分块，代码用固定分块
- overlap 的作用：保持边界上下文连贯，避免关键信息被切断
"""

import re
from dataclasses import dataclass
from enum import Enum


class ChunkStrategy(Enum):
    SEMANTIC = "semantic"      # 按标点/段落语义切分
    FIXED_SIZE = "fixed"       # 固定长度 + overlap
    RECURSIVE = "recursive"    # 递归分隔符切分
    SENTENCE = "sentence"      # 按句子切分


@dataclass
class ChunkConfig:
    strategy: ChunkStrategy = ChunkStrategy.SEMANTIC
    max_chunk: int = 512
    min_chunk: int = 80
    overlap: int = 50           # 相邻块的重叠字符数
    separators: list[str] = None  # 递归分隔符优先级列表


def chunk_text(text: str, strategy: ChunkStrategy | None = None,
               config: ChunkConfig | None = None) -> list[str]:
    """统一入口：按指定策略分块"""
    cfg = config or ChunkConfig()
    strat = strategy or cfg.strategy

    if strat == ChunkStrategy.SEMANTIC:
        return semantic_chunk(text, cfg.max_chunk, cfg.min_chunk)
    elif strat == ChunkStrategy.FIXED_SIZE:
        return fixed_size_chunk(text, cfg.max_chunk, cfg.overlap)
    elif strat == ChunkStrategy.RECURSIVE:
        separators = cfg.separators or ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]
        return recursive_chunk(text, cfg.max_chunk, cfg.overlap, separators)
    elif strat == ChunkStrategy.SENTENCE:
        return sentence_chunk(text, cfg.max_chunk, cfg.min_chunk)
    else:
        return semantic_chunk(text, cfg.max_chunk, cfg.min_chunk)


def semantic_chunk(text: str, max_chunk: int = 512, min_chunk: int = 80) -> list[str]:
    """语义分块：标点边界 + 短句合并 + 长句递归拆分

    适用：文档、知识库、对话记录
    """
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
            # 长句按逗号拆
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


def fixed_size_chunk(text: str, chunk_size: int = 400, overlap: int = 50) -> list[str]:
    """固定大小分块 + overlap

    适用：代码、结构化文本
    """
    if len(text) <= chunk_size:
        return [text.strip()] if text.strip() else []

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        # 尝试在边界处截断（优先句号/换行）
        if end < len(text):
            for sep in ["\n", "。", "！", "？", "；", "，"]:
                pos = text.rfind(sep, start, end)
                if pos > start + chunk_size // 3:
                    end = pos + 1
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - overlap if end < len(text) else end

    return chunks


def recursive_chunk(text: str, chunk_size: int = 500, overlap: int = 50,
                    separators: list[str] | None = None) -> list[str]:
    """递归分块：按优先级依次尝试分隔符

    思路：先用高阶分隔符（段落），太长的再用低阶（句子 → 逗号 → 字符）
    这是 LangChain RecursiveCharacterTextSplitter 的同款策略。

    面试重点：递归分块能保持语义完整性，比固定分块对最终检索质量提升明显。
    """
    if separators is None:
        separators = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]

    if len(text) <= chunk_size:
        return [text.strip()] if text.strip() else []

    # 找第一个能分割的分隔符
    for sep in separators:
        if sep == "":
            # 最后手段：按字符切
            return fixed_size_chunk(text, chunk_size, overlap)

        parts = text.split(sep)
        if len(parts) == 1:
            continue

        # 用这个分隔符，对每个部分递归处理
        chunks = []
        buffer = ""

        for part in parts:
            # 带上分隔符
            candidate = (buffer + sep + part).strip(sep).strip() if buffer else part

            if len(candidate) <= chunk_size:
                buffer = candidate
            else:
                if buffer:
                    chunks.append(buffer)
                # 递归处理超长的部分
                sub_chunks = recursive_chunk(part, chunk_size, overlap, separators)
                chunks.extend(sub_chunks)
                buffer = ""

        if buffer:
            chunks.append(buffer)

        return [c for c in chunks if c.strip()]

    return [text.strip()]


def sentence_chunk(text: str, max_chunk: int = 512, min_chunk: int = 40) -> list[str]:
    """句子级分块：每句一块，短句合并

    适用：FAQ、短对话
    """
    sentences = re.split(r'(?<=[。！？~！？…\n])\s*', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks = []
    buffer = ""

    for sent in sentences:
        combined = buffer + sent if buffer else sent
        if len(combined) <= max_chunk:
            buffer = combined
        else:
            if buffer.strip() and len(buffer) >= min_chunk:
                chunks.append(buffer.strip())
            buffer = sent

    if buffer.strip() and len(buffer) >= min_chunk:
        chunks.append(buffer.strip())

    return chunks


def estimate_chunk_count(text: str, strategy: ChunkStrategy, max_chunk: int = 512) -> int:
    """估算分块数量，用于 UI 展示"""
    return len(chunk_text(text, strategy, ChunkConfig(max_chunk=max_chunk)))
