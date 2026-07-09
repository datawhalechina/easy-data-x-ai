import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI, OpenAIError

from config import Config

if __package__:
    from .d2_chunking_strategies import (
        dynamic_overlap_chunk,
        fixed_overlap_chunk,
        flatten_parent_child,
        parent_child_chunk,
        semantic_chunk,
    )
else:
    from d2_chunking_strategies import (
        dynamic_overlap_chunk,
        fixed_overlap_chunk,
        flatten_parent_child,
        parent_child_chunk,
        semantic_chunk,
    )

# ============================================================
# d2_5：高级 Chunking 策略对比实验
#
# 对比三种策略 + 固定 overlap 基线：
#   1. 固定 overlap（基线）
#   2. 语义分块
#   3. 动态 overlap
#   4. 父子 chunk（子块检索 → 父块上下文）
#
# 运行前：
#   - pip install pyseekdb openai
#   - 优先使用 seekdb 向量检索；不可用时自动降级为内存检索
#   - 语义分块需要配置 SILICONFLOW_API_KEY（见 .env.example）
#
# 给学生的背景说明：
#   - 本实验同时包含「分块阶段」和「检索阶段」两个维度。
#   - seekdb 嵌入式模式不可用时，只影响检索后端，会降级为内存词项匹配。
#   - SILICONFLOW_API_KEY 只用于语义分块阶段的句子 Embedding。
#   - 因此：seekdb 降级不代表 API Key 无效；配置了 Key 仍会运行语义分块。
# ============================================================


SAMPLE_LONG_DOC = """
# 数据库运维手册

## 错误码参考

错误码 E-4011 表示连接被拒绝。解决方案：确认数据库服务是否正在运行，检查防火墙规则是否允许对应端口的访问。若服务正常但仍被拒绝，请核对白名单配置。

错误码 E-4012 表示数据库连接超时。解决方案：检查网络配置，确认数据库服务端口是否开放，建议超时时间设置为 30 秒。同时检查中间网络设备是否存在丢包。

错误码 E-4013 表示认证失败。解决方案：检查用户名和密码是否正确，确认账户是否被锁定。如果账户被锁定，需要联系管理员解锁后重试。

## 性能优化

数据库查询性能优化指南：合理使用索引可以将查询速度提升 10 倍以上。建议对高频查询的 WHERE 条件列建立索引。避免在索引列上使用函数，否则会导致索引失效。

执行计划分析是定位慢查询的关键步骤。开启慢查询日志后，优先优化扫描行数最多的 SQL。对于大表分页，推荐使用延迟关联或游标分页替代深分页 OFFSET。

## 访问控制

访问控制架构设计：基于 RBAC 模型实现用户权限管理，支持角色继承和细粒度的资源级权限控制。建议按最小权限原则分配角色，定期审计权限配置。

多租户场景下，应在连接层注入租户标识，并在 SQL 层强制附加租户过滤条件，避免跨租户数据泄露。

## 版本发布

OB-4.2.1 版本新特性：支持在线 DDL 操作、改进了并行查询引擎、修复了分区表在特定条件下的数据倾斜问题。升级前请备份数据并阅读升级指南。

## 备份与恢复

数据备份与恢复：建议每天进行全量备份，每小时进行增量备份。恢复时优先使用最近的全量备份，再应用增量备份。备份文件应存储在独立的存储介质上。

## 连接池配置

连接池配置最佳实践：最大连接数建议设置为 CPU 核心数的 2-4 倍。连接超时时间建议设置为 30 秒，空闲连接超时建议设置为 600 秒。监控活跃连接数，避免连接泄漏。
""".strip()


EVAL_QUERIES = [
    {"query": "错误码 E-4012 连接超时怎么解决", "keyword": "E-4012"},
    {"query": "RBAC 角色权限如何设计", "keyword": "RBAC"},
    {"query": "OB-4.2.1 在线 DDL 新特性", "keyword": "在线 DDL"},
    {"query": "连接池最大连接数设多少", "keyword": "连接池"},
    {"query": "慢查询执行计划怎么分析", "keyword": "执行计划"},
]


