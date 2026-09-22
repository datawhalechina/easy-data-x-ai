---
title: I7：PowerContext 的设计与实现
outline: deep
---

# I7：PowerContext 的设计与实现

> Easy Data x AI 课程 · 产业应用篇 · 第 7 节

::: tip 本节定位
本节以开源上下文管理系统 PowerContext 为案例，把 I6 的五个数据角色拆成可运行的领域对象与接口：Scope、Source、Memory、PreparedContext 与 Handoff。学习重点是架构边界与可替换接口：先理解每一层为什么这样设计，再学习如何调用。
:::

::: warning 版本提示
本文依据 2026 年 9 月初的 PowerContext 开源实现（oceanbase/powercontext master 分支）与配套文档整理，实验部分在本地最小模式（SQLite、未接入模型）下实测验证。项目仍在快速演进，安装方式、配置项、接口与内部约束应以目标版本文档和实测结果为准。
:::

## 学习目标

完成本节后，你将能够：

1. 说出 PowerContext 的定位，以及它与 PowerMem 的承接关系；
2. 画出 Scope、Source、Artifact、PreparedContext 的数据关系；
3. 解释不可变修订与精确引用为什么能支撑审计；
4. 区分直接写入与候选审核两类治理路径；
5. 说明 Work Contract、Handoff 与 Task Outcome 的交接闭环；
6. 描述 Core SDK、Client、Server、HTTP、MCP 与 CLI 的职责边界；
7. 比较 SQLite、seekDB、OceanBase 三个存储后端与四种检索模式的取舍；
8. 运行一个最小回路实验并解读关键响应字段。

## 1. PowerContext 是什么

PowerContext 是 OceanBase 社区开源的上下文管理系统，让项目和 Agent 的上下文可以交接和继续。它是课程里 PowerMem 的全面升级，在记忆之外扩展了证据、交接、经验与技能四类资产。

长期使用多个编码 Agent 的团队会遇到一类共性问题：这次会话完成了推理和决策，下次会话或换一个 Agent 接手时，决策依据、约束与进行到一半的任务都留在上一个会话里。PowerContext 把这类内容从聊天记录中拆出来，作为项目数据单独持久化，让人和多种 Agent 共享同一份工作上下文。

### 1.1 与 PowerMem 的承接关系

D4 用 PowerMem 演示了记忆的存储、检索与遗忘。PowerContext 是同一个团队对更大问题的回答：

| 维度 | PowerMem | PowerContext |
| --- | --- | --- |
| 关注对象 | 记忆条目的存取与衰减 | 证据、记忆、交接、经验、技能的完整链路 |
| 资产类型 | 记忆 | 记忆、交接、经验、技能 |
| 证据模型 | 依赖对话输入 | 独立来源层，记录可引用证据 |
| 交付形态 | SDK 接入为主 | 本地服务，HTTP、MCP、CLI 多入口 |
| 延续 | 课程 D4 的实现参考 | 本节的案例对象 |

PowerMem 解决的问题被 PowerContext 保留为记忆资产，同时上下文被当作一类需要版本、引用与生命周期的数据来管理。

### 1.2 四类资产与能力分级

PowerContext 管理四类资产：

| 资产 | 回答的问题 | 生命周期要点 |
| --- | --- | --- |
| Memory | 以后还要影响判断的知识 | 活跃与停用状态，跨会话复用 |
| Handoff | 进行中的工作交给谁、从哪开始 | 随任务推进，可提交为里程碑 |
| Experience | 审核过的判断经验 | 批准后的当前版本才能被引用 |
| Skill | 可重复执行的做法 | 批准后还要显式导出才可执行 |

对应能力按 Profile 分级，接入方可以按需选择：

| 级别 | 覆盖能力 |
| --- | --- |
| 最小 | 记忆读写、来源采集、上下文注入 |
| 推荐 | 任务契约、交接、确认与结果回写 |
| 完整 | 经验沉淀、技能管理、候选审核 |

分级贯穿整节：先跑通最小回路，再按任务需要扩展，避免一上来就承担全部功能。

## 2. 领域模型：归属、证据与不可变资产

