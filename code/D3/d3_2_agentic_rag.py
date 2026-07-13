import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Config
import pyseekdb
import json
from openai import OpenAI

# ============================================================
# d3_2：Agentic RAG 完整链路
#
# 演示：
#   1. 定义 search_knowledge_base 工具（Tool Use）
#   2. Agent 自主决定是否调用工具检索知识库
#   3. 基于检索结果生成准确回答
#   4. 对比"需要检索"和"不需要检索"两种场景
#
# 运行前：先运行 d3_1_ingest.py 写入数据
# 运行：python d3_2_agentic_rag.py
# ============================================================


# ---------- 0. 连接知识库 ----------

db = pyseekdb.Client()
collection_name = "d3_product_kb"

if not db.has_collection(collection_name):
    print("❌ 未找到知识库，请先运行 d3_1_ingest.py 写入数据")
    exit(1)

collection = db.get_collection(collection_name)
print(f">>> 已连接知识库：{collection_name}，共 {collection.count()} 条文档\n")


# ---------- 1. 初始化 LLM 客户端 ----------

client = OpenAI(
    api_key=Config.SILICONFLOW_API_KEY,
    base_url=Config.SILICONFLOW_BASE_URL,
)
MODEL = "deepseek-ai/DeepSeek-V3"


# ---------- 2. 定义工具 ----------

tools = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": (
                "从产品知识库中检索相关信息。"
                "当用户询问产品功能、错误码、版本信息、性能优化、营收数据等问题时使用。"
                "查询文本应尽量保留用户问题中的关键词和专有名词（如版本号、错误码）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "用于检索知识库的查询文本，应保留用户问题中的关键词和专有名词"
                    }
                },
                "required": ["query"]
            }
        }
    }
]


# ---------- 3. 工具执行函数 ----------

def execute_search(query: str) -> str:
    """调用 seekdb 混合检索，返回格式化的检索结果"""
    # 使用混合检索：向量语义 + 全文关键词
    results = collection.hybrid_search(
        query={"where_document": {"$contains": query.split()[0] if query.split() else query}, "n_results": 5},
        knn={"query_texts": [query], "n_results": 5},
        rank={"rrf": {}},
        n_results=3,
    )

    docs = results.get("documents", [[]])[0]
    if not docs:
        return "知识库中未找到相关内容。"

    formatted = []
    for i, doc in enumerate(docs):
        formatted.append(f"[结果 {i+1}]\n{doc}")
    return "\n\n".join(formatted)


# ---------- 4. Agentic RAG 主函数 ----------

def ask_agent(question: str) -> str:
    """
    Agentic RAG 主循环：
    Agent 自主决定是否调用工具，基于检索结果生成回答
    """
    messages = [
        {
            "role": "system",
            "content": (
                "你是一个产品技术文档助手。回答用户问题时，请先查询知识库获取准确信息，"
                "然后基于查询结果回答。如果知识库中没有相关信息，请诚实告知用户。"
                "回答时请引用具体的数据和版本号，不要猜测。"
            )
        },
        {"role": "user", "content": question}
    ]

    # 第一次调用：让 Agent 判断是否需要检索
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=tools,
    )

    message = response.choices[0].message

    # Agent 决定调用工具
    if message.tool_calls:
        tool_call = message.tool_calls[0]
        arguments = json.loads(tool_call.function.arguments)
        query_text = arguments["query"]

        print(f"  → Agent 决定检索：\"{query_text}\"")

        search_results = execute_search(query_text)
        print(f"  → 检索到 {search_results.count('[结果')} 条相关内容")

        # 将工具调用和结果加入消息历史
        messages.append(message)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": search_results
        })

        # 第二次调用：基于检索结果生成最终回答
        final_response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
        )
        return final_response.choices[0].message.content

    # Agent 决定不调用工具，直接回答（如闲聊、常识问题）
    print("  → Agent 直接回答（无需检索）")
    return message.content


# ---------- 5. 测试用例 ----------

test_cases = [
    {
        "question": "OB-4.2.1 版本和旧版本兼容吗？",
        "expect": "需要检索（版本兼容性）"
    },
    {
        "question": "遇到 E-4012 错误怎么解决？",
        "expect": "需要检索（错误码）"
    },
    {
        "question": "2024年Q3的总营收是多少？",
        "expect": "需要检索（财务数据）"
    },
    {
        "question": "你好，今天天气怎么样？",
        "expect": "不需要检索（闲聊）"
    },
]

print("=" * 60)
print("Agentic RAG 演示")
print("=" * 60)

for i, case in enumerate(test_cases, 1):
    print(f"\n【问题 {i}】{case['question']}")
    print(f"  预期行为：{case['expect']}")
    answer = ask_agent(case["question"])
    print(f"  回答：{answer[:200]}{'...' if len(answer) > 200 else ''}")
    print()

print("=" * 60)
print("✅ Agentic RAG 演示完成")
print("   关键点：Agent 自主判断是否需要检索，而不是每次都查知识库")
print("   这就是 'Agentic' 的含义——主动决策，而不是被动执行流程")
