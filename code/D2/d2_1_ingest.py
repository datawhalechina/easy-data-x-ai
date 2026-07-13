import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Config
import pyseekdb

# ============================================================
# d2_1：文档切分与写入 seekdb
#
# 演示：
#   1. 如何将长文档切分为带重叠的小片段（Chunking）
#   2. 如何将文档写入 seekdb（pyseekdb 会自动向量化）
#   3. 写入后验证数据条数
#
# 运行前确认：
#   - 已安装 pyseekdb：pip install pyseekdb
#   - 无需配置 API Key（pyseekdb 嵌入模式，本地运行）
# ============================================================


# ---------- 0. 切分函数 ----------

def chunk_document(text: str, chunk_size: int = 200, overlap: int = 30) -> list[str]:
    """
    将长文档切分为带重叠的小片段。
    overlap（重叠）确保片段边界处的语义不丢失。
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        start += chunk_size - overlap  # 每次前进 chunk_size - overlap
    # 过滤掉空片段
    return [c for c in chunks if c]


# ---------- 1. 准备示例文档 ----------

# 模拟一个技术知识库，包含错误码、最佳实践、版本说明等内容
raw_docs = [
    {
        "text": "错误码 E-4012 表示数据库连接超时。解决方案：检查网络配置，确认数据库服务端口是否开放，建议超时时间设置为 30 秒。",
        "category": "error_codes",
        "version": "4.2"
    },
    {
        "text": "错误码 E-4013 表示认证失败。解决方案：检查用户名和密码是否正确，确认账户是否被锁定。如果账户被锁定，需要联系管理员解锁。",
        "category": "error_codes",
        "version": "4.2"
    },
    {
        "text": "错误码 E-4011 表示连接被拒绝。解决方案：确认数据库服务是否正在运行，检查防火墙规则是否允许对应端口的访问。",
        "category": "error_codes",
        "version": "4.2"
    },
    {
        "text": "数据库查询性能优化指南：合理使用索引可以将查询速度提升 10 倍以上。建议对高频查询的 WHERE 条件列建立索引。避免在索引列上使用函数，否则会导致索引失效。",
        "category": "best_practices",
        "version": "4.2"
    },
    {
        "text": "访问控制架构设计：基于 RBAC 模型实现用户权限管理，支持角色继承和细粒度的资源级权限控制。建议按最小权限原则分配角色，定期审计权限配置。",
        "category": "architecture",
        "version": "4.1"
    },
    {
        "text": "OB-4.2.1 版本新特性：支持在线 DDL 操作、改进了并行查询引擎、修复了分区表在特定条件下的数据倾斜问题。升级前请备份数据并阅读升级指南。",
        "category": "release_notes",
        "version": "4.2.1"
    },
    {
        "text": "数据备份与恢复：建议每天进行全量备份，每小时进行增量备份。恢复时优先使用最近的全量备份，再应用增量备份。备份文件应存储在独立的存储介质上。",
        "category": "best_practices",
        "version": "4.2"
    },
    {
        "text": "连接池配置最佳实践：最大连接数建议设置为 CPU 核心数的 2-4 倍。连接超时时间建议设置为 30 秒，空闲连接超时建议设置为 600 秒。",
        "category": "best_practices",
        "version": "4.2"
    },
]


# ---------- 2. 初始化 seekdb ----------

print(">>> 正在初始化 seekdb...")
db = pyseekdb.Client()
collection_name = "d2_knowledge_base"

# 如果已存在则先删除，确保每次运行都是干净的
if db.has_collection(collection_name):
    db.delete_collection(collection_name)
    print(f">>> 已删除旧的集合：{collection_name}")

collection = db.create_collection(name=collection_name)
print(f">>> 集合创建成功：{collection_name}\n")


# ---------- 3. 切分并写入文档 ----------

all_ids = []
all_texts = []
all_metadatas = []

doc_idx = 0
for doc in raw_docs:
    chunks = chunk_document(doc["text"])
    for chunk_idx, chunk in enumerate(chunks):
        chunk_id = f"doc_{doc_idx}_chunk_{chunk_idx}"
        all_ids.append(chunk_id)
        all_texts.append(chunk)
        all_metadatas.append({
            "category": doc["category"],
            "version": doc["version"],
            "source_doc_idx": doc_idx,
        })
    doc_idx += 1

# 批量写入
collection.add(
    ids=all_ids,
    documents=all_texts,
    metadatas=all_metadatas,
)

print(f">>> 原始文档数：{len(raw_docs)}")
print(f">>> 切分后片段数：{len(all_ids)}")
print(f">>> seekdb 中实际存储条数：{collection.count()}")
print()

# 展示前 3 条写入的片段
print(">>> 写入示例（前 3 条）：")
for i in range(min(3, len(all_texts))):
    print(f"  [{all_ids[i]}] {all_texts[i][:60]}...")
    print(f"  元数据：{all_metadatas[i]}")
    print()

print(">>> d2_1 完成！数据已写入 seekdb，可运行 d2_2 / d2_3 / d2_4 继续体验。")
