import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Config
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool

# ============================================================
# Tool Use 完整流程演示（Mock 版 —— 用假数据演示流程）
# 如果想看接入真实向量数据库的版本，请运行 d1_5_tool_use_seekdb.py
# ============================================================

# ---------- 0. 初始化模型 ----------
llm = init_chat_model(
    "deepseek-ai/DeepSeek-V3",
    model_provider="openai",
    **Config.get_siliconflow_config()
)


# ---------- 1. 定义工具 ----------
# 在 LangChain 中，用 @tool 装饰器定义工具
# 函数名 = 工具名，docstring = 工具描述，参数类型注解 = 参数 Schema

@tool
def query_knowledge_base(query: str) -> str:
    """从知识库中检索与用户问题相关的内容。当用户的问题涉及产品功能、技术文档、操作指南等需要查阅知识库的场景时使用。"""
    # Mock 版本：用硬编码的假数据模拟知识库检索
    fake_docs = {
        "检索方式": "seekdb 支持三种检索方式：关键词检索（BM25）、语义向量检索（基于 Embedding 的相似度匹配）、混合检索（关键词 + 语义的加权融合，推荐使用）。",
        "部署模式": "seekdb 支持两种部署模式：嵌入模式（Embedded Mode）作为 Python 库直接运行在应用内，适合原型开发；服务器模式（Server Mode）适合生产环境，支持高并发和分布式扩展。",
        "SDK": "pyseekdb 是 seekdb 的 Python SDK，支持 Schemaless API，无需预定义表结构，直接创建 collection 并写入文档即可。",
    }

    # 简单的关键词匹配
    results = []
    for key, doc in fake_docs.items():
        if key in query or any(word in query for word in key):
            results.append(doc)

    if not results:
        results = list(fake_docs.values())  # 没匹配到就返回全部

    return "\n\n".join(results)


# ---------- 2. 绑定工具并发起调用（流式） ----------
print(">>> 用户提问：seekdb 支持哪些检索方式？混合检索是怎么实现的？")
print(">>> 等待模型判断是否需要调用工具...\n")

# 把工具绑定到模型上
llm_with_tools = llm.bind_tools([query_knowledge_base])

messages = [
    ("system", "你是一个技术文档助手。当用户问及产品相关问题时，请先查询知识库获取准确信息。"),
    ("user", "seekdb 支持哪些检索方式？混合检索是怎么实现的？"),
]

# 流式调用，需要聚合 chunks 才能拿到完整的 tool_calls
chunks = list(llm_with_tools.stream(messages))
response = chunks[0]
for chunk in chunks[1:]:
    response += chunk


# ---------- 3. 处理工具调用 ----------
if response.tool_calls:
    tool_call = response.tool_calls[0]
    print(f">>> 模型决定调用工具：{tool_call['name']}")
    print(f">>> 工具参数：{tool_call['args']}\n")

    # 执行工具
    result = query_knowledge_base.invoke(tool_call["args"])

    print(f">>> 知识库检索结果：\n{result}\n")

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
    # 模型没有调用工具，直接回答了
    print(f">>> 模型直接回答（未调用工具）：\n{response.content}")

# ============================================================
# 对比说明：
# - d1_4（本文件）：Mock 版，工具背后是硬编码的假数据，用于理解 Tool Use 流程
# - d1_5：seekdb 版，工具背后是真实的向量数据库检索，体验 Tool Use + 真实数据
# 两者的 Tool Use 流程完全一样，区别只在于工具内部的实现
# ============================================================