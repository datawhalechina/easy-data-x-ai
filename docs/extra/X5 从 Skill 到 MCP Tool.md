---
title: X5 从 Skill 到 MCP Tool
---

# X5：从 Skill 到 MCP Tool

> Easy Data x AI 课程 · 扩展篇 · 第五期
>
> 当一份 Skill 足够稳定、通用，并且需要被多个 Agent 客户端复用时，可以把它进一步发布成 MCP Tool。

## 开场：为什么把 Skill 发布成工具

P4 已经把 Skill 讲成一种可管理、可检索、可复用的经验数据，也补充了同一个 Skill 在不同 Coding Agent 中落地时会遇到的互操作问题。

但如果我们希望一个稳定能力不只是被不同客户端读取，而是能以统一接口被发现、传参和调用，就需要再往前走一步：把稳定的 Skill 封装成 MCP Tool。

Skill 和 MCP Tool 不是替代关系，而是递进关系：

```text
Skill 负责沉淀“怎么做”
MCP Tool 负责定义“怎么被调用”
MCP Server 负责承载并暴露这些 Tool
Claude / Cursor / Codex 等客户端负责发现和调用 Tool
```

这一章用一个最小可运行示例，把 `code-review` Skill 包装成 `review_code_diff` MCP Tool，并用 MCP Inspector、Claude Code、Cursor 和 Codex 跑通本地 stdio 调用。

## 1. 为什么 Skill 需要 MCP 化

Skill 本质上是一份任务经验包。它适合描述目标、适用场景、输入输出、执行步骤、检查清单和示例。对人和 Agent 来说，这很自然，因为它像一份任务说明书。

但跨客户端复用时，只有说明书还不够。不同客户端对 Skill 的扫描目录、触发方式和上下文注入机制并不完全相同。如果我们希望一个能力被 Claude、Cursor、Codex 等客户端以同样的方式调用，就需要一个更稳定的接口层。

MCP 化做的事情，就是把 Skill 中已经稳定的部分提炼成工具接口：

| Skill 元素 | MCP Tool 对应物 | 示例 |
| --- | --- | --- |
| `name` | tool name | `code-review` -> `review_code_diff` |
| `description` | tool description | 告诉客户端什么时候适合调用 |
| Inputs | input schema | `diff: str`、`focus: str` |
| Steps / Checklist | 工具内部逻辑 | 按 correctness、security、tests 等维度检查 |
| Output Format | return value | 返回结构化 Markdown review report |

所以 MCP 化不是把 `SKILL.md` 改个文件名，而是把经验文档中的稳定流程变成一个可调用、可验证、边界清晰的工具。

## 2. 示例目标：把 code-review Skill 包装成 MCP Tool

这里继续使用 P4 中的 `code-review` Skill。它适合作为 MCP 示例，原因很简单：

1. 输入稳定：通常是 git diff、PR diff 或 changed code snippet。
2. 检查维度稳定：correctness、maintainability、security、tests、compatibility、project conventions。
3. 输出格式稳定：按 Critical、Major、Minor 等严重程度组织 findings。
4. 复用需求明确：Claude、Cursor、Codex 都可能需要执行代码审查。

本章要实现的最小目标是：

```text
code-review Skill
        ↓
review_code_diff MCP Tool
        ↓
skill-mcp-demo MCP Server
        ↓
Claude / Cursor / Codex 通过本地 stdio 方式调用
```

为了聚焦 MCP 的接口化过程，示例工具不接真实 LLM，也不依赖外部 API。它只返回一份结构化 Markdown 报告，用来演示“Skill -> MCP Tool”的最小闭环。后续如果要做成真实审查引擎，可以把内部逻辑替换成 LLM review、静态分析、项目规则检索或 CI 日志分析。

## 3. 实现最小 MCP Server

新增文件：

```text
code/X5/mcp_skill_server.py
```

代码如下：

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("skill-mcp-demo")


@mcp.tool()
def review_code_diff(
    diff: str,
    focus: str = "correctness, maintainability, security, tests",
) -> str:
    """
    Review a code diff according to the code-review Skill checklist.

    Args:
        diff: Git diff, pull request diff, or changed code snippet.
        focus: Review focus areas.

    Returns:
        A structured review report grouped by severity.
    """
    return f"""# Code Review Result

## Focus
{focus}

## Input Summary
Received diff with {len(diff)} characters.

## Review Checklist
1. Correctness
2. Maintainability
3. Security
4. Tests
5. Compatibility
6. Project conventions

## Findings
- Critical: 暂无，需结合真实 diff 判断
- Major: 请检查核心逻辑、边界条件和异常路径
- Minor: 请检查命名、重复代码和可读性

## Suggested Next Steps
1. 补充或更新测试用例。
2. 重点检查 diff 中的输入校验、错误处理和兼容性影响。
3. 如果这是 PR，请结合 CI 日志和项目约定进一步审查。
"""


