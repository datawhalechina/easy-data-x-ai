---
title: I7：PowerContext 的设计与实现
outline: deep
---

# I7：PowerContext 的设计与实现

> Easy Data x AI 课程 · 产业应用篇 · 第 7 节

::: tip 本节定位
本节以 PowerContext 为例，解释来源处理、精确引用、上下文装配、交接与经验审核的实现方式，并通过接口实验核对预算限制、交接提交和历史读取。I6 介绍上下文工程的接入与使用，本节重点理解这些行为背后的数据模型和职责边界。
:::

[《上下文工程概述》](./I6%20课程稿：上下文工程概述.md)通过保存、跨会话读取和修订一条决定，说明了上下文的数据职责与使用方法。本章沿着 PowerContext 的处理流程，进一步解释这些要求如何落实到实现中：来源经过什么处理才能成为可用内容，不同类型的内容如何进入请求，以及交接和经验审核为什么需要各自的状态。章末再通过接口实验核对预算、交接和历史读取的行为。

PowerContext 围绕持续推进的工作维护上下文，用稳定的 Scope 关联证据、记忆、交接与结果。人、Agent 或会话更换后，后续参与者仍能从这些记录继续工作。来源处理、请求装配和交接审核围绕这份工作上下文配合，各自决定什么内容可以保存、提供或复用。

阅读时沿用来源（Source）、产物（Artifact）、工作范围（Scope）和准备好的上下文（PreparedContext）等概念。记忆系统的基础实现可以参阅[《Agent 开发与记忆系统》](../dev/D4%20课程稿：Agent%20开发与记忆系统.md)。本文以 PowerContext [提交 `61ebcd85`][source-baseline] 为源码基线，链接均固定到该提交。

## 学习目标

学完本章，你将能够：

1. 沿着来源处理流程，区分显式写入、内容提取和候选审核。
2. 解释不同类型的上下文如何共享引用机制，又如何按各自规则参与请求。
3. 理解 PreparedContext 的候选选择、预算裁剪和文本渲染过程。
4. 说明临时交接、持久交接和审核后的经验分别在什么时候可用。
5. 对照接口响应检查预算限制、交接提交和条目停用，解释观察到的结果。

## 1. 来源如何形成可用的上下文

PowerContext 用 Source 保存材料或材料引用，用 Artifact 保存整理后的产物，由 Trigger 根据事件和状态决定处理动作。三者的关系可以记为 `Source → Artifact ← Trigger`：来源提供依据，触发规则控制产物何时生成、更新或使用。理解了这一区别，就能解释为什么采集成功后还可能查不到记忆。

### 1.1 写入路径取决于内容是否已经明确

PowerContext 的写入入口需要区分两类输入：调用方已经确认要保存的内容，以及还需要整理的原始材料。前者可以直接写入 Memory；后者先保存为 Source，再由配置好的处理流程提取记忆或整理主题。任务结果也可以作为来源，用于生成待审核的经验。

Source 可以保存材料快照，也可以记录外部适配器管理的材料引用。后续整理使用这些证据，不要求把来源系统中的全部数据迁入 PowerContext。

下面列出了几条主要路径。图中的处理步骤需要相应的配置，接收 Source 本身不会启动所有分支。

```text
Explicit entries ----------------------> Memory

Source --+--> Extract ------------------> Memory
         |
         +--> Topic processing ---------> Topic Memory

Task Outcome --> Candidate --approve--> Experience
```

图中的 Task Outcome 也是一种 Source。它记录实际执行结果，生成器可以据此提出经验，但只有经过审核的内容才成为正式 Experience。不同分支的终点不同，调用方需要知道返回的是来源记录、待审提案，还是已经可用的产物。

[`MemoryService.remember`][memory-service]体现了直接写入与提取的区别。直接写入接收条目内容，不需要生成模型；提取路径接收证据，再调用配置的生成流程。两条路径最终都要形成带引用的记忆变更，因此手工保存与自动提取的内容可以使用相同的读取方式。

### 1.2 主题处理保留材料之间的联系

