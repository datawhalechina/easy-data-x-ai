import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Config
import pyseekdb
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool

# ============================================================
# Tool Use + seekdb 真实向量检索 演示（LangChain 版）
# 对比 d1_4_tool_use_mock.py，本文件的 Tool Use 流程完全一样
# 区别在于：工具背后接入的是 seekdb 真实的向量数据库，而不是假数据
# ============================================================

# ---------- 0. 初始化 seekdb 知识库 ----------
print(">>> 正在初始化 seekdb 知识库...")

db = pyseekdb.Client()
collection_name = "d1_knowledge_base"

# 如果已存在则先删除，确保每次运行都是干净的
try:
    db.delete_collection(collection_name)
except Exception:
    pass

collection = db.create_collection(name=collection_name)

# 写入一些关于 seekdb 的文档
docs = [
    "seekdb 支持两种部署模式：嵌入模式（Embedded Mode）作为 Python 库直接运行在应用内，适合原型开发；服务器模式（Server Mode）适合生产环境，支持高并发和分布式扩展。",
    "seekdb 支持三种检索方式：关键词检索（BM25）、语义向量检索（基于 Embedding 的相似度匹配）、混合检索（关键词 + 语义的加权融合，推荐使用）。",
    "pyseekdb 是 seekdb 的 Python SDK，支持 Schemaless API，无需预定义表结构，直接创建 collection 并写入文档即可。",
    "seekdb 的混合检索原理：同时执行关键词检索和语义向量检索，然后通过 RRF（Reciprocal Rank Fusion）算法将两种结果融合排序，兼顾精确匹配和语义理解。",
    "seekdb 的嵌入模式不需要单独部署服务器，数据存储在本地目录中，适合开发测试和小规模应用。",
    "seekdb 支持自动向量化：写入文档时自动调用 Embedding 模型生成向量，查询时也自动将查询文本转为向量进行检索。",
]

collection.add(
    ids=[f"doc_{i}" for i in range(len(docs))],
    documents=docs,
)

print(f">>> 知识库就绪，已写入 {len(docs)} 条文档\n")


# ---------- 1. 初始化模型 ----------
llm = init_chat_model(
    "deepseek-ai/DeepSeek-V3",
    model_provider="openai",
    **Config.get_siliconflow_config()
)


# ---------- 2. 定义工具 ----------
@tool
def search_seekdb(query: str) -> str:
    """从 seekdb 知识库中检索与用户问题相关的内容。当用户的问题涉及 seekdb 的产品功能、技术文档、部署方式、检索方式等需要查阅知识库的场景时使用。"""
    results = collection.query(query_texts=[query], n_results=3)
    if results and results["documents"] and results["documents"][0]:
        formatted = []
        for i, doc in enumerate(results["documents"][0]):
            formatted.append(f"[文档{i+1}] {doc}")
        return "\n\n".join(formatted)
    return "未找到相关文档。"


# ---------- 3. 绑定工具并发起调用（流式） ----------
user_question = "seekdb 支持哪些检索方式？混合检索是怎么实现的？"
print(f">>> 用户提问：{user_question}")
print(">>> 等待模型判断是否需要调用工具...\n")

llm_with_tools = llm.bind_tools([search_seekdb])

messages = [
    ("system", "你是一个技术文档助手。当用户问及 seekdb 相关问题时，请先查询知识库获取准确信息，然后基于检索结果回答。"),
    ("user", user_question),
]

# 流式调用，需要聚合 chunks 才能拿到完整的 tool_calls
chunks = list(llm_with_tools.stream(messages))
response = chunks[0]
for chunk in chunks[1:]:
    response += chunk


# ---------- 4. 处理工具调用 ----------
if response.tool_calls:
    tool_call = response.tool_calls[0]
    print(f">>> 模型决定调用工具：{tool_call['name']}")
    print(f">>> 工具参数：{tool_call['args']}\n")

    # 执行工具（调用 seekdb 进行真实的向量检索）
    result = search_seekdb.invoke(tool_call["args"])

    print(f">>> seekdb 检索结果：\n{result}\n")

    # 把检索结果作为补充信息传回模型
    # 注意：硅基流动的 API 对 tool_calls 消息格式兼容性有限
    # 这里用更通用的方式——把检索结果放进 user 消息中
    messages.append(("user", f"以下是从知识库中检索到的相关内容，请基于这些内容回答用户的问题：\n\n{result}"))

    # 第二次调用：流式输出最终回答
    print(">>> 模型最终回答：")
    for chunk in llm.stream(messages):
        print(chunk.content, end="", flush=True)
    print()
else:
    print(f">>> 模型直接回答（未调用工具）：\n{response.content}")


# ---------- 5. 清理 ----------
try:
    db.delete_collection(collection_name)
    print("\n>>> 知识库已清理")
except Exception:
    pass