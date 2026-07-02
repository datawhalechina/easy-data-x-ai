# F0：课前闲聊 —— OpenClaw 为什么越用越好用？

> OceanBase 社区在 3 月 23 日会上线一套在线课程《Easy Data x AI》，在第一节课程开始之前，我们想先和大家进行一次课前闲聊。
>

<!-- 这是一张图片，ocr 内容为： -->
![](https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/base_knowledge/F0/F0-01.png)

最近深度使用了 OpenClaw，基本上每天都要跟它交流几个小时，也慢慢摸索出了一些经验。

看到不少人说 OpenClaw 不好用，我想先聊聊 “不好用” 的原因，再深入拆解一个我认为被大多数人忽略的核心问题 —— OpenClaw 越用越好用的本质到底是什么?

**开门见山，先直接说结论：是数据。**

这不是调侃，是我读完它的源码之后得出的判断，下面展开说。

欢迎大家关注 OceanBase 社区公众号 “老纪的技术唠嗑局”，在这里，我们会持续为大家更新与 #AI 相关的有趣技术内容！

## 为什么很多人觉得 OpenClaw 不好用？
在聊 OpenClaw 的核心机制之前，先排除几个常见的“用法问题”。很多人说不好用，其实不是产品的问题，大概率都是使用姿势不对。

<!-- 这是一张图片，ocr 内容为： -->
![](https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/base_knowledge/F0/F0-02.png)

### 错误的使用姿势一：把 Agent 当成通才
很多人的用法是：配一个 agent，什么都让它干。写代码找它，写文案找它，做数据分析还找它。

仔细想想，现实世界里是不是每个公司都分岗位？每个专家都专精一个或几个领域？AI agent 也是一样的。

OpenClaw 支持多 Agent 架构，你可以配置多个 agent，每个负责一个领域。而且从代码层面来看，这不只是"分工"那么简单——每个 agent 有**独立的 workspace 目录、独立的 memory 数据库、独立的 session 历史**。

也就是说，一个专门做代码审查的 agent，它积累的所有经验都是关于代码审查的，不会被你让它帮你写周报的那些对话污染掉。

这就像一个公司里，让每个员工专注一个领域，他的经验积累是垂直的、深度的，而不是水平的、稀薄的。

### 错误的使用姿势二：没有“培训”你的 Agent
**这是今天我想展开讲一讲的部分。**

很多人装好 OpenClaw，开箱就用，觉得效果一般，然后就下了结论说不好用。但你想想，你招一个新员工，他第一天来上班你就指望他跟干了三年的老员工一样好使？

Agent 需要培训。需要跟它多对话，告诉它你的偏好，让它了解你的工作场景，跟它一起踩坑然后把经验固化下来。

这个过程，用 OpenClaw 的术语叫 “形成 SOP”，用更技术的话说，叫**积累 workspace 数据文件**。

这就是 OpenClaw 越用越好用的核心机制，也是这个话题的重点。

### 错误的使用姿势三：模型没选对
这里的关键认知是：OpenClaw 本身不生产智能，它是一个让 AI 模型发挥得更好的框架。框架再好，底层模型不行，上限就在那里。

就像你给一个实习生写了一份非常详尽的操作手册，他可能还是做不好；但你给一个高级工程师同样的手册，他能做到远超你预期的水平。

## OpenClaw 的核心机制：一个自我进化的数据系统
<!-- 这是一张图片，ocr 内容为： -->
![](https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/base_knowledge/F0/F0-03.png)

我去读了 OpenClaw 的源码，把整个 “越用越好用” 的机制拆解清楚了。

说白了，它的架构可以用一句话概括：**每次对话前，把一堆 md 数据文件拼进 prompt；对话后，让 agent 把新学到的东西写回这些 md 数据文件。**

就这么简单。但这个简单的循环，构成了一个威力巨大的飞轮。

> 说明：
>
> 这里 markdown 估计自己也没想到，如今居然能被用来承载 AI 时代的记忆数据。
>
> 当然，只用 md 文件也会引入一些问题，比如：
>
> + 加载的 md 文件中涉及大量数据，会占据上下文长度（上下文过载），进而导致消耗 token；
> + 云上 agent 使用 md 存储数据，难以进行版本管理；
> + 等等等等。
>
> 
>
> 这里暂时不对此进行展开。
>