独立条目适合保存可以单独引用的事实。多份材料共同描述一个主题时，Topic Memory 将它们整理为标题、摘要和详情。检索可以先找到主题，后续再读取详情，避免每次请求都重新拼接全部来源。

[`TopicMemoryProcessor.process`][topic-processing]按批读取新增来源，将其转换为生成输入，再准备主题变更。生成内容需要引用实际处理过的证据；更新已有主题时，也需要关联先前版本。这样，主题可以逐步扩充，接收者仍能找到某次修订所依据的材料。

处理进度与来源采集分别记录。材料已经接收、主题尚未更新，是允许出现的中间状态。调用方看到采集成功后，仍需检查后续处理是否完成，才能判断新内容是否已经进入可检索的主题。

触发规则负责根据事件和当前状态决定待执行动作，读取材料和生成内容由运行时完成。这个分工定义在 [`Trigger.activate`][trigger-protocol] 中，让同一份来源可以参与不同的整理流程。

## 2. 共用引用机制，分别决定如何使用

### 2.1 各类内容有不同的读取方式

PowerContext 按内容类型提供不同的读取入口。装配一次请求时，事实、主题、背景和经验各自提供不同粒度的信息：

| 类型 | 提供给请求的内容 | 选入方式 |
| --- | --- | --- |
| Memory | 可单独引用的事实、决定和约束 | 按查询检索有效条目 |
| Topic Memory | 一个主题的摘要及相关内容 | 搜索主题后精确读取，或通过装配设置选入 |
| Profile | Scope 的背景快照 | 在装配设置中显式选择正式快照 |
| Experience | 经审核的做法及其结果依据 | 召回审核后的当前版本 |

这里的区别直接影响接口设计。Profile 的选择由装配设置决定，加入的是背景快照；Topic Memory 则允许先发现主题，再读取具体内容。装配器需要接收这些不同形态的候选，并按本次请求的设置组合它们。

其他类型也有自己的使用入口。Handoff 通过交接流程读取，Skill 需要显式发布或导出给宿主，Prompt 则保存特定生成操作使用的提示词配置。它们共享产物模型，但不会全部混入普通记忆召回。各类型的完整定义见[核心概念文档][core-concepts]。

### 2.2 引用随内容一起流转

共同的产物模型解决的是内容身份问题。`ArtifactRef` 使用 `family`、`artifact_id` 和 `revision` 定位修订，再与 Scope 组合成完整地址。Memory 的引用粒度更细：`MemoryCitation` 还包含条目 ID 和正文版本 ID，能够指出一份 Memory 中的具体条目。

内容更新会形成新的修订，已有修订继续保留。条目停用后退出当前召回，过去的精确引用仍能读到当时的内容。

这些引用在检索、裁剪和交接之间继续传递。只把正文复制到下一步，会丢失内容所属的版本；让引用与正文一起流转，后续操作才有确定的核对对象。停用和版本选择等规则控制哪些内容参与召回，精确读取则保留核对历史的能力。

产物的 Lineage 记录生成时实际使用的来源和其他产物。引用回答读到了什么，Lineage 则帮助解释它依据什么形成。两者的结构都定义在 [Artifact 与引用模型][artifact-models]中，装配器直接保留这些身份信息。

## 3. PreparedContext 怎样装配一次请求

检索完成后，运行时把候选内容交给 `PreparedContextBuilder`。检索负责提供相关候选，装配器按请求中的类型选择和预算决定最终输出。全文与向量检索的取舍已在《上下文工程概述》中讨论，这里关注结果怎样进入上下文。

[`MemoryService.search`][memory-service]先过滤不符合准入条件的候选，再融合排序，并按配置进行可选重排，引用随结果保留。显式请求的检索能力不可用时会报错；自动模式可以选择可用的检索方式，并返回实际使用的模式。接入方因此能够区分检索没有命中与服务缺少相应能力。

下面以显式指定 `assembly` 的文本装配路径为例。`assembly` 控制选择哪些类型、按什么顺序放置、每类最多放多少；`max_bytes` 限制完整输出的大小。

