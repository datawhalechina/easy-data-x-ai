---
title: X3 从零到一上手混合检索：AI Native 统一数据基座实战
---

# Hybrid Search 混合搜索

## 摘要

| | |
|------|------|
| **解决什么痛点** | 消除多搜索方法拼装的搜索效果差、运维复杂度高与数据一致性的问题 |
| **核心价值** | 一条 SQL 完成向量 + 全文 + 标量搜索，高质高效取得数据 |
| **适用场景** | RAG 知识库、多模态搜索等需要结构化数据与非结构化或半结构化数据混合搜索场景 |
| **关键限制** | 仅支持堆表和 HNSW 索引，仅 MySQL 模式可用 |

> OceanBase 混合搜索支持在单条 SQL 中融合向量搜索（语义）、全文搜索（关键词）与标量过滤（结构化条件），通过内置 RRF 等融合算法自动实现合并排序。它以单一数据库架构替代了'向量库 + 搜索引擎'的繁琐拼装，性能更优的同时兼顾搜得全和搜得准。

**目录**

- [1. 一句话理解](#1-一句话理解) — 60 秒了解 Hybrid Search 是什么
- [2. 为什么需要混合搜索](#2-为什么需要混合搜索) — 单一搜索的局限性
- [3. 快速开始](#3-快速开始) — 5 分钟上手：建表、建索引、第一条混合查询
- [4. 查询能力详解](#4-查询能力详解) — 向量搜索、全文搜索、标量过滤、融合算法
- [5. 实战场景与最佳实践](#5-实战场景与最佳实践) — 混搜在RAG中的应用
- [6. 竞品对比](#6-竞品对比) — 与 MySQL、PostgreSQL、Elasticsearch 等对比
- [7. 限制与兼容性](#7-限制与兼容性) — 关键限制、语法限制、参数限制
- [8. 总结](#8-总结) — 核心价值与推荐路径

## 1. 一句话理解

**Hybrid Search = 向量搜索 + 全文搜索 + 标量过滤，一条 SQL 完成，数据库内核自动融合排序。**

```sql
SELECT id, title, __score
FROM HYBRID_SEARCH(
  TABLE articles,
  '{
    "knn": {
      "field": "embedding",
      "query_vector": "[0.1, 0.2, 0.3, 0.4]",
      "k": 10,
      "filter": {
        "range": {"id": {"gte": 1, "lte": 10}}
      }
    },
    "query": {
      "match": {"title": "数据库优化"}
    },
    "rank": {
      "rrf": {"rank_constant": 60}
    },
    "size": 10
  }'
);
```

这条 SQL 同时做了四件事：
- **向量搜索**：通过 `knn` 找语义相近的文档
- **全文搜索**：通过 `query.match` 找关键词匹配的文档
- **标量过滤**：通过 `knn.filter.range` 限定 id 范围，仅对向量搜索结果做过滤
- **融合排序**：通过 `rank.rrf` 自动合并两路结果，输出最终排名

## 2. 为什么需要混合搜索

### 2.1 单一搜索的盲区

以一个 RAG 知识库为例，假设数据库中存储了以下文档：

| id | title | content | category |
|----|-------|---------|----------|
| 1 | OceanBase 4.6.0 功能更新 | 本次版本新增了向量搜索能力，支持 HNSW 索引... | 版本发布 |
| 2 | OceanBase 版本功能速查 | 向量索引：4.3 系列起支持；全文搜索：4.3.1 起支持... | 速查手册 |
| 3 | 向量索引选型指南 | 对比 HNSW、IVF 等向量索引的适用场景与性能... | 最佳实践 |
| 4 | OceanBase 4.6.0 升级指南 | 从 4.5.x 升级至 4.6.0，支持向量搜索功能... | 运维手册 |

当用户发起查询 **"OceanBase 向量索引"** 时：

| 搜索方式 | 命中结果 | 漏掉结果 | 原因 |
|---------|---------|---------|------|
| 向量搜索（语义） | 文档 1、3、4 | **文档 2** | 语义上"向量索引"≈"向量搜索"≈"向量搜索"，能召回 1、3、4；但文档 2 是速查表格式，语义信息稀疏，向量搜索难以匹配 |
| 全文搜索（关键词） | 文档 2、3 | **文档 1、4** | 精确匹配"向量索引"命中文档 2 和 3；文档 1 用的是"向量搜索"、文档 4 用的是"向量搜索"，关键词不匹配，被遗漏 |
| **混合搜索** | **文档 1、2、3、4** | — | 向量搜索召回 1、3、4（语义相关），全文搜索召回 2、3（关键词匹配），融合后 1、2、3、4 全部命中 |

**关键词搜索会遗漏同义表述，语义搜索会遗漏精确术语，混合搜索才能兼顾"搜得全"和"搜得准"。**

### 2.2 现有方案的局限

在实际落地混合搜索时，常见的方案有这些，各有其适用场景和局限：

| 方案 | 特点与局限 |
|------|----------|
| 纯向量搜索 | 向量搜索能力强大，但在关键词精确匹配、标量过滤方面需要额外组件配合 |
| 纯全文搜索 | 关键词搜索效果优秀，但缺乏语义理解能力，同义词、近义词场景召回不足 |
| 单套数据库管理向量数据和全文数据，应用层拼接 | 数据库提供向量和全文搜索能力但不提供内置融合，需在业务代码中分别调用再手动合并排序，开发成本高、融合质量依赖经验 |
| 向量数据库 + 关系数据库分离部署 | 底层多套系统分别提供向量检索、关系存储与全文检索能力，组合部署引入运维复杂度，数据同步和事务一致性需额外关注 |

这些方案的核心问题在于：**搜索能力分散在不同系统中，难以在数据库内核层面完成统一索引构建和结果融合。**

### 2.3 Hybrid Search 的价值

**Hybrid Search 在数据库内核层面统一多模态搜索能力。**

| 收益维度 | 说明 |
|----------|------|
| 融合效果 | 内置 RRF/Weighted Sum 等算法，内核级优化排序质量 |
| 开发效率 | 一条 SQL 替代应用层多路合并逻辑，既减少了开发工作量，也降低了拼接带来的额外出错风险 |
| 运维简化 | 单一数据库替代"向量数据库 + 关系数据库"多系统拼装 |
| 数据一致性 | ACID 事务保证搜索数据与业务数据天然一致 |

## 3. 快速开始

### 3.1 创建堆表

Hybrid Search 仅支持堆表（ORGANIZATION HEAP）。建表时声明向量列（`VECTOR`）、JSON 列和 Array 列，用于存储多模态数据：

```sql
CREATE TABLE articles(
    id INT,
    title VARCHAR(255),              -- 文本标题，用于全文搜索
    content TEXT,                     -- 文本内容，用于全文搜索
    embedding VECTOR(4),              -- 向量列，维度与示例数据保持一致（生产环境根据 embedding 模型调整）
    title_embedding VECTOR(4),         -- 向量列，维度与示例数据保持一致（生产环境根据 embedding 模型调整）
    tags JSON,                        -- JSON 标签，用于标量过滤
    categories ARRAY(VARCHAR(100))   -- 数组分类，用于标量过滤
) ORGANIZATION = HEAP;
```

### 3.2 创建索引

为需要搜索的列创建对应索引。向量搜索需要向量索引（推荐 HNSW_SQ，在内存与性能间取得平衡），全文搜索需要全文索引，JSON/Array 列的过滤建议创建 Search Index 加速：

```sql
-- 向量索引：用于语义相似度搜索
CREATE VECTOR INDEX idx_embedding ON articles(embedding)
  WITH (distance=l2, type=hnsw_sq, lib=vsag);
CREATE VECTOR INDEX idx_title_embedding ON articles(title_embedding)
  WITH (distance=l2, type=hnsw_sq, lib=vsag);

-- 全文索引：用于关键词匹配
CREATE FULLTEXT INDEX idx_title on articles(title);

-- Search Index：加速 JSON/Array 列的标量过滤
ALTER TABLE articles ADD SEARCH INDEX idx_tags(tags);
ALTER TABLE articles ADD SEARCH INDEX idx_categories(categories);
```

### 3.3 插入示例数据

准备几条测试数据，包含不同主题的机器学习相关文章：

```sql
INSERT INTO articles VALUES (
    1,
    'Machine Learning Basics',
    'Introduction to machine learning algorithms and concepts',
    '[0.1, 0.2, 0.3, 0.4]',
    '[0.1, 0.2, 0.3, 0.4]',
    '{"level": "beginner", "topic": "ml"}',
    ARRAY('AI', 'ML')
);

INSERT INTO articles VALUES (
    2,
    'Deep Learning Guide',
    'Comprehensive guide to neural networks and deep learning',
    '[0.15, 0.25, 0.35, 0.45]',
    '[0.15, 0.25, 0.35, 0.45]',
    '{"level": "advanced", "topic": "dl"}',
    ARRAY('AI', 'Deep Learning')
);

INSERT INTO articles VALUES (
    3,
    'Python Programming',
    'Learn Python programming from scratch',
    '[0.05, 0.1, 0.15, 0.2]',
    '[0.05, 0.1, 0.15, 0.2]',
    '{"level": "beginner", "topic": "python"}',
    ARRAY('Programming')
);

INSERT INTO articles VALUES (
    4,
    'Database Systems',
    'Introduction to relational database management systems',
    '[0.2, 0.1, 0.3, 0.2]',
    '[0.2, 0.1, 0.3, 0.2]',
    '{"level": "intermediate", "topic": "database"}',
    ARRAY('Database', 'SQL')
);
```

### 3.4 执行混合查询

```sql
SELECT id, title, __score
FROM HYBRID_SEARCH(
  TABLE articles,
  '{
    "knn": {
      "field": "embedding",
      "query_vector": "[0.1,0.2,0.3,0.4]",
      "k": 5
    },
    "query": {
      "match": {"title": "learning"}
    },
    "rank": {
      "rrf": {"rank_constant": 60}
    },
    "size": 5
  }'
);
```

这条 SQL 的每个部分作用如下：

| 子句 | 作用 |
|------|------|
| `HYBRID_SEARCH(TABLE articles, ...)` | 指定要搜索的表 |
| `"knn": {...}` | **向量搜索**：在 `embedding` 列上，用 `[0.1,0.2,0.3,0.4]` 向量找最相似的 5 条 |
| `"query": {...}` | **全文搜索**：在 `title` 列上，匹配包含 "learning" 的文档 |
| `"rank": {...}` | **融合排序**：用 RRF 算法合并两路结果，`rank_constant=60` 控制排名权重 |
| `"size": 5` | **返回数量**：最终返回融合后的前 5 条结果 |
| `__score` | 融合后的最终分数，越高表示越匹配 |

一句话总结：**`knn` 负责语义搜索，`query` 负责关键词搜索，`rank` 负责融合排序。**

## 4. 查询能力详解

### 4.1 查询模式总览

```
你的查询需要什么？
├─ 语义相似 ──→ knn 子句（向量搜索）
├─ 关键词匹配 ──→ query 子句（全文搜索）
├─ 结构化过滤 ──→ filter 子句（标量过滤）
└─ 组合需求 ──→ 多子句 + rank 融合
```

| 查询模式 | 查询语句结构 | 适用场景 |
|---------|----------|----------|
| 单路向量 | 仅 `knn` | 语义相似度搜索 |
| 单路全文 | 仅 `query` | 关键词/短语匹配 |
| 标量过滤 | `query.bool.filter` | 结构化条件筛选 |
| 混合查询 | `knn` + `query` + `rank` | 语义 + 关键词 + 过滤组合 |

查询语句基本格式：

```sql
HYBRID_SEARCH(TABLE table_name, 'DSL_STRING')
```

查询语句 DSL_STRING 的顶层结构：

```json
{
  "knn": { ... },       // 向量搜索（可选，也可为数组表示多路向量）
  "query": { ... },     // 查询条件（可选，支持全文、标量、Array、JSON）
  "rank": { ... },      // 融合算法（knn 和 query 同时存在时有效）
  "from": 0,            // 分页偏移（默认 0）
  "size": 10,           // 返回结果数（默认 10）
  "min_score": 0.0      // 最低分数阈值（可选）
}
```

`query` 子句支持以下类型查询，各有不同的放置位置和相关性评分规则。**相关性评分**指子句是否参与 BM25 等分数的计算——参与评分的子句影响结果排序，不参与的仅做过滤，只决定"哪些文档入选"而不影响排序。

| 类别 | 子句 | 可用位置 | 相关性评分 | 说明 |
|------|------|---------|----------|------|
| 全文搜索 | match / match_phrase / multi_match / query_string | query 顶层、bool 内任意子句 | 顶层和 must/should 参与，filter/must_not 不参与 | 关键词/短语匹配，参与 BM25 相关性评分 |
| 组合查询 | bool | query 顶层、bool 内任意子句 | 子句决定 | must/should 仅支持全文类子句且参与评分，filter/must_not 支持所有类型但不参与评分 |
| 标量过滤 | term / terms / range | query 顶层、bool.filter/must_not、knn.filter | 否 | 精确匹配、范围过滤 |
| Array 过滤 | array_contains / array_contains_all / array_overlaps | query 顶层、bool.filter/must_not、knn.filter | 否 | 数组列过滤 |
| JSON 过滤 | json_contains / json_member_of / json_overlaps | query 顶层、bool.filter/must_not、knn.filter | 否 | JSON 列过滤 |
| JSON 路径提取 | 字段名.路径（如 doc_json.name） | 结合 term/terms/range 使用 | 否 | 从 JSON 中提取标量值 |

**组合规则**：

- 全文搜索子句可在query内的任何位置使用；bool.filter 中的全文子句仅做过滤，不参与评分
- 标量过滤、Array 过滤、JSON 过滤**不能**放在 bool.must/bool.should 中（会报错），其余位置可用（query 顶层、bool.filter、bool.must_not、knn.filter）
- 嵌套 bool 的评分豁免：如果 bool 处于外层 filter 或 must_not 内，其内部 must/should 也不参与评分，此时标量/Array/JSON 子句可以出现在嵌套的 must/should 中
- knn.filter 与 query.bool.filter **不共享**：如果全文和向量都需要相同的过滤条件，必须分别指定

### 4.2 向量搜索

> **优势**：能理解语义相似性，召回同义词、近义词相关结果，无需精确关键词匹配。
> **劣势**：可能遗漏精确术语，对专有名词匹配精度不如关键词搜索；需要预计算向量嵌入。

`knn` 完整结构：

```json
{
  "knn": {
    "field": "embedding",              // 必填，向量列名
    "query_vector": "[0.1,0.2,...]",   // 必填，查询向量，推荐字符串格式
    "k": 10,                           // 必填，返回结果数 [1, 16384]
    "boost": 1.0,                      // 可选，融合权重，默认 1.0，范围 >= 0
    "similarity": 0.8,                 // 可选，相似度阈值 [0.0, 1.0]，不支持 IP 距离
    "filter": { ... },                 // 可选，过滤条件，语法同 query.bool，不参与评分
    "search_options": {                // 可选，向量查询调优参数
      "ef_search": 64,                 //   HNSW 搜索宽度 [1, 1000]，默认 1000
      "refine_k": 4.0,                 //   精细搜索倍率 [1.0, 1000.0]，仅 HNSW_BQ 索引支持
      "filter_mode": "pre",            //   过滤模式：pre / pre-knn / pre-brute / post / post-index-merge
      "drop_ratio_search": 0.0,        //   稀疏向量搜索丢弃率 [0.0, 0.9]
    }
  }
}
```

| 子句 | 作用 |
|------|------|
| `field` + `query_vector` + `k` | 基础向量搜索：在 `embedding` 列上用查询向量找最相似的 `k` 条 |
| `boost` | 融合权重，用于 WRRF/Weighted Sum 场景 |
| `similarity` | 相似度阈值，仅返回相似度 >= 0.5 的结果（不支持 IP 距离） |
| `filter` | 标量过滤，语法与 `query.bool` 相同，不参与评分 |
| `search_options` | 向量查询调优参数 |

#### knn 参数

| 参数 | 必填 | 默认值 | 取值范围 | 说明 |
|------|------|--------|----------|------|
| `field` | 是 | - | - | 向量列名 |
| `query_vector` | 是 | - | - | 查询向量，推荐字符串格式 `"[0.1,0.2,...]"` |
| `k` | 是 | - | [1, 16384] | 返回结果数 |
| `boost` | 否 | 1.0 | >= 0 或 > 0，详见具体规则 | 融合权重（WRRF/Weighted Sum 场景） |
| `similarity` | 否 | - | [0.0, 1.0] | 相似度阈值，仅返回相似度 >= 该值的结果；不支持 IP 距离 |
| `filter` | 否 | - | - | 过滤条件，语法同 `query.bool`，不参与评分 |
| `search_options` | 否 | - | - | 向量查询调优参数，详见下方 |

#### search_options 参数

| 参数 | 默认值 | 取值范围 | 适用索引类型 | 说明 |
|------|--------|----------|--------------|------|
| `ef_search` | 1000 | [1, 1000] | 所有 HNSW 索引 | HNSW 搜索宽度，值越大召回率越高但速度越慢 |
| `refine_k` | 1.0 | [1.0, 1000.0] | **仅 HNSW_BQ** | 精细搜索倍率，用于量化向量索引的重排 |
| `filter_mode` | 自适应 | 见下方 | 所有索引 | 过滤模式 |
| `drop_ratio_search` | 0.0 | [0.0, 0.9] | 稀疏向量索引 | 稀疏向量搜索丢弃率 |

**filter_mode 选项**：

| 值 | 含义 | 适用场景 |
|----|------|----------|
| `"pre"` | 自适应先过滤后向量 | 默认策略，根据选择性自动选择 |
| `"pre-knn"` | 先过滤后向量 + KNN | 过滤条件选择性高时 |
| `"pre-brute"` | 先过滤后向量 + 暴力扫描 | 数据量小（< 2 万行）时 |
| `"post"` | 先向量后过滤 | 过滤条件选择性低时 |
| `"post-index-merge"` | 先向量后过滤 + 索引合并 | 有辅助索引时 |

#### 多路向量搜索

`knn` 支持数组形式，实现多路向量搜索。每路向量搜索独立执行，结果按融合算法合并：

```sql
SELECT id, title, __score
FROM HYBRID_SEARCH(
  TABLE articles,
  '{
    "knn": [
      {
        "field": "embedding",
        "query_vector": "[0.1,0.2,0.3,0.4]",
        "k": 5,
        "boost": 0.7
      },
      {
        "field": "title_embedding",
        "query_vector": "[0.4,0.3,0.2,0.1]",
        "k": 5,
        "boost": 0.3
      }
    ],
    "size": 5
  }'
);
```

多路向量搜索的要点：
- 每路 `knn` 的 `field` 可以是不同向量列
- 每路可独立设置 `boost`、`filter`、`search_options` 等参数
- 各路的 `filter` 不共享，需要分别指定
- 多路向量的结果取并集，按分数融合算法排名

### 4.3 全文搜索

> **优势**：精确匹配关键词，对专有名词、型号、ID 等精确术语召回率高；支持 BM25 相关性评分。
> **劣势**：无法理解语义，同义词、近义词需要额外配置；可能返回关键词匹配但语义不相关的结果。

`query` 全文搜索结构：

```json
{
  "query": {
    // 全文搜索（参与评分）
    "match": { ... },                  // 单字段匹配
    "match_phrase": { ... },           // 短语匹配
    "multi_match": { ... },            // 多字段匹配
    "query_string": { ... },           // 查询字符串

    // 组合查询
    "bool": { ... }                    // 布尔组合，可嵌套全文和标量过滤
  }
}
```

> 标量过滤（term/terms/range）、Array 过滤、JSON 过滤的用法见 4.4 节。

#### match 查询

单字段全文匹配，支持简写和完整格式：

```sql
-- 简写格式
{"match": {"title": "machine learning"}}

-- 完整格式：
{"match": {"title": {"query": "machine learning", "boost": 2.0, "operator": "and", "minimum_should_match": 2}}}
```

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| query | 是 | - | 查询文本 |
| boost | 否 | 1.0 | 权重，query 内的第一层对象的 boost 需 > 0， 其他情况 >= 0 |
| operator | 否 | "or" | 分词后的匹配逻辑，"and" 要求所有词都匹配 |
| minimum_should_match | 否 | 1 | 分词后最小匹配词数，只接受非负整数 |

#### match_phrase 查询

短语匹配，词序必须一致：

```sql
{"match_phrase": {"title": {"query": "machine learning", "slop": 2, "boost": 1.5}}}
```

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| query | 是 | - | 查询短语 |
| slop | 否 | 0 | 允许词项间的距离，0 表示必须紧邻且顺序一致 |
| boost | 否 | 1.0 | 权重，query 内的第一层对象的 boost 需 > 0， 其他情况 >= 0 |

#### multi_match 查询

跨多字段全文匹配，支持字段权重语法 `"字段名^权重"`：

```sql
{
  "multi_match": {
    "query": "machine learning",
    "fields": ["title^2.0", "content"],
    "type": "best_fields",
    "operator": "or",
    "minimum_should_match": 1,
    "boost": 1.5
  }
}
```

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| fields | 是 | - | 字段列表，支持权重语法如 `"title^2.0"`，未指定则默认 1.0 |
| query | 是 | - | 查询文本 |
| type | 否 | "best_fields" | 匹配策略：best_fields / most_fields |
| operator | 否 | "or" | 分词后的匹配逻辑 |
| minimum_should_match | 否 | 1 | 分词后最小匹配词数 |
| boost | 否 | 1.0 | 权重，query 内的第一层对象的 boost 需 > 0， 其他情况 >= 0 |

#### query_string 查询

支持词权重语法 `"词^权重"`，用空格分隔多个词项（默认 OR 逻辑）：

```sql
{
  "query_string": {
    "query": "database^2.0 optimization",
    "fields": ["title^1.5", "content"],
    "type": "best_fields",
    "default_operator": "and",
    "minimum_should_match": 1,
    "boost": 1.0
  }
}
```

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| query | 是 | - | 查询文本，支持词权重语法如 `"word^0.3"` |
| fields | 是 | - | 字段列表，支持权重语法如 `"title^2.0"` |
| type | 否 | "best_fields" | 匹配策略：best_fields / most_fields |
| default_operator | 否 | "or" | 分词后的默认匹配逻辑（注意：与 match/multi_match 的 `operator` 参数名不同） |
| minimum_should_match | 否 | 1 | 分词后最小匹配词数 |
| boost | 否 | 1.0 | 权重，query 内的第一层对象的 boost 需 > 0， 其他情况 >= 0 |

> **注意**：`query_string.query` 的查询文本中出现以下内容会触发错误：
> - **保留关键字**（不区分大小写）：`and`, `or`, `not`, `to`
> - **保留字符**：`+ - & | ! = < > ( ) [ ] { } " ~ * ? : \ /`
>
> 例如 `"query": "database and optimization"` 会因 `and` 触发 `ERROR 1210: query contains reserved keyword`；`"query": "hello (world)"` 会因 `(` 触发 `ERROR 1210: query contains reserved character`。
> 如需使用这些词或字符，请改用 `match` 系列或 `bool` 查询组合。

#### bool 组合查询

```sql
{
  "bool": {
    "must": [
      {"match": {"title": "learning"}}
    ],
    "should": [
      {"match": {"content": "algorithm"}}
    ],
    "must_not": [
      {"match": {"title": "deep"}}
    ],
    "filter": [
      {"range": {"id": {"gte": 1, "lte": 5}}}
    ],
    "minimum_should_match": 1,
    "boost": 1.2
  }
}
```

| 子句 | 评分 | 必填 | 说明 |
|------|------|------|------|
| must | 是 | 否（至少一个正向条件） | 必须匹配，参与评分 |
| should | 是 | 否 | 可选匹配，参与评分 |
| must_not | 否 | 否 | 排除匹配，不参与评分；需存在至少一个正向条件才可使用 |
| filter | 否 | 否（至少一个正向条件） | 必须匹配，不参与评分 |
| minimum_should_match | - | 否 | should 子句最低匹配数；should 存在且 must/filter 都不存在时默认 1，否则默认 0 |
| boost | - | 否 | 权重值，**必须 > 0**，默认 1.0 |

### 4.4 标量过滤

> **优势**：精确筛选结构化条件（价格范围、时间区间、标签等），过滤性能高。Array/JSON 列可利用 Search Index 加速，标量列通过普通索引（如 B-tree）加速。
> **劣势**：仅做布尔判断不计入相关性评分，不能单独完成语义或关键词搜索，需配合其他搜索方式使用。

标量过滤条件不参与评分、不支持 boost，可放在 query 顶层、`bool.filter`/`bool.must_not` 或 `knn.filter` 中，不能放在 `bool.must`/`bool.should` 中。

#### range 范围查询

```sql
{"range": {"id": {"gte": 3, "lte": 100}}}
```

| 操作符 | 说明 |
|--------|------|
| gt | 大于 |
| gte | 大于等于 |
| lt | 小于 |
| lte | 小于等于 |

支持数值和日期类型。

#### term / terms 精确匹配

```sql
-- 单值匹配
{"term": {"id": 1}}

-- 多值匹配
{"terms": {"id": [1, 3, 5]}}
```

| 操作符 | 说明 | 值格式 |
|--------|------|--------|
| term | 精确匹配单个值 | 单个值 |
| terms | 匹配多个值中的任意一个 | 数组 |

#### Array 过滤

Array 列过滤放在 query 顶层，支持三种操作符：

```sql
-- 包含指定元素
{"array_contains": {"categories": "ai"}}

-- 与指定数组有交集
{"array_overlaps": {"categories": ["ai", "cloud"]}}

-- 包含指定数组的所有元素
{"array_contains_all": {"categories": ["ai", "ml"]}}
```

| 操作符 | 说明 | 值格式 |
|--------|------|--------|
| array_contains | 数组包含指定元素 | 单个值 |
| array_overlaps | 数组与指定数组有交集 | 数组 |
| array_contains_all | 数组包含指定数组的所有元素 | 数组 |

> **注意**：建议为对应列创建 Search Index 以加速 Array 过滤查询。Array 过滤不能放在 `bool.must`/`bool.should` 中。

#### JSON 过滤

JSON 列过滤放在 query 顶层，支持三种操作符，均通过 `candidate` 指定候选值、可选 `path` 指定 JSON 路径：

```sql
-- json_contains：检查 doc_json 是否包含 {"name": "doc2"}
{"json_contains": {"doc_json": {"candidate": {"name": "doc2"}, "path": "$"}}}

-- json_member_of：检查 doc_json.name 值是否属于候选数组
{"json_member_of": {"doc_json": {"candidate": "doc2", "path": "$.name"}}}

-- json_overlaps：检查 doc_json 的 $.tags 路径是否与候选数组有交集
{"json_overlaps": {"doc_json": {"candidate": ["database", "mysql"], "path": "$.tags"}}}
```

| 操作符 | 说明 | candidate 格式 |
|--------|------|---------------|
| json_contains | JSON 文档是否包含候选值 | JSON 对象或其字符串形式 |
| json_member_of | JSON 值是否属于候选数组 | JSON 值或其字符串形式 |
| json_overlaps | JSON 文档与候选值是否有交集 | JSON 数组或其字符串形式 |

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| candidate | 是 | - | 候选值，可以是 JSON 对象或其字符串形式（需注意转义） |
| path | 否 | `"$"` | JSON 路径，如 `$.tags`，默认根路径 |

> **注意**：建议为 JSON 列创建 Search Index 以加速过滤。JSON 过滤不能放在 `bool.must`/`bool.should` 中。

#### JSON 路径提取

在 `term`、`terms`、`range` 等标量过滤中，可以通过 `字段名.路径` 语法提取 JSON 字段中的嵌套值：

```sql
-- term：精确匹配 JSON 路径值
{"term": {"doc_json.name": "doc2"}}

-- range：范围过滤 JSON 路径值
{"range": {"doc_json.metadata.score": {"gte": 50}}}

-- terms：多值匹配 JSON 路径值
{"terms": {"doc_json.name": ["doc1", "doc2", "doc3"]}}
```

> **注意**：`doc_json.name` 等价于 `json_extract(doc_json, '$.name')`。

### 4.5 混合查询与融合算法

> **优势**：兼顾语义理解和关键词精确匹配，召回率和准确率同时提升；内置多种融合算法，无需应用层拼接。
> **劣势**：需要同时维护向量索引和全文索引，存储成本增加；融合算法参数需要调优.

#### 4.5.1 哪些搜索可以融合

Hybrid Search 的 `knn` 和 `query` 子句可同时存在，**只要任意一方存在即可执行查询**。两方都指定时，`rank` 控制融合方式；仅一方指定时，按该方自身的分数返回结果。

`knn` 支持数组形式的多路向量搜索，`query` 为单路（多条件通过 `bool.must`/`bool.should` 组合）。标量过滤（`term`/`terms`/`range`/`array_*`/`json_*`）不参与评分，仅筛选结果。

| 搜索类型 | 路数 | 参与评分 | 说明 |
|----------|------|---------|------|
| 向量搜索（`knn`）| 1~N 路 | 是 | 单路对象或多路数组形式，每路独立产生分数 |
| 全文搜索（`query`）| 1 路 | 是 | `match`/`match_phrase`/`multi_match`/`query_string` 产生 BM25 分数 |
| 标量过滤（`filter`/`term`/`terms`/`range`/`array_*`/`json_*`）| 不限 | 否 | 可放在 `knn.filter` 或 `query.bool.filter`/`query.bool.must_not` 中 |

**常用组合模式**：

| 模式 | knn | query | filter | 说明 |
|------|:---:|:-----:|:------:|------|
| 纯单路向量 | 对象 | - | - | 仅向量语义搜索 |
| 纯多路向量 | 数组 | - | - | 多个向量列各自搜索后融合 |
| 纯全文 | - | match等 | - | 仅关键词匹配搜索 |
| 纯标量 | - | - | bool.filter/array_*/json_* | 仅结构化条件筛选，不产生评分 |
| 向量 + 全文 | 对象/数组 | match等 | - | 语义 + 关键词两路融合 |
| 向量 + 标量 | 对象/数组 | - | knn.filter 或 bool.filter | 向量搜索 + 结构化条件过滤 |
| 全文 + 标量 | - | match等 | bool.filter | 关键词搜索 + 结构化条件过滤 |
| 向量 + 全文 + 标量 | 对象/数组 | match等 | filter（knn 或 bool 内）| 三者组合，覆盖最复杂搜索需求 |

> **什么是「一路」？** `knn` 数组中的每个元素是独立的一路向量搜索——例如同时搜文本向量和图片向量是 2 路。`query` 中的多条件（如 `bool.must` 内多个 `match`）仍算作 1 路全文搜索，它们在单路内通过 bool 组合，而非多路独立融合。标量过滤（`filter`）不产生评分，不参与融合排序。

> **注意**：仅标量过滤（无 knn 无全文 match）可以执行，但结果无相关性排序，仅按表的自然顺序返回。如需要排序，至少指定一路向量或全文。

#### 4.5.2 向量 + 全文融合

```sql
SELECT id, title, __score
FROM HYBRID_SEARCH(
  TABLE articles,
  '{
    "knn": {
      "field": "embedding",
      "query_vector": "[0.1,0.2,0.3,0.4]",
      "k": 5,
      "boost": 1.0
    },
    "query": {
      "match": {
        "title": {
          "query": "learning",
          "boost": 1.0
        }
      }
    },
    "size": 5
  }'
);
```

同时指定 `knn` 和 `query` 时，默认使用 Weighted Sum 融合——两路分数直接相加，各路权重默认 1.0。

#### 4.5.3 多路向量 + 全文融合

当有多列向量数据时（如文本向量、图像向量），可以同时进行多路向量搜索：

```sql
SELECT id, title, __score
FROM HYBRID_SEARCH(
  TABLE articles,
  '{
    "knn": [
      {
        "field": "embedding",
        "query_vector": "[0.1,0.2,0.3,0.4]",
        "k": 10,
        "boost": 0.7
      },
      {
        "field": "title_embedding",
        "query_vector": "[0.3,0.4,0.2,0.1]",
        "k": 10,
        "boost": 0.3
      }
    ],
    "query": {
      "match": {"title": "手机"}
    },
    "rank": {"rrf": {"rank_constant": 60}},
    "size": 10
  }'
);
```

**注意事项**：
- 每路向量可设置不同 `boost` 权重（上例中文本权重 0.7，图像权重 0.3）
- 各路 `filter` 独立，需要时分别指定
- 多路向量结果先取并集，再与全文结果融合

#### 4.5.4 融合算法详解

混合搜索的核心问题是：**向量搜索的产物和全文搜索的产物产生的逻辑不同，怎么合并才能最好地贴近请求的原意？**

- 向量搜索返回的是语义的距离值（如 L2 距离 0~∞，余弦相似度 -1~1）
- 全文搜索返回的是 BM25 分数（通常 0~30）

直接把两种分数加在一起，就像把摄氏度和华氏度相加——数字虽然能算出来，但是无法很好的反应温度。融合算法就是解决这个"单位不同"的问题，将两种产物结合在一起，使得结果更符合请求。

```
你的场景属于哪种？
├─ 两路搜索的结果质量差不多 ──→ Weighted Sum（默认，直接加）
├─ 不确定哪路搜索的结果更好 ──→ RRF（只看排名，不看分数）
├─ 想让某路搜索的结果更优先 ──→ WRRF（排名融合 + 加权）
└─ 发现某路结果总是霸占前排 ──→ Weighted Sum + MinMax（先归一化再加）
```

| 算法 | 查询语句语法 | 核心思路 | 适用场景 |
|------|----------|---------|----------|
| Weighted Sum | 默认 / `"rank":{"weighted_sum":{"normalizer":"none"}}` | 直接加权求和——两路分数直接相加 | 两路搜索的结果质量差不多 |
| Weighted Sum + MinMax | `"rank":{"weighted_sum":{"normalizer":"minmax"}}` | 先归一化再加——把两路分数都缩到 0~1 再相加 | 某路结果总是霸占前排 |
| RRF | `"rank":{"rrf":{"rank_constant":60}}` | 只看排名不看分数——按排名位置计算分数 | 不确定哪路搜索更好时最稳妥 |
| WRRF | RRF + 各路 boost | 排名融合 + 差异化权重——在 RRF 基础上强调某路 | 想让某路搜索的结果更优先 |

**选择建议**：拿不准时优先用 RRF，它不受分数范围影响，无需调参就能正常工作。

**融合权重（boost）设置位置**：

| 位置 | 语法 | 取值范围 | 说明 |
|------|------|---------|------|
| `knn` 层级 | `"knn": {"boost": 1.0}` | >= 0 | 控制向量搜索路权重 |
| `knn` 数组元素 | `"knn": [{"boost": 0.7}, ...]` | >= 0 | 多路向量时每路独立权重 |
| 全文子句的第一级对象内 | `"match": {"title": {"boost": 1.0}}` | >= 0 | match/multi_match 等子句内 |
| 全文子句**非**第一级对象内 | `"match": {"title": {"boost": 1.0}}` | > 0 | match/multi_match 等子句内 |
| `bool` 层级 | `"bool": {"boost": 1.0}` | > 0 | 控制整个 bool 查询权重 |

> **注意**：`query` 顶层不支持 `boost` 参数；`knn.boost` 与全文子句 `boost` 是乘法关系。

**RRF 融合**

**设计思路**：RRF（Reciprocal Rank Fusion）的核心思想是——**放弃分数，只看排名**。不管向量搜索的分数是 0.95 还是全文搜索的分数是 28.5，RRF 只关心"这个文档在第几名"。排名越靠前，贡献的分数越高；排名越靠后，衰减越平缓。这样就从根源上消除了"分数单位不同"的问题。

```sql
SELECT id, title, __score
FROM HYBRID_SEARCH(
  TABLE articles,
  '{
    "knn": {
      "field": "embedding",
      "query_vector": "[0.1,0.2,0.3,0.4]",
      "k": 5,
      "boost": 1.0
    },
    "query": {
      "match": {
        "title": {
          "query": "learning",
          "boost": 1.0
        }
      }
    },
    "rank": {
      "rrf": {
        "rank_constant": 60,
        "rank_window_size": 100
      }
    },
    "size": 5
  }'
);
```

RRF 公式：`score = Σ(weight_i × 1 / (rank_constant + rank_i))`

- `rank_constant`：默认 60，范围 >= 1。它控制排名靠前的结果优势有多大——值越小，Top 1 和 Top 10 的差距越大；值越大，排名间的差距越平缓
- `rank_window_size`：排名窗口大小，默认等于 `from + size`，必须 >= `size`。控制融合时的候选集范围——增大可以扩大候选集提升召回率，但增加计算开销
- 各路结果按原始分数降序排列后分配排名

**rank_constant 怎么选？**
- 默认 60 适合大多数场景，不需要调整
- 如果你希望排名靠前的结果优势更明显（更"精英"），可以调小到 10~30
- 如果你希望排名间的差距更平缓（更"民主"），可以调大到 100+

**WRRF 融合（加权 RRF）**

**设计思路**：RRF 默认对两路搜索一视同仁，但实际场景中你往往更信任某一路。比如 RAG 场景中语义理解通常比关键词匹配更重要，电商搜索中商品名称的精确匹配通常比描述的语义相似更重要。WRRF 在 RRF 的基础上给每路搜索设一个 `boost` 权重，让你能表达"我更看重哪一路"。

```sql
SELECT id, title, __score
FROM HYBRID_SEARCH(
  TABLE articles,
  '{
    "knn": {
      "field": "embedding",
      "query_vector": "[0.1,0.2,0.3,0.4]",
      "k": 5,
      "boost": 2.0
    },
    "query": {
      "match": {
        "title": {
          "query": "learning",
          "boost": 1.0
        }
      }
    },
    "rank": {
      "rrf": {
        "rank_constant": 60,
        "rank_window_size": 100
      }
    },
    "size": 5
  }'
);
```

上例中向量搜索的 `boost=2.0`，全文搜索的 `boost=1.0`，意味着向量搜索排名靠前的结果对最终分数的贡献是全文搜索的两倍。

> **注意**：`boost` 可以设置在 `knn` 层级或全文子句（如 `match`/`multi_match`）内部。`knn.boost` 控制向量搜索的权重，全文子句内的 `boost` 控制该子句的权重（两者是乘法关系）。`query` 顶层不支持 `boost` 参数。

**boost 怎么选？**
- 1.0 = 一视同仁（默认）
- 1.5~2.0 = 适度侧重，适合"某一路更重要但不排斥另一路"的场景
- 3.0+ = 强调某一路，适合"几乎只看某一路，另一路做补充"的场景

**Weighted Sum + MinMax 归一化**

**什么时候需要归一化？**
- 如果你发现某一路的结果总是排在前面，不是因为更相关，而是因为分数天然更高，就需要归一化
- 如果你不确定是否需要，用 RRF 更稳妥——RRF 天然不受分数范围影响

**设计思路**：Weighted Sum 是最直观的融合——把两路分数加起来。但直接相加有个问题：如果向量搜索的分数范围是 0~1，而全文搜索的分数范围是 0~30，那全文搜索的分数天然就压过了向量搜索，即使向量搜索认为某个文档非常相关，也抵不过全文搜索的一个中等分数。MinMax 归一化的作用是先把两路分数都缩放到 0~1 的同一区间，避免某一路分数完全主导了查询。

```sql
SELECT id, title, __score
FROM HYBRID_SEARCH(
  TABLE articles,
  '{
    "knn": {
      "field": "embedding",
      "query_vector": "[0.1,0.2,0.3,0.4]",
      "k": 5,
      "boost": 0.7
    },
    "query": {
      "match": {
        "title": {
          "query": "learning",
          "boost": 0.3
        }
      }
    },
    "rank": {
      "weighted_sum": {
        "normalizer": "minmax",
        "rank_window_size": 100
      }
    },
    "size": 5
  }'
);
```

归一化公式：`normalized_score = (score - min) / (max - min)`

当 max 与 min 差值极小时（< 1e-6），归一化分数默认为 1.0。

#### 4.5.5 分页与过滤

**min_score 分数过滤**

仅返回融合分数 >= min_score 的结果，过滤掉相关度低的低分文档：

```sql
SELECT id, title
FROM HYBRID_SEARCH(
  TABLE articles,
  '{
    "knn": {
      "field": "embedding",
      "query_vector": "[0.1,0.2,0.3,0.4]",
      "k": 5,
      "boost": 0.7
    },
    "query": {
      "match": {
        "title": {
          "query": "learning",
          "boost": 0.3
        }
      }
    },
    "min_score": 0.5,
    "size": 5
  }'
);
```

**from / size 分页**

```sql
SELECT id, title
FROM HYBRID_SEARCH(
  TABLE articles,
  '{
    "knn": {
      "field": "embedding",
      "query_vector": "[0.1,0.2,0.3,0.4]",
      "k": 5
    },
    "from": 2,
    "size": 3,
    "min_score": 0.1
  }'
);
```

- `from`：偏移量，默认 0
- `size`：返回结果数，默认 10
- **限制**：`from + size <= 10000`

**向量 + 全文 + 标量过滤（完整示例）**

```sql
SELECT id, title
FROM HYBRID_SEARCH(
  TABLE articles,
  '{
    "knn": {
      "field": "embedding",
      "query_vector": "[0.1,0.2,0.3,0.4]",
      "k": 5,
      "boost": 1.5
    },
    "query": {
      "bool": {
        "must": [
          {"match": {"title": "learning"}}
        ],
        "filter": [
          {"range": {"id": {"gte": 1, "lte": 8}}}
        ],
        "boost": 1.0
      }
    },
    "rank": {
      "rrf": {"rank_constant": 60}
    },
    "size": 5
  }'
);
```

## 5. 实战场景与最佳实践

> 前四章讲清了混搜的能力边界和语法。这一章换一个角度：**如果没有混搜，实现以下场景会有多麻烦**。
>
> 下面用一个典型 RAG 知识库场景为例子，体现混搜的**简单高效**。

### 5.1 RAG / AI 对话系统

#### 5.1.1 场景需求

用户向 AI 提一个自然语言问题，如「OceanBase 分布式事务怎么保证一致性」。系统需要从知识库中找出最相关的文档片段，喂给 LLM 生成回答。

这个场景的核心诉求：

- **语义覆盖**：用户问题不会恰好匹配文档标题，必须靠语义理解找到意思相近的文档
- **关键词兜底**：专有名词（如"两阶段提交""全局快照"）语义模型可能遗漏，需要精确关键词命中
- **召回率优先**：宁可多召回几篇让 LLM 自己挑，也别漏掉关键信息

#### 5.1.2 传统做法

不使用混合搜索时，典型方案是 LLM 扩写、改写、转换 + 向量和全文索引双查，应用层合并：

```
步骤 1：将用户的问题通过 LLM 进行扩写 -> 三到五个衍生问题，提高查询命中率
步骤 2：将每个衍生问题向量化，调用向量索引查语义相近的文档 -> Top 20 × 衍生问题个数
步骤 3：提取问题中的关键词，调用全文索引查关键词匹配的文档 -> Top 20 × 衍生问题个数
步骤 4：应用层合并去重（两路可能有重叠文档）并手动实现 RRF 排序，取 Top 5 返回
```

这种做法的问题：

- 两个系统独立查询，应用代码复杂度高
- 在计算层返回结果后做融合的效率低，数据库内核在多路查询时可以做存储查询优化，加速查询效率、降低硬件开销

#### 5.1.3 使用混合搜索

一条 SQL 替代上述步骤 2 至步骤 4。建表包含向量列和全文索引列，查询时同时在向量路和全文路召回，RRF 自动融合：

```sql
-- 1. 建表（示例使用 4 维向量，实际使用时根据 embedding 模型调整）
CREATE TABLE rag_docs(
    id INT,
    title VARCHAR(255),
    content TEXT,
    embedding VECTOR(4),
    category VARCHAR(50),
    created_at DATE
) ORGANIZATION = HEAP;

-- 2. 建索引
CREATE VECTOR INDEX idx_emb ON rag_docs(embedding)
  WITH (distance=cosine, type=hnsw_sq, lib=vsag);
CREATE FULLTEXT INDEX idx_title on rag_docs(title);

-- 3. 混合查询
SELECT id, title, content, __score
FROM HYBRID_SEARCH(
  TABLE rag_docs,
  '{
    "knn": {
      "field": "embedding",
      "query_vector": "[0.12,0.34,0.56,0.78]",
      "k": 20,
      "boost": 1.5
    },
    "query": {
      "multi_match": {
        "query": "分布式事务一致性",
        "fields": ["title", "content"]
      }
    },
    "rank": {
      "rrf": {"rank_constant": 60}
    },
    "size": 5
  }'
);
```

混搜的查询语句与传统做法的对应关系：

| 查询语句语法 | 对应传统哪一步 |
|-----------|---------------|
| `knn` | 步骤 2：向量检索 |
| `query` | 步骤 3：全文检索 |
| `rank.rrf` | 步骤 4：手动 RRF 排序 |

**参数选择思路**：
- `distance=cosine`：文本语义搜索推荐余弦距离，对向量长度不敏感
- `k=20`：先多召回一些结果，由 RRF 融合筛选出最匹配的 Top 5
- `boost=1.5`：语义搜索权重略高，RAG 场景语义理解比关键词更关键
- `rrf`：不确定两路分数分布时的稳健选择，对异常分数不敏感

| 调优目标 | 操作 | 预期效果 |
|----------|------|----------|
| 召回率偏低 | 增大 `knn.k` 和 `query` 的召回数 | 更多候选进入融合，减少漏召回 |
| 关键词命中弱 | 提高 `query` 路的 `boost` | 精确关键词结果的排序更靠前 |
| 语义路干扰大 | 设置 `min_score` 过滤低分结果 | 减少无关语义结果的噪音 |
| 期望更激进的重排 | 调小 `rank_constant`（如 30） | 排名位置的影响放大，高分项更突出 |
| 期望更保守的重排 | 调大 `rank_constant`（如 100） | 排名位置的影响缩小，各路更均衡 |

> **实战提示**：
> - 向量维度必须与 embedding 模型输出一致（如 OpenAI text-embedding-3-small 输出 1536 维）
> - 全文索引需要使用 utf8mb4 字符集，否则中文分词可能异常
> - `k` 值不宜过大，通常 k = 3~5 × size 即可，k 越大计算量越大

## 6. 竞品对比

### 6.1 核心竞品对比

| 维度 | OceanBase | MySQL | PostgreSQL | Elasticsearch | Oracle 26ai | TiDB |
|------|-----------|-------|------------|---------------|-------------|------|
| **混合搜索接口** |
| SQL 接口 | ✅ | ❌ | ❌ 需应用层拼接 | ✅ | ✅ | ❌ |
| Python/SDK 混搜 | 🔄 适配中 | ❌ | ❌ 需应用层融合 | ✅ elasticsearch-py | ✅ | ✅ pytidb SDK |
| **融合算法** |
| 支持算法 | RRF / Weighted Sum / WRRF | - | - | RRF / scripted | RRF / RSF | RRF / Weighted |
| 权重控制 | boost 参数 | - | - | boost 参数 | score_weight | vs_weight / fts_weight |
| 多路支持 | N路向量 + 1路全文 + 标量过滤 | - | - | 多路 | 1路向量 + 1路全文 | 1路向量 + 1路全文 |
| **事务与架构** |
| 事务支持 | ACID | ACID | ACID | 不支持 | ACID | ACID |

### 6.2 OceanBase 优势

1. **单一 SQL 实现多模态搜索**：无需多系统组合，一条 SQL 完成向量 + 全文 + 标量过滤
2. **内置多种融合算法**：Weighted Sum / RRF / WRRF，覆盖主流融合需求
3. **MySQL 协议兼容**：降低迁移成本，现有 MySQL 生态工具可直接使用
4. **分布式架构**：支持水平扩展，适合大规模数据场景
5. **事务一致性**：混合搜索与业务数据在同一数据库，天然支持 ACID 事务
6. **多语言支持**：全文索引支持多种语言
7. **高压缩比**：文档存储空间压缩比高，适合海量数据

## 7. 限制与兼容性

### 7.1 关键限制

以下限制决定是否能够采用 Hybrid Search 方案，建议在实际使用前确认：

| 限制项 | 影响 | 建议方案 |
|--------|------|----------|
| 仅支持行存表（堆表，ORGANIZATION HEAP）| 列存表无法使用 Hybrid Search | 使用堆表存储需要混合搜索的数据 |
| 仅支持 HNSW 系列索引（HNSW / HNSW_SQ / HNSW_BQ）| IVF 系列索引（IVF_FLAT/IVF_SQ8/IVF_PQ）不兼容 | 创建向量索引时指定 `type=hnsw_sq`（推荐）或 `type=hnsw` |
| 仅支持 MySQL 模式 | Oracle 模式不可用 | 在 MySQL 租户中使用 |

### 7.2 语法限制

以下限制影响 SQL 编写方式：

| 限制项 | 说明 | 推荐写法 |
|--------|------|----------|
| 不支持同层 WHERE | 过滤条件必须在查询语句内指定 | `WHERE` → `knn.filter` 或 `query.bool.filter` |
| 不支持同层 LIMIT | 分页使用查询语句内的 `from`/`size` | `LIMIT` → `"size": 10` |
| 不支持同层 ORDER BY | 结果按融合分数自动排序 | 不可指定排序 |
| 不支持被搜索的列有多个向量或全文索引 | SQL接口的混合搜索只会看第一条全文或向量索引，如果是多个索引的话可能会提示无法找到全文索引 | 被引用的列只保留一条向量或全文索引（该行为待确认是否by design） |
| 向量查询必须带索引 | 无向量索引时报错 | 先创建 `VECTOR INDEX` |
| 全文查询必须带索引 | 无全文索引时报错 | 先创建 `FULLTEXT INDEX` |
| 分数列名为 `__score` | 双下划线，非 ES 风格的 `_score` | `SELECT __score` |
| 全文搜索保留字限制 | 不支持 `and`/`or`/`not`/`to` 关键字及 21 个特殊字符 | 使用 `match` 或 `bool` 查询替代 |

### 7.3 参数限制

以下参数有取值范围限制：

| 参数 | 限制范围 |
|------|------|
| `from + size` | <= 10000 |
| KNN `k` | [1, 16384] |
| `rank_constant` | >= 1 |
| `rank_window_size` | >= size |
| `similarity` | 不支持 IP 距离 |
| `knn.boost` | >= 0 |
| 全文搜索的第一层子句中的权重 | >= 0 |
| 全文搜索**非**第一层子句中的权重 | > 0 |
| `bool.boost` | > 0 |
| 字段权重 / 词权重 | > 0 |

### 7.4 其他

| 项目 | 说明 |
|--------|------|
| 标量条件不计分 | `filter` 内的条件不参与评分，不支持 `boost`；`range`/`term`/`terms` 不能在需要算分的 `must`/`should` 中使用 |
| 不支持生成列 | 查询语句中不能使用生成列 |
| 不支持 `rank_feature` | 当前版本不支持 `rank_feature` 查询 |
| 多路向量不支持稀疏向量 | `knn` 数组形式的多路向量搜索仅支持稠密向量 |
| 全文联合索引无效 | 全文列的联合索引（`CREATE FULLTEXT INDEX idx on table (col1, col2)`）对混搜无效，需为每列单独建索引 |
| 字段名大小写不敏感 | 查询语句中的字段名大小写不敏感 |
| 各路 filter 不共享 | `query` 和每个 `knn` 的 `filter` 独立，需分别指定 |
| `refine_k` 适用范围 | 仅 HNSW_BQ 索引支持，普通 HNSW/HNSW_SQ 不支持 |

### 7.5 版本差异

| 版本 | Hybrid Search 方式 | 说明 |
|------|---------------------|------|
| 4.4.1 | dbms_hybrid_search 包 | 兼容 ES 混合查询语法，仅支持 RRF 融合 |
| 4.6.0 | HYBRID_SEARCH SQL 语法 | 纯 SQL 路径，兼容 ES DSL 语法，支持 RRF / Weighted Sum / MinMax 归一化 |

4.6.0 的 HYBRID_SEARCH 语法是推荐使用方式，功能更完整。

### 7.6 常见问题

**Q: HYBRID_SEARCH 和 dbms_hybrid_search 包有什么区别？**

| 对比项 | HYBRID_SEARCH (4.6.0+) | dbms_hybrid_search (4.4.1) |
|--------|------------------------|---------------------------|
| 语法 | 纯 SQL 语法 | PL 包调用 |
| 融合算法 | Weighted Sum / RRF / WRRF | 仅 RRF |
| 推荐 | 推荐使用 | 兼容旧版本 |

**Q: 全文索引和 Search Index 有什么区别？**

| 对比项 | FULLTEXT INDEX | SEARCH INDEX |
|--------|---------------|--------------|
| 用途 | 全文搜索（BM25 评分） | 加速 JSON/Array 列过滤 |
| 支持类型 | VARCHAR / TEXT | JSON / ARRAY，支持在单列或多列上创建（如 `ADD SEARCH INDEX idx(tags, categories)`）|
| 是否计分 | 是 | 否 |
| 查询语句中使用 | match / match_phrase 等 | array_contains 等 |

## 8. 总结

OceanBase Hybrid Search 在 4.6.0 版本提供了一条 SQL 实现多模态搜索的能力，核心价值：

- **消除搜索盲区**：向量搜索 + 全文搜索互补，提升召回率
- **简化开发运维**：单一数据库替代多系统组合，一条 SQL 替代应用层多路合并
- **灵活的融合策略**：内置 Weighted Sum / RRF / WRRF 三种融合算法，适应不同场景

推荐使用路径：
1. **初次使用**：从 RRF 融合开始，无需调参
2. **精细调优**：切换到 Weighted Sum + minmax，通过 boost 控制各路权重
3. **性能优化**：调整 ef_search、filter_mode 等参数

---

::: tip 📝 贡献者
本章由 [@JasonZhang10086](https://github.com/JasonZhang10086) 贡献，内容来自 OceanBase Hybrid Search 特性指南。
:::