## 骨架：7 个核心数据
OpenClaw 给每个 agent 的 workspace 预设了 7 类核心数据：

<!-- 这是一张图片，ocr 内容为： -->
![](https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/base_knowledge/F0/F0-04.png)

### 1. SOUL.md — Agent 是谁
这个文件定义了 agent 的人格：语气、风格、边界、价值观。有意思的是，模板里写着一句话："This file is yours to evolve. As you learn who you are, update it."——这个文件是你自己的，随着你了解自己，去更新它。

也就是说，agent 的"人格"不是你一次写死的，是它在跟你互动的过程中，自己慢慢调整的。它发现你喜欢简洁直接的回答，就会把这个偏好写进自己的灵魂文件里。

<!-- 这是一张图片，ocr 内容为： -->
![](https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/base_knowledge/F0/F0-05.png)

### 2. USER.md — 用户是谁
这是 agent 对你的画像：你的名字、时区、工作习惯、技术偏好、沟通风格。每次对话中 agent 了解到关于你的新信息，就会更新这个文件。用得越久，这个画像越精准，agent 就越"懂你"。

<!-- 这是一张图片，ocr 内容为： -->
![](https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/base_knowledge/F0/F0-06.png)

### 3. AGENTS.md — 做事的规矩和踩过的坑
这是最关键的一个文件。它定义了 agent 的行为规范，更重要的是，**记录了所有踩过的坑**。

我在源码里看到它的模板有一条明确的指令："When you learn a lesson → update AGENTS.md"、"When you make a mistake → document it so future-you doesn't repeat it."

翻译成人话就是：你犯了一个错，把它记下来，这样以后的你就不会再犯。 这就是为什么 OpenClaw 越用越好——不是因为模型变聪明了，是因为 AGENTS.md 里的踩坑记录越来越多。每一条记录都是一次错误的代价换来的经验，被固化成了一行文字，从此永远生效。

<!-- 这是一张图片，ocr 内容为： -->
![](https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/base_knowledge/F0/F0-07.png)

### 4. TOOLS.md — 环境备忘
记录你的工作环境：SSH 主机名、摄像头设备名、文件路径习惯等。agent 踩坑后自己补充。

<!-- 这是一张图片，ocr 内容为： -->
![](https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/base_knowledge/F0/F0-08.png)

### 5. SKILL.md × N — 各领域的操作手册
每个 SKILL.md 定义了一个特定领域的操作规范。OpenClaw 内置了 52 个 skill，涵盖 GitHub issue 管理、邮件处理、健康检查、代码审查等。

更关键的是，你可以自己写 skill。比如你每周都要出一份特定格式的周报，你可以把格式要求、数据来源、输出模板写成一个 SKILL.md，放到 workspace 里。从此 agent 每次做周报都会按照这个规范来，不需要你每次重新描述。

Skill 的加载有优先级：内置的优先级最低，workspace 里用户自定义的优先级最高。也就是说你可以覆盖任何内置 skill 的行为。

<!-- 这是一张图片，ocr 内容为： -->
![](https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/base_knowledge/F0/F0-09.png)

### 6. memory/*.md — 日常记忆
Agent 每天会写一个日期命名的 md 文件，记录当天的对话要点、做了什么、学到什么。这些文件会被索引到 SQLite 数据库里，支持全文搜索和向量检索。

<!-- 这是一张图片，ocr 内容为： -->
![](https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/base_knowledge/F0/F0-10.png)

### 7. MEMORY.md — 提炼后的长期记忆
Agent 会定期把 daily memory 里的重要内容提炼到这个数据文件里。相当于从日记中整理出来的笔记精华。这个文件每次对话都会被加载进 prompt，所以 agent 的"长期记忆"就存在这里。

<!-- 这是一张图片，ocr 内容为： -->
![](https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/base_knowledge/F0/F0-11.png)

### 血肉：用户和 Agent 共同生长出来的自定义文件
以上 7 类数据是框架预设的骨架。但 workspace 本质就是一个普通文件夹，agent 有文件读写能力，它可以在里面创建任何它需要的文件和目录。

比如一个帮你管理项目的 agent，用久了它的 workspace 里可能长出这样的结构：

