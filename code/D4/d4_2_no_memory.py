import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Config
from openai import OpenAI

# ============================================================
# d4_2：无记忆 Agent 演示
#
# 演示：
#   1. 每次对话都是全新的，不保留任何上下文
#   2. Agent 无法记住用户的身份、偏好、历史信息
#   3. 为 d4_3（有记忆版本）提供对比基准
#
# 运行：python d4_2_no_memory.py
# ============================================================


# ---------- 1. 初始化 LLM 客户端 ----------

client = OpenAI(
    api_key=Config.SILICONFLOW_API_KEY,
    base_url=Config.SILICONFLOW_BASE_URL,
)
MODEL = "deepseek-ai/DeepSeek-V3"


# ---------- 2. 无记忆的 Agent ----------

def chat_without_memory(user_input: str) -> str:
    """
    无记忆的 Agent：每次对话都是全新的。
    messages 列表只包含当前这一轮的 system prompt 和用户输入，
    没有任何历史信息。
    """
    messages = [
        {
            "role": "system",
            "content": "你是一个友好的技术助手。根据用户的问题提供有针对性的建议。"
        },
        {"role": "user", "content": user_input}
    ]

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages
    )

    return response.choices[0].message.content


# ---------- 3. 演示对话序列 ----------

print("=" * 60)
print("无记忆 Agent 演示")
print("=" * 60)
print("观察：每一轮对话都是独立的，Agent 不记得上一轮说过什么")
print()

# 第 1 轮：告诉 Agent 用户身份和偏好
print("【第 1 轮】告知身份和偏好")
print("-" * 40)
q1 = "我是一个 Python 开发者，主要做后端开发，喜欢简洁的回答。"
print(f"用户：{q1}")
a1 = chat_without_memory(q1)
print(f"Agent：{a1[:200]}{'...' if len(a1) > 200 else ''}")

# 第 2 轮：问 Web 框架推荐（Agent 应该不记得你是 Python 开发者）
print("\n【第 2 轮】推荐 Web 框架")
print("-" * 40)
q2 = "帮我推荐一个 Web 框架"
print(f"用户：{q2}")
a2 = chat_without_memory(q2)
print(f"Agent：{a2[:300]}{'...' if len(a2) > 300 else ''}")
print()
print("  ⚠️  注意：Agent 不知道你是 Python 开发者，可能推荐了各种语言的框架")

# 第 3 轮：问缓存方案（Agent 应该不记得你喜欢简洁回答）
print("\n【第 3 轮】询问缓存方案")
print("-" * 40)
q3 = "怎么给我的项目加缓存？"
print(f"用户：{q3}")
a3 = chat_without_memory(q3)
print(f"Agent：{a3[:300]}{'...' if len(a3) > 300 else ''}")
print()
print("  ⚠️  注意：Agent 不记得你喜欢简洁回答，可能给了很长的解释")

# 第 4 轮：模拟"第二天"重新打开
print("\n【第 4 轮】模拟重启后继续昨天的话题")
print("-" * 40)
q4 = "继续昨天的话题，帮我选一个数据库方案。"
print(f"用户：{q4}")
a4 = chat_without_memory(q4)
print(f"Agent：{a4[:300]}{'...' if len(a4) > 300 else ''}")
print()
print("  ⚠️  注意：Agent 完全不知道'昨天的话题'是什么")

print()
print("=" * 60)
print("总结：无记忆 Agent 的问题")
print("  1. 每轮对话独立，无法利用用户的历史信息")
print("  2. 推荐不够个性化，无法针对用户的技术栈")
print("  3. 重启后完全失忆，用户需要重复介绍自己")
print("  → 运行 d4_3_with_memory.py 查看有记忆版本的效果对比")
