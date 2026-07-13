import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyseekdb

# ============================================================
# d3_1：构建知识库
#
# 演示：
#   1. 将预处理好的文档片段写入 seekdb
#   2. 知识库包含版本说明、错误码、财务数据、最佳实践等内容
#   3. 为后续 d3_2（Agentic RAG）和 d3_3（对比实验）提供数据基础
#
# 运行：python d3_1_ingest.py
# ============================================================


# ---------- 1. 准备示例数据集 ----------
# 模拟一个技术产品的知识库，包含多种类型的文档片段
# 这些内容已经完成了分块处理，每条记录就是一个 chunk

knowledge_chunks = [
    # 版本兼容性说明
    {
        "id": "kb_001",
        "content": "OB-4.2.1 版本兼容性说明：OB-4.2.1 与 OB-4.1.x 保持向后兼容，但不兼容 OB-3.x 系列。升级前请确认所有客户端驱动已更新至 4.x 版本。已知问题：在 ARM 架构下 JIT 编译存在偶发性能退化。",
        "doc_type": "release_notes",
        "version": "4.2.1"
    },
    {
        "id": "kb_002",
        "content": "OB-4.1.0 版本兼容性说明：OB-4.1.0 为大版本升级，不兼容 OB-3.x 的数据格式，需要执行数据迁移工具。与 OB-4.0.x 保持兼容。",
        "doc_type": "release_notes",
        "version": "4.1.0"
    },
    {
        "id": "kb_003",
        "content": "OB-3.2.4 版本兼容性说明：OB-3.2.4 与 OB-3.x 全系列兼容。这是 3.x 系列的最终维护版本，建议尽快升级至 4.x。",
        "doc_type": "release_notes",
        "version": "3.2.4"
    },
    # 错误码手册
    {
        "id": "kb_004",
        "content": "错误码 E-4012：数据库连接池耗尽。当并发连接数超过 max_connections 配置值时触发。解决方案：(1) 增大 max_connections 参数，(2) 检查应用是否存在连接泄漏，(3) 考虑使用连接池中间件。",
        "doc_type": "error_codes",
        "version": "4.2"
    },
    {
        "id": "kb_005",
        "content": "错误码 E-4013：认证握手超时。客户端在 10 秒内未完成认证流程时触发。解决方案：(1) 检查网络延迟，(2) 确认 SSL 证书配置正确，(3) 排查防火墙是否拦截了认证端口。",
        "doc_type": "error_codes",
        "version": "4.2"
    },
    {
        "id": "kb_006",
        "content": "错误码 E-4011：SQL 语法解析失败。通常由不支持的 SQL 方言或语法错误引起。解决方案：(1) 检查 SQL 语句是否符合 OB-SQL 语法规范，(2) 使用 EXPLAIN 命令验证。",
        "doc_type": "error_codes",
        "version": "4.2"
    },
    # 财务数据
    {
        "id": "kb_007",
        "content": "2024年Q3营收数据：总营收 2.87 亿元，同比增长 34%。其中云服务收入 1.92 亿元，占比 67%；License 收入 0.95 亿元，占比 33%。新增付费客户 127 家，客户续约率 96.2%。",
        "doc_type": "financial",
        "version": "2024Q3"
    },
    {
        "id": "kb_008",
        "content": "2024年Q2营收数据：总营收 2.41 亿元，同比增长 28%。其中云服务收入 1.55 亿元，License 收入 0.86 亿元。新增付费客户 98 家。",
        "doc_type": "financial",
        "version": "2024Q2"
    },
    # 性能调优
    {
        "id": "kb_009",
        "content": "并行查询优化指南：OB-4.2 引入了自适应并行执行引擎。通过设置 parallel_degree 参数控制并行度。建议值：OLAP 场景设为 CPU 核数的 2 倍，OLTP 场景保持为 1。大表全表扫描场景下，并行查询可带来 5-8 倍性能提升。",
        "doc_type": "best_practices",
        "version": "4.2"
    },
    {
        "id": "kb_010",
        "content": "索引设计最佳实践：为高频查询条件列创建索引。复合索引的列顺序应遵循最左前缀原则。避免在低基数列（如性别、状态）上单独建立索引。定期使用 ANALYZE TABLE 更新统计信息。",
        "doc_type": "best_practices",
        "version": "4.2"
    },
    {
        "id": "kb_011",
        "content": "数据分区策略：支持 Range、Hash、List 和 Key 四种分区方式。时序数据建议使用 Range 分区按月划分；高并发写入场景建议使用 Hash 分区打散热点。分区数建议控制在 64-256 之间。",
        "doc_type": "best_practices",
        "version": "4.2"
    },
    # API 参考
    {
        "id": "kb_012",
        "content": "DBMS_HYBRID_SEARCH 函数说明：执行混合检索，同时利用向量语义搜索和全文关键词搜索。语法：DBMS_HYBRID_SEARCH(collection, query_text, top_k, filters)。内部使用 RRF 算法融合两种搜索的排序结果。",
        "doc_type": "api_reference",
        "version": "4.2"
    },
]


# ---------- 2. 初始化 seekdb 并写入数据 ----------

print(">>> 正在初始化 seekdb...")
db = pyseekdb.Client()
collection_name = "d3_product_kb"

# 如果已存在则先删除，确保每次运行都是干净的
if db.has_collection(collection_name):
    db.delete_collection(collection_name)
    print(f">>> 已删除旧集合：{collection_name}")

collection = db.create_collection(name=collection_name)
print(f">>> 集合创建成功：{collection_name}\n")

# 批量写入
collection.add(
    ids=[chunk["id"] for chunk in knowledge_chunks],
    documents=[chunk["content"] for chunk in knowledge_chunks],
    metadatas=[{"doc_type": chunk["doc_type"], "version": chunk["version"]} for chunk in knowledge_chunks],
)

print(f">>> 已写入 {collection.count()} 个知识片段")
print()

# 展示写入的数据分布
from collections import Counter
type_counts = Counter(chunk["doc_type"] for chunk in knowledge_chunks)
print(">>> 知识库内容分布：")
for doc_type, count in type_counts.items():
    print(f"    {doc_type}: {count} 条")

print()
print(">>> d3_1 完成！知识库已就绪，可运行 d3_2 / d3_3 继续体验。")
