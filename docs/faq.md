# 学习 FAQ

这里集中回答课程导航、示例代码和参与共建时最常见的问题。

## 我应该从哪一篇开始？

第一次学习建议先完成 F1、F2。这两篇提供公共概念和 Agent 全景图。之后，产品经理和决策者可以沿道篇 P1～P5 学习，开发者可以沿术篇 D1～D5 动手实践。两条路线不是互斥的，P2 与 D2、D3，P3 与 D4 都适合配对阅读。

## 没有 API Key 能学习吗？

可以。概念文章、绝大多数单元测试和 D3 的 60 条离线评测都不需要 API Key。需要调用真实模型或 Embedding 的示例会在运行说明中明确标注，并从本地 `.env` 读取密钥。

## API Key 应该放在哪里？

复制 `code/.env.example` 为 `code/.env`，只在本机填写。仓库已经忽略 `.env`，但提交前仍应检查差异，确保密钥、个人数据库地址和临时模型配置没有进入版本控制。

## 如何运行示例代码？

在项目根目录创建并激活虚拟环境。macOS / Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r code/requirements-test.txt
```

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r code/requirements-test.txt
```

再进入课程对应目录，按照正文中的顺序运行脚本。D3 可以先在仓库根目录执行不需要数据库和 API Key 的离线评测：

```bash
python code/D3/d3_5_evaluate.py
```

## 为什么同一篇里有“离线测试”和“真实接口测试”？

离线测试用于稳定验证流程、边界和指标计算，适合每次修改后重复运行。真实接口测试用于确认当前模型、网络和供应商兼容性，会产生调用费用，也可能受服务状态影响。两种结果不能互相替代。

## 示例运行失败时先检查什么？

依次检查 Python 版本与依赖、当前工作目录、`.env` 是否存在、数据库连接参数、示例要求的前置脚本是否已经执行。错误仍然存在时，请保留完整命令和报错，在 GitHub Issue 中说明操作系统与 Python 版本。

## macOS 或 Windows 为什么不能直接使用 seekdb Embedded？

Embedded 依赖能在当前平台加载的原生扩展 `pylibseekdb`。Windows 请使用隔离的 seekdb Server；macOS / Linux 安装了匹配扩展时可用 Embedded，否则也使用 Server。

以下命令在**仓库根目录、已激活的虚拟环境**中执行。先启动共用 Server（需安装并运行 Docker）：

```bash
docker compose -f code/docker-compose.yml up -d
docker compose -f code/docker-compose.yml exec -T seekdb mysql -h127.0.0.1 -P2881 -uroot -e "SELECT 1;"
```

首次启动需要等待初始化；查询失败时查看容器日志并稍后重试。共用实例与 `code/X2/docker-compose.yml` 都占用 `2881/2886`，应二选一；X2 默认复用共用实例。

再配置当前会话的 Server 模式，最后运行自检。macOS / Linux：

```bash
export SEEKDB_MODE=server
export SEEKDB_HOST=127.0.0.1
export SEEKDB_PORT=2881
export SEEKDB_DATABASE=easy_data_x_ai_demo
export SEEKDB_ALLOW_DESTRUCTIVE=1
python code/check_seekdb_env.py
```

Windows PowerShell：

```powershell
$env:SEEKDB_MODE = "server"
$env:SEEKDB_HOST = "127.0.0.1"
$env:SEEKDB_PORT = "2881"
$env:SEEKDB_DATABASE = "easy_data_x_ai_demo"
$env:SEEKDB_ALLOW_DESTRUCTIVE = "1"
python code/check_seekdb_env.py
```

自检会验证演示库连接。运行 D3 / X2 集成测试前，还需显式创建隔离测试库，再配置 `SEEKDB_TEST_*`；只设置测试库名不会创建数据库。完整命令见 [Code README](https://github.com/datawhalechina/easy-data-x-ai/blob/main/code/README.md)。

## 模型未开通、Key 无权限和限流怎么区分？

- 返回 401 / authentication：优先检查 Key 是否正确、是否读到了预期 `.env`。
- 返回 403 / model permission：检查账号是否开通了正文指定模型。
- 返回 429 / rate limit：等待后重试，并查看服务商的并发与额度限制。
- 返回 model not found：核对模型 Code，不要把控制台展示名当成接口参数。

## MCP 示例提示依赖不存在怎么办？

先在当前虚拟环境执行 `python -m pip check`，再按 `code/requirements.txt` 安装依赖。确认启动命令使用的是同一个 Python 解释器，避免系统 Python 与虚拟环境混用。

## 哪些示例会修改数据库？

D2、D3 的写入、更新和重建示例会修改集合。Server 模式还要求显式设置 `SEEKDB_ALLOW_DESTRUCTIVE=1`，这是为了提醒你只能对隔离的演示或测试库操作。不要把该变量用于生产数据库。

## 如何清理本地实验数据？

Embedded 模式的数据位于各示例目录下的本地数据目录，可以在确认路径后删除。Server 模式请连接到你专门创建的演示数据库，按集合清理；不要使用宽泛的递归删除命令，也不要复用生产库。

## 如何参与课程共建？

先阅读仓库中的贡献指南，再通过 Issue 对齐范围。一个 PR 尽量只解决一个明确问题，并附上对应测试、构建结果或页面截图，方便维护者复核。
