# Code 目录

本目录包含《Easy Data x AI》课程"术篇"部分的示例代码。

## 目录结构

```
code/
├── config.py          # 统一配置管理
├── .env.example       # 环境变量示例文件
├── requirements.txt   # Python 依赖
├── D1/                # 大模型 API 工程化基础
├── D2/                # AI 应用的数据层
├── D3/                # Agentic RAG 实战
├── D4/                # Agent 开发与记忆系统
├── D5/                # 课程总结
├── P5/                # 综合案例：AI Agent ROI 计算模型
├── X2/                # 扩展篇：Skill 结构化管理与按需加载
└── X5/                # 扩展篇：从 Skill 到 MCP Tool
```

## 快速开始

推荐 Python 3.11。CI 固定使用 Python 3.11；X2 与当前 `pyseekdb` 依赖也要求 Python 3.11+。

### 1. 安装依赖

以下命令均从仓库根目录执行。建议使用独立虚拟环境，避免系统中旧版
`pyseekdb` 影响示例退出和资源释放：

macOS/Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r code/requirements-test.txt
python -m pip check
```

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r code/requirements-test.txt
python -m pip check
```

### 2. 配置 API Key

macOS/Linux：

```bash
cp code/.env.example code/.env
```

Windows PowerShell：

```powershell
Copy-Item code/.env.example code/.env
```

只有真实模型示例需要 API Key。编辑 `code/.env`，填写你准备使用的服务：

```bash
# SiliconFlow API（用于 Hunyuan-MT-7B, DeepSeek-V3 等）
SILICONFLOW_API_KEY=your_siliconflow_api_key_here

# 阿里云 DashScope API（用于 Qwen 等）
DASHSCOPE_API_KEY=your_dashscope_api_key_here
```

`config.py` 会优先读取 `code/.env`；如果该文件不存在，会继续向上查找父目录中的 `.env`（例如仓库根目录 `.env`）。系统环境变量优先级更高，不会被 `.env` 中的同名变量覆盖。

### 3. 运行示例

先运行不需要 API Key 和数据库的 D3 离线评测，确认 Python 环境可用：

```bash
python code/D3/d3_5_evaluate.py
```

该脚本会实际执行查询改写、多路自适应检索、纠错重试和答案校验，并在 `code/D3/reports/` 生成离线评测与策略对比报告。

再运行需要真实模型的示例：

macOS/Linux：

```bash
cd code/D1
python3 d1_1_base.py
```

Windows PowerShell：

```powershell
cd code/D1
python d1_1_base.py
```

## 配置说明

所有代码文件都已统一使用 `config.py` 中的配置，无需在每个文件中单独配置 API Key。

- `Config.get_siliconflow_config()` - 获取 SiliconFlow API 配置
- `Config.get_dashscope_config()` - 获取阿里云 DashScope API 配置

## 运行条件

| 模块 | 运行条件 |
| --- | --- |
| X1 | 纯 Python 标准库，不需要 API Key |
| D1/d1_1～d1_5 | 需要 `SILICONFLOW_API_KEY`；d1_5 还需要 seekdb |
| D1/d1_6 | 需要 `DASHSCOPE_API_KEY`，模型为 `qwen-plus`，并需要 seekdb |
| D2 | 需要 seekdb；语义分块对比还需要 `SILICONFLOW_API_KEY` |
| D3/D4 | 模型示例需要 `SILICONFLOW_API_KEY`，并需要 seekdb |
| D3/d3_5 | 60 条确定性离线评测，不需要 API Key 或 seekdb |
| X2 | Embedded 模式无需外部服务；Server 模式需要先启动 seekdb Server |
| X5 | 需要安装 MCP 依赖，并准备好 X2 的本地数据 |
| P5 | 默认使用确定性离线 Agent；LangSmith 上报为可选功能 |

### seekdb 准备（OceanBase）

Embedded 模式依赖能在当前平台加载的 `pylibseekdb`。Windows 请使用 seekdb Server；macOS / Linux 没有匹配的原生扩展时也使用 Server。

以下命令均在**仓库根目录、已激活的虚拟环境**中执行。先启动并配置 Server，再运行自检。

#### 1. 启动 Server（推荐 Docker）

需要已安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)。

D1～D4 与 X2 默认共用一个实例，各自使用独立数据库：

```bash
docker compose -f code/docker-compose.yml up -d
```

`code/X2/docker-compose.yml` 是可选的独立实例方案，与上面的共用实例**二选一**。两份配置都占用宿主机的 `2881/2886` 端口，不能同时启动；X2 默认复用已启动的共用实例，具体步骤见 [X2 README](X2/README.md)。

