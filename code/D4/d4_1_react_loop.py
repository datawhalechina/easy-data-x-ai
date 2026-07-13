import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Config
import json
from openai import OpenAI

# ============================================================
# d4_1：ReAct 推理循环演示
#
# 演示：
#   1. Agent 的多步推理循环（ReAct 模式：推理 → 行动 → 观察 → ...）
#   2. Agent 自主决定调用哪个工具、调用几次
#   3. 最大步数限制，防止 Agent 无限循环
#   4. 对比单步 vs 多步推理的效果差异
#
# 运行：python d4_1_react_loop.py
# ============================================================


# ---------- 1. 初始化 LLM 客户端 ----------

client = OpenAI(
    api_key=Config.SILICONFLOW_API_KEY,
    base_url=Config.SILICONFLOW_BASE_URL,
)
MODEL = "deepseek-ai/DeepSeek-V3"


# ---------- 2. 定义工具集 ----------
# 模拟两个工具：一个查天气，一个查汇率
# Agent 需要根据问题自主决定调用哪个、调用几次

def get_weather(city: str) -> str:
    """模拟天气查询"""
    weather_data = {
        "北京": "晴天，气温 22°C，湿度 45%",
        "上海": "多云，气温 25°C，湿度 70%",
        "东京": "小雨，气温 18°C，湿度 85%",
        "纽约": "晴天，气温 20°C，湿度 50%",
    }
    return weather_data.get(city, f"未找到 {city} 的天气数据")


def get_exchange_rate(from_currency: str, to_currency: str) -> str:
    """模拟汇率查询"""
    rates = {
        ("USD", "CNY"): 7.24,
        ("CNY", "USD"): 0.138,
        ("JPY", "CNY"): 0.048,
        ("CNY", "JPY"): 20.83,
        ("USD", "JPY"): 150.2,
    }
    rate = rates.get((from_currency.upper(), to_currency.upper()))
    if rate:
        return f"1 {from_currency} = {rate} {to_currency}"
    return f"未找到 {from_currency} 到 {to_currency} 的汇率数据"


# 工具定义（OpenAI Function Calling 格式）
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的当前天气信息，包括天气状况、气温和湿度。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，如：北京、上海、东京、纽约"
                    }
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_exchange_rate",
            "description": "查询两种货币之间的汇率。支持 USD（美元）、CNY（人民币）、JPY（日元）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_currency": {
                        "type": "string",
                        "description": "源货币代码，如 USD、CNY、JPY"
                    },
                    "to_currency": {
                        "type": "string",
                        "description": "目标货币代码，如 USD、CNY、JPY"
                    }
                },
                "required": ["from_currency", "to_currency"]
            }
        }
    }
]

# 工具执行映射
tool_functions = {
    "get_weather": lambda args: get_weather(args["city"]),
    "get_exchange_rate": lambda args: get_exchange_rate(args["from_currency"], args["to_currency"]),
}


# ---------- 3. ReAct 推理循环 ----------

def agent_loop(question: str, max_steps: int = 5) -> str:
    """
    ReAct 推理循环：
    推理 → 行动 → 观察 → 推理 → 行动 → 观察 → ... → 最终回答

    关键点：
    - Agent 自主决定是否调用工具、调用哪个工具
    - 每次工具调用的结果会反馈给 Agent，进入下一轮推理
    - max_steps 防止无限循环
    """
    messages = [
        {
            "role": "system",
            "content": (
                "你是一个智能助手，可以查询天气和汇率信息。"
                "如果用户的问题需要多个信息才能回答，请分步查询。"
                "回答时请综合所有查询结果，给出完整的回答。"
            )
        },
        {"role": "user", "content": question}
    ]

    print(f"  [开始] 用户提问：{question}")

    for step in range(1, max_steps + 1):
        # 推理：让 Agent 决定下一步行动
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
        )

        message = response.choices[0].message

        # 检查 Agent 是否决定调用工具
        if message.tool_calls:
            # 行动：执行工具调用
            messages.append(message)

            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)

                print(f"  [步骤 {step}] 调用工具：{func_name}({arguments})")

                # 执行工具
                result = tool_functions[func_name](arguments)
                print(f"           结果：{result}")

                # 观察：将工具结果反馈给 Agent
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
        else:
            # Agent 决定不再调用工具，直接给出最终回答
            print(f"  [步骤 {step}] Agent 给出最终回答（共 {step} 步）")
            return message.content

    # 达到最大步数限制
    print(f"  [警告] 达到最大步数限制（{max_steps}步），强制结束")
    return "抱歉，我无法在有限步骤内完成这个任务。"


# ---------- 4. 测试用例 ----------

print("=" * 60)
print("ReAct 推理循环演示")
print("=" * 60)

# 测试 1：简单问题（可能只需要一次工具调用）
print("\n【测试 1】简单问题：单次工具调用")
print("-" * 40)
answer = agent_loop("北京今天天气怎么样？")
print(f"  回答：{answer}")

# 测试 2：复合问题（需要多次工具调用）
print("\n【测试 2】复合问题：需要多次工具调用")
print("-" * 40)
answer = agent_loop("我想从北京去东京旅游，帮我查一下两个城市的天气，以及人民币兑日元的汇率。")
print(f"  回答：{answer[:300]}{'...' if len(answer) > 300 else ''}")

# 测试 3：不需要工具的问题
print("\n【测试 3】闲聊问题：不需要工具")
print("-" * 40)
answer = agent_loop("你好，你能做什么？")
print(f"  回答：{answer[:200]}{'...' if len(answer) > 200 else ''}")

print()
print("=" * 60)
print("关键要点：")
print("  1. Agent 的核心是一个推理循环，不是单次 API 调用")
print("  2. Agent 自主决定调用哪个工具、调用几次")
print("  3. max_steps 是安全阀，防止 Agent 无限循环")
print("  4. 每次工具调用的结果都会反馈给 Agent，驱动下一轮推理")
