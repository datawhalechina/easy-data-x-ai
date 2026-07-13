import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyseekdb

# ============================================================
# d3_3：对比实验——纯向量检索 vs 混合检索（含元数据过滤）
#
# 演示：
#   1. 同一组查询，分别用纯向量检索和混合/增强检索
#   2. 直观看到两种策略在精确匹配场景下的结果差距
#   3. 展示三种检索能力的适用场景：
#      - 向量语义：理解"意思"
#      - 全文关键词：精确匹配错误码、函数名等
#      - 元数据过滤：精确匹配版本号、分类等结构化字段
#
# 运行前：先运行 d3_1_ingest.py 写入数据
# 运行：python3 d3_3_compare.py
# ============================================================


# ---------- 0. 连接知识库 ----------

db = pyseekdb.Client()
collection_name = "d3_product_kb"

if not db.has_collection(collection_name):
    print("❌ 未找到知识库，请先运行 d3_1_ingest.py 写入数据")
    exit(1)

collection = db.get_collection(collection_name)
print(f">>> 已连接知识库：{collection_name}，共 {collection.count()} 条文档\n")


# ---------- 1. 辅助函数 ----------

def get_top1_snippet(results: dict) -> str:
    """提取 Top-1 结果的前 65 个字符"""
    docs = results.get("documents", [[]])[0]
    if not docs:
        return "（无结果）"
    return docs[0][:65] + "..."


def vector_only(query: str, n_results: int = 3) -> dict:
    """纯向量检索：只用语义相似度"""
    return collection.query(
        query_texts=[query],
        n_results=n_results,
    )


def hybrid_with_keyword(query: str, keyword: str, n_results: int = 3) -> dict:
    """混合检索：向量语义 + 全文关键词，RRF 融合"""
    return collection.hybrid_search(
        query={"where_document": {"$contains": keyword}, "n_results": 5},
        knn={"query_texts": [query], "n_results": 5},
        rank={"rrf": {}},
        n_results=n_results,
    )


def vector_with_metadata(query: str, metadata_filter: dict, n_results: int = 3) -> dict:
    """向量检索 + 元数据过滤：语义搜索 + 结构化字段精确匹配"""
    return collection.query(
        query_texts=[query],
        where=metadata_filter,
        n_results=n_results,
    )


# ---------- 2. 对比实验 ----------

print("=" * 70)
print("对比实验：纯向量检索 vs 增强检索（混合/元数据过滤）")
print("=" * 70)

# 测试用例：每个用例展示一种精确匹配场景
test_cases = [
    {
        "desc": "场景一：精确错误码查询",
        "query": "E-4012 错误怎么解决",
        "vector_fn": lambda q: vector_only(q),
        "enhanced_fn": lambda q: hybrid_with_keyword(q, "E-4012"),
        "enhanced_label": "混合检索（全文关键词 E-4012）",
        "correct": "E-4012",
    },
    {
        "desc": "场景二：精确季度数据查询",
        "query": "2024年Q3的营收情况",
        "vector_fn": lambda q: vector_only(q),
        "enhanced_fn": lambda q: hybrid_with_keyword(q, "Q3"),
        "enhanced_label": "混合检索（全文关键词 Q3）",
        "correct": "Q3",
    },
    {
        "desc": "场景三：精确版本号查询（版本号含点号，全文搜索分词器不支持）",
        "query": "OB-4.2.1 版本和旧版本兼容吗",
        "vector_fn": lambda q: vector_only(q),
        "enhanced_fn": lambda q: vector_with_metadata(q, {"version": "4.2.1"}),
        "enhanced_label": "向量检索 + 元数据过滤（version=4.2.1）",
        "correct": "4.2.1",
    },
    {
        "desc": "场景四：精确函数名查询",
        "query": "DBMS_HYBRID_SEARCH 函数的用法",
        "vector_fn": lambda q: vector_only(q),
        "enhanced_fn": lambda q: hybrid_with_keyword(q, "DBMS_HYBRID_SEARCH"),
        "enhanced_label": "混合检索（全文关键词 DBMS_HYBRID_SEARCH）",
        "correct": "DBMS_HYBRID_SEARCH",
    },
    {
        "desc": "场景五：纯语义查询（对照组，两种方式差异不大）",
        "query": "怎么优化数据库的查询性能",
        "vector_fn": lambda q: vector_only(q),
        "enhanced_fn": lambda q: hybrid_with_keyword(q, "性能"),
        "enhanced_label": "混合检索（全文关键词 性能）",
        "correct": "性能",
    },
]

vector_hits = 0
enhanced_hits = 0

for i, case in enumerate(test_cases, 1):
    query = case["query"]
    v_results = case["vector_fn"](query)
    e_results = case["enhanced_fn"](query)

    v_top1 = get_top1_snippet(v_results)
    e_top1 = get_top1_snippet(e_results)

    v_hit = case["correct"] in v_top1
    e_hit = case["correct"] in e_top1

    if v_hit:
        vector_hits += 1
    if e_hit:
        enhanced_hits += 1

    v_mark = "✅" if v_hit else "❌"
    e_mark = "✅" if e_hit else "❌"

    print(f"\n【{case['desc']}】")
    print(f"  查询：\"{query}\"")
    print(f"  纯向量检索 Top-1 {v_mark}：{v_top1}")
    print(f"  {case['enhanced_label']} Top-1 {e_mark}：{e_top1}")

# 汇总
print()
print("=" * 70)
print("汇总结果：")
print(f"  纯向量检索命中率：{vector_hits}/{len(test_cases)} = {vector_hits/len(test_cases)*100:.0f}%")
print(f"  增强检索命中率：  {enhanced_hits}/{len(test_cases)} = {enhanced_hits/len(test_cases)*100:.0f}%")
print()
print("三种检索能力的适用场景：")
print("  向量语义检索  → 理解用户意图，找语义相关内容（适合开放式问题）")
print("  全文关键词检索 → 精确匹配错误码、函数名、专有名词（适合精确标识符）")
print("  元数据过滤    → 精确匹配版本号、分类等结构化字段（适合有明确属性的查询）")
print()
print("结论：生产级 RAG 需要三种能力组合使用，而不是只用向量搜索。")
print("      seekdb 在一个引擎内原生支持三种检索，不需要维护多套系统。")
