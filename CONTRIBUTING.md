# 贡献指南

感谢你对《Easy Data x AI》课程的关注！🙏

这是一门面向所有 AI 爱好者的「Data 与 AI」入门教程，目前处于 **Alpha 内测阶段**，正在邀请社区一起把课程打磨完善。无论是修正一个错别字、补充一段实验、还是认领一节扩展课程，每一份贡献都很有价值。

> 本课程由 [Datawhale](https://github.com/datawhalechina) 与 [OceanBase 社区](https://open.oceanbase.com/) 联合共建。

---

## 一、欢迎的贡献类型

| 类型 | 说明 | 是否需先开 Issue |
| --- | --- | --- |
| **错别字 / 标点修正** | 直接提 PR | 否 |
| **表述改善** | 措辞不清、语句不通、逻辑跳跃 | 否 |
| **排版修复** | 代码块格式、列表缩进、图片说明 | 否 |
| **事实性勘误** | 技术描述有误（请附参考链接） | 否 |
| **完善已有章节** | 认领「共建任务列表」中的任务（见第四节） | 建议（认领即可） |
| **新增扩展章节** | 在 `docs/extra/` 下贡献扩展篇（X1–X5） | **是**（先开 Issue 对齐方向） |
| **工程 / 基建改进** | CI、依赖、示例代码 bug（见第四节列表 C） | 否 |
| **问题反馈 / 讨论** | 知识点不清楚、想提建议 | 通过 Issue |

---

## 二、快速上手

### 1. Fork 并克隆仓库

```bash
git clone https://github.com/<your-username>/easy-data-x-ai.git
cd easy-data-x-ai
```

### 2. 本地预览课程文档

课程站点基于 **VitePress** 构建：

```bash
npm install
npm run docs:dev
```

开发服务器启动后，按提示访问本地地址（默认 `http://localhost:5173`），修改 Markdown 会自动热重载。

### 3. 找到要修改的文件

课程正文都在 `docs/` 目录下，按篇章组织：

```
docs/
├── base_knowledge/   # 公共基础篇 F0–F2
├── pm/               # 道篇 P1–P5（产品 / 心法）
├── dev/              # 术篇 D1–D5（开发 / 功法）
└── extra/            # 扩展篇 X1–X5（新增章节放这里）
```

配套示例代码在 `code/` 目录，按章节分文件夹（`code/D1/`、`code/D2/` …）。

### 4. 提交 PR

```bash
git checkout -b fix/typo-p3
git add docs/pm/"P3 课程稿：Agent 记忆系统设计.md"
git commit -m "fix: 修正 P3 章节若干错别字"
git push origin fix/typo-p3
```

PR 标题建议遵循如下格式：

```
fix:  修正 <章节> <简要说明>      # 错别字、勘误
docs: 完善 <章节> <简要说明>      # 内容补充
feat: 新增扩展篇 <X编号> <标题>   # Extra-Chapter
chore: <工程/基建说明>            # CI、依赖、脚本
```

> ✅ **认领任务的同学**：请在 PR 描述里注明认领的任务编号（如「认领 #3」），方便归档统计。

---

## 三、Markdown 写作规范

- 中文与英文、数字之间加空格：`LangChain 是一个框架` ✓，`LangChain是一个框架` ✗
- 代码、命令、变量名用反引号包裹：`` `HYBRID_SEARCH()` ``
- 专有名词保持原文大小写：`OceanBase`、`seekdb`、`PowerMem`、`LangChain`、`RAGAS`
- 图片放在 `docs/public/images/` 下，正文用相对路径引用
- 涉及可运行代码的章节，请把示例同步放到 `code/` 对应目录，并保证能跑通

---

## 四、共建任务列表（认领制）

> 我们会根据下面的列表陆续开成一个个 Issue，你可以在感兴趣的 Issue 下留言认领，完成后提 PR 即可。
> 课程中涉及 LangChain 相关内容，也欢迎 LangChain 社区的同学一起参与。
> **完成一条任务即可提交一个 PR。**

### 难度说明

| 级别 | 适合人群 | 典型任务 |
| --- | --- | --- |
| **L1** | 第一次参与共建，有写作能力即可 | 补充文档说明、衔接段落、设计规范 |
| **L2** | 能基于课程内容做实验分析 | 对比实验、选型指南、成本分析 |
| **L3** | 有工程实现能力，能写可运行代码 | 完整代码实现、benchmark 复现、MCP 实战 |

### 列表 A：完善已有章节（P3–P5 / D2–D5）

| # | 章节 | 待完善的点 | 共建方向 | 难度 |
| --- | --- | --- | --- | --- |
| 1 | **P3** | 记忆时效性管理只提了难点，没有给解法 | 补充「记忆衰减策略」：结合艾宾浩斯曲线，给出遗忘分数计算 + 主动淘汰的具体方案 | L2 |
| 2 | **P3** | 多 Agent 共享记忆的边界问题未展开 | 补充「多 Agent 记忆隔离与共享」：何时隔离、何时共享、如何设计命名空间 | L2 |
| 3 | **P3** | 记忆冲突处理（新旧信息矛盾）完全缺失 | 补充「记忆冲突解决策略」：时间戳优先 / 置信度加权 / 人工介入三种模式对比 | L2 |
| 4 | **P4** | Skill 全量注入上下文导致爆炸，课程没有给解法 | 补充「通过 seekdb 结构化管理 Skill」：把 Skill 存入数据库，按需语义检索加载，对比全量注入 vs 按需加载的 Token 占用 | L3 |
| 5 | **P4** | Skill 标准化的具体原则没有展开 | 补充「Skill 设计规范」：命名、描述、参数、示例的标准格式，参考 MCP Tool 规范 | L1 |
| 6 | **P4 → D5** | P4 讲了 Skill 分割问题，但没有为 D5 的 MCP 做铺垫，两篇脱节 | 在 P4 结尾补「从 Skill 到 MCP：为什么需要标准化协议」，作为 D5 的引入 | L1 |
| 7 | **P5** | 三层度量框架讲了指标，但没有说怎么落地监测 | 补充「度量框架实施指南」：用 LangSmith / Prometheus 搭一套最小可用监控 dashboard | L3 |
| 8 | **P5** | 缺少成本–收益分析 | 补充「AI Agent ROI 计算模型」：数据层 / 模型层 / 业务层的投入产出估算框架 | L2 |
| 9 | **D2** | 向量化模型选型只推荐了 bge-m3，没有讲怎么选 | 补充「Embedding 模型选型指南」：中英文、多模态、成本、延迟四个维度横评 | L2 |
| 10 | **D2** | Chunking 策略只讲了基础分块，高级技巧缺失 | 补充「高级 Chunking 策略」：语义分块、动态 overlap、父子 chunk 三种策略对比实验 | L3 |
| 11 | **D3** | 对比实验样本量太小，无统计显著性 | 扩充评测数据集，补充更多场景（多跳问题、时效性查询、模糊表达），重跑 RAGAS 对比 | L3 |
| 12 | **D3** | P2 梳理的工程痛点在 D3 没有逐一给出解法 | 按 P2 痛点列表逐一补充对应代码实现（查询改写 / 自适应检索 / 答案验证等） | L3 |
| 13 | **D3** | 缺检索延迟和成本数据 | 补充「混合检索 vs 纯向量」的延迟 / 成本 / 精度三角对比实验 | L2 |
| 14 | **D4** | 记忆存储成本没有讨论 | 补充「长期记忆的存储成本控制」：压缩策略、冷热分层、定期清理的工程实践 | L2 |
| 15 | **D4** | 多用户记忆隔离方案缺失 | 补充「多用户 / 多租户记忆隔离」：user_id 命名空间 + 权限校验的实现示例 | L3 |
| 16 | **D5** | MCP 标准化几乎完全缺失（标题承诺但正文没展开） | 补充「MCP 实战」：从零实现一个 MCP Server，把 P4 设计的 Skill 发布成 MCP Tool，跑通 Claude / Cursor 调用 | L3 |
| 17 | **D5** | 跨平台 Skill 互操作没有示例 | 补充「同一个 Skill 在 Claude Code / Cursor / Copilot 中的调用差异」对比 | L2 |

### 列表 B：扩展篇共建（Extra-Chapter X1–X5）

> 在 `docs/extra/` 目录下独立创建、维护新的课程章节。每节都有一个「共建入口」与列表 A 的任务相呼应，形成「学 → 练 → 共建」的闭环。
>
> 扩展篇方向较多，**认领前请先开 Issue 对齐内容大纲**。

| # | 扩展课程标题 | 热点趋势 | 共建入口（对应列表 A） |
| --- | --- | --- | --- |
| **X1** | 探究 AI Agent 记忆系统：从遗忘曲线到永久记忆 | AI 记忆 | 多 Agent 记忆冲突解决（→ #1/#2/#3） |
| **X2** | 多 Skill 给上下文工程带来的麻烦：如何应对 Agent「爆上下文」 | 多 Skill / 上下文工程 | Skill 设计规范（→ #4/#5） |
| **X3** | 从零到一上手混合检索：AI Native 统一数据基座实战 | Agentic RAG / 混合检索 | 扩充 RAG 评测数据集（→ #11/#12） |
| **X4** | 海量 AI Agent 多模数据降本：数据湖库登场 | 数据湖库 × AI | 开源「湖到 RAG」教程（→ #14/#15） |
| **X5** | 由你来定！ | ？？？ | ？？？ |

### 列表 C：工程 / 基建任务（Good First Issue）

> 来自社区已提出的现有 Issue，适合想从工程角度参与的同学，多为 L1–L2 难度。

| 关联 Issue | 待办 | 难度 |
| --- | --- | --- |
| [#6](https://github.com/datawhalechina/easy-data-x-ai/issues/6) | `.env.example` 占位符与 `Config.check_api_key` 判定不一致，修正误判逻辑 | L1 |
| [#7](https://github.com/datawhalechina/easy-data-x-ai/issues/7) | `config.py` 注释与实现不一致：按注释实现向上查找 `.env` | L1 |
| [#8](https://github.com/datawhalechina/easy-data-x-ai/issues/8) | 示例脚本 `sys.path.append('..')` 从根目录运行会导入失败，改为稳健的路径处理 | L2 |
| [#9](https://github.com/datawhalechina/easy-data-x-ai/issues/9) | README 补充 Windows PowerShell 命令示例（`cp` / `python3` 等） | L1 |
| [#10](https://github.com/datawhalechina/easy-data-x-ai/issues/10) | Tool Use 示例只处理首个 tool_call，且 `list(stream)` 聚合不通用，改为通用实现 | L2 |
| [#12](https://github.com/datawhalechina/easy-data-x-ai/issues/12) | VitePress 依赖为 alpha 且用 `^` 范围，锁定版本提升构建可复现性 | L2 |
| [#13](https://github.com/datawhalechina/easy-data-x-ai/issues/13) | 补充 PR/Push 的 CI 校验工作流（docs build / Python 示例语法检查等） | L2 |

---

## 五、参与方式总览

1. **提 Issue 参与讨论**：先开 Issue 说明你的建议、需求或共建思路（可用下方 Issue 模板）。
2. **认领任务提 PR**：在对应 Issue 下留言认领，在章节文件中调整、完善、补充，完成后提 PR。
3. **贡献扩展篇**：在 `docs/extra/` 下独立创建新章节（先开 Issue 对齐大纲）。

> 提交 PR 后，记得在描述里注明认领的任务编号（#编号），方便归档。

---

## 六、致谢与收获

我们希望每一位参与者不仅留下贡献，也能收获成长。所有被合并 PR 的贡献者都会获得以下激励：

### 🏆 贡献者墙

所有合并过 PR 的贡献者会自动登上仓库 README 的**贡献者墙**（头像 + GitHub 主页 + 贡献量），由 GitHub Action 自动更新，无需手动申请。

### 🎁 实体礼品

按贡献量分档赠送 **OceanBase 社区定制周边**：

| 档位 | 条件（示例） | 礼品 |
| --- | --- | --- |
| 入门 | 合并 1 个有效的 PR（列表 A / 列表 C） | OceanBase 定制贴纸 / 徽章 |
| 进阶 | 合并 2 个及以上的内容完善类 PR（列表 A） | OceanBase 专属马克杯 / 帆布包 |
| 核心 | 独立完成一节扩展篇内容（X1 ~ X5） | OceanBase 定制 T 恤 |

### 🌟 成长与社区收获

- **课程署名**：扩展篇作者会在课程对应章节页面**正式署名**。
- **纳入 OceanBase 社区布道师体系**：表现突出的共建者可被推荐为「种子布道师」，获得 OceanBase 官方证书。
- **讲师 / 露出机会**：受邀参与社区直播、线下 Meetup、高校行，输出自己的内容。
- **优秀贡献者评选**：定期评选季度优秀贡献者，额外礼品 + 社区公众号专访。
- **职业机会**：优秀贡献者可获得蚂蚁集团及 OceanBase 实习 / 内推推荐。
- **联合社区礼品**：根据课程共建的贡献量，还可获得 OceanBase 社区为大家准备的定制礼物，以及 LangChain 中国社区的礼品。

---

## 七、提问与讨论

- **课程内容问题**：在 [Issues](https://github.com/datawhalechina/easy-data-x-ai/issues) 提问，或在配套视频评论区留言。
- **加入交流群**：扫描 README 底部二维码，加入 Data x AI 课程交流群。

再次感谢你的贡献，期待与你一起把这门课打磨成精品！🚀