if __name__ == "__main__":
    mcp.run()
```

这段代码里有三个关键点：

1. `FastMCP("skill-mcp-demo")` 定义了一个本地 MCP Server。
2. `@mcp.tool()` 把普通 Python 函数暴露成 MCP Tool。
3. 函数签名和 docstring 会帮助客户端理解工具名称、参数和用途。

## 4. 运行与本地测试

### 4.1 安装依赖

课程仓库统一把示例依赖放在 `code/requirements.txt` 中。建议在仓库根目录执行：

```bash
python -m pip install -r code/requirements.txt
```

安装完成后，可以先确认 MCP CLI 是否可用：

```bash
mcp --help
```

如果只想运行本章 MCP 示例，也可以只安装 MCP CLI：

```bash
python -m pip install "mcp[cli]"
```

### 4.2 用 MCP Inspector 验证工具

对于初学者来说，最直观的验证方式不是直接启动 stdio server，而是使用 MCP Inspector：

```bash
mcp dev code/X5/mcp_skill_server.py
```

打开 MCP Inspector 后，先确认左侧 Transport Type 是 `STDIO`，再点击 `Connect` 连接本地 server。

![](https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/extra/X5/01-mcp-inspector-connect.png)

在 Inspector 页面中确认三件事：

1. server 能连接成功；
2. tools 列表里能看到 `review_code_diff`；
3. 输入一段简单 diff 后，能返回结构化 Markdown review report。

调用 `review_code_diff` 时，可以填入下面这组参数：

```text
diff:
diff --git a/app.py b/app.py
+print("hello")

focus:
correctness, tests
```

填写参数时，先切到顶部的 `Tools`，点击 `List Tools`，选择 `review_code_diff`，再把 diff 和 focus 填入右侧表单。

![](https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/extra/X5/02-mcp-inspector-tool-input.png)

点击 `Run Tool` 后，如果看到 `Tool Result: Success` 和 `# Code Review Result`，就说明 MCP Tool 已经被成功调用。

![](https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/extra/X5/03-mcp-inspector-tool-result.png)

如果 Inspector 能调用成功，就说明 MCP Server 本身已经跑通。接下来客户端配置只是“如何让不同 Agent 发现这个 server”的问题。

### 4.3 常见问题

如果本地测试失败，可以先检查下面几项：

1. 确认当前目录是仓库根目录，否则 `code/X5/mcp_skill_server.py` 可能找不到。
2. 确认当前 Python 环境已经安装 `mcp[cli]`。
3. 如果 `mcp dev` 能启动，但客户端配置失败，优先检查客户端配置中的 `command` 和 `args` 是否能在终端中单独运行。
4. 如果相对路径不稳定，可以在后续客户端配置中改用绝对路径。
5. 如果直接运行 `python code/X5/mcp_skill_server.py` 后终端没有输出，这是正常现象；stdio MCP Server 通常由 Claude Code、Cursor、Codex 等客户端拉起，不建议把直接运行作为主要验证方式。
6. 不要在 `python code/X5/mcp_skill_server.py` 的终端里手动粘贴 diff。这个进程等待的是 MCP 客户端发送的 JSON-RPC 消息，普通文本会被当成非法协议输入。

## 5. 在 Claude Code 中配置

Claude Code 可以用命令添加本地 stdio MCP Server。建议在仓库根目录执行：

```bash
claude mcp add --transport stdio --scope project skill-mcp-demo -- python code/X5/mcp_skill_server.py
```

这里：

- `--transport stdio` 表示这是本地进程型 MCP Server；
- `--scope project` 会在项目中生成或更新 `.mcp.json`，适合课程 demo；
- `--` 后面的内容是实际启动 server 的命令；
- 如果不想把配置放进项目，可以把 `--scope project` 改成 `--scope local`，或使用默认 local 配置。

验证命令：

```bash
claude mcp list
```

如果项目级 MCP 显示为待批准状态，进入 Claude Code 后先按提示批准当前项目的 MCP 配置。随后可以用 `/mcp` 检查 `skill-mcp-demo` 是否连接成功，然后提问：

