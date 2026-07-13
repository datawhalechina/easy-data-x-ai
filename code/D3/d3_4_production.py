import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Config
import pyseekdb
import json
from openai import OpenAI

# ============================================================
# d3_4：从实验到生产——几个关键工程要点
#
# 演示：
#   1. 工具描述（Tool Description）质量对 Agent 行为的影响
#   2. top_k 参数的取舍
#   3. 数据更新：增量写入而非全量重建
#
# 运行前：先运行 d3_1_ingest.py 写入数据
# 运行：python d3_4_production.py
# ============================================================


# ---------- 0. 连接知识库 ----------

db = pyseekdb.Client()
collection_name = "d3_product_kb"

if not db.has_collection(collection_name):
    print("❌ 未找到知识库，请先运行 d3_1_ingest.py 写入数据")
    exit(1)

collection = db.get_collection(collection_name)
print(f">>> 已连接知识库：{collection_name}，共 {collection.count()} 条文档\n")

client = OpenAI(
    api_key=Config.SILICONFLOW_API_KEY,
    base_url=Config.SILICONFLOW_BASE_URL,
)
MODEL = "deepseek-ai/DeepSeek-V3"


# ---------- 1. 工具描述质量的影响 ----------

print("=" * 60)
print("【要点一】工具描述质量对 Agent 行为的影响")
print("=" * 60)

def ask_with_tool_desc(question: str, tool_description: str, label: str) -> str:
    """用指定的工具描述发起 Agent 调用"""
    tools = [{
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": tool_description,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "查询文本"}
                },
                "required": ["query"]
            }
        }
    }]

    messages = [
        {"role": "system", "content": "你是一个技术助手，回答用户关于产品的问题。"},
        {"role": "user", "content": question}
    ]

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=tools,
    )

    message = response.choices[0].message
    if message.tool_calls:
        return f"[{label}] ✅ Agent 调用了工具，查询：\"{json.loads(message.tool_calls[0].function.arguments)['query']}\""
    else:
        return f"[{label}] ⚠️  Agent 直接回答（未调用工具）：\"{message.content[:80]}...\""


# 测试问题：这个问题应该触发工具调用
test_q = "OB-4.2.1 版本和旧版本兼容吗？"
print(f"\n测试问题：{test_q}\n")

# 模糊的工具描述
vague_desc = "查询数据库"
result1 = ask_with_tool_desc(test_q, vague_desc, "模糊描述")
print(result1)

# 清晰的工具描述
clear_desc = (
    "从产品知识库中检索相关信息。"
    "当用户询问产品功能、错误码、版本信息、性能优化、营收数据等问题时使用。"
    "查询文本应保留用户问题中的关键词和专有名词（如版本号、错误码）。"
)
result2 = ask_with_tool_desc(test_q, clear_desc, "清晰描述")
print(result2)

print()
print("结论：工具描述越清晰，Agent 越能在正确的时机调用工具。")
print("      模糊的描述会导致 Agent 不知道什么时候该用这个工具。")


# ---------- 2. top_k 参数的取舍 ----------

print()
print("=" * 60)
print("【要点二】top_k 参数的取舍")
print("=" * 60)

query = "数据库性能优化"
print(f"\n查询：\"{query}\"")
print()

for top_k in [1, 3, 5, 8]:
    results = collection.hybrid_search(
        query={"where_document": {"$contains": "性能"}, "n_results": top_k + 2},
        knn={"query_texts": [query], "n_results": top_k + 2},
        rank={"rrf": {}},
        n_results=top_k,
    )
    docs = results.get("documents", [[]])[0]
    # 计算相关内容比例（包含"性能"或"优化"的文档）
    relevant = sum(1 for d in docs if "性能" in d or "优化" in d or "索引" in d or "分区" in d)
    print(f"  top_k={top_k}：返回 {len(docs)} 条，其中相关 {relevant} 条，"
          f"噪声比例 {(len(docs)-relevant)/max(len(docs),1)*100:.0f}%")

print()
print("结论：top_k 设太小可能遗漏关键信息，设太大会引入噪声干扰模型推理。")
print("      实践中 top_k=3~5 是常见起点，根据数据密度和查询类型调整。")


# ---------- 3. 增量更新知识库 ----------

print()
print("=" * 60)
print("【要点三】增量更新知识库（不需要全量重建）")
print("=" * 60)

print(f"\n当前知识库文档数：{collection.count()}")

# 模拟新增一条文档（比如新版本发布说明）
new_doc = {
    "id": "kb_013",
    "content": "OB-4.3.0 版本新特性：支持向量索引加速，引入自适应压缩算法，存储空间减少 30%。与 OB-4.2.x 完全兼容，支持滚动升级。",
    "doc_type": "release_notes",
    "version": "4.3.0"
}

# 增量写入（不删除已有数据）
# 先检查是否已存在，避免重复写入报错
existing = collection.get(ids=[new_doc["id"]])
if not existing.get("ids"):
    collection.add(
        ids=[new_doc["id"]],
        documents=[new_doc["content"]],
        metadatas=[{"doc_type": new_doc["doc_type"], "version": new_doc["version"]}],
    )
    print(f"增量写入 1 条新文档后：{collection.count()} 条")
else:
    print(f"文档已存在，当前共 {collection.count()} 条")

# 验证新文档可以被检索到（用元数据过滤，因为版本号含点号全文搜索不支持）
results = collection.query(
    query_texts=["OB-4.3.0 版本特性"],
    where={"version": "4.3.0"},
    n_results=1,
)
docs = results.get("documents", [[]])[0]
if docs and "4.3.0" in docs[0]:
    print(f"✅ 新文档可以被检索到：{docs[0][:60]}...")
else:
    print("⚠️  新文档未被检索到")

print()
print("结论：seekdb 支持对已有集合追加数据，不需要每次都删库重建。")
print("      生产环境中，'数据新鲜度'往往比'检索算法精细调优'更影响用户体验。")

print()
print("=" * 60)
print("✅ d3_4 完成！三个生产要点演示结束。")
