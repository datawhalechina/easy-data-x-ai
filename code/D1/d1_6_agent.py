import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Config
import pyseekdb
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool
from langchain.agents import create_agent

# ============================================================
# 从 Tool Use 到 Agent：感知 → 推理 → 行动 循环演示
#
# 在 d1_4 和 d1_5 中，我们手动编排了 Tool Use 的流程：
#   调用模型 → 检查 tool_calls → 执行工具 → 把结果传回模型
#
# 本文件把这个过程封装成一个 Agent 循环，让你看到
# F2 中讲的 "感知 → 推理 → 行动 → 观察" 是怎么在代码中体现的：
#   - 推理：模型分析用户问题，决定要不要用工具
#   - 行动：调用工具（查知识库）
#   - 观察：拿到工具返回的结果
#   - 继续推理：基于结果生成最终回答，或者再查一次
#
# 这就是 F2 中说的：
# "Agent 不是一次性生成答案，而是在'思考-行动-观察'的循环中逐步完成任务。"
# ============================================================


# ---------- 0. 初始化 seekdb 知识库 ----------
print(">>> 正在初始化 seekdb 知识库...")

db = pyseekdb.Client()
collection_name = "d1_agent_kb"

try:
    db.delete_collection(collection_name)
except Exception:
    pass

collection = db.create_collection(name=collection_name)

# 写入更丰富的文档，覆盖 F2 中提到的 Agent 四大能力
docs = [
    # RAG 相关
    "seekdb 支持三种检索方式：关键词检索（BM25）、语义向量检索（基于 Embedding 的相似度匹配）、混合检索（关键词 + 语义的加权融合，推荐使用）。",
    "seekdb 的混合检索原理：同时执行关键词检索和语义向量检索，然后通过 RRF（Reciprocal Rank Fusion）算法将两种结果融合排序，兼顾精确匹配和语义理解。",
    "Agentic RAG 与传统 RAG 的区别：传统 RAG 是固定流程（查→答），Agentic RAG 是 Agent 主动判断——要不要查？查哪里？查的结果够不够用？需要再查一次吗？",
    # Memory 相关
    "Agent Memory 分为三种类型：语义记忆（记住事实和偏好）、情景记忆（记住过往经验）、程序记忆（记住行为规则）。这是 CoALA 论文提出的分类框架。",
    "PowerMem 是基于 seekdb 构建的 Agent 记忆系统，把记忆的提炼、检索、遗忘封装成开箱即用的能力。",
    # MCP 相关
    "MCP（Model Context Protocol）是 Anthropic 推出的标准化协议，让 AI 工具可以通过统一接口调用外部服务——一次实现，处处可用。",
    # 部署相关
    "seekdb 支持两种部署模式：嵌入模式（Embedded Mode）作为 Python 库直接运行在应用内，适合原型开发；服务器模式（Server Mode）适合生产环境。",
    "pyseekdb 是 seekdb 的 Python SDK，支持 Schemaless API，无需预定义表结构，直接创建 collection 并写入文档即可。",
]

collection.add(
    ids=[f"doc_{i}" for i in range(len(docs))],
    documents=docs,
)

print(f">>> 知识库就绪，已写入 {len(docs)} 条文档\n")


# ---------- 1. 初始化模型 ----------
# 使用阿里云百炼（通义千问）API，兼容 OpenAI 格式，支持 tool calling
llm = init_chat_model(
    "qwen-plus",
    model_provider="openai",
    **Config.get_dashscope_config()
)


# ---------- 2. 定义工具 ----------
@tool
def search_knowledge_base(query: str) -> str:
    """从知识库中检索与用户问题相关的内容。当用户的问题涉及 seekdb、RAG、Agent Memory、MCP 等产品功能或技术概念时使用。"""
    results = collection.query(query_texts=[query], n_results=3)
    if results and results["documents"] and results["documents"][0]:
        formatted = []
        for i, doc in enumerate(results["documents"][0]):
            formatted.append(f"[文档{i+1}] {doc}")
        return "\n\n".join(formatted)
    return "未找到相关文档。"


