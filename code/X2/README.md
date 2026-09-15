# X2 · Skill 结构化管理与按需加载

本目录是扩展篇 X2 的配套示例代码，演示如何用 **seekdb 结构化存储 + 混合检索按需加载** 应对 Agent「爆上下文」问题。

方案源自 [oceanbase-doc-skills](https://github.com/amber-moe/oceanbase-doc-skills)，存储层已迁移为 seekdb。

## 目录结构

```
X2/
├── docker-compose.yml        # 可选：X2 独立 seekdb Server
├── .env.example              # seekdb 连接配置模板
├── x2_1_compare_context.py   # 全量注入 vs 按需加载的 Token 对比
├── storage/                  # SkillStorage 抽象 + seekdb 实现
├── database/                 # seekdb 初始化、连接检测与集合常量
├── models/                   # Skill / Rule / Example 数据模型
├── parsers/                  # SKILL.md 解析与规则/示例抽取
├── services/                 # 迁移、查询、CRUD 服务
├── tools/                    # 命令行迁移与查询工具
└── skills/                   # 示例 SKILL.md 文件
```

## 快速开始

步骤 1、2 均从**仓库根目录**执行；步骤 3 再进入 `code/X2`。后续命令使用同一个已激活的虚拟环境。

### 1. 安装依赖（Python 3.11+）

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r code/requirements-test.txt
```

macOS / Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r code/requirements-test.txt
```

### 2. 选择运行模式（二选一）

#### Server 模式（Windows 或没有可用原生扩展的平台）

默认复用 D1～D4 的共用容器。以下 Docker 命令适用于 macOS / Linux / PowerShell；已经启动该容器时，重复 `up -d` 会复用它：

```bash
docker compose -f code/docker-compose.yml up -d
docker compose -f code/docker-compose.yml exec -T seekdb mysql -h127.0.0.1 -P2881 -uroot -e "SELECT 1;"
```

首次初始化可能需要几分钟；查询失败时查看容器日志，待初始化结束后重试。这里使用 Compose 默认的本地 `root` 账号和空密码。

只需 X2 独立实例时，可将上述命令中的 `code/docker-compose.yml` 替换为 `code/X2/docker-compose.yml`。**两种实例二选一**，它们都占用宿主机 `2881/2886` 端口，不能同时启动。已有共用容器时直接复用即可。

显式配置 X2 使用的独立演示库，避免沿用 D1～D4 的库名：

Windows PowerShell：

```powershell
$env:SEEKDB_MODE = "server"
$env:SEEKDB_HOST = "127.0.0.1"
$env:SEEKDB_PORT = "2881"
$env:SEEKDB_DATABASE = "x2_skills"
```

macOS / Linux：

```bash
export SEEKDB_MODE=server
export SEEKDB_HOST=127.0.0.1
export SEEKDB_PORT=2881
export SEEKDB_DATABASE=x2_skills
```

自定义服务账号时，还需配置 `SEEKDB_USER`、`SEEKDB_PASSWORD` 等连接参数。也可以将 `code/X2/.env.example` 复制为 `code/X2/.env` 保存配置；已有系统环境变量优先于 `.env`。

共用容器只自动创建 D1～D4 演示库；步骤 3 的初始化脚本会创建 `x2_skills`，因此首次运行时应先初始化，再检查 X2 连接。

#### Embedded 模式（已安装匹配的 `pylibseekdb`）

macOS / Linux 的原生扩展能实际加载时，无需 Docker。先在仓库根目录配置并自检：

```bash
export SEEKDB_MODE=embedded
export SEEKDB_DATABASE=x2_skills
python code/check_seekdb_env.py
```

若原生扩展无法加载，按上面的 Server 步骤配置后继续。

### 3. 初始化 → 迁移 → 查询

默认向量模型首次使用时需要联网下载；若初始化或迁移长时间等待，请检查模型下载网络。模型缓存完整后，这部分可离线运行。

```bash
cd code/X2

# 创建数据库并初始化集合
python database/init_seekdb.py

# 初始化成功后检查连接
python database/check_seekdb.py

# 将 SKILL.md 迁移入库
python tools/migrate.py skills/ --all

# 查询 Skill（混合检索）
python tools/query_tool.py list
python tools/query_tool.py search "API documentation"
python tools/query_tool.py get api-doc-writing

# 运行上下文对比示例
python x2_1_compare_context.py
```

## 架构

三个 seekdb 集合，通过 metadata 关联：

| 集合 | 用途 | 检索方式 |
| --- | --- | --- |
| `x2_skills` | 元数据 + 完整正文 | hybrid search（向量 + 全文） |
| `x2_rules` | 格式化/命名规则 | 按 `skill_name` 精确过滤 |
| `x2_examples` | 代码示例 | 按 `skill_name` 精确过滤 |

```
SKILL.md → migrate → seekdb → search_skills(query) → 只加载 rules/examples
```

## 故障排查

| 现象 | 处理 |
| --- | --- |
| `无法连接 127.0.0.1:2881` | 在仓库根目录启动步骤 2 选定的 Compose 实例，等待 SQL 查询成功后重试；不要再启动另一份 Compose |
| Embedded 模式加载原生绑定失败 | 确认当前系统和 Python 版本有匹配的 `pylibseekdb`；否则改用 Docker Server 模式 |
| 集合为空 | 确认已执行 `migrate.py skills/ --all` |

更多连接配置见 [`database/README.md`](database/README.md)。

## 延伸阅读

- 课程文档：[X2 多 Skill 与上下文工程](../../docs/extra/X2%20多%20Skill%20给上下文工程带来的麻烦：如何应对%20Agent「爆上下文」.md)
- seekdb 文档：[docs.seekdb.ai](https://docs.seekdb.ai/seekdb/doc-overview/)
- 完整案例：[oceanbase-doc-skills](https://github.com/amber-moe/oceanbase-doc-skills)