I6 讨论的职责在 PowerContext 中落成四类持久对象与一组关系：Scope 划定归属，Source 保存证据，Artifact 保存不可变资产，PreparedContext 是临时装配结果。

![Scope 划定归属边界，Source 与 Artifact 落位，PreparedContext 按请求装配](/images/industry/I7/I7-01-domain-model.png)

### 2.1 Scope：一切数据的归属边界

Scope 是所有数据的隔离边界。来源、记忆、交接历史与统计都归属某个 Scope，检索和装配默认只在当前 Scope 内进行。

Scope 的两个设计要点值得注意：

- Scope 的标识由服务端生成。创建时只交标题和摘要，系统返回一个 ID；应用把它当普通键保存即可，不要自己用目录名、仓库名或会话 ID 去拼。
- Scope 负责数据归谁、和谁隔开，不管谁有权访问。权限还是要靠宿主和接入层的鉴权来做。

一个长期项目里，把仓库或工作流绑到同一个稳定的 Scope，各次会话共用这一份数据。仓库路径可以用来找到这个 Scope，但不能拿它当 Scope 本身。会话标识、临时目录这类经常变的值更不行，否则每次都会落到一块空的数据空间。

### 2.2 Source：可引用的证据

Source 记录发生过什么。PowerContext 把一次证据事件保存为不可变的观察，每个观察带精确的 SourceRef，引用不会因为内容被重新采集而漂移。

来源有两种物化方式：

| 物化方式 | 内容从哪里来 | 适用情况 |
| --- | --- | --- |
| captured | PowerContext 自己保存的内容快照 | 消息、任务结果等本地可持内容 |
| referenced | 外部不可变位置的引用 | 只能寻址外部对象的场景 |

Work Contract 与 Task Outcome 在系统里也以来源形式保存：委托基线是任务开始时写入的证据，任务结果回写后形成可审计的记录。

### 2.3 Artifact：不可变修订的资产层

PowerContext 用 Artifact 表达可复用的长期资产。一个 Artifact 有稳定的标识，内容按不可变 Revision 演进，精确引用格式为内容族、标识与修订号的组合，例如 `memory/project-notes@3`。

这样的设计带来三条约束：

- 写操作只产生新 Revision，已发布内容不修改；
- 旧 Revision 保持可读，引用旧版本不会悄悄变成新版本；
- Revision 是并发的比较基线，过期写入会被拒绝。

### 2.4 四类 Family 的数据形态

Artifact 按内容族划分，各自保存不同的字段：

| Family | 主要字段 | 本课程的对照 |
| --- | --- | --- |
| Memory | 条目清单、条目正文、活跃状态 | D4 的事实化记忆 |
| Handoff | 目标、状态、下一步、证据、已知缺口 | 跨会话的任务接力 |
| Experience | 情境、动作、结果、教训 | X1-3 的经验沉淀 |
| Skill | 名称、描述、指令、校验方式 | P4 的 Skill 资产 |

记忆条目本身是两层结构：逻辑条目保持不变，正文以不可变条目版本演进；内容哈希把引用与正文锚定在一起，读取时按需校验。课程 X1-1 讨论的冲突裁决与版本链，在这里是内置的存储契约。

### 2.5 数据关系小结

- Source 只做证据，进入不了注入面；
- Artifact 修订记录血缘，血缘来自实际传入的证据引用；
- 批准后的当前版本才能被检索与引用；
- PreparedContext 每次请求重新生成，不落库。

把这条关系链记牢，后面的接口与存储讨论就都有落点。

## 3. 修订、证据引用与生命周期管理

本节的设计围绕三个问题展开：内容变化后如何演进，引用如何保持可信，谁有权把变化发布为资产。

### 3.1 不可变修订

每次有效变更在同一 Artifact 下产生新的 Revision。修改记忆、提交交接、批准经验都会推进 Revision，旧 Revision 继续可读。

并发安全通过显式基线传递实现。客户端带着它认为的当前 Revision 写入，系统校验不匹配就拒绝：

| 场景 | 行为 |
| --- | --- |
| 无基线写入 | 按当前头追加，返回新 Revision |
| 显式基线等于当前头 | 正常提交 |
| 显式基线落后于当前头 | 返回 409 revision_conflict，不自动覆盖 |