# ---------- 3. 用 create_agent 构建 Agent ----------
# 之前在硅基流动 API 下，我们需要手动实现 Agent 循环（推理→行动→观察）
# 现在换成百炼 API（完全兼容 OpenAI tool calling 格式），
# 可以直接用 LangChain 的 create_agent，一行代码搞定！

SYSTEM_PROMPT = (
    "你是一个 AI 技术文档助手，专门回答关于 seekdb、RAG、Agent Memory、MCP 等技术问题。\n"
    "当用户提问时，请先查询知识库获取准确信息，然后基于检索结果回答。\n"
    "如果第一次检索的结果不够完整，可以用不同的关键词再查一次。\n"
    "回答时请用中文，条理清晰。"
)

# 一行代码创建 Agent —— 等价于之前手写的整个 run_agent() 函数！
agent = create_agent(
    model=llm,
    tools=[search_knowledge_base],
    system_prompt=SYSTEM_PROMPT,
)


def run_agent(question: str) -> str:
    """
    运行 Agent（流式输出）。

    create_agent 内部自动实现了 F2 中描述的循环：
      感知（用户提问）→ 推理（要不要查？）→ 行动（查知识库）→ 观察（拿到结果）→ 继续推理...

    不再需要手动写 for 循环、手动拼消息了！
    """
    final_answer = ""
    
    for chunk in agent.stream({"messages": [("user", question)]}):
        # chunk 的结构是 {node_name: {'messages': [messages]}}
        for node_name, node_output in chunk.items():
            if not isinstance(node_output, dict) or "messages" not in node_output:
                continue
            for msg in node_output["messages"]:
                # 打印中间步骤
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        print(f"   [行动] 调用工具 '{tc['name']}'，参数：{tc['args']}")
                elif hasattr(msg, "type") and msg.type == "tool":
                    doc_count = msg.content.count("[文档") if msg.content else 0
                    print(f"   [观察] 工具返回了 {doc_count} 条相关文档")
                elif hasattr(msg, "content") and msg.content and node_name == "model":
                    # 流式输出最终回答
                    print(msg.content, end="", flush=True)
                    final_answer += msg.content

    print()  # 换行
    return final_answer


# ---------- 4. 与 Agent 对话 ----------
# 准备几个问题，展示 Agent 的不同行为

questions = [
    "Agentic RAG 和传统 RAG 有什么区别？",
    "Agent 的记忆系统是怎么分类的？有什么工具可以用？",
    "seekdb 支持哪些检索方式？混合检索的原理是什么？",
]

for i, question in enumerate(questions):
    print(f"\n{'='*60}")
    print(f"问题 {i+1}：{question}")
    print('='*60)

    answer = run_agent(question)

    print(f"\n>>> 最终回答：\n{answer}")


# ---------- 5. 清理 ----------
try:
    db.delete_collection(collection_name)
    print(f"\n{'='*60}")
    print(">>> 知识库已清理")
except Exception:
    pass

# ============================================================
# 回顾：从 d1_1 到 d1_6 的演进
#
# d1_1  基础调用      → 用代码调用大模型（一问一答）
# d1_2  多轮对话      → 手动维护消息历史
# d1_3  流式输出      → 提升用户体验
# d1_4  Tool Use Mock → 手动编排工具调用流程（假数据）
# d1_5  Tool Use Real → 手动编排 + 真实向量检索（seekdb）
# d1_6  Agent 循环    → 自动化的"推理→行动→观察"多轮循环
#
# d1_4/d1_5 中你手动写的那些 if/else 逻辑，
# 在 d1_6 中被 create_agent 一行代码替代了！
#
# 关键变化：
# - 之前（硅基流动 API）：手动写 for 循环 + 消息拼接，因为 API 不完全兼容
# - 现在（百炼 API）：直接用 create_agent，因为百炼完全兼容 OpenAI 格式
#
# create_agent 底层基于 LangGraph，自动处理了：
#   1. 把工具绑定到模型
#   2. 调用模型，检查是否有 tool_calls
#   3. 如果有，执行工具，把结果以 role:"tool" 格式传回
#   4. 循环直到模型给出最终回答
#
# 这就是 F2 中说的：
# "Agent 不是'一个更聪明的 ChatGPT'，
#  而是一个具有'感知→推理→行动'循环能力的系统。"
# ============================================================