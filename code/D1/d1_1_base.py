import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Config
from langchain.chat_models import init_chat_model

# 使用统一配置
llm = init_chat_model(
    "tencent/Hunyuan-MT-7B",
    model_provider="openai",  # 通过 OpenAI 兼容接口调用
    **Config.get_siliconflow_config()
)

response = llm.invoke([
    ("system", "你是一个简洁高效的技术助手。用中文回答，尽量用一两句话。"),
    ("user", "什么是 RAG？"),
])

print(response.content)