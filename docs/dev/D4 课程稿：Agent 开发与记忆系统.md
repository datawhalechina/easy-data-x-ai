# D4：Agent 开发与记忆系统

> Easy Data x AI 课程 · 术篇 · 第四期
>
> 上一期你构建了一个能查知识库的 RAG Agent。这一期，我们给它装一个大脑——让它记住你是谁、你说过什么、你需要什么。

## 开场：那个每次都失忆的 Agent

你在 D3 构建的 RAG Agent 已经能回答知识库相关的问题了。用户提问，Agent 通过 Tool Use 调用 seekdb 检索知识库，基于检索结果生成回答。效果不错。

但你有没有试过连续和它聊五轮以上？

第一轮你说：“我是 Python 开发者，最近在做一个数据分析项目。”Agent 回答得很好。

第二轮你问：“帮我推荐一个适合的数据库方案。”Agent 给了你一个通用的推荐列表——MySQL、PostgreSQL、MongoDB，什么都有。

等等，你刚刚告诉过它你是 Python 开发者在做数据分析项目啊？它为什么不直接推荐 pandas + seekdb 这种 Python 友好的方案？为什么要给你推荐一堆 Java 生态更常用的选项？

因为**它根本不记得你说过什么**。

更准确地说，在同一个对话窗口内，它能记住——因为你的代码把历史消息都放在 `messages` 列表里了。但一旦会话结束、程序重启，一切归零。下次你再来，它不知道你是谁、不知道你喜欢什么、不知道你上次的问题解决了没有。

P3 用了一个精确的类比：这就像一个每天早上都会彻底失忆的同事。他很聪明，但你每天都要重新做一次自我介绍。

今天，我们来解决这个问题。不只是“让 Agent 能记住”，而是让它**智能地记住**——记该记的，忘该忘的，想起该想起的。

## 第一部分：Agent 不是一次性回答机器

在动手加记忆之前，我们先理解一件很多开发者忽略的事：Agent 和你之前写的那些“调 API 拿回答”的代码，在架构上有本质区别。

### Agent 的推理循环

D1 你学了 Tool Use，知道模型可以声明“我要调用一个工具”，你的代码去执行，结果传回来，模型继续推理。

但 D1 的例子是一个**单次循环**——用户提问 → 模型判断要不要调工具 → 调一次 → 拿到结果 → 回答。

真实的 Agent 不是这么工作的。它是一个**多步推理循环**，业界称为 **ReAct 模式**（Reasoning + Acting）：

```
推理 → 行动 → 观察 → 推理 → 行动 → 观察 → ... → 最终回答
```

用伪代码表示：

```python
def agent_loop(user_input, tools, max_steps=10):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input}
    ]
    
    for step in range(max_steps):
        response = llm.chat(messages=messages, tools=tools)
        
        if response.has_tool_calls():
            # 推理后决定行动：调用工具
            for tool_call in response.tool_calls:
                result = execute_tool(tool_call)
                messages.append(tool_call_message)
                messages.append(tool_result_message(result))
            # 观察结果后继续循环，进入下一轮推理
        else:
            # 推理后决定：信息够了，直接回答
            return response.content
    
    return "抱歉，我无法完成这个任务。"
```

一个关键细节：循环有**最大步数限制**（`max_steps`）。为什么？因为 Agent 有时候会“转圈”——它调用了工具，拿到的结果不够好，又调用一次，结果还是不够好，于是陷入循环。

理解了这个结构，你就能理解 Agent 的两个常见问题：

- **Agent 转圈（Looping）**：它在循环中反复调用工具，但每次拿到的数据都不足以推进推理。根因通常是数据层的问题——检索结果不够相关，或者工具定义不够清晰。
- **Agent 卡住（Getting Stuck）**：它不知道下一步该调用什么工具，或者所有工具都试过了但没有得到有用的信息。同样，根因往往在数据层。

这和 P1 讲的判断一致：**Agent 表现不好，多半不是模型不够聪明，是它没拿到够好的数据。**

![](https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/dev/D4/01-react-loop.png)

现在，带着这个理解，我们来看记忆系统如何融入这个循环。

## 第二部分：记忆系统的工程实现