实测中，把过期的 `expected_revision` 提交给已经前移的 Artifact，会得到 `revision_conflict` 错误。冲突可见、可重试，旧内容不会被静默覆盖。

### 3.2 精确引用与证据

引用落在三个粒度上：

| 引用对象 | 粒度 | 示例 |
| --- | --- | --- |
| Artifact Revision | 资产与修订号 | `experience/X@1` |
| Source 观察 | 来源与观察序号 | `content/session-7` |
| Memory 条目版本 | 条目与正文版本 | entry_id 与 entry_version_id 的组合 |

检索结果里的命中会带回完整引用，上下文装配把引用原样交给模型侧。引用证明内容可定位，内容是否仍然正确由调用方按版本与来源状态判断，两层职责分开。

### 3.3 直接写入与候选审核

不同内容族采用不同的治理路径，策略固定在内容族上：

| 内容族 | 治理路径 | 原因 |
| --- | --- | --- |
| Memory | 直接写入 Revision | 高频、低风险、需要即时可用 |
| Experience / Skill | 先生成候选，人工审核后发布 | 影响面大、需要人确认 |

候选不是 Artifact，不进入检索，也没有 Artifact 标识。审核动作本身是终态操作：批准在同一事务里写入新 Revision 并返回结果引用，拒绝只记录原因。给候选与目标分别携带版本号，防止审核过程中提案或目标被并发修改。

生成与确认分离是一条值得带走的经验：模型负责生成候选，人负责确认，确认结果成为唯一发布路径。

### 3.4 Handoff 与工作连续性闭环

Handoff 用来把进行中的工作交给下一个会话或 Agent：目标是什么、做到哪了、下一步做什么。它默认是临时说明，不是长期记忆。只有明确要求留下时，才会写成一条可引用的历史。

整条闭环可以看成四步：

```text
记下委托（Work Contract）
  → 交出当前进度（Handoff）
  → 接手方核对并回执（Acknowledgement）
  → 结束时记下真实结果（Task Outcome）
```

Handoff 本身先打草稿、再定稿。定稿后的内容可以直接交给下一个会话；需要留下里程碑时，再单独提交。接手可以基于这份定稿，也可以基于已经提交的历史。

设计上要记住这几条：

- 草稿可以先看、先改，提交之后才变成可引用的历史；
- 交过来的内容只当参考，还是要以当前指令和现场状态为准；
- 接手方要明确说接了、还要澄清，还是不接；说「接了」也不等于获得执行权限，权限仍在宿主这边；
- 任务结果只记实际发生了什么：做成了、做了一半、卡住、失败、取消，或者确实判断不了。

### 3.5 失败方向的边界

失败分两种，处理方式不一样：

- 自动帮忙的步骤，比如自动召回、采集提示词，失败了不要卡住宿主任务，但要把原因留下，方便排查；
- 你明确要求写入、提交、审核、导出时，失败必须如实报错，不能假装成功。

前一种是为了不拖垮正在进行的对话，后一种是为了不把脏数据写进去。

## 4. PreparedContext：一次装配的交付边界

I6 把上下文准备说成「这次请求装进模型的那一份材料」。PowerContext 把它做成一个显式接口：先找出相关内容，再按预算裁成一份有界视图。

### 4.1 先检索，再装配

| 步骤 | 输入 | 输出 |
| --- | --- | --- |
| 检索 | 查询和 Scope | 带引用的相关候选 |
| 装配 | 候选和字节预算 | 一份有界的 PreparedContext |

检索负责谁更相关，装配负责放得下多少、能不能信。两步分开，后面可以各自改。

### 4.2 这份材料默认不可信

装配结果会包进固定格式，并标明是不可信历史：

```text
BEGIN_POWERCONTEXT_PREPARED_CONTEXT_V1
  trust = untrusted_history
  条目内容 + 精确引用
END_POWERCONTEXT_PREPARED_CONTEXT_V1
```

意思是三件：

- 里面的内容只当数据看，不能当成系统指令或工具授权；
- 每条可见内容都带着精确引用，可以回到原版本核对；
- 宿主注入时，历史材料排在当前指令后面。

### 4.3 预算与状态

