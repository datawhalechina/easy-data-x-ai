import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Config
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool

if __package__:
    from .mock_knowledge_base import search_mock_knowledge_base
    from .tool_call_loop import run_tool_call_loop
else:
    from mock_knowledge_base import search_mock_knowledge_base
    from tool_call_loop import run_tool_call_loop


@tool
def query_knowledge_base(query: str) -> str:
    """从模拟知识库中检索产品功能、技术文档或操作指南。"""
    return search_mock_knowledge_base(query)


def print_tool_result(tool_call, result):
    print(f">>> 模型决定调用工具：{tool_call['name']}")
    print(f">>> 工具参数：{tool_call['args']}\n")
    print(f">>> 知识库检索结果：\n{result}\n")


def run_demo(llm):
    print(">>> 用户提问：seekdb 支持哪些检索方式？混合检索是怎么实现的？")
    llm_with_tools = llm.bind_tools([query_knowledge_base])
    response = run_tool_call_loop(
        llm_with_tools,
        [
            ("system", "你是技术文档助手，产品问题请先查询知识库。"),
            ("user", "seekdb 支持哪些检索方式？混合检索是怎么实现的？"),
        ],
        {query_knowledge_base.name: query_knowledge_base},
        max_rounds=5,
        on_tool_result=print_tool_result,
        legacy_user_message_fallback=True,
    )
    print(f">>> 模型最终回答：\n{response.content}")
    return response


def main(model_factory=init_chat_model) -> int:
    # Key 边界：模型初始化前失败，避免产生任何外部调用。
    try:
        Config.require_api_key("SILICONFLOW_API_KEY")
    except RuntimeError as exc:
        print(f"❌ {exc}")
        return 1
    llm = model_factory(
        "deepseek-ai/DeepSeek-V3",
        model_provider="openai",
        **Config.get_siliconflow_config(),
    )
    run_demo(llm)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