```plain
workspace/
├── SOUL.md
├── USER.md
├── AGENTS.md
├── TOOLS.md
├── MEMORY.md
├── memory/
│   ├── 2026-03-01.md
│   └── 2026-03-02.md
├── projects/
│   ├── project-alpha/
│   │   ├── progress.md
│   │   ├── decisions.md
│   │   └── risks.md
│   └── project-beta/
│       └── progress.md
├── templates/
│   ├── weekly-report.md
│   └── meeting-notes.md
└── contacts/
    └── team-preferences.md
```

这些额外的文件没有任何 schema 约束，完全是 agent 在使用过程中自己组织出来的。每个人的 agent 最终长出来的形态不一样，取决于你跟它聊了什么、做了什么、在哪些领域用它。

**这意味着你的 agent 是真正 “私人定制” 的——不是你在设置页面勾选了几个选项，是它通过几百次对话的数据，自己生长出了一套只适合你的知识数据体系。**

## 自我进化的闭环
上面说的都是静态的文件结构，真正有意思的是这些文件是怎么被维护和更新的。OpenClaw 设计了一个 agent 自我进化的闭环：

```plain
对话开始
  → 加载 workspace 所有核心 md 文件到 system prompt

  → agent 根据用户问题，先 memory_search 检索相关记忆
  
  → agent 执行任务

  → 任务中学到新东西 / 犯了错 / 发现了用户新偏好
  
  → agent 把数据写回相关文件（AGENTS.md / USER.md / memory/*.md / MEMORY.md）
  
  → 文件变更触发 Memory 索引重建（全文索引 + 向量索引）
  
  → 对话结束
```

```plain
下次对话开始

  → 加载更新后的 md 文件数据

  → 搜索到新索引的记忆

  → agent 行为更精准

  → 循环
```

注意这里面有两层循环：

+ **外层循环：数据读写。** 每次对话加载，对话中更新。这是"经验"层面的积累——agent 知道了哪些事该做、哪些事不该做、你喜欢什么、你的环境是什么样的。
+ **内层循环：向量索引检索。** 当 memory 文件越来越多，agent 不可能把所有内容都塞进 prompt（有 token 限制），所以 OpenClaw 分别用不同数据库的全文搜索能力和向量检索能力做了一个搜索引擎。agent 每次对话前被指令要求先搜索相关记忆再回答，这样即使积累了几百个 memory 文件，也能找到相关的信息。



**两层循环合在一起，就是一个完整的 “学习-记忆-检索-应用” 系统。而这个系统最宝贵的，就是使用过程中存储的数据。**

<!-- 这是一张图片，ocr 内容为： -->
![](https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/base_knowledge/F0/F0-12.png)

## 这意味着什么？
理解了 OpenClaw 的这套机制之后，可以获得几个推论：

1. 你的 Agent 的价值，都在数据里代码是公开的，模型是通用的。真正属于你的、不可替代的部分，是你 workspace 里那堆数据。那些数据里编码了你的偏好、你的工作流、你踩过的坑、你的项目上下文。换台电脑，把 workspace 文件夹拷过去，体验原封不动。删掉这些数据，一切从零开始。
2. 调教 Agent 就是写数据不需要学编程，不需要理解 prompt engineering 的技术细节。你只需要用自然语言把你的经验、偏好、规范写成 md 文件，放到 workspace 里就行了。OpenClaw 的代码会自动把它们在合适的时机注入到 prompt 中。甚至你不需要自己写——你跟 agent 对话的过程中，它自己就会把学到的东西写成 md。你要做的只是在它犯错时纠正它，它会自己记住。
3. Agent 之间的差距就是数据的差距两个人用同样版本的 OpenClaw、同样的模型，体验可能天差地别。差别就在于他们各自 workspace 里积累了什么。一个人用了三个月，workspace 里有几十个 skill、上百条踩坑记录、完善的用户画像；另一个人刚装上，workspace 只有默认模板。这跟现实世界的专家差距是一样的——两个人智商差不多（模型一样），差距在于积累的经验和知识（md 数据文件）。
4. 这可能是 AI Agent 产品的通用范式。**OpenClaw 做的这套 “数据即知识” 的架构，是很有普适性的。任何 AI agent 产品，如果想要做到 “越用越好用”，最终都要解决知识持久化和检索的问题。**



OpenClaw 中的数据，承载的就是一个不断进化的专家系统——它知道你是谁、你要什么、怎么做你的事、哪些坑不能踩。

## OpenClaw 实操建议
最后为大家提供几个实操层面的建议：

