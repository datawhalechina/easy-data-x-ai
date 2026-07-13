import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyseekdb

# ============================================================
# d2_3：混合搜索示例
#
# 演示：
#   1. 混合搜索（向量 + 全文）如何精确命中错误码
#   2. 混合搜索如何同时保留语义理解能力
#   3. 加上结构化过滤（按 version 筛选）
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

def print_results(results: dict, title: str):
    """格式化打印搜索结果"""
    print(f"{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}")
    docs = results.get("documents", [[]])[0]
    distances = results.get("distances", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    if not docs:
        print("  （无结果）")
    for i, (doc, dist, meta) in enumerate(zip(docs, distances, metadatas)):
        print(f"  [{i+1}] 分数：{dist:.4f}")
        print(f"       内容：{doc[:80]}{'...' if len(doc) > 80 else ''}")
        print(f"       分类：{meta.get('category', '-')}  版本：{meta.get('version', '-')}")
        print()


# ---------- 2. 混合搜索：精确编号场景 ----------

print("【场景一：混合搜索——精确命中错误码】")
print("查询：'错误码 E-4012 的解决方案'\n")

results = collection.hybrid_search(
    query={"where_document": {"$contains": "E-4012"}, "n_results": 5},  # 全文搜索：精确匹配关键词
    knn={"query_texts": ["错误码 E-4012 的解决方案"], "n_results": 5},  # 向量搜索：语义检索
    rank={"rrf": {}},  # RRF 算法融合两路结果
    n_results=3,
)
print_results(results, "混合搜索结果（向量 + 全文）")

print("✅ 混合搜索将 E-4012 精确排在第一位。")
print("   全文搜索精确匹配了'E-4012'关键词，向量搜索补充了语义相关内容。")
print("   两种信号通过 RRF 算法在引擎内部融合，不需要你写任何合并逻辑。\n")


# ---------- 3. 混合搜索：语义理解场景 ----------

print("【场景二：混合搜索——语义理解依然有效】")
print("查询：'怎么设计用户权限'\n")

results = collection.hybrid_search(
    query={"where_document": {"$contains": "权限"}, "n_results": 5},  # 全文搜索
    knn={"query_texts": ["怎么设计用户权限"], "n_results": 5},         # 向量搜索
    rank={"rrf": {}},
    n_results=3,
)
print_results(results, "混合搜索结果（向量 + 全文）")

print("✅ 混合搜索同样能找到'访问控制架构'的文档。")
print("   向量搜索的语义理解能力在混合搜索中完整保留。\n")


# ---------- 4. 混合搜索 + 结构化过滤 ----------

print("【场景三：混合搜索 + 结构化过滤——只搜 4.2 版本的文档】")
print("查询：'性能优化'，限定 version=4.2\n")

results = collection.hybrid_search(
    query={"n_results": 5},                                              # 全文搜索（无关键词过滤）
    knn={"query_texts": ["性能优化"], "where": {"version": "4.2"}, "n_results": 5},  # 向量搜索 + 版本过滤
    rank={"rrf": {}},
    n_results=3,
)
print_results(results, "混合搜索 + 过滤结果")

print("✅ 向量搜索 + 全文搜索 + 关系过滤，三种能力在一条查询中完成。")
print("   这就是'一个厨房，所有菜都能做'的实际体验。\n")
