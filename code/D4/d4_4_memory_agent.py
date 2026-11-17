import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Config
import json
import time
import math
import uuid
from openai import OpenAI
from seekdb_runtime import create_seekdb_client, require_destructive_seekdb_access

# ============================================================
# d4_4：完整记忆 Agent（交互式）
#
# 演示：
#   1. 完整的记忆 Agent 架构：程序记忆 + 语义记忆 + 情景记忆
#   2. 跨会话持久化：退出重启后记忆依然保留
#   3. 交互式对话：可以连续聊多轮
#
# 推荐对话序列（课程建议）：
#   1. "我是一个 Python 开发者，在一家做 SaaS 产品的创业公司工作。"
#   2. "我喜欢简洁的回答，不需要太多解释。"
#   3. "帮我推荐一个适合的消息队列方案。"
#   4. "我们团队之前试过 RabbitMQ，感觉配置太复杂了。"
#   5. "那 Celery 呢？"
#   然后退出重启，再输入：
#   6. "我之前说过我在哪种公司工作来着？"
#   7. "帮我选一个数据库方案。"
#
# 运行：python d4_4_memory_agent.py
# ============================================================


# ---------- 1. 初始化 ----------

MODEL = "deepseek-ai/DeepSeek-V3"
MEMORY_COLLECTION = "user_memory_persistent"
D4_DIR = Path(__file__).resolve().parent
MEMORY_DB_PATH = D4_DIR / "memory_persistent.db"

client = None
db = None
memory_col = None


def initialize_runtime(*, api_client=None, database=None):
    """显式创建外部依赖，并复用持久化记忆集合。"""
    global client, db, memory_col
    require_destructive_seekdb_access("写入 D4 持久化记忆库")
    client = api_client if api_client is not None else OpenAI(
        api_key=Config.SILICONFLOW_API_KEY,
        base_url=Config.SILICONFLOW_BASE_URL,
    )
    db = database if database is not None else create_seekdb_client(
        path=MEMORY_DB_PATH
    )
    if db.has_collection(MEMORY_COLLECTION):
        memory_col = db.get_collection(name=MEMORY_COLLECTION)
        print(f">>> 已加载历史记忆库，当前记忆数量：{memory_col.count()}")
    else:
        memory_col = db.create_collection(name=MEMORY_COLLECTION)
        print(">>> 首次运行，记忆库已创建")
    return memory_col


def close_runtime():
    """显式释放数据库连接和运行时引用。"""
    global client, db, memory_col
    active_client = client
    active_database = db
    try:
        if active_client is not None:
            close_client = getattr(active_client, "close", None)
            if callable(close_client):
                close_client()
        if active_database is not None:
            close = getattr(active_database, "close", None)
            if callable(close):
                close()
            else:
                exit_context = getattr(active_database, "__exit__", None)
                if callable(exit_context):
                    exit_context(None, None, None)
    finally:
        client = None
        db = None
        memory_col = None


def _require_model_client(api_client=None):
    active_client = api_client if api_client is not None else client
    if active_client is None:
        raise RuntimeError("请先调用 initialize_runtime() 初始化模型客户端")
    return active_client


def _require_memory_collection(collection=None):
    active_collection = collection if collection is not None else memory_col
    if active_collection is None:
        raise RuntimeError("请先调用 initialize_runtime() 初始化记忆库")
    return active_collection


def _response_content(response, *, allow_empty=False):
    """读取模型响应；事实提炼可对空响应安全降级。"""
    choices = getattr(response, "choices", None)
    message = getattr(choices[0], "message", None) if choices else None
    content = getattr(message, "content", None) if message is not None else None
    if isinstance(content, str) and content.strip():
        return content
    if allow_empty:
        return None
    raise RuntimeError("模型返回空响应：缺少 choices、message 或 content")


# ---------- 2. 程序记忆（System Prompt）----------
# 程序记忆是 Agent 的行为规则，存储在 System Prompt 中
# 这是三种长期记忆中唯一可以自我修改的

BASE_SYSTEM_PROMPT = """你是一个友好、专业的技术助手。

你的行为准则：
- 根据你对用户的了解，提供个性化的、有针对性的回答
- 如果用户提供了新的个人信息或偏好，自然地融入对话中
- 如果用户说过喜欢简洁，就给简洁的回答；如果没有特别说明，可以适当详细
- 推荐技术方案时，优先考虑用户已知的技术栈"""


# ---------- 3. 记忆管理函数 ----------

def extract_facts(user_input: str, assistant_reply: str, *, api_client=None) -> list[str]:
    """用 LLM 从对话中提炼关键事实"""
    prompt = f"""从以下对话中提取关于用户的关键事实和偏好。
只提取明确的、关于这位用户的信息（身份、技术栈、偏好、经历、踩过的坑等）。
不要提取通用知识。如果没有值得记录的用户信息，返回空列表。

对话：
用户：{user_input}
助手：{assistant_reply}

以 JSON 数组格式返回，每个元素是一条事实字符串。
如果没有值得记录的信息，返回：[]"""

    response = _require_model_client(api_client).chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )

    content = _response_content(response, allow_empty=True)
    if content is None:
        return []
    content = content.strip()
    try:
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
                if "value" in f and "fact" in f:
                    str_facts.append(f"{f['fact']}：{f['value']}")
                else:
                    str_facts.append(str(f))
        return str_facts
    except Exception:
        return []


