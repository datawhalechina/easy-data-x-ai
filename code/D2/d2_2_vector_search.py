import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyseekdb

# ============================================================
# d2_2：纯向量搜索示例
#
# 演示：
#   1. 向量搜索（语义检索）的能力——能找到"意思相近"的内容
#   2. 向量搜索的软肋——遇到精确编号（如错误码）时容易搞混
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
        print(f"  [{i+1}] 相关度分数：{dist:.4f}")
        print(f"       内容：{doc[:80]}{'...' if len(doc) > 80 else ''}")
        print(f"       分类：{meta.get('category', '-')}  版本：{meta.get('version', '-')}")
        print()


# ---------- 2. 向量搜索的优势场景：语义理解 ----------

print("【场景一：向量搜索的优势——语义理解】")
print("查询：'怎么设计用户权限'（文档里写的是'访问控制架构'，没有共同关键词）\n")

results = collection.query(
    query_texts="怎么设计用户权限",
    n_results=3,
)
print_results(results, "向量搜索结果")

print("✅ 向量搜索能找到'访问控制架构'的文档——因为它理解了语义上的等价性。")
print("   '用户权限' ≈ '访问控制' ≈ 'RBAC'，在语义空间中距离很近。\n")


# ---------- 3. 向量搜索的软肋：精确编号 ----------

print("【场景二：向量搜索的软肋——精确编号】")
print("查询：'错误码 E-4012 的解决方案'\n")

results = collection.query(
    query_texts="错误码 E-4012 的解决方案",
    n_results=3,
)
print_results(results, "向量搜索结果")

print("⚠️  注意排名第一的是哪个错误码？")
print("   E-4011、E-4012、E-4013 在语义空间中几乎一样近——它们都是'错误码'。")
print("   向量搜索无法区分'差一位数字'的重要性，排序带有随机性。")
print("   如果 Agent 拿到错误的错误码文档去回答用户，结果就是错的。\n")
print("   → 这就是为什么需要混合搜索（见 d2_3）\n")