等待初始化完成后，用镜像内置的 MySQL 客户端执行一次查询（macOS / Linux / PowerShell 命令相同）：

```bash
docker compose -f code/docker-compose.yml exec -T seekdb mysql -h127.0.0.1 -P2881 -uroot -e "SELECT 1;"
```

首次启动可能需要几分钟；若连接失败，查看 `docker compose -f code/docker-compose.yml logs --tail=50 seekdb`，待初始化结束后重试。只有查询成功才说明数据库已就绪。以下命令使用此 Compose 的默认本地账号 `root` 和空密码；自定义账号或密码时需同步调整连接参数。

#### 2. 配置 Server 环境变量

Windows PowerShell（仅对当前会话生效）：

```powershell
$env:SEEKDB_MODE = "server"
$env:SEEKDB_HOST = "127.0.0.1"
$env:SEEKDB_PORT = "2881"
$env:SEEKDB_DATABASE = "easy_data_x_ai_demo"
$env:SEEKDB_ALLOW_DESTRUCTIVE = "1"
```

macOS / Linux：

```bash
export SEEKDB_MODE=server
export SEEKDB_HOST=127.0.0.1
export SEEKDB_PORT=2881
export SEEKDB_DATABASE=easy_data_x_ai_demo
export SEEKDB_ALLOW_DESTRUCTIVE=1
```

`SEEKDB_ALLOW_DESTRUCTIVE=1` 允许示例重建集合，**只能用于专门的演示/测试数据库**，禁止对生产库设置。

#### 3. 集成测试专用变量

`code/run_tests.py` 中的 D3 / X2 真实数据库用例优先读取 `SEEKDB_TEST_*`，不要与日常演示库混用：

共用 Compose 只初始化演示库 `easy_data_x_ai_demo`。**先显式创建测试库**，再配置测试环境变量；仅设置库名不会创建数据库：

```bash
docker compose -f code/docker-compose.yml exec -T seekdb mysql -h127.0.0.1 -P2881 -uroot -e "CREATE DATABASE IF NOT EXISTS easy_data_x_ai_test; CREATE DATABASE IF NOT EXISTS easy_data_x_ai_x2_test;"
docker compose -f code/docker-compose.yml exec -T seekdb mysql -h127.0.0.1 -P2881 -uroot -D easy_data_x_ai_test -e "SELECT DATABASE(), 1;"
```

Windows PowerShell：

```powershell
$env:SEEKDB_TEST_HOST = "127.0.0.1"
$env:SEEKDB_TEST_PORT = "2881"
$env:SEEKDB_TEST_DATABASE = "easy_data_x_ai_test"
$env:SEEKDB_TEST_X2_DATABASE = "easy_data_x_ai_x2_test"
$env:SEEKDB_ALLOW_DESTRUCTIVE = "1"
```

macOS / Linux：

```bash
export SEEKDB_TEST_HOST=127.0.0.1
export SEEKDB_TEST_PORT=2881
export SEEKDB_TEST_DATABASE=easy_data_x_ai_test
export SEEKDB_TEST_X2_DATABASE=easy_data_x_ai_x2_test
export SEEKDB_ALLOW_DESTRUCTIVE=1
```

使用自定义测试账号时，还需设置 `SEEKDB_TEST_USER` 和 `SEEKDB_TEST_PASSWORD`。

#### 4. 健康检查

```bash
python -m pip check
python code/check_seekdb_env.py
```

Server 自检会验证 `SEEKDB_*` 配置并实际连接演示库执行只读查询；`SEEKDB_TEST_*` 指向的测试库由下面的集成测试验证。

## 测试

在仓库根目录、已激活的虚拟环境中运行（macOS / Linux / PowerShell 命令相同）：

```bash
python code/run_tests.py
python -m compileall -q code
npm run docs:build
```

`code/run_tests.py` 会显式运行配置、D1～D4、X1、X2、X5 和 P5 测试，
并在任意测试组执行 0 个测试或跳过测试时返回失败。CI 使用离线模型替身和临时数据库；
需要 API Key 的真实模型调用应在本地单独执行并与离线测试结果分开记录。

**Windows 说明**：未安装 `pylibseekdb` 时，D3/X2 的真实数据库用例必须先按上文启动 Server 并设置 `SEEKDB_TEST_*`，否则会失败并给出可操作的提示（不是静默跳过）。X1、P5 以及各目录中不依赖数据库的用例可在无 Docker 环境直接通过。

## 说明

各章节的代码示例将随着课程内容的完善陆续添加。
