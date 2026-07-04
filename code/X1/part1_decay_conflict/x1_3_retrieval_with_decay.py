"""
x1_3_retrieval_with_decay.py — 两阶段检索：粗筛 + 精排

本脚本演示衰减如何融入检索流程。核心公式:
  final_score = semantic_score × retention × forgotten_multiplier

运行:
  python x1_3_retrieval_with_decay.py

输入: fixtures/sample_memories.json
输出:
  - 同一 query 下「仅语义排序」与「语义×衰减排序」的 Top-5 结果对比
  - 哪些记忆因访问强化进入 Top-N，哪些因衰减被挤出 Top-N
  - 被遗忘记忆的降权效果

关键设计决策: 不是简单的"相似度 × 衰减"一步到位，而是:
  阶段 1 (粗筛): 向量索引快速过滤 → 圈定候选集 (几十到几百条)
  阶段 2 (精排): 只在候选集上叠加衰减维度 → final_score 排序
  这样做的原因是百万级记忆无法逐条算衰减分再排——粗筛用向量索引的毫秒级性能。

对应正文: X1-1 §3.1 "两阶段检索：先语义，再衰减"
"""

import math
import json
import os
from datetime import datetime


NOW = datetime(2026, 2, 1, 12, 0, 0)
DEFAULT_DECAY_RATE = 1.5
DEFAULT_DECAY_RATE_MULTIPLIERS = {"working": 1, "short_term": 7, "long_term": 60}
FORGOTTEN_SCORE_MULTIPLIER = 0.1
ARCHIVE_THRESHOLD = 0.3


def calculate_retention(created_at: datetime, memory_type: str, access_count: int) -> float:
    hours_elapsed = (NOW - created_at).total_seconds() / 3600
    multiplier = DEFAULT_DECAY_RATE_MULTIPLIERS.get(memory_type, 1)
    reinforcement = math.log1p(access_count)
    strength = DEFAULT_DECAY_RATE * multiplier * (1 + reinforcement)
    return max(0.0, min(1.0, math.exp(-hours_elapsed / (24 * strength))))


def load_memories(filepath: str) -> list:
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["memories"]


def simulate_semantic_score(memory: dict, query: str) -> float:
    """
    模拟语义相似度分数（中文友好）。
    实际系统中这是 embedding 余弦相似度，这里用主题关键词字典模拟。

    思路：每个语义主题（编程语言、食物偏好、云平台等）维护一组关键词；
    - 先识别 query 涉及哪些主题；
    - 然后看 memory 的内容在该主题下命中了多少关键词。
    这样既贴近"语义相关"的直觉，又不需要真正的 embedding 模型。
    """
    content = memory["content"]

    # 主题词典：覆盖示例库 12 条记忆的所有话题
    topic_keywords = {
        "编程语言": ["Python", "Java", "Go", "Rust", "编程", "语言", "开发", "后端", "主力", "微服务", "框架"],
        "食物偏好": ["吃", "披萨", "素", "食物", "饮食", "餐厅", "过敏", "花生", "肉类"],
        "云平台": ["AWS", "阿里云", "云", "平台", "迁移", "公司"],
        "编辑器": ["VS Code", "编辑器", "IDE", "插件"],
        "电商项目": ["电商", "项目", "Django", "PostgreSQL", "技术栈"],
        "代码风格": ["代码", "风格", "注释", "简洁"],
        "学习": ["学", "教程", "初学者", "考虑"],
    }

    # 找出 query 涉及的主题
    query_topics = [
        topic for topic, keywords in topic_keywords.items()
        if any(kw in query for kw in keywords)
    ]

    if not query_topics:
        # 兜底：query 没识别出主题，返回最低分（仍高于粗筛阈值以保证可见性）
        return 0.10

    # 在相关主题下，统计 memory 命中的关键词数
    score = 0.0
    for topic in query_topics:
        keywords = topic_keywords[topic]
        hits = sum(1 for kw in keywords if kw in content)
        score += hits * 0.20

    return min(1.0, score)