装配按字节预算工作，默认 8000 字节，上限 32768，单条最多 2000，最多装 8 条。这里再补两个实现行为：

- 返回的 `content_bytes` 不能超过这次请求的预算，按 UTF-8 计算；
- 状态只有 `ready` 和 `empty`。`empty` 表示这次没装到内容，不是鉴权失败，也不是服务挂了。

## 5. 接入接口的设计边界

同一套能力有多个入口，语义保持一份。

![同一套领域语义，通过 Core SDK、HTTP、Client、MCP、CLI 与 Web UI 分层暴露](/images/industry/I7/I7-02-interface-layers.png)

### 5.1 各入口干什么

| 入口 | 形态 | 职责 |
| --- | --- | --- |
| Core SDK | 进程内 Python 对象 | 核心逻辑，不管配置和存储怎么选 |
| Server | FastAPI 服务 | 上面挂 HTTP、MCP 和网页 |
| Python Client | 异步客户端 | 给应用代码调 HTTP |
| HTTP API | OpenAPI 契约 | 完整能力，哪种语言都能接 |
| MCP | Streamable HTTP | 给运行中的 Agent 用的精选工具 |
| CLI | 命令行工具 | 配置、诊断、管服务、人工审核 |
| Web UI | 只读看板 | 看统计和交接报告 |

记住两条：核心逻辑保持干净，存储和调度可以换；进程内、HTTP 和 MCP 走同一套校验，只是露出来的多少不同。

### 5.2 OpenAPI 是契约源

HTTP 契约以 OpenAPI 为准，Python Client 也是从这份契约生成的。调试时可以直接看 `/openapi.json`，或打开文档页看每个接口。

### 5.3 MCP 不是全部能力

MCP 给运行中的 Agent 用：记记忆、检索、采集来源、交接和任务结果这些都能做。装配上下文、导出技能、生成经验这类事留在 HTTP 和 CLI，不做成 MCP 工具。原因很简单：MCP 跟着 Agent 跑，装配和人工管理发生在宿主这边。

### 5.4 出错时怎么看

所有接口用同一套错误格式：

```text
HTTP 状态码
  + {"error": {"code": ..., "message": ..., "details": ...}}
  + X-PowerContext-Request-ID 请求头
```

常见情况：401 没登录，404 找不到，409 版本或状态冲突，422 请求不合法，503 能力暂时不可用。每次请求都有一个请求 ID，顺着它能把日志串起来。

插件侧也约定了错误分类和单行 JSON 事件，用来区分认证失败、版本不匹配、服务不可用和响应格式错误。先把「出错时能看见什么」定清楚，再写插件，后面排查会省很多事。

## 6. 存储后端与检索契约

数据最后还是要落到存储上。上层接口保持同一套检索说法，具体用哪个库，换配置即可。

### 6.1 三个存储后端

| 后端 | 形态 | 检索能力 | 适用场景 |
| --- | --- | --- | --- |
| SQLite | 本地文件，默认 | FTS5 全文 + sqlite-vec 向量 | 个人与单机开发 |
| seekDB | 嵌入式向量数据库 | 向量与混合检索 | Linux / macOS 本地增强 |
| OceanBase | 分布式数据库 | FULLTEXT 与向量 HNSW | 团队共享与规模化部署 |

![三个存储后端共享同一份检索契约，能力差异通过能力探测暴露](/images/industry/I7/I7-03-storage-backends.png)

换后端不用改领域逻辑。课程 I2 讲过的向量、全文、混合检索，在这里就是各后端自己实现的索引能力。

### 6.2 检索和写入要一起成功

每个后端都要守同一份约定：

- 正文、当前版本指针和检索索引在同一个事务里提交或回滚；
- 指针和索引丢了可以重建，真数据只存一份；
- 检索只命中当前版本、而且还处于活跃状态的内容。

最容易看出来的，是启动时的表现：没配任何模型时，SQLite 仍然会建好全文索引，记忆写入和检索马上能用。

### 6.3 向量能力要显式打开

向量和混合检索要配置 Embedding 模型和维度，不是装上就能用：

| 情况 | 行为 |
| --- | --- |
| 未配置向量 | 只有全文和自动模式 |
| 配置了向量 | 才有向量和混合检索 |
| 明确要一种还不具备的能力 | 直接报错，不会悄悄降级 |