P3 用 CoALA 框架把 Agent 记忆分成了短期记忆和三种长期记忆（语义记忆、情景记忆、程序记忆）。那是产品设计视角的分类。现在我们从工程视角来看：这些概念在代码里长什么样？

### 短期记忆：你已经在用了

短期记忆就是**当前会话的对话历史**。你在 D1 就写过：

```python
messages = [
    {"role": "system", "content": "你是一个技术助手。"},
    {"role": "user", "content": "什么是 RAG？"},
    {"role": "assistant", "content": "RAG 是检索增强生成..."},
    {"role": "user", "content": "它和微调有什么区别？"}
]
```

这个 `messages` 列表就是短期记忆。它有两个特点：会话期间随用随取，会话结束就消失。

在 LangGraph 等框架中，短期记忆的管理被封装成 **Checkpointer** 的概念——它负责在每一步推理后保存当前状态，这样即使中途出错也能恢复。本质上就是对 `messages` 列表的持久化管理。

短期记忆的工程挑战不大，但有一个值得注意的点：随着对话轮数增加，`messages` 列表越来越长，迟早会撞上上下文窗口的限制。这时候你需要做**截断或摘要**——而怎么截断、保留哪些信息、丢弃哪些信息，本身就是一个数据决策。

### 长期记忆——语义记忆：这是重头戏

语义记忆存储的是**关于用户的事实和偏好**。P3 用了“百科全书”的类比——记的是“什么是什么”。

从工程角度，语义记忆要做三件事，对应 P3 讲的“记、忘、想起”：

**第一步：提炼（记）**

不是把对话原文存进去，而是从对话中**提取关键事实**。

比如一段对话：

```
用户：我最近在用 FastAPI 做后端，感觉比 Flask 好用多了。
Agent：FastAPI 确实在性能和类型提示方面有优势...
用户：对，我们团队前端用的是 React。
```

从这段对话中应该提取的记忆是：

- “用户后端使用 FastAPI”
- “用户之前用过 Flask”
- “用户团队前端使用 React”

而不是把整段对话的原文存进去。这个提炼过程由 LLM 完成——让另一个 LLM 调用（或同一个模型的后台任务）从对话中萃取结构化的事实。

**第二步：检索（想起）**

存进去的记忆，需要在正确的时候被想起来。这个“想起来”的过程，本质上就是一个**语义检索**——和 D2、D3 讲的 RAG 是同一个问题。

当用户在新的对话中说“帮我推荐一个 ORM 框架”时，Agent 需要从记忆中检索出“用户后端使用 FastAPI”这条信息，然后推荐和 FastAPI 兼容的 ORM（比如 SQLAlchemy 或 Tortoise ORM），而不是推荐一堆 Java 的 ORM。

检索方式和 RAG 一样：把当前查询向量化，在记忆库中找语义最相关的条目。混合检索在这里同样有价值——如果用户说“我之前提到过 FastAPI”，全文搜索能精确匹配到“FastAPI”这个关键词，比纯语义检索更可靠。

**第三步：降权（忘）**

这是 P3 花了最多篇幅讲的部分，也是工程上最有挑战的部分。

三个月前用户说“我喜欢详细的解释”。最近他连续说了三次“太长了，简洁一点”。现在他问一个问题，Agent 应该用哪种风格回答？

如果所有记忆都是等权重的，Agent 会困惑——它同时看到“喜欢详细”和“要简洁”两条矛盾的信息。正确的做法是：旧的偏好随时间自然降权，新的偏好优先生效。这就是 P3 讲的“艾宾浩斯遗忘曲线”在工程上的应用。

### 长期记忆——情景记忆：成功经验的复用

情景记忆存的是**过去的交互经历**——什么方法有效、什么方案失败了。

在工程上，情景记忆最常见的实现方式是 **few-shot 示例**。当 Agent 遇到一个新问题时，从记忆中检索出类似问题的成功处理案例，放进当前的 Prompt 中作为参考。

