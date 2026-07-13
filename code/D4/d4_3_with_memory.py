import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Config
import json
import time
import math
from openai import OpenAI
import pyseekdb

# ============================================================
# d4_3：有记忆的 Agent 演示
#
# 演示：
#   1. 用 seekdb 实现语义记忆（存储用户事实和偏好）
#   2. 用 LLM 从对话中自动提炼关键事实
#   3. 用混合检索在正确时机"想起"相关记忆
#   4. 用时效性权重实现"遗忘曲线"（旧记忆自然降权）
#   5. 与 d4_2 对比，展示记忆系统的效果差异
#
# 运行：python d4_3_with_memory.py
# ============================================================


# ---------- 1. 初始化 ----------

client = OpenAI(
    api_key=Config.SILICONFLOW_API_KEY,
    base_url=Config.SILICONFLOW_BASE_URL,
)
MODEL = "deepseek-ai/DeepSeek-V3"

# 初始化 seekdb，用于存储记忆
db = pyseekdb.Client(path="./memory.db")
MEMORY_COLLECTION = "user_memory_demo"

# 如果已存在则先清空，确保演示效果干净
if db.has_collection(MEMORY_COLLECTION):
    db.delete_collection(MEMORY_COLLECTION)
memory_col = db.create_collection(name=MEMORY_COLLECTION)

print(">>> 记忆库已初始化（演示模式：每次运行重置）")


# ---------- 2. 记忆管理函数 ----------

def extract_facts_from_conversation(user_input: str, assistant_reply: str) -> list[str]:
    """
    用 LLM 从一轮对话中提炼关键事实。
    只提取关于用户的客观事实和偏好，不提取通用知识。
    """
    prompt = f"""从以下对话中提取关于用户的关键事实和偏好。
只提取明确的、关于这位用户的信息（身份、技术栈、偏好、经历等）。
不要提取通用知识或 Agent 的回答内容。
如果没有值得记录的用户信息，返回空列表。

对话：
用户：{user_input}
助手：{assistant_reply}

以 JSON 数组格式返回，每个元素是一条事实字符串。例如：
["用户是 Python 开发者", "用户喜欢简洁的回答", "用户在创业公司工作"]

如果没有值得记录的信息，返回：[]"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )

    content = response.choices[0].message.content.strip()

    # 提取 JSON 数组
    try:
        # 处理可能包含 markdown 代码块的情况
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        facts = json.loads(content)
        if not isinstance(facts, list):
            return []
        # 确保每个元素都是字符串（防止 LLM 返回字典格式）
        str_facts = []
        for f in facts:
            if isinstance(f, str):
                str_facts.append(f)
            elif isinstance(f, dict):
                # 将字典转为字符串，如 {"fact": "职业", "value": "Python开发者"} → "职业：Python开发者"
                if "value" in f and "fact" in f:
                    str_facts.append(f"{f['fact']}：{f['value']}")
                else:
                    str_facts.append(str(f))
        return str_facts
    except Exception:
        return []


def add_memory(facts: list[str]):
    """将提炼出的事实存入 seekdb 记忆库"""
    if not facts:
        return

    current_time = time.time()
    ids = []
    documents = []
    metadatas = []

    for i, fact in enumerate(facts):
        memory_id = f"mem_{int(current_time)}_{i}"
        ids.append(memory_id)
        documents.append(fact)
        metadatas.append({
            "created_at": current_time,
            "access_count": 0,  # 被检索到的次数（用于遗忘曲线）
        })

    memory_col.add(ids=ids, documents=documents, metadatas=metadatas)
    print(f"  [记忆] 存入 {len(facts)} 条新记忆：{facts}")


def search_memory(query: str, top_k: int = 5) -> list[str]:
    """
    从记忆库中检索与当前问题相关的记忆。
    使用时效性权重：越新的记忆权重越高（模拟遗忘曲线）。
    """
    if memory_col.count() == 0:
        return []

    results = memory_col.query(query_texts=[query], n_results=min(top_k, memory_col.count()))

    if not results or not results["documents"] or not results["documents"][0]:
        return []

    current_time = time.time()
    weighted_memories = []

    for doc, metadata in zip(results["documents"][0], results["metadatas"][0]):
        # 计算时效性权重（艾宾浩斯遗忘曲线简化版）
        # 记忆越新、被访问次数越多，权重越高
        age_days = (current_time - metadata["created_at"]) / 86400
        recency_weight = math.exp(-age_days / 30)  # 30天半衰期
        access_bonus = metadata.get("access_count", 0) * 0.1  # 每次访问加分
        weight = recency_weight + access_bonus

        weighted_memories.append((doc, weight, metadata))

    # 按权重排序，返回最相关的记忆
    weighted_memories.sort(key=lambda x: x[1], reverse=True)
    return [m[0] for m in weighted_memories[:top_k]]


# ---------- 3. 有记忆的 Agent ----------

def chat_with_memory(user_input: str) -> str:
    """
    有记忆的 Agent：
    1. 推理前：从记忆库检索相关的用户信息，注入 System Prompt
    2. 推理：基于记忆上下文生成个性化回答
    3. 推理后：从对话中提炼新事实，存入记忆库
    """
    # 步骤 1：检索相关记忆
    relevant_memories = search_memory(query=user_input, top_k=5)
    memory_context = "\n".join([f"- {m}" for m in relevant_memories])

    # 步骤 2：构建包含记忆的 System Prompt
    if memory_context:
        system_content = f"""你是一个友好的技术助手。根据用户的问题提供有针对性的建议。