def save_memory(facts: list[str], *, collection=None):
    """将事实存入记忆库"""
    if not facts:
        return

    current_time = time.time()
    ids = [str(uuid.uuid4()) for _ in facts]
    metadatas = [{"created_at": current_time, "access_count": 0} for _ in facts]

    _require_memory_collection(collection).add(
        ids=ids,
        documents=facts,
        metadatas=metadatas,
    )


def recall_memory(query: str, top_k: int = 5, *, collection=None) -> list[str]:
    """检索相关记忆，带时效性权重"""
    active_collection = _require_memory_collection(collection)
    if active_collection.count() == 0:
        return []

    n = min(top_k, active_collection.count())
    results = active_collection.query(query_texts=[query], n_results=n)

    if not results or not results["documents"] or not results["documents"][0]:
        return []

    current_time = time.time()
    weighted = []

    ids = results.get("ids", [[]])[0]
    updated_ids = []
    updated_metadatas = []
    for memory_id, doc, meta in zip(
        ids,
        results["documents"][0],
        results["metadatas"][0],
    ):
        # 时效性权重：30天半衰期的指数衰减
        age_days = (current_time - meta["created_at"]) / 86400
        weight = math.exp2(-age_days / 30) + meta.get("access_count", 0) * 0.1
        weighted.append((doc, weight))
        updated_metadata = dict(meta)
        updated_metadata["access_count"] = meta.get("access_count", 0) + 1
        updated_ids.append(memory_id)
        updated_metadatas.append(updated_metadata)

    # 只更新本次检索实际返回的记忆 ID。
    if updated_ids:
        active_collection.update(
            ids=updated_ids,
            metadatas=updated_metadatas,
        )

    weighted.sort(key=lambda x: x[1], reverse=True)
    return [m[0] for m in weighted]


def show_memory_stats(*, collection=None):
    """显示当前记忆库状态"""
    active_collection = _require_memory_collection(collection)
    count = active_collection.count()
    if count == 0:
        print("  [记忆库] 暂无记忆")
        return

    print(f"  [记忆库] 共 {count} 条记忆：")
    all_mem = active_collection.get()
    if all_mem and all_mem["documents"]:
        for i, doc in enumerate(all_mem["documents"][-5:], 1):  # 只显示最近 5 条
            print(f"    {i}. {doc}")
        if count > 5:
            print(f"    ... 还有 {count - 5} 条更早的记忆")


# ---------- 4. 完整记忆 Agent ----------

def chat(
    user_input: str,
    verbose: bool = True,
    *,
    api_client=None,
    collection=None,
) -> str:
    """
    完整记忆 Agent：
    - 程序记忆（System Prompt）：定义行为规则
    - 语义记忆（seekdb）：存储用户事实和偏好
    - 情景记忆（seekdb）：存储过去的成功经验（本示例简化为同一个库）
    """
    # 1. 检索语义记忆
    memories = recall_memory(query=user_input, top_k=5, collection=collection)
    memory_text = "\n".join([f"- {m}" for m in memories]) if memories else "暂无已知信息，请在对话中了解用户。"

    # 2. 构建带记忆的完整 System Prompt
    system_prompt = f"""{BASE_SYSTEM_PROMPT}

你对当前用户有以下了解：
{memory_text}

请根据以上信息提供个性化的回答。"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ]

    # 3. 调用模型
    active_client = _require_model_client(api_client)
    response = active_client.chat.completions.create(
        model=MODEL,
        messages=messages
    )
    reply = _response_content(response)

    # 4. 提炼并存储新记忆
    facts = extract_facts(user_input, reply, api_client=active_client)
    if facts and verbose:
        print(f"  [记忆提炼] {facts}")
    save_memory(facts, collection=collection)

    return reply


# ---------- 5. 交互式主循环 ----------

def run_interactive():
    """启动交互式记忆 Agent。"""
    global memory_col
    print()
    print("=" * 60)
    print("完整记忆 Agent（交互式）")
    print("=" * 60)
    print("输入 'quit' 或 '退出' 结束对话")
    print("输入 '/memory' 查看当前记忆库")
    print("输入 '/clear' 清空记忆库（重新开始）")
    print()
    show_memory_stats()
    print()

    while True:
        try:
            user_input = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ["quit", "exit", "退出"]:
            print("再见！记忆已保存，下次启动时会自动加载。")
            break
        if user_input == "/memory":
            show_memory_stats()
            continue
        if user_input == "/clear":
            db.delete_collection(MEMORY_COLLECTION)
            memory_col = db.create_collection(name=MEMORY_COLLECTION)
            print("  [记忆库] 已清空")
            continue

        print()
        reply = chat(user_input, verbose=True)
        print(f"\nAgent: {reply}")
        print()


def main() -> int:
    try:
        Config.require_api_key("SILICONFLOW_API_KEY")
    except RuntimeError as exc:
        print(f"❌ {exc}")
        return 1
    try:
        initialize_runtime()
        run_interactive()
    finally:
        close_runtime()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
