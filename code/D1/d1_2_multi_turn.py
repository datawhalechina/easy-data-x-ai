import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Config
from langchain.chat_models import init_chat_model

# 使用统一配置
llm = init_chat_model(
    "tencent/Hunyuan-MT-7B",
    model_provider="openai",
    **Config.get_siliconflow_config()
)

messages = [
    ("system", "你是一个简洁高效的技术助手。"),
    ("user", "什么是 RAG？"),
    ("assistant", "RAG 是检索增强生成，先从知识库检索相关内容，再让模型基于这些内容生成回答。"),  # 让模型在回答你追问的下一个问题之前，知道你们之前聊了什么
    ("user", "它和直接把文档塞进 Prompt 有什么区别？"),
]

response = llm.invoke(messages)

print(response.content)