<!-- 这是一张图片，ocr 内容为： -->
![](https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/base_knowledge/F0/F0-13.png)

+ **主动引导 Agent 形成 SOP。** 不要等 agent 自己慢慢摸索，在你已经有成熟工作流的领域，直接告诉它"以后这类任务都按照这个流程来"，让它写成 SKILL.md。
+ **定期审查 workspace 文件。** Agent 自己写的东西不一定都对，定期看看 AGENTS.md、USER.md 里有没有过时或者不准确的数据，及时修正。
+ **善用多 Agent。** 不同领域配不同 agent，让每个 agent 的知识积累保持垂直和纯粹。一个专做代码的 agent 比一个什么都做的 agent 好用得多。
+ **备份你的 workspace。** 这是你最有价值的数字资产之一。建议用 Git 管理（OpenClaw 默认就是 Git 跟踪的），定期推到远程仓库。
+ **选对模型。** 一堆精心打磨的 md 文件喂给一个弱模型，效果也有限。



## 结语
OpenClaw 的源码有几十万行，但让它"越用越好用"的核心机制，说穿了就是**数据** 的读写循环。代码提供了管道——渠道接入、模型调用、工具执行、memory 索引。但流过管道的水，是那些不断积累的数据。

换句话说：**OpenClaw 的代码框架决定了它能做什么，数据决定了它做得多好。** 而后者，是你和你的 agent 一起，在一次次对话中攒出来的。

<!-- 这是一张图片，ocr 内容为： -->
![](https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/base_knowledge/F0/F0-14.png)


## What's more?
## <!-- 这是一张图片，ocr 内容为： -->
![](https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/base_knowledge/F0/F0-15.png)
> 在 OpenClaw 的运行机制背后，数据是关键中的关键。
>
> 我们即将上线的社区课程，会从 “数据” 这个视角为大家进一步展开。
>

### OceanBase 社区课程《Easy Data x AI》上线预告
<!-- 这是一张图片，ocr 内容为： -->
![](https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/base_knowledge/F0/F0-16.png)

### 为什么要为大家带来这套课程？
最近和身边的同事和朋友聊天，几乎所有人都在讨论模型——哪个模型更强、哪个模型更便宜、哪个模型多模态能力更好。

但我们从和用户的沟通中发现，真实业务场景中模型的回答不准确，绝大多数场景都不是模型不行，而是它根本就没拿到正确的数据。

AI 助手不够个性化，不是模型不懂你，而是它根本没有关于你的数据。

Agent 做不好复杂任务，不是推理能力不足，而是它调用的知识和技能的数据基础有缺陷……

现在 AI 爱好者认知的空白主要在于：**大家很多没有看到 AI 能力的另一半——数据**。

大多数人只盯着前者，我们这门课程会结合后者（Data），**讲清 Data 在 GenAI/Agent 中扮演的角色**——给大家呈现一个以数据为视角的完整认知框架。

我们这套 Easy Data x AI 的课程，希望能为大家建立一个 AI 时代的认知基础：**AI 产品的能力上限 = 数据质量 ********* 模型能力**。

<!-- 这是一张图片，ocr 内容为： -->
![](https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/base_knowledge/F0/F0-17.png)

### 为什么叫 Easy？
我们这是一门面向普罗大众的科普课程，不是传统的工程实训。

课程名叫“Easy Data x AI”，“Easy”是对学习者的承诺——轻量、清晰、有即时收获；“Data x AI”是课程的视角——从数据的角度解释 AI 应用的效果差异。

> **“Easy”的准确含义**：Easy 是认知门槛低，不是内容浅薄。
>
> 课程会引用 CoALA 论文框架、ReAct 模式等业界前沿概念，但每个概念都用日常类比和直觉案例讲透，不需要学习者预先具备学术背景。
>

### 这门课程适合谁？
> 双轨并行，论道与习术
>

为了满足不同角色的学习需求，我们将课程精心设计为两条路径：“道篇”与“术篇”。

#### 道篇
> 悟其道（零基础 AI 爱好者和产品决策者的“心法篇”）
>

“道篇” ：在这里，我们不谈代码，只论道 —— 建立判断力，理解基础原理，学习做出正确的判断和选择。

<!-- 这是一张图片，ocr 内容为： -->
![](https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/base_knowledge/F0/F0-18.png)

学习“道篇”的同学平时不需要写代码，但需要有足够的认知深度来进行一些判断和决策。