自动模式在混合检索不可用时会退回全文，但返回结果里会如实写它实际用了哪种。先问服务端支持什么，再决定怎么查。

### 6.4 检索怎么走，重排默认为关

一次检索大致是：

```text
召回（全文 / 向量 / 混合）
  → 融合与粗排
  → 可选重排（默认关闭）
  → 返回带引用的命中
```

重排要再调一次生成模型，所以默认关掉。打开之后，模型只负责排出先后，引用和身份仍由系统填写，模型不能自己编一个内容标识。

### 6.5 工程上怎么选

| 取舍问题 | 结论 |
| --- | --- |
| 要不要向量检索 | 先看查询是不是需要语义相近；不需要就不配 |
| 用什么后端 | 单机先 SQLite，规模化再评估分布式 |
| 显式还是自动模式 | 你点名要的能力没有，就该报错；自动模式降级要说清楚 |
| 开不开重排 | 默认关，只有质量确实受益时再开 |

和 I6 一样：能力按任务需要一级一级加，每一级先确认有收益。

## 7. 一个最小可运行实验

下面在本地最小模式里跑通一遍：SQLite 存储，不接模型，也不开鉴权。官方安装说明以 macOS / Linux 和 Python 3.11 以上为主；课程在 2026 年 9 月 7 日的 Windows 和 Python 3.12 上，用同一份 HTTP 契约跑通。

### 7.1 安装与启动

按官方快速入门安装 CLI 和 Server：

```bash
uv tool install "powercontext[cli,server] @ git+https://github.com/oceanbase/powercontext.git@master"
```

启动服务：

```bash
powercontext server run
```

默认监听 `127.0.0.1:8000`。用下面的命令确认服务健康：

```bash
powercontext ready
powercontext capabilities
```

最小模式下，`capabilities` 会列出四类内容族，以及 `auto`、`fts` 两种检索模式；模型相关能力是关着的。

### 7.2 最小回路

下面用标准库脚本做四件事：创建 Scope、写入一条记忆、检索、装配。响应比较长，脚本只打印要点：

```python
import json
import urllib.request

BASE = "http://127.0.0.1:8000"

def api(path, method="GET", payload=None):
    req = urllib.request.Request(BASE + path, method=method)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(payload).encode("utf-8")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))

# 1. 创建 Scope，拿回服务端给的 scope_id
scope = api("/v1/scopes", "POST", {
    "title": "I7 demo",
    "summary": "PowerContext 课程实验",
    "idempotency_key": "demo-scope-1",
})
sid = scope["scope_id"]
print("scope:", sid)

# 2. 显式写入一条记忆
remember = api("/v1/memory/remember", "POST", {
    "scope_id": sid,
    "kind": "constraint",
    "text": "回答存储后端取舍问题时必须给出适用条件。",
})
print("revision:", remember["memory"]["revision"])
print("entry_id:", remember["entry"]["citation"]["entry_id"])

# 3. 检索记忆
search = api("/v1/memory/search", "POST", {
    "scope_id": sid,
    "query": "存储后端 取舍 约束",
    "mode": "auto",
    "limit": 5,
})
print("mode:", search["mode"])
for hit in search["hits"]:
    print("hit:", hit["citation"]["memory_ref"]["revision"], hit["matched_by"])

# 4. 装配本次请求的上下文
prepared = api("/v1/context/prepare", "POST", {
    "scope_id": sid,
    "query": "存储后端取舍",
    "max_bytes": 1024,
})
print("status:", prepared["status"])
print("content_bytes:", prepared["content_bytes"])
```

打印出来的字段可以这样读：

| 打印项 | 含义 |
| --- | --- |
| `scope:` 开头的字符串 | 服务端给的 Scope 标识 |
| `revision: 1` | 第一条记忆写成了 Revision 1 |
| `entry_id:` 开头的字符串 | 这条记忆自己的逻辑 ID |
| `mode: fts` | 没配向量时，自动模式会落到全文检索 |
| `hit:` 行 | 命中了哪一版、从哪条通道找到的 |
| `status: ready` | 装配成功，里面有内容 |
| `content_bytes:` 数值 | 实际装进去的字节数，不会超过这次请求的 1024 |