```text
Recall hits + Profile snapshot
              |
assembly ---> Select
              |
max_bytes --> Fit
              |
            Render
              |
              v
       PreparedContext
```

### 3.1 按类型选择，并用引用去重

[`PreparedContextBuilder`][prepared-context]遍历 `assembly.sections`，分别取得 Memory、Experience、Topic Memory 和 Profile 的候选。每条候选同时携带内容和精确来源，去重时使用 Scope、修订以及条目版本等身份信息。

这使装配器能够识别同一内容的重复命中，而不必依靠正文相似度猜测。不同版本即使文字相近，也有不同的身份；是否允许该版本参与本次请求，由对应类型的读取规则决定。

各部分共享总预算，装配顺序因此会影响最终留下的内容。排在前面的部分可能先用掉大部分空间，后面的候选即使相关，也可能放不下。类型选择、顺序和数量上限都由请求明确表达，便于调用方根据任务调整。

### 3.2 裁剪时保留引用和可读内容

放入一条候选前，装配器会测量加入它之后的完整输出，包括正文、引用和格式说明。正文过长时，缩短的是展示内容，引用仍保持完整。

[`fit_context_text_item`][prepared-text]寻找预算内能够容纳的正文前缀，同时避免切断生成的转义序列。若剩余空间只够保留极短的片段，装配器会放弃这条候选，继续尝试后面的条目。因此，一个靠前的长条目放不下，并不意味着后面的短条目也必须丢弃。

运行时还分别统计正文被缩短和条目被省略的情况。这些内部记录有助于排查内容减少发生在哪一步，相应行为可对照[上下文装配测试][prepared-tests]阅读。

### 3.3 渲染形成可交付的文本

渲染器将选中的内容、精确引用和历史材料说明组织为文本，并明确标记为不可信历史内容。历史 Markdown 和控制字符经过处理，避免原始内容直接改变交付文本的结构。接收者仍需按当前指令和权限使用这些材料。

装配结果使用 `ready` 或 `empty` 表达本次是否存在可交付内容，并携带实际 UTF-8 字节数。运行时只返回这次请求的准备结果，不会把裁剪后的文本重新存为长期记忆。下一次请求可以重新选择类型、调整预算，再从持久内容生成新的视图。公开字段定义见[上下文数据模型][runtime-models]。

## 4. 交接与经验各自有完成条件

### 4.1 临时交接可以使用，持久交接需要提交

[`HandoffService`][handoff-service]把准备、定稿和提交拆成独立操作。`prepare` 根据目标和证据生成草稿，`finalize` 校验证据后返回 `PreparedHandoff`。接手者可以直接读取这份临时交接；需要保留里程碑时，再调用 `commit` 保存修订。

```text
Draft -> Finalize -> PreparedHandoff -> Continue
                         |
                       Commit
                         |
                         v
                  Handoff Revision -> Continue
```

两条路径都可以让工作继续，区别在于是否留下持久版本。`PreparedHandoff` 包含交接内容及定稿时的版本基线；提交时，系统会检查这个基线是否仍然有效，避免较早准备的交接覆盖后来更新的进度。

这也给人工核对留下了位置。草稿生成后，可以先检查目标、已验证进度和证据，再决定交给接手者，或保存为后续可引用的记录。一次生成调用完成，并不代表交接已经定稿或提交。

接手方通过 Acknowledgement 记录接受、需要澄清或拒绝交接。它表达接手者对当前工作的确认，相关结构见[工作连续性模型][work-models]。

### 4.2 任务结果经过审核才能成为经验

工作记录中的 Work Contract 保存目标和完成条件，Task Outcome 保存实际结果及检查情况。它们作为 Source 留下依据，经验生成可以引用这些记录。部分完成、失败或尚未验证的结果需要如实保留，否则后续生成器容易把未经证实的做法写成成功经验。

生成出的 Experience 先保存在 Candidate 中，拥有独立的提案版本和证据。审核针对这个确定版本进行；提案或准备替换的内容发生变化后，需要重新核对。批准后形成正式产物，被拒绝的提案保留审核记录，不参与经验召回。具体处理见 [`ReviewService.approve`][review-service]。

