# 代码可运行性修复说明

在 Windows 上把 `code/` 里的示例过了一遍，主要卡在 seekdb。下面按「怎么踩坑 → 为什么挂 → 改了什么 → 怎么验的」写，方便 review。

验证机器：Windows 11，Python 3.14.3（venv），依赖用清华源装的。CI 是 ubuntu + 3.11，那边默认能走 Embedded，和本机行为不一样，这点后面会反复提到。

---

## 一、先说怎么装环境

仓库根目录：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r code/requirements-test.txt
python -m pip check
python -m compileall -q code
```

本机 `pip check` 是干净的。装下来的版本记了一份 `pip_freeze.txt`，几个关键的：

- langchain 1.4.0
- langchain-core 1.6.3
- langchain-openai 1.6.2
- langgraph 1.2.11
- openai 3.13.0
- pyseekdb 1.4.0.post1
- mcp 1.30.0
- ragas 0.2.15
- datasets 5.0.1

`requirements.txt` 里还是用 `>=` 下限，兼容 CI；上面这组是这次真跑通的组合。

---

## 二、踩到的问题

### 1. Windows 上一碰 seekdb Embedded 就崩，报错没法用

**怎么复现**

机器上没有 `pylibseekdb`（Windows 也装不上），也不设 `SEEKDB_MODE=server` / `SEEKDB_TEST_HOST`，然后跑：

```powershell
$env:PYTHONPATH = "code"
.\.venv\Scripts\python.exe -m unittest discover -s code/D3 -p "test*.py"
```

**修复前**

直接甩 pyseekdb 内部英文栈：

```text
RuntimeError: Embedded Client is not available because pylibseekdb is not available.
Please install pylibseekdb (Linux only) or use RemoteServerClient (host/port) instead.
```

初学者根本不知道下一步该干什么。

**为什么会这样**

Embedded 依赖平台扩展 `pylibseekdb`，Linux 能装，Windows 不行。但：

- `code/seekdb_runtime.py` 在默认 Embedded 分支上直接 `pyseekdb.Client(path=...)`，事前不查能力；
- D3 集成测试 `create_test_client()` 没配外部库时无脑回退 Embedded；
- X2 测试更直接，`real_database_env()` 里写死了 `SEEKDB_MODE=embedded`，和生产代码 `resolve_mode()`（没 pylibseekdb 时本该走 Server）拧着。

**改了什么**

| 文件 | 改动 |
| --- | --- |
| `code/seekdb_runtime.py` | 加了 `embedded_available()` 和中文提示文案；Embedded 前先检查，失败时把 Server 环境变量怎么配写清楚 |
| `code/D3/test_d3_pyseekdb_integration.py` | 没有 `SEEKDB_TEST_HOST` 且没有 pylibseekdb 时，报可操作错误，不再把内部栈甩出来 |
| `code/X2/tests/test_x2_runnability.py` | `real_database_env()` 跟生产逻辑对齐，不再写死 embedded |
| `code/test_seekdb_runtime.py` | 补了一条「没 pylibseekdb 时 Embedded 该失败」的用例；原路径用例 mock 掉 `embedded_available` |
| `code/D3/test_d3_hardening.py` | 路径锚定用例改成在假 `pyseekdb` + Embedded 可用的 patch 还活着的时候调 `create_db_client()`，免得打到真客户端 |

**修完之后（本机没 Docker）**

- D3：70 条里 69 过，只剩真实集成那条，错误信息变成「请起 Server 并设 SEEKDB_TEST_*」
- X2：25 条里 24 过，同样只剩集成那条

### 2. D1–D4 没有能直接用的 Server 启动文件

README 里写了「macOS/Windows 请启动隔离 seekdb Server」，但仓库里只有 X2 自己的 compose，D1–D4 共用的那一份没有，健康检查命令也不统一。学员照着文档会卡在「去哪起库」。

补了：

- `code/docker-compose.yml`：D1–D4 共用 `oceanbase/seekdb`，2881/2886，演示库名 `easy_data_x_ai_demo`
- `code/check_seekdb_env.py`：一键看 Embedded 能不能用、当前 mode、Server 端口通不通，不通就打印下一步命令
- `code/README.md` / `docs/faq.md` / `code/X2/README.md`：把启动、环境变量、`SEEKDB_TEST_*`、健康检查写全；X2 的安装命令改成跟仓库统一的 `requirements-test.txt`，去掉 `python3.12` 这种和课程推荐 3.11+ 打架的说法

本机没装 Docker，所以 `check_seekdb_env.py` 会退出码 1，但提示是完整的，见 `logs/check_seekdb_env.txt`。

### 3. 无库时 `run_tests.py` 在 Windows 全绿不了

这不是 bug，是门槛设计：`run_tests.py` 禁止用 skip 冒充验证过。D3/X2 真实库用例在既没有 Embedded 也没有 Server 时就必须失败。Linux CI 默认有 Embedded 所以全绿。

处理方式：**不改成静默跳过**，只把错误改成可操作的，并在 README/FAQ 写清 Windows 要先起 Server。

---

## 三、离线能跑通的部分（无 Key、无 Docker）

| 项 | 结果 |
| --- | --- |
| `pip check` / `compileall -q code` | 过 |
| 配置 / seekdb_runtime / 导入路径 / 测试运行器元测试 | 过 |
| D1 | 27 过 |
| D2 | 21 过 |
| D3 单元（不含需库集成） | 69 过 + 1 条可操作错误 |
| D3 离线评测 `d3_5_evaluate.py` | 60 条，Hit@3=1.0，拒答=1.0，报告在 `code/D3/reports/` |
| D4 / X1(36) / X4 / X5 / P5(38) | 过 |
| 没配 `SILICONFLOW_API_KEY` 时跑 `d1_1_base.py` | 明确报错退出，不往外呼 |

详细日志在压缩包 `logs/` 里。

---

## 四、OceanBase / seekdb Server 准备步骤

本机没 Docker，库没起，步骤留给有 Docker 的环境：

```powershell
docker compose -f code/docker-compose.yml up -d

