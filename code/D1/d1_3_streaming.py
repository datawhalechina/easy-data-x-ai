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

for chunk in llm.stream([
    ("system", "你是一个技术助手。"),
    ("user", "用三句话解释什么是向量数据库。"),
]):
    print(chunk.content, end="", flush=True)

print()  # 最后换行