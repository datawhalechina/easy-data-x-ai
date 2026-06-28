# X2 · seekdb 数据层

X2 使用 [seekdb](https://docs.seekdb.ai/seekdb/doc-overview/) 存储 Skill / Rule / Example，三个集合名见 `collections.py`。

## 部署模式

| 平台 | 推荐模式 | 说明 |
| --- | --- | --- |
| macOS / Windows | **Server** | 嵌入式依赖 `pylibseekdb`，仅 Linux 可用 |
| Linux | Embedded 或 Server | 默认自动选 Embedded；也可 Docker Server |

### Server 模式（课程推荐，尤其 macOS）

```bash
cd code/X2
docker compose up -d
python database/check_seekdb.py
```

Docker 会在启动时创建 `x2_skills` 数据库（见 `docker-compose.yml` 中 `SEEKDB_DATABASE`）。

### Embedded 模式（Linux）

无需 Docker，`pyseekdb` 会在 `database/skills.seekdb/` 下创建本地数据目录：

```bash
python database/check_seekdb.py   # 模式应显示 embedded
python database/init_seekdb.py
```

## 环境变量

复制 `.env.example` 为 `.env` 后可覆盖默认值：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `SEEKDB_MODE` | 自动 | `server` 或 `embedded` |
| `SEEKDB_HOST` | `127.0.0.1` | Server 地址 |
| `SEEKDB_PORT` | `2881` | Server 端口 |
| `SEEKDB_DATABASE` | `x2_skills` | 数据库名 |
| `SEEKDB_TENANT` | `sys` | seekdb Server 租户 |
| `SEEKDB_USER` | `root` | 用户名 |
| `SEEKDB_PASSWORD` | 空 | 密码 |

连接逻辑集中在 `seekdb_client.py`，`SeekdbStorage` 与各 CLI 工具共用。

## 常用命令

```bash
python database/check_seekdb.py          # 连接检测
python database/init_seekdb.py           # 创建三集合
python database/init_seekdb.py --force   # 清空重建
```