```python
# 伪代码：检索类似的历史成功案例
similar_episodes = memory.search_episodes(
    query="用户问数据库部署方案",
    top_k=2
)

# 把历史成功案例作为 few-shot 示例放进 Prompt
system_prompt = f"""你是一个技术助手。

以下是你过去成功帮助用户的案例，供参考：
{format_episodes(similar_episodes)}

请根据用户当前的问题给出建议。"""
```

这样 Agent 就能从过往经验中学习，避免在同一类问题上反复试错。

### 长期记忆——程序记忆：可自我进化的行为规则

程序记忆就是 Agent 的 **System Prompt 和行为规则**。在代码里，它就是 `messages[0]`——那条 `role: "system"` 的消息。

有趣的是，程序记忆是三种长期记忆中唯一一种 **Agent 可以自我修改**的。如果用户反复给负面反馈（“你的回答太啰嗦了”），Agent 可以自动在自己的行为规则里加一条“回答要简洁”。

这和 D5 要讲的 Skill 直接相关——Skill 本质上就是结构化的程序记忆，是 Agent 的“操作手册”。D5 会展开。

### 三种长期记忆在代码中的位置

把它们放回 Agent 的推理循环中，就能看清楚每种记忆在什么时候发挥作用：

```python
def agent_with_memory(user_input, tools, memory):
    # 程序记忆 → System Prompt
    system_prompt = memory.get_procedural_rules()
    
    # 语义记忆 → 检索相关的用户事实
    relevant_facts = memory.search_semantic(query=user_input, top_k=5)
    
    # 情景记忆 → 检索相似的成功案例
    similar_episodes = memory.search_episodic(query=user_input, top_k=2)
    
    messages = [
        {"role": "system", "content": f"""{system_prompt}
        
关于这位用户，你知道以下信息：
{format_facts(relevant_facts)}

以下是过去类似问题的处理经验：
{format_episodes(similar_episodes)}"""},
        {"role": "user", "content": user_input}
    ]
    
    # 进入 ReAct 推理循环
    response = agent_loop(messages, tools)
    
    # 对话结束后，提炼新的记忆
    memory.extract_and_store(user_input, response)
    
    return response
```

看到了吗？三种长期记忆都是在 Agent 推理循环**之前**被注入到 Prompt 中的。它们的作用是让 Agent 在开始推理时就已经“认识”这个用户、“记得”过去的经验、“知道”自己该怎么做。

![](https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/dev/D4/02-memory-architecture.png)

## 第三部分：用 PowerMem 给 Agent 装上记忆

理解了原理，我们来动手。

上面那段代码展示了记忆系统的逻辑结构，但真正实现起来有大量的工程细节：LLM 提取事实的 Prompt 怎么写？记忆的存储格式怎么定？时效性降权的算法怎么实现？检索用纯向量还是混合？

这些问题 PowerMem 已经封装好了。PowerMem 是基于 seekdb 构建的 Agent 记忆系统——它用 seekdb 做底层的数据存储和混合检索，用 LLM 做记忆的提炼和管理，用艾宾浩斯曲线做时效性降权。

先来看一个**没有记忆**的 Agent 是什么效果，再看加了 PowerMem 之后是什么效果。

### 没有记忆的 Agent

```python
from openai import OpenAI

client = OpenAI()

def chat_without_memory(user_input):
    """无记忆的 Agent：每次对话都是全新的"""
    messages = [
        {"role": "system", "content": "你是一个友好的技术助手。根据用户的问题提供有针对性的建议。"},
        {"role": "user", "content": user_input}
    ]
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages
    )
    
    return response.choices[0].message.content
```

用这个 Agent 跑几轮对话：

```python
print("--- 第 1 轮 ---")
print(chat_without_memory("我是一个 Python 开发者，主要做后端开发，喜欢简洁的回答。"))

print("\n--- 第 2 轮 ---")
print(chat_without_memory("帮我推荐一个 Web 框架"))

print("\n--- 第 3 轮 ---")
print(chat_without_memory("怎么给我的项目加缓存？"))
```

你会看到：第 2 轮它不知道你是 Python 开发者，可能推荐 Java 的 Spring 或 JavaScript 的 Express；第 3 轮它不知道你喜欢简洁回答，可能给你一大段从基础讲起的长文。

每一轮都是一次全新的对话，上一轮说过的话全部消失。

