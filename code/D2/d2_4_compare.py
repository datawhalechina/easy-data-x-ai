import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyseekdb

# ============================================================
# d2_4：纯向量搜索 vs 混合搜索 对比实验
#
# 演示：
#   同样的数据、同样的查询，两种搜索策略的结果差异
#   重点关注：精确编号（错误码）场景下的排名差异
#
# 运行前：先运行 d2_1_ingest.py 写入数据
# ============================================================


# ---------- 0. 连接已有集合 ----------

db = pyseekdb.Client()
collection_name = "d2_knowledge_base"

if not db.has_collection(collection_name):
    print("❌ 未找到知识库，请先运行 d2_1_ingest.py 写入数据")
    exit(1)

collection = db.get_collection(collection_name)
print(f">>> 已连接知识库：{collection_name}，共 {collection.count()} 条文档\n")


# ---------- 1. 辅助函数 ----------

def run_comparison(query_text: str, n_results: int = 3):
    """
    对同一个查询分别执行纯向量搜索和混合搜索，并排版对比输出。
    """
    print(f"\n{'#'*60}")
    print(f"  查询：「{query_text}」")
    print(f"{'#'*60}\n")

    # 纯向量搜索（使用 query 接口，只做语义检索）
    vector_results = collection.query(
        query_texts=query_text,
        n_results=n_results,
    )

    # 混合搜索（向量 + 全文，使用正确的 API 格式）
    hybrid_results = collection.hybrid_search(
        query={"where_document": {"$contains": query_text}, "n_results": n_results + 2},  # 全文搜索
        knn={"query_texts": [query_text], "n_results": n_results + 2},                    # 向量搜索
        rank={"rrf": {}},  # RRF 融合
        n_results=n_results,
    )

    # 提取文档列表
    vector_docs = vector_results.get("documents", [[]])[0]
    hybrid_docs = hybrid_results.get("documents", [[]])[0]
    vector_scores = vector_results.get("distances", [[]])[0]
    hybrid_scores = hybrid_results.get("distances", [[]])[0]

    # 并排输出
    print(f"  {'纯向量搜索':<35}  {'混合搜索（向量 + 全文）'}")
    print(f"  {'-'*35}  {'-'*35}")

    max_len = max(len(vector_docs), len(hybrid_docs))
    for i in range(max_len):
        # 向量搜索结果
        if i < len(vector_docs):
            v_text = vector_docs[i][:30] + "..." if len(vector_docs[i]) > 30 else vector_docs[i]
            v_score = f"({vector_scores[i]:.3f})"
            v_col = f"[{i+1}] {v_text} {v_score}"
        else:
            v_col = ""

        # 混合搜索结果
        if i < len(hybrid_docs):
            h_text = hybrid_docs[i][:30] + "..." if len(hybrid_docs[i]) > 30 else hybrid_docs[i]
            h_score = f"({hybrid_scores[i]:.3f})"
            h_col = f"[{i+1}] {h_text} {h_score}"
        else:
            h_col = ""

        print(f"  {v_col:<45}  {h_col}")

    print()


# ---------- 2. 对比实验 ----------

print("=" * 60)
print("  D2 对比实验：纯向量搜索 vs 混合搜索")
print("=" * 60)

# 实验一：精确编号场景（向量搜索的软肋）
run_comparison("错误码 E-4012 的解决方案")
print("📌 分析：")
print("   纯向量搜索：E-4011/E-4012/E-4013 在语义空间几乎等距，排名带随机性")
print("   混合搜索：全文搜索精确命中'E-4012'，将其推到第一位")
print("   → 差一位数字 = 完全不同的错误，这不是'效果差一点'，是'对和错'的问题\n")

# 实验二：语义理解场景（向量搜索的优势）
run_comparison("怎么设计用户权限")
print("📌 分析：")
print("   纯向量搜索：能找到'访问控制架构'——语义理解有效")
print("   混合搜索：同样能找到，语义能力完整保留")
print("   → 混合搜索不是'替代'向量搜索，而是在保留语义能力的同时补上精确匹配\n")

# 实验三：性能优化场景
run_comparison("数据库性能优化")
print("📌 分析：")
print("   两种方式都能找到相关内容，但混合搜索的排名更稳定")
print("   全文搜索的关键词命中信号让结果更可预期\n")

print("=" * 60)
print("  结论：混合搜索不是可选优化，是 AI 应用数据层的基本要求")
print("=" * 60)
print()
print("下一步：运行 D3 的代码，把 Tool Use（D1）和混合检索（D2）连起来，")
print("构建一个完整的 Agentic RAG 系统。")