def _extract_query_terms(query: str) -> list[str]:
    """从查询中提取中英文关键词片段。"""
    terms = re.findall(r"[A-Za-z0-9][\w.-]*|[\u4e00-\u9fff]{2,}", query)
    return [t for t in terms if len(t) >= 2]


def _lexical_score(query: str, text: str) -> float:
    terms = _extract_query_terms(query)
    if not terms:
        return 0.0
    return sum(1.0 for term in terms if term in text)


class InMemoryRetriever:
    """seekdb 不可用时的降级检索器（词项匹配打分）。"""

    def __init__(self, texts: list[str], metadatas: list[dict]):
        self.texts = texts
        self.metadatas = metadatas

    def search(self, query: str, k: int = 3) -> list[str]:
        scored = [
            (_lexical_score(query, text), idx)
            for idx, text in enumerate(self.texts)
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        top_indices = [idx for _, idx in scored[:k]]
        return [self.texts[idx] for idx in top_indices]

    def search_with_context(self, query: str, k: int = 3) -> list[str]:
        scored = [
            (_lexical_score(query, text), idx)
            for idx, text in enumerate(self.texts)
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        contexts: list[str] = []
        for _, idx in scored[:k]:
            contexts.append(self.texts[idx])
            parent_text = self.metadatas[idx].get("parent_text", "")
            if parent_text:
                contexts.append(parent_text)
        return contexts


class SeekdbRetriever:
    """基于 pyseekdb 的向量检索器。"""

    def __init__(self, collection):
        self.collection = collection

    def search(self, query: str, k: int = 3) -> list[str]:
        results = self.collection.query(query_texts=[query], n_results=k)
        return results.get("documents", [[]])[0]

    def search_with_context(self, query: str, k: int = 3) -> list[str]:
        results = self.collection.query(query_texts=[query], n_results=k)
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        contexts = list(docs)
        for meta in metas:
            parent_text = meta.get("parent_text", "")
            if parent_text:
                contexts.append(parent_text)
        return contexts


def build_embed_fn():
    api_key = Config.SILICONFLOW_API_KEY
    if not api_key or api_key == "YOUR_API_KEY":
        raise RuntimeError("语义分块需要 SILICONFLOW_API_KEY，请在 code/.env 中配置")

    client = OpenAI(
        api_key=Config.SILICONFLOW_API_KEY,
        base_url=Config.SILICONFLOW_BASE_URL,
    )

    def embed_batch(texts: list[str]) -> list[list[float]]:
        response = client.embeddings.create(model="BAAI/bge-m3", input=texts)
        return [item.embedding for item in response.data]

    return embed_batch


def has_siliconflow_key() -> bool:
    api_key = Config.SILICONFLOW_API_KEY
    return bool(api_key and api_key != "YOUR_API_KEY")


def prepare_strategy_chunks(strategy: str) -> tuple[list[str], list[dict]]:
    if strategy == "fixed":
        texts = fixed_overlap_chunk(SAMPLE_LONG_DOC, chunk_size=200, overlap=30)
        return texts, [{"strategy": strategy} for _ in texts]

    if strategy == "semantic":
        texts = semantic_chunk(SAMPLE_LONG_DOC, build_embed_fn())
        return texts, [{"strategy": strategy} for _ in texts]

    if strategy == "dynamic":
        texts = dynamic_overlap_chunk(SAMPLE_LONG_DOC, chunk_size=200)
        return texts, [{"strategy": strategy} for _ in texts]

    if strategy == "parent_child":
        parents = parent_child_chunk(SAMPLE_LONG_DOC, parent_size=500, child_size=120)
        return flatten_parent_child(parents)

    raise ValueError(f"未知策略：{strategy}")


def create_seekdb_retriever(strategy: str, use_parent_context: bool) -> SeekdbRetriever | None:
    try:
        import pyseekdb
    except ImportError:
        return None

    try:
        db = pyseekdb.Client()
    except ValueError:
        return None

    coll_name = f"d2_chunking_{strategy}"
    if db.has_collection(coll_name):
        db.delete_collection(coll_name)
    collection = db.create_collection(name=coll_name)

    texts, metadatas = prepare_strategy_chunks(strategy)
    collection.add(
        ids=[f"chunk_{i}" for i in range(len(texts))],
        documents=texts,
        metadatas=metadatas,
    )
    retriever = SeekdbRetriever(collection)
    retriever.use_parent_context = use_parent_context
    retriever.chunk_count = len(texts)
    retriever.avg_chunk_size = sum(len(t) for t in texts) / max(len(texts), 1)
    return retriever


def create_memory_retriever(strategy: str) -> InMemoryRetriever:
    texts, metadatas = prepare_strategy_chunks(strategy)
    retriever = InMemoryRetriever(texts, metadatas)
    retriever.chunk_count = len(texts)
    retriever.avg_chunk_size = sum(len(t) for t in texts) / max(len(texts), 1)
    return retriever


def recall_at_k(retriever, query: str, keyword: str, use_parent_context: bool, k: int = 3) -> bool:
    if use_parent_context:
        docs = retriever.search_with_context(query, k=k)
    else:
        docs = retriever.search(query, k=k)
    return keyword in " ".join(docs)


def evaluate_strategy(strategy: str, backend: str, use_parent_context: bool = False) -> dict:
    if backend == "seekdb":
        retriever = create_seekdb_retriever(strategy, use_parent_context)
        if retriever is None:
            raise RuntimeError("seekdb 不可用")
    else:
        retriever = create_memory_retriever(strategy)

    hits = sum(
        int(recall_at_k(retriever, item["query"], item["keyword"], use_parent_context))
        for item in EVAL_QUERIES
    )
    return {
        "strategy": strategy,
        "chunk_count": retriever.chunk_count,
        "avg_chunk_size": retriever.avg_chunk_size,
        "recall_at_3": hits / len(EVAL_QUERIES),
    }


def detect_backend() -> str:
    try:
        import pyseekdb
        pyseekdb.Client()
        return "seekdb"
    except (ImportError, ValueError):
        print(">>> seekdb 嵌入式模式不可用，降级为内存词项匹配检索")
        return "memory"


def print_runtime_notes(backend: str):
    print(">>> 实验说明：分块策略与检索后端是两件事")
    if backend == "memory":
        print(">>> 当前 seekdb 不可用，仅检索阶段降级；不影响语义分块调用 Embedding API")
    if has_siliconflow_key():
        print(">>> 已检测到 SILICONFLOW_API_KEY，将尝试运行语义分块")
    else:
        print(">>> 未检测到 SILICONFLOW_API_KEY，稍后会跳过语义分块")


def print_report(rows: list[dict], backend: str):
    print("\n" + "=" * 72)
    print("  D2 高级 Chunking 策略对比实验")
    print(f"  检索后端：{'seekdb 向量检索' if backend == 'seekdb' else '内存词项匹配（降级）'}")
    print("=" * 72)
    print(f"  {'策略':<16} {'块数':>6} {'均长':>8} {'Recall@3':>10}")
    print("  " + "-" * 44)

    labels = {
        "fixed": "固定 overlap",
        "semantic": "语义分块",
        "dynamic": "动态 overlap",
        "parent_child": "父子 chunk",
    }
    for row in rows:
        label = labels.get(row["strategy"], row["strategy"])
        print(
            f"  {label:<16} {row['chunk_count']:>6} "
            f"{row['avg_chunk_size']:>7.0f}字 {row['recall_at_3']:>9.0%}"
        )

    print("\n[分析要点]")
    print("   · 固定 overlap：实现简单，但容易在章节边界处切断语义")
    print("   · 语义分块：按主题跳变切分，适合话题切换频繁的长文")
    print("   · 动态 overlap：在标题/段落边界加大重叠，低成本改善边界召回")
    print("   · 父子 chunk：子块精准检索 + 父块完整上下文，适合多跳推理")
    print("=" * 72 + "\n")


def main():
    backend = detect_backend()
    print_runtime_notes(backend)
    results: list[dict] = []

    results.append(evaluate_strategy("fixed", backend))
    results.append(evaluate_strategy("dynamic", backend))
    results.append(evaluate_strategy("parent_child", backend, use_parent_context=True))

    try:
        results.append(evaluate_strategy("semantic", backend))
    except (RuntimeError, OpenAIError) as exc:
        print(">>> 跳过语义分块：", exc)

    print_report(results, backend)


if __name__ == "__main__":
    main()