已批准的 Experience 还可以作为 Skill 生成的依据，将可复用的方法整理成操作说明和校验步骤。这会产生新的 Skill 候选，仍需独立审核，不会因引用了已批准的经验就自动获得批准。实现见[候选生成服务][review-generation]。

Experience 的正式当前版本可以参与上下文召回，Skill 则需要显式发布或导出，供宿主发现和加载。内容审核、发布和宿主执行各自保留边界，避免把一次批准解释为自动安装或执行。

## 5. 宿主与持久上下文如何配合

PowerContext 通过 HTTP、Python Client 或 MCP 提供这些能力，也允许进程内组合。远程契约由 [OpenAPI][openapi] 定义，[MCP 工具集合][mcp-server]选择其中适合 Agent 调用的操作。不同入口共用 Scope、内容版本和引用，宿主适配器负责关联当前工作，并决定何时采集、检索和注入。

Scope 指定资料范围，服务端另行检查访问权限。更换宿主后可以继续读取同一组上下文，但不能仅凭知道 Scope ID 就获得访问或执行授权。

宿主拿到 PreparedContext 后，需要保留引用和历史材料标记，再将它放入模型请求。工作结束时，可以回写结果或准备交接，供后续处理使用。具体接入步骤和效果核对方法见[《上下文工程概述》](./I6%20课程稿：上下文工程概述.md)。

辅助召回失败时，宿主可以记录原因并继续原任务；显式保存、审核或提交失败时，则必须如实返回失败。前者避免上下文服务中断正在进行的工作，后者保证后续参与者不会把未完成的写入当成已有记录。正常的 `empty` 响应与这些错误也需要分别处理。

SQLite、seekDB 和 OceanBase 后端为这些过程提供持久化与检索能力。对于上层流程，需要保持的是内容版本、引用和有效状态的含义；后端适配细节可以从[持久化模块][persistence]继续阅读。

## 6. 实验：核对上下文接口的行为

下面沿用[《上下文工程概述》](./I6%20课程稿：上下文工程概述.md)中的 PowerContext 1.0.0 服务与 Codex 接入环境，不需要配置生成或向量模型。源码解读采用前面注明的提交，接口练习使用 1.0.0；这里涉及的装配、交接和 Memory 读取操作在该版本中已经提供。尚未接入时，先完成前一章的服务启动、Scope 创建和插件检查。

继续使用原练习 Scope，但新建一条专用 Memory，避免后面的停用操作影响任务对照。请 Agent 显示当前 Scope ID，与终端中的 `POWERCONTEXT_CODEX_SCOPE_ID` 核对，然后发送：

> 请在当前 Scope 显式保存一条 Memory，kind 使用 fact，正文为 `Context lab entry remains available across sessions.`。保存后搜索 `Context lab entry`，展示返回的正文和完整 citation。本次不创建其他记忆。

保存完整 citation，后面的交接与历史读取会用到。若这个 Scope 已有同名测试条目，请先核对并选定一条，避免重复写入影响搜索结果。

### 6.1 对照预算，检查装配结果

前面的 `PreparedContextBuilder` 负责在预算内组织文本。现在通过 HTTP 请求观察它的输出：退出 Codex，回到保留了 Scope 环境变量的终端，执行下面的命令。`assembly` 只选择 Memory，最多取三条，便于排除其他产物类型的影响。

```bash
curl --fail --silent --show-error \
  --header 'Content-Type: application/json' \
  --data "{\"scope_id\":\"$POWERCONTEXT_CODEX_SCOPE_ID\",\"query\":\"Context lab entry\",\"max_bytes\":8000,\"assembly\":{\"sections\":[{\"family\":\"memory\",\"limit\":3}]}}" \
  http://127.0.0.1:8000/v1/context/prepare
```

PowerContext 1.0.0 的 `max_bytes` 范围为 512 到 32768，默认是 8000。先记录响应，再把命令中的预算改为 512，比较以下字段：