```text
请调用 skill-mcp-demo 的 review_code_diff，审查下面这个 diff：

diff --git a/app.py b/app.py
+print("hello")
```

## 6. 在 Cursor 中配置

Cursor 更适合直接使用项目级配置。可以新建：

```text
.cursor/mcp.json
```

内容如下：

```json
{
  "mcpServers": {
    "skill-mcp-demo": {
      "command": "python",
      "args": ["code/X5/mcp_skill_server.py"]
    }
  }
}
```

验证步骤：

1. 重启或刷新 Cursor 窗口；
2. 打开 Cursor 的 Customize / MCP，或当前版本中对应的 MCP 设置页面；
3. 确认 `skill-mcp-demo` 已连接；
4. 在 Agent 聊天中要求调用 `review_code_diff` 审查一段 diff；
5. 如果连接失败，打开 Output 面板，选择 `MCP Logs` 查看错误。

如果相对路径无法启动，可以把 `args` 改成绝对路径，例如：

```json
["/Users/your-name/path/to/easy-data-x-ai/code/X5/mcp_skill_server.py"]
```

## 7. 在 Codex 中配置

Codex 可以用 `codex mcp add` 添加本地 MCP Server：

```bash
codex mcp add skill-mcp-demo -- python code/X5/mcp_skill_server.py
```

验证命令：

```bash
codex mcp --help
codex
```

进入 Codex TUI 后使用：

```text
/mcp
```

确认 `skill-mcp-demo` 已连接，然后让 Codex 调用工具：

```text
请调用 skill-mcp-demo 的 review_code_diff，审查下面这个 diff：

diff --git a/app.py b/app.py
+print("hello")
```

如果 Claude Code 或 Codex 的命令不可用，可以再考虑手写 MCP 配置。核心都是把本地 stdio server 配成 `command = "python"` 和 `args = ["code/X5/mcp_skill_server.py"]`。不同客户端的配置文件位置和字段可能随版本变化，应以客户端当前文档为准。

## 8. Prompt Skill、代码函数调用、MCP Tool 的对比

同一个 `code-review` 能力，可以有三种落地方式：

| 方式 | 适合场景 | 优点 | 局限 |
| --- | --- | --- | --- |
| Prompt Skill | 流程还在沉淀，需要频繁调整说明 | 灵活、易修改、适合人读 | 不同客户端加载方式不统一 |
| 代码函数调用 | 只在某个应用内部使用 | 实现简单、工程可控 | 绑定具体项目，跨客户端复用成本高 |
| MCP Tool | 能力稳定，希望被多个客户端统一调用 | 标准化、可发现、可传参、边界清晰 | 需要维护 MCP Server 和工具 schema |

一个自然的演进路径是：

```text
Prompt / 手动流程
        ↓
沉淀为 Skill
        ↓
在多个任务中复用并迭代
        ↓
稳定后封装为 MCP Tool
        ↓
通过 MCP Server 暴露给多个 Agent 客户端
```

## 9. 小结：什么时候值得把 Skill 发布成 MCP Tool

并不是所有 Skill 都值得立即 MCP 化。一个 Skill 适合发布成 MCP Tool，通常需要满足几个条件：

1. 任务边界清晰：知道这个能力解决什么、不解决什么；
2. 输入输出稳定：参数和返回结果可以结构化描述；
3. 执行流程可复用：不是一次性 Prompt，而是能在多个项目里重复使用；
4. 有跨客户端需求：希望 Claude、Cursor、Codex 或其他客户端都能调用；
5. 需要更清晰的权限和执行边界：例如限制工具访问哪些文件、调用哪些 API、返回哪些结果。

本章的 `review_code_diff` 是一个教学 demo，不是真实代码审查引擎。它的价值在于展示 Skill 到 MCP Tool 的接口化过程：先把经验沉淀成 Skill，再把稳定能力包装成标准化工具，最后通过 MCP Server 暴露给不同客户端。

实际项目中，可以在这个最小 server 的基础上继续扩展：读取真实 git diff、接入 LLM、叠加静态分析、读取项目规则、结合 CI 日志，或者把多个稳定 Skill 逐步发布为多个 MCP Tool。

不同客户端的配置文件位置和字段可能会随版本变化，实际使用时应以对应客户端的 MCP 文档为准。本文示例聚焦的是最小、最容易理解的本地 stdio MCP Server 路径。