你对这位用户有以下了解：
{memory_context}

请根据你了解的信息，提供个性化的、有针对性的回答。"""
    else:
        system_content = "你是一个友好的技术助手。根据用户的问题提供有针对性的建议。如果用户提供了个人信息，请自然地记住并在后续回答中体现。"

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_input}
    ]

    # 步骤 3：调用模型
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages
    )
    reply = response.choices[0].message.content

    # 步骤 4：提炼并存储新记忆
    facts = extract_facts_from_conversation(user_input, reply)
    add_memory(facts)

    return reply


# ---------- 4. 演示对话序列（与 d4_2 相同的问题，对比效果）----------

print()
print("=" * 60)
print("有记忆 Agent 演示")
print("=" * 60)
print("观察：Agent 会记住用户信息，并在后续对话中体现")
print()

# 第 1 轮：告诉 Agent 用户身份和偏好
print("【第 1 轮】告知身份和偏好")
print("-" * 40)
q1 = "我是一个 Python 开发者，主要做后端开发，喜欢简洁的回答。"
print(f"用户：{q1}")
a1 = chat_with_memory(q1)
print(f"Agent：{a1[:200]}{'...' if len(a1) > 200 else ''}")
print(f"  [记忆库] 当前记忆数量：{memory_col.count()}")

# 第 2 轮：问 Web 框架推荐（Agent 应该记得你是 Python 开发者）
print("\n【第 2 轮】推荐 Web 框架")
print("-" * 40)
q2 = "帮我推荐一个 Web 框架"
print(f"用户：{q2}")
a2 = chat_with_memory(q2)
print(f"Agent：{a2[:300]}{'...' if len(a2) > 300 else ''}")
print()
print("  ✅ 注意：Agent 记得你是 Python 开发者，应该推荐 Python 框架")

# 第 3 轮：问缓存方案（Agent 应该记得你喜欢简洁回答）
print("\n【第 3 轮】询问缓存方案")
print("-" * 40)
q3 = "怎么给我的项目加缓存？"
print(f"用户：{q3}")
a3 = chat_with_memory(q3)
print(f"Agent：{a3[:300]}{'...' if len(a3) > 300 else ''}")
print()
print("  ✅ 注意：Agent 记得你喜欢简洁回答，应该给出简洁的建议")

# 第 4 轮：模拟"第二天"重新打开（记忆已持久化在 seekdb 中）
print("\n【第 4 轮】模拟重启后继续昨天的话题")
print("-" * 40)
q4 = "继续昨天的话题，帮我选一个数据库方案。"
print(f"用户：{q4}")
a4 = chat_with_memory(q4)
print(f"Agent：{a4[:300]}{'...' if len(a4) > 300 else ''}")
print()
print("  ✅ 注意：Agent 记得你是 Python 开发者，应该推荐 Python 友好的数据库")

# 展示当前记忆库内容
print()
print("=" * 60)
print("当前记忆库内容（共 {} 条）：".format(memory_col.count()))
print("-" * 40)
all_memories = memory_col.get()
if all_memories and all_memories["documents"]:
    for i, doc in enumerate(all_memories["documents"], 1):
        print(f"  {i}. {doc}")

print()
print("=" * 60)
print("总结：有记忆 Agent 的优势")
print("  1. 记住用户身份和技术栈，推荐更有针对性")
print("  2. 记住用户偏好，回答风格更符合期望")
print("  3. 记忆持久化在 seekdb 中，重启后仍然有效")
print("  → 运行 d4_4_memory_agent.py 体验完整的交互式记忆 Agent")