def two_stage_retrieval(
    memories: list,
    query: str,
    quality_threshold: float = 0.15,
    use_decay: bool = True,
) -> list:
    """
    两阶段检索：
    1. 粗筛：过滤 semantic_score < quality_threshold 的记忆
    2. 精排：semantic_score × retention（如果 use_decay=True）
    """
    candidates = []
    for mem in memories:
        sem_score = simulate_semantic_score(mem, query)
        if sem_score < quality_threshold:
            continue

        retention = calculate_retention(
            datetime.fromisoformat(mem["created_at"]),
            mem["memory_type"],
            mem["access_count"],
        )

        is_forgotten = retention < ARCHIVE_THRESHOLD
        forgotten_mult = FORGOTTEN_SCORE_MULTIPLIER if is_forgotten else 1.0

        if use_decay:
            final_score = sem_score * retention * forgotten_mult
        else:
            final_score = sem_score

        candidates.append({
            "id": mem["id"],
            "content": mem["content"],
            "semantic_score": sem_score,
            "retention": retention,
            "is_forgotten": is_forgotten,
            "final_score": final_score,
            "memory_type": mem["memory_type"],
            "is_active": mem["is_active"],
        })

    candidates.sort(key=lambda x: x["final_score"], reverse=True)
    return candidates


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    fixtures_path = os.path.join(script_dir, "fixtures", "sample_memories.json")
    memories = load_memories(fixtures_path)

    queries = [
        "用户用什么编程语言",
        "用户喜欢吃什么",
        "用户用什么云平台",
    ]

    print("=" * 85)
    print("X1-3 两阶段检索对比：仅语义排序 vs 语义×衰减排序")
    print(f"{'=' * 85}")

    for query in queries:
        print(f"\n{'-' * 85}")
        print(f"查询: 「{query}」")
        print(f"{'-' * 85}")

        semantic_only = two_stage_retrieval(memories, query, use_decay=False)
        with_decay = two_stage_retrieval(memories, query, use_decay=True)

        print(f"\n  {'排名':<6} {'仅语义排序':<55} {'分数':<8}")
        print(f"  {'-' * 69}")
        for i, c in enumerate(semantic_only[:5]):
            print(f"  #{i+1:<5} {c['content']:<55} {c['final_score']:.3f}")

        print(f"\n  {'排名':<6} {'语义×衰减排序':<50} {'分数':<8} {'保留率':<10}")
        print(f"  {'-' * 74}")
        for i, c in enumerate(with_decay[:5]):
            flag = " [!]遗忘" if c["is_forgotten"] else ""
            print(f"  #{i+1:<5} {c['content']:<47}{flag:<4}  {c['final_score']:.3f}     {c['retention']:.3f}")

        # 对比变化
        top5_sem = set(c["id"] for c in semantic_only[:5])
        top5_decay = set(c["id"] for c in with_decay[:5])
        promoted = top5_decay - top5_sem
        demoted = top5_sem - top5_decay

        if promoted or demoted:
            print(f"\n  排序变化：")
            for pid in promoted:
                mem = next(c for c in with_decay if c["id"] == pid)
                print(f"    ^ {pid} 进入 Top5（保留率={mem['retention']:.3f}，访问强化效果）")
            for pid in demoted:
                mem = next(c for c in semantic_only if c["id"] == pid)
                print(f"    v {pid} 跌出 Top5（保留率低，衰减降权）")

    # 遗忘记忆的特殊处理
    print(f"\n{'=' * 85}")
    print("遗忘记忆的降权效果")
    print(f"{'=' * 85}")
    print(f"  被标记为遗忘的记忆（保留率 < {ARCHIVE_THRESHOLD}），")
    print(f"  final_score 会乘以 forgotten_score_multiplier = {FORGOTTEN_SCORE_MULTIPLIER}")
    print(f"  这些记忆不会被删除，但检索排名大幅下降。")
    print()


if __name__ == "__main__":
    main()