这条路径适合希望了解 AI 技术的爱好者，以及需要能够与 AI 技术团队对话，理解 Agent、RAG、Memory、Skill、MCP 这些概念在产品设计中的含义，能够评估一个 AI 功能的可行性，知道数据层的选择如何影响产品体验的产品决策者。

#### 术篇
> 用其术（开发者的“功法篇”）
>

“术篇” ：在这里，我们以可运行的代码和可观察的结果为核心，让你在动手实践中建立工程直觉。

<!-- 这是一张图片，ocr 内容为： -->
![](https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/base_knowledge/F0/F0-19.png)

不用担心，我们会把代码体验控制在“五分钟跑通”的量级。深度工程细节一律放入“延伸阅读”，不让主线超载。

这条路径适合已经能够调用 LLM API，但对如何构建完整 AI 应用（知识库、记忆、Agent）缺乏系统认知，希望可以立即上手并看到效果的工具和清晰的架构参考，而不是理论框架的开发者。

### 课程整体架构
```plain
公共基础篇
├── F1：大模型的本质与边界
└── F2：AI Agent 的完整图景
    ├── 道篇（P1-P5）
    │   ├── P1：找准 Agent 的用武之地 —— AI Agent 场景识别
    │   ├── P2：让 Agent 会查资料 —— RAG 产品设计
    │   ├── P3：让 Agent 真正记住你 —— 记忆系统设计
    │   ├── P4：把经验变可复用 —— Skill 与知识管理
    │   └── P5：用数据验证价值 —— 案例与度量
    └── 术篇（D1-D5）
        ├── D1：打通 Agent 与数据 —— 大模型 API 入门
        ├── D2：一个系统搞定 —— 统一 AI Native  数据层实战
        ├── D3：实践出真知 —— Agentic RAG 实战
        ├── D4：记哪些、忘哪些？—— Agent 记忆系统开发
        └── D5：课程总结
```

课程更新时间为：2026 / 3 / 23 ~ 2026 / 5 / 20。

一共 12 节课，公共基础篇 2 节 + 道篇 5 节 + 术篇 5 节。

道篇和术篇，每周会分别更新一期。

| 篇章 | 课程编号 | 上线时间 | 课程标题 |
| --- | --- | --- | --- |
| 公共基础篇 | F1 | 3 / 23 | 大模型的本质与边界 |
| | F2 | 3 / 30 | AI Agent 的完整图景 |
| 道篇 | P1 | 4 / 8 | 找准 Agent 的用武之地 —— AI Agent 场景识别 |
| | P2 | 4 / 15 | 让 Agent 会查资料 —— RAG 产品设计 |
| | P3 | 4 / 22 | 让 Agent 真正记住你 —— 记忆系统设计 |
| | P4 | 4 / 29 | 把经验变可复用 —— Skill 与知识管理 |
| | P5 | 5 / 11 | 用数据验证价值 —— 案例与度量 |
| 术篇 | D1 | 4 / 13 | 打通 Agent 与数据 —— 大模型 API 入门 |
| | D2 | 4 / 20 | 一个系统搞定 —— 统一 AI Native 数据层实战 |
| | D3 | 4 / 27 | 实践出真知 —— Agentic RAG 实战 |
| | D4 | 5 / 6 | 记哪些、忘哪些？—— Agent 记忆系统开发 |
| | D5 | 5 / 13 | 课程总结 |
| 结营仪式 | | 5 / 20 | 结营仪式 |


### 洞察先行
我们相信，当你看懂了数据，才是真正看懂了 AI 的未来。《Easy Data x AI》的核心哲学是“洞察先行”，每一节课程都力求传递一个核心洞察。我们希望这些凝练的观点，能成为您认知工具箱里的一部分。

无论你是零基础的 AI 爱好者，还是需要建立 AI 判断力的产品决策者，还是渴望动手实践的工程师，我们都诚挚地邀请你加入《Easy Data x AI》第一季课程。

在这里，你将收获的不仅是知识与技能，更会获得一个看待 AI 产品的全新视角。

最后，欢迎各位老师在 https://github.com/datawhalechina/easy-data-x-ai 参与课程共建。

也欢迎各位老师加入 Data x AI 交流群~

<div align="center">
  <img src="https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/base_knowledge/F0/F0-20.png" width="200" />
</div>