| 字段 | 要核对的内容 |
| --- | --- |
| `schema` | 是否为 `powercontext.prepared-context.v1` |
| `status` | 有可交付内容时为 `ready`，无可输出内容时为 `empty` |
| `content_bytes` | 是否等于正文实际 UTF-8 字节数，且不超过请求预算 |
| `content` | 是否保留历史材料标记和精确引用，正文是否缩短或省略 |

预算覆盖的是完整输出，引用和格式说明也占空间。短记忆在两个预算内都能装下时，结果可能相同；若 512 字节连必要结构都容纳不了，响应会是 `empty`，正文为 `null`，字节数为 0。先确认 8000 字节下能搜到测试条目，再解释缩小预算后的变化。

保持内容和配置不变，以相同查询、`assembly` 和预算重复请求，对照 `status`、`content` 和 `content_bytes`。若结果变化，先检查候选版本与排序；只固定查询文本，还不足以确定装配输入相同。

要进一步观察单条裁剪，可以增加一条包含相同关键词的长测试记忆，保留两条 citation，再调整预算。某条内容放不下时，后面的短条目仍可能入选。这个行为可以对照[装配测试][prepared-tests]中的 `test_text_budget_keeps_later_short_entries_and_reports_candidate_rank` 阅读：测试固定候选及顺序，专门检查预算选择，避免把检索变化误认为装配变化。

这些响应只说明服务准备了什么。命令将结果显示在终端，并没有把它送入模型请求。注入、使用和任务收益仍按《上下文工程概述》中的证据分别判断。

### 6.2 先读取临时交接，再提交保存

重新启动 Codex，确认仍绑定原 Scope。读取测试 Memory 后，请 Agent 根据本次练习的实际进度准备交接：

> 请为本次上下文接口检查准备交接，列出已经验证的结果、尚未检查的项目和下一步，关联测试 Memory 的 citation。使用 handoff_current_work 准备后展示返回结果，暂不调用 commit_handoff。尚未执行的检查请保留为待办。

核对目标、进度和证据后，让 Agent 取出返回结果中的 `handoff` 对象，完整传给 `continue_handoff` 的 `prepared` 字段，并将 `selection` 设为 `prepared`。这一步应能读取定稿后的内容，但此时还没有保存新的 Handoff 修订。可以结合工具调用记录，检查这次读取没有发生提交。

确认内容准确后，再明确要求调用 `commit_handoff`，保存返回的完整 `reference`。在新会话中，将该引用传给 `continue_handoff` 的 `revision` 字段，`selection` 设为 `exact`，核对读到的目标、已验证进度和待办是否一致。使用具体修订，可以避免把之后更新的交接误认为本次结果。

实验中的两个读取入口，对应前面的临时对象和持久版本。`continue_handoff` 返回内容，只能确认接手者读到了交接；需要记录接手意愿时，还应通过 `acknowledge_handoff` 单独表达接受、待澄清或拒绝。

### 6.3 停用条目，再读取原引用

完成预算和交接检查后，再停用本章的测试 Memory。先读取当前条目，保留完整 citation，然后要求 Agent 使用 `retire_memory_entry` 停用它，并说明这是实验结束后的清理。这里只停用指定测试条目。

分别核对当前搜索、当前状态与旧引用：

| 读取方式 | 预期结果 |
| --- | --- |
| 用原关键词调用 `search_memory` | 不再返回被停用的条目 |
| 用 `list_memory_entries` 并设置 `include_inactive: true` | 该条目的当前状态为 `inactive` |
| 用停用前保存的 citation 调用 `get_memory_entry` | 仍能读取当时的正文和状态 |

旧引用读取的是当时的快照，其中仍可能显示 `active`。这与当前条目已经停用并不矛盾：准入规则控制当前召回，精确引用保留历史核对能力。停用也不会删除持久交接中保存的旧证据引用。

如果做过长文本扩展实验，也请逐条核对后停用新增的测试记忆。保留预算响应、临时交接对象、提交后的引用，以及停用前后的读取结果，就能把本章介绍的边界与实际返回值对应起来。

### 6.4 可选：核对矛盾条目的处理

