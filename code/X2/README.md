# X2 · Skill 结构化管理与按需加载

本目录是扩展篇 X2 的配套示例代码，演示如何用 **seekdb 结构化存储 + 混合检索按需加载** 应对 Agent「爆上下文」问题。

方案源自 [oceanbase-doc-skills](https://github.com/amber-moe/oceanbase-doc-skills)，存储层已迁移为 seekdb。

## 目录结构

```
X2/
├── docker-compose.yml        # 课程推荐：Docker 启动 seekdb Server
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

### 0. 启动 seekdb（macOS / Windows 必做）

> **macOS 不支持嵌入式 seekdb**（缺少 `pylibseekdb`），课程推荐使用 Docker Server 模式。Linux 可跳过此步，自动使用嵌入式模式。

```bash
cd code/X2

# 启动 seekdb Server（端口 2881）
docker compose up -d

# 等待就绪后检测连接
python database/check_seekdb.py
```

可选：复制环境变量模板（Server 模式显式配置）

```bash
cp .env.example .env
```

### 1. 安装依赖（Python 3.11+）

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install pyseekdb PyYAML
```

### 2. 初始化 → 迁移 → 查询

```bash
# 初始化 seekdb 集合
python database/init_seekdb.py

# 将 SKILL.md 迁移入库
python tools/migrate.py skills/ --all

# 查询 Skill（混合检索）
python tools/query_tool.py list
python tools/query_tool.py search "API documentation"
python tools/query_tool.py get api-doc-writing

# 运行上下文对比示例
python x2_1_compare_context.py
```

### Linux 嵌入式模式（无需 Docker）

```bash
cd code/X2
pip install pyseekdb PyYAML
python database/check_seekdb.py    # 应显示 embedded 模式
python database/init_seekdb.py
python tools/migrate.py skills/ --all
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
| `无法连接 127.0.0.1:2881` | 执行 `docker compose up -d`，再跑 `check_seekdb.py` |
| macOS 嵌入式报错 | 正常，请用 Docker Server 模式 |
| 集合为空 | 确认已执行 `migrate.py skills/ --all` |

更多连接配置见 [`database/README.md`](database/README.md)。

## 延伸阅读

- 课程文档：[X2 多 Skill 与上下文工程](../../docs/extra/X2%20多%20Skill%20给上下文工程带来的麻烦：如何应对%20Agent「爆上下文」.md)
- seekdb 文档：[docs.seekdb.ai](https://docs.seekdb.ai/seekdb/doc-overview/)
- 完整案例：[oceanbase-doc-skills](https://github.com/amber-moe/oceanbase-doc-skills)