### 7.3 冲突行为验证

先在刚才那个 Scope 里再写一条记忆，把当前 Revision 推到 2，然后带着过期的 `expected_revision: 1` 再写一次：

```python
api("/v1/memory/remember", "POST", {
    "scope_id": sid,
    "kind": "constraint",
    "text": "第二次写入，Revision 前移到 2。",
})

resp = api("/v1/memory/remember", "POST", {
    "scope_id": sid,
    "kind": "constraint",
    "text": "基于旧基线的写入。",
    "expected_revision": 1,
})
```

当前 Revision 已经是 2 时，第二步会得到 HTTP 409。标准库碰到非 2xx 会抛 `HTTPError`，响应体里的错误码是 `revision_conflict`。把 `expected_revision` 换成服务端刚返回的当前 Revision，就能正常提交。

### 7.4 清理

停掉服务进程，删掉实验数据目录即可。目录位置看 `POWERCONTEXT_HOME`；没设置时，用默认的用户数据目录。

## 8. 一套最小验收流程

接入或自研类似系统时，可以按这个顺序验：

1. 用最小模式启动，确认没模型也能写记忆、做全文检索；
2. 建一个专属 Scope，确认数据归在这里、和其他 Scope 隔开；
3. 写入一条记忆，换个会话还能检索到，并且引用字段是完整的；
4. 带着过期基线再写，确认会明确报版本冲突；
5. 装配一次上下文，确认字节预算生效，材料被标成不可信历史；
6. 提交一次交接，用新会话续上，并记下任务结果；
7. 打开向量配置，确认能力探测里出现了新模式；
8. 记下每次请求的耗时和注入字节，对照任务质量看有没有退步。

第 5 步和第 7 步最容易暴露实现和文档对不上，版本升级后建议重跑。

## 9. 常见误区

### 9.1 误区一：用会话标识当 Scope

会话一结束，数据空间就换了，长期记忆和交接都会落空。Scope 要绑在长期稳定的项目或工作流上。

### 9.2 误区二：装了 MCP 就拥有全部能力

MCP 只是给 Agent 用的精选工具。装配上下文、生成类操作还在 HTTP 和 CLI 这边。接入前先对照能力表，看这个入口够不够用。

### 9.3 误区三：向量检索一定优于全文检索

向量要配模型、还要维护索引；术语对得准的时候，全文往往更稳。怎么检索，看查询类型和数据规模。课程 D2 和 I2 的结论，在这里同样成立。

### 9.4 误区四：批准了就能执行

Experience 批准后可以检索和引用；Skill 批准后还要再导出一次，导出到哪里、谁有权执行，由宿主决定。批准只表示内容通过了审核。

### 9.5 误区五：没有模型就用不了

没模型时，记忆写入、全文检索和装配都能用。模型影响的是提炼、经验生成这类增强能力，属于可选项。

## 10. 与其他课程的关系

- P3《Agent 记忆系统设计》：记忆该怎么设计，信任边界在哪；
- P4《Skill 与 Agent 知识管理》：Skill 资产，以及按需加载；
- D2《AI 应用的数据层》：向量、全文和混合检索的基础；
- D4《Agent 开发与记忆系统》：记忆系统的最小实现对照；
- X1 系列《探究 AI Agent 记忆系统》：记忆生命周期和冲突处理；
- X2《多 Skill 给上下文工程带来的麻烦》：全量注入会出什么问题；
- I2《向量数据库与 RAG》：检索后端和索引能力；
- I6《上下文工程概述》：本节的分析框架；
- I8《案例场景和测评构建》：把这套系统接到测评链路上。

## 参考资料

- [PowerContext 开源仓库](https://github.com/oceanbase/powercontext)
- [PowerContext 官方文档](https://oceanbase.github.io/powercontext/)
- [PowerContext 记忆层设计 RFC](https://github.com/oceanbase/powercontext/blob/master/docs/zh/rfcs/0014_memory_layer_design.md)
- [PowerContext 端到端测评架构 RFC](https://github.com/oceanbase/powercontext/blob/master/docs/zh/rfcs/0081_end_to_end_evaluation_architecture.md)
