"""Tiny deterministic knowledge base used by the D1 Tool Use demo."""

_DOCUMENTS = (
    (
        ("检索方式", "检索", "关键词", "语义向量", "向量检索", "混合检索"),
        "seekdb 支持关键词、语义向量和混合检索。",
    ),
    (
        ("部署模式", "嵌入模式", "服务器模式"),
        "seekdb 支持嵌入模式和服务器模式。",
    ),
    (
        ("pyseekdb", "python sdk", "sdk"),
        "pyseekdb 是 seekdb 的 Python SDK，支持 Schemaless API。",
    ),
)

_NO_MATCH_MESSAGE = "模拟知识库中没有找到匹配条目，请补充具体产品关键词。"


def search_mock_knowledge_base(query: str) -> str:
    """按完整短语匹配模拟条目，未命中时不返回无关文档。"""
    if not isinstance(query, str) or not query.strip():
        return _NO_MATCH_MESSAGE

    normalized_query = query.casefold()
    matches = [
        document
        for keywords, document in _DOCUMENTS
        if any(keyword.casefold() in normalized_query for keyword in keywords)
    ]
    return "\n\n".join(matches) if matches else _NO_MATCH_MESSAGE