### 有记忆的 Agent

```python
from powermem import PowerMem

memory = PowerMem(user_id="developer_001")

def chat_with_memory(user_input):
    """有记忆的 Agent：能记住用户信息，跨会话持久化"""
    
    # 从记忆中检索与当前问题相关的用户信息
    relevant_memories = memory.search(query=user_input, top_k=5)
    
    # 构建包含记忆的 System Prompt
    memory_context = "\n".join([m["content"] for m in relevant_memories])
    
    system_prompt = f"""你是一个友好的技术助手。根据用户的问题提供有针对性的建议。

你对这位用户有以下了解：
{memory_context if memory_context else "暂无已知信息，请在对话中了解用户。"}

请根据你了解的信息，提供个性化的回答。"""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ]
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages
    )
    
    assistant_reply = response.choices[0].message.content
    
    # 对话结束后，提炼并存储新的记忆
    memory.add(
        messages=[
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": assistant_reply}
        ]
    )
    
    return assistant_reply
```

同样跑几轮：

```python
print("--- 第 1 轮 ---")
print(chat_with_memory("我是一个 Python 开发者，主要做后端开发，喜欢简洁的回答。"))

print("\n--- 第 2 轮 ---")
print(chat_with_memory("帮我推荐一个 Web 框架"))

print("\n--- 第 3 轮 ---")
print(chat_with_memory("怎么给我的项目加缓存？"))
```

这次效果完全不同：

- 第 2 轮：Agent 记得你是 Python 开发者，直接推荐 FastAPI 或 Django，不会给你推荐 Java 框架
- 第 3 轮：Agent 记得你喜欢简洁回答，直接给出核心建议——“用 Redis 做缓存，`pip install redis`，三行代码搞定”，而不是从“什么是缓存”讲起

更重要的是，这些记忆是**跨会话持久化的**。你关掉程序、明天重新打开，Agent 仍然记得你是 Python 开发者、喜欢简洁回答。

### 两个版本对话效果对比

为了让差距更直观，我们把同一组问题分别交给两个版本，对比回答：

| 轮次 | 用户输入 | 无记忆 Agent | 有记忆 Agent |
| --- | --- | --- | --- |
| 1 | “我是 Python 开发者，喜欢简洁回答” | “好的，有什么可以帮你的？” | “好的，我记住了！有什么可以帮你的？” |
| 2 | “推荐一个 Web 框架” | 长篇介绍 Spring、Express、Django、Rails.。。 | “推荐 FastAPI——异步、类型安全、性能好，适合 Python 后端。” |
| 3 | “怎么部署到云上？” | 泛泛而谈各种云平台、各种语言的部署方案 | “FastAPI 部署推荐 Docker + 云平台。Dockerfile 三行搞定……” |
| 4 | “数据库怎么选？” | 列出所有主流数据库的优缺点对比 | “Python 后端推荐 PostgreSQL 或 seekdb。配合 SQLAlchemy ORM……” |
| 5 | “谢谢，今天先到这” | “不客气！” | “不客气！下次继续聊你的项目。” |

关掉程序，第二天重新打开——

| 轮次 | 用户输入 | 无记忆 Agent | 有记忆 Agent |
| --- | --- | --- | --- |
| 6 | “继续昨天的话题” | “抱歉，我不知道昨天聊了什么。” | “好的，昨天你在搭建 Python 后端项目。我们聊到了数据库选型，还需要继续吗？” |

**天壤之别。**

![](https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/dev/D4/03-memory-before-after.png)

## 第四部分：框架集成——不需要重写你的架构

你可能在想：我已经用了 LangChain 或其他 Agent 框架，加 PowerMem 要改多少代码？

答案是：**几乎不用改架构**。

PowerMem 的设计思路是作为一个**记忆层**独立存在，而不是替代你的 Agent 框架。它通过两个接入点和你现有的 Agent 交互：

1. **推理前注入**：在构建 Prompt 时，调用 `memory.search()` 检索相关记忆，拼到 System Prompt 里
2. **推理后存储**：对话结束后，调用 `memory.add()` 提炼并存储新记忆