另建独立 Scope，用同一关键词保存两条互不兼容的约束，并注明它们分别来自尚未定稿的提案。要求 Agent 搜索并列出双方的完整 citation，说明分歧以及需要你确认的事项。核对两条记录都已返回，避免把漏检误认为冲突已经解决。

由你确认最终采用哪条约束，再要求 Agent 修订相应记录、停用另一条，并保留决定依据。重新搜索应只返回仍然有效的结论；用两个旧 citation 则仍能核对提案原文。若 Agent 只按写入时间选择较新的记录，需要纠正选择依据。

这个练习验证的是显式核对、修订和停用。保存两条 Memory 不会自动触发冲突裁决，也不会把它们转入 Experience 或 Skill 的候选审核流程。

[source-baseline]: https://github.com/oceanbase/powercontext/tree/61ebcd85a6f8ad51eb72ac64f5e4eeac6f7e18e9
[core-concepts]: https://github.com/oceanbase/powercontext/blob/61ebcd85a6f8ad51eb72ac64f5e4eeac6f7e18e9/docs/zh/docs/get-started/core-concepts.md
[artifact-models]: https://github.com/oceanbase/powercontext/blob/61ebcd85a6f8ad51eb72ac64f5e4eeac6f7e18e9/src/powercontext/artifacts/models.py
[trigger-protocol]: https://github.com/oceanbase/powercontext/blob/61ebcd85a6f8ad51eb72ac64f5e4eeac6f7e18e9/src/powercontext/triggers/protocols.py
[topic-processing]: https://github.com/oceanbase/powercontext/blob/61ebcd85a6f8ad51eb72ac64f5e4eeac6f7e18e9/src/powercontext/builtin/runtime/topic_memory_processing.py
[memory-service]: https://github.com/oceanbase/powercontext/blob/61ebcd85a6f8ad51eb72ac64f5e4eeac6f7e18e9/src/powercontext/builtin/artifacts/memory/service.py
[runtime-models]: https://github.com/oceanbase/powercontext/blob/61ebcd85a6f8ad51eb72ac64f5e4eeac6f7e18e9/src/powercontext/builtin/runtime/models.py
[prepared-context]: https://github.com/oceanbase/powercontext/blob/61ebcd85a6f8ad51eb72ac64f5e4eeac6f7e18e9/src/powercontext/builtin/runtime/prepared_context.py
[prepared-text]: https://github.com/oceanbase/powercontext/blob/61ebcd85a6f8ad51eb72ac64f5e4eeac6f7e18e9/src/powercontext/builtin/runtime/prepared_text.py
[prepared-tests]: https://github.com/oceanbase/powercontext/blob/61ebcd85a6f8ad51eb72ac64f5e4eeac6f7e18e9/tests/builtin/runtime/test_prepared_context.py
[handoff-service]: https://github.com/oceanbase/powercontext/blob/61ebcd85a6f8ad51eb72ac64f5e4eeac6f7e18e9/src/powercontext/builtin/artifacts/handoff/service.py
[work-models]: https://github.com/oceanbase/powercontext/blob/61ebcd85a6f8ad51eb72ac64f5e4eeac6f7e18e9/src/powercontext/builtin/work/models.py
[review-service]: https://github.com/oceanbase/powercontext/blob/61ebcd85a6f8ad51eb72ac64f5e4eeac6f7e18e9/src/powercontext/builtin/review/service.py
[review-generation]: https://github.com/oceanbase/powercontext/blob/61ebcd85a6f8ad51eb72ac64f5e4eeac6f7e18e9/src/powercontext/builtin/review/generation.py
[openapi]: https://github.com/oceanbase/powercontext/blob/61ebcd85a6f8ad51eb72ac64f5e4eeac6f7e18e9/openapi/powercontext.yaml
[mcp-server]: https://github.com/oceanbase/powercontext/blob/61ebcd85a6f8ad51eb72ac64f5e4eeac6f7e18e9/src/powercontext/server/mcp.py
[persistence]: https://github.com/oceanbase/powercontext/tree/61ebcd85a6f8ad51eb72ac64f5e4eeac6f7e18e9/src/powercontext/builtin/persistence