$env:SEEKDB_MODE = "server"
$env:SEEKDB_HOST = "127.0.0.1"
$env:SEEKDB_PORT = "2881"
$env:SEEKDB_DATABASE = "easy_data_x_ai_demo"
$env:SEEKDB_ALLOW_DESTRUCTIVE = "1"

# 集成测试用隔离库，别和演示库混用
$env:SEEKDB_TEST_HOST = "127.0.0.1"
$env:SEEKDB_TEST_PORT = "2881"
$env:SEEKDB_TEST_DATABASE = "easy_data_x_ai_test"
$env:SEEKDB_TEST_X2_DATABASE = "easy_data_x_ai_x2_test"
$env:SEEKDB_ALLOW_DESTRUCTIVE = "1"

.\.venv\Scripts\python.exe code\check_seekdb_env.py
.\.venv\Scripts\python.exe code\run_tests.py
```

X2 也可以用自己的 compose：`cd code/X2 && docker compose up -d`，再 `python database/check_seekdb.py`。

按上面做完之后，Windows 上的 `run_tests.py` 应该能和 Linux CI 一样绿。

---

## 五、改了哪些文件

代码：

- `code/seekdb_runtime.py`
- `code/test_seekdb_runtime.py`
- `code/D3/test_d3_pyseekdb_integration.py`
- `code/D3/test_d3_hardening.py`
- `code/X2/tests/test_x2_runnability.py`

文档 / 准备脚本：

- `code/README.md`
- `code/docker-compose.yml`（新增）
- `code/check_seekdb_env.py`（新增）
- `docs/faq.md`
- `code/X2/README.md`

验证日志（工作区 `logs/`，一般不用提 PR）：

- `pip_install.txt` / `pip_freeze.txt` / `pip_check.txt`
- `run_tests_before.txt`（修复前）
- `test_d3_final.txt` / `test_x2_final.txt`
- `check_seekdb_env.txt` / `offline_matrix.txt`