无论你用 LangChain、LlamaIndex、还是自己手写的 Agent 循环，这两个接入点的位置都是明确的。以 LangChain 为例：

```python
from langchain.chat_models import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from powermem import PowerMem

memory = PowerMem(user_id="user_001")
llm = ChatOpenAI(model="gpt-4o")

def build_prompt_with_memory(user_input):
    """在现有 Agent 的 Prompt 中注入记忆"""
    memories = memory.search(query=user_input, top_k=5)
    memory_text = "\n".join([m["content"] for m in memories])
    
    return f"""你是一个技术助手。

你对当前用户有以下了解：
{memory_text}

请根据以上信息提供个性化的回答。"""

# 在你的 Agent 流程中，只需要修改两处：
# 1. Prompt 构建时加入 memory.search()
# 2. 对话结束后调用 memory.add()
```

底层的数据存储和检索由 seekdb 处理——向量索引、全文索引、混合检索，都是 D2 讲过的那套能力。PowerMem 在 seekdb 之上增加了记忆特有的逻辑：LLM 自动提取关键事实、艾宾浩斯曲线管理时效性、记忆冲突检测与合并。

你不需要关心这些内部细节。从使用者的角度，`memory.search()` 和 `memory.add()` 就是你需要的全部 API。

## 我们的思考

记忆系统看起来是个 AI 问题，但拆到底是个数据问题——怎么存、怎么查、怎么过期。

我们在做 PowerMem 的过程中，最大的感受是：每一个“AI 层面”的设计决策，最终都落到了数据层面的实现上。

**“记什么”是一个数据提炼问题。** 从一段对话中提取关键事实，本质上是把非结构化数据（对话原文）变成结构化数据（事实条目）。LLM 负责理解语义和判断重要性，但提炼出来的结果要以什么格式存、怎么建索引，是数据层的决策。

**“想起什么”是一个数据检索问题。** 和 RAG 完全是同一个机制——把当前查询向量化，在记忆库中做混合检索，返回最相关的条目。D2 和 D3 你花了大量时间研究的检索策略，在记忆系统中一模一样地适用。

**“忘什么”是一个数据生命周期管理问题。** PowerMem 用艾宾浩斯遗忘曲线来实现时效性管理：每条记忆有一个权重，随时间自然衰减；但如果这条记忆在后续对话中被再次提及，权重回升。经常被用到的记忆权重持续维持在高位，不再被提及的记忆自然淡出。

这套机制在 LOCOMO 基准测试（Shopify 开发的 Agent 长期记忆评估基准）上取得了 78.7% 的准确率。作为对比，把所有历史对话直接塞进上下文窗口的“暴力方案”只有 52.9%。差距接近 50%。

这个数据说明了一件反直觉的事：**把所有信息都“记住”，效果反而不如有选择地记忆。** 信息过载会干扰检索——当上下文中塞满了过时的、无关的信息，模型反而找不到真正有用的那几条。

PowerMem 封装了这些最佳实践。安装 `powermem` 之后，几十行代码就能给你的 Agent 加上智能记忆——自动提取关键事实、混合检索召回相关记忆、艾宾浩斯曲线管理时效性。你不需要自己实现这些机制，但你需要理解它们背后的逻辑——因为当记忆系统表现不够好的时候，问题几乎一定出在这三个环节中的某一个。

## 动手体验：构建你的记忆 Agent

### 环境准备

```python
# 终端运行
# pip install openai powermem pyseekdb
```

### 完整代码：一个有记忆的对话 Agent

```python
from openai import OpenAI
from powermem import PowerMem

client = OpenAI()
memory = PowerMem(user_id="demo_user")

def chat(user_input):
    # 1. 检索相关记忆
    memories = memory.search(query=user_input, top_k=5)
    memory_text = "\n".join([m["content"] for m in memories]) if memories else "暂无"
    
    # 2. 构建带记忆的 Prompt
    messages = [
        {"role": "system", "content": f"""你是一个友好、专业的技术助手。

你对当前用户有以下了解：
{memory_text}

请根据你对用户的了解，提供个性化的、有针对性的回答。
如果用户提供了新的个人信息或偏好，自然地融入对话中。"""},
        {"role": "user", "content": user_input}
    ]
    
    # 3. 调用模型
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages
    )
    reply = response.choices[0].message.content
    
    # 4. 提炼并存储新记忆
    memory.add(
        messages=[
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": reply}
        ]
    )
    
    return reply

# 开始对话
while True:
    user_input = input("\n你: ")
    if user_input.lower() in ["quit", "exit", "退出"]:
        break
    print(f"\nAgent: {chat(user_input)}")
```

### 试试这个对话序列

跑起来之后，按这个顺序输入，观察 Agent 的行为：

```
你: 我是一个 Python 开发者，在一家做 SaaS 产品的创业公司工作。
你: 我喜欢简洁的回答，不需要太多解释。
你: 帮我推荐一个适合的消息队列方案。
你: 我们团队之前试过 RabbitMQ，感觉配置太复杂了。
你: 那 Celery 呢？
```

在第 3 轮，观察 Agent 是否直接推荐 Python 生态的方案（而不是泛泛列举所有语言的选项）。在第 4 轮之后，观察 Agent 是否避免再次推荐 RabbitMQ。在第 5 轮，观察 Agent 的回答是否简洁——因为你在第 2 轮说过“喜欢简洁的回答”。

然后，**退出程序，重新启动**，再输入：

```
你: 我之前说过我在哪种公司工作来着？
你: 帮我选一个数据库方案。
```

如果记忆系统正常工作，Agent 应该记得你在 SaaS 创业公司工作，并且推荐 Python 友好、适合创业公司规模的数据库方案。

## 这节课要留下的印象

如果这节课的所有内容你只记住一句话，记住这句：

> **给 Agent 加记忆，难的不是代码——难的是该记什么、该忘什么、该想起什么。这三个问题，本质上都是数据处理和检索的问题。**

## 课后行动

1. **跑通 Notebook**：运行本模块的代码，构建一个有记忆的对话 Agent，和它连续聊 5 轮以上。退出后重新启动，确认记忆跨会话保持。

2. **做一个有趣的实验**：在前几轮对话中，故意提供一些偏好信息和个人背景——

   - “我喜欢简洁的回答”
   - “我是 Python 开发者”
   - “我们公司用的是 AWS”
   - “上次你推荐的 FastAPI 方案我已经在用了”

   然后在后续对话中，观察 Agent 是否在合适的时候自然地调用了这些信息。它有没有在你问 Web 框架时优先推荐 Python 的？有没有在你问部署方案时默认用 AWS 的？有没有记住你说过喜欢简洁、实际给出简洁的回答？

3. **对比体验**：用同样的对话序列分别测试“有记忆”和“无记忆”版本，直观感受差距。

## 延伸阅读

如果你对本期提到的概念想做进一步了解，以下是一些推荐资源：

- **ReAct 论文原文**：[ReAct： Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)，定义了 Agent “推理-行动”循环模式的经典论文
- **CoALA 论文**：[Cognitive Architectures for Language Agents](https://arxiv.org/pdf/2309.02427)，系统定义了 Agent 记忆的分类框架（语义记忆、情景记忆、程序记忆），被 LangChain 等主流框架广泛采用
- **LangGraph 记忆架构**：LangGraph 的 Checkpointer 和 Memory Store 实现，是当前主流 Agent 框架中记忆管理的工程参考
- **LOCOMO Benchmark**：[github.com/Shopify/locomo](https://github.com/Shopify/locomo)，Shopify 开发的 Agent 长期记忆评估基准，用于衡量记忆系统的检索准确率

> **下一期预告**：D5 · 课程总结——今天讲的程序记忆告诉我们 Agent 需要”操作手册”。但当手册越来越多、分散在不同平台时，一个新问题出现了：经验数据的碎片化。D5 我们来解决这个问题，同时用 MCP 把你构建的所有能力变成标准化服务，完成整个 Dev 路径的最后一块拼图。

---

欢迎各位老师在 https://github.com/datawhalechina/easy-data-x-ai 参与课程共建。

也欢迎各位老师加入 Data x AI 交流群~

<div align="center">
  <img src="https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/base_knowledge/F0/F0-20.png" width="200" />
</div>