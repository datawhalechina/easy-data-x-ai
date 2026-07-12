"""
配置管理模块
从 .env 文件加载 API 配置
"""
import os
from pathlib import Path


def _find_env_file(start_dir=None):
    """从指定目录开始向上查找 .env 文件，优先使用更靠近代码目录的配置。"""
    current_dir = Path(start_dir or Path(__file__).resolve().parent).resolve()

    for directory in (current_dir, *current_dir.parents):
        env_path = directory / ".env"
        if env_path.is_file():
            return env_path

        if (directory / ".git").exists():
            break

    return None


# 尝试加载 python-dotenv
try:
    from dotenv import load_dotenv
    # 加载 .env 文件（优先 code/.env，找不到时向上查找父目录）
    env_path = _find_env_file()
    if env_path is not None:
        load_dotenv(env_path)
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    print("提示: 未安装 python-dotenv，将直接从环境变量读取配置")
    print("建议运行: pip install python-dotenv")


# API 配置
class Config:
    """统一配置管理"""

    # SiliconFlow 配置
    SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "YOUR_API_KEY")
    SILICONFLOW_BASE_URL = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")

    # 阿里云 DashScope 配置
    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "YOUR_API_KEY")
    DASHSCOPE_BASE_URL = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

    # OpenAI 配置（可选）
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "YOUR_API_KEY")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    @classmethod
    def check_api_key(cls, key_name="SILICONFLOW_API_KEY"):
        """检查 API Key 是否已配置"""
        key = getattr(cls, key_name)
        template_value = f"your_{key_name.lower()}_here"
        if key in {"YOUR_API_KEY", template_value} or not key:
            print(f"⚠️  警告: {key_name} 未配置！")
            print(f"请在 code/.env 或仓库根目录 .env 文件中设置 {key_name}")
            return False
        return True

    @classmethod
    def get_siliconflow_config(cls):
        """获取 SiliconFlow 配置"""
        return {
            "base_url": cls.SILICONFLOW_BASE_URL,
            "api_key": cls.SILICONFLOW_API_KEY,
        }

    @classmethod
    def get_dashscope_config(cls):
        """获取 DashScope 配置"""
        return {
            "base_url": cls.DASHSCOPE_BASE_URL,
            "api_key": cls.DASHSCOPE_API_KEY,
        }


if __name__ == "__main__":
    # 测试配置
    print("当前配置状态:")
    print(f"SILICONFLOW_API_KEY: {'已配置' if Config.SILICONFLOW_API_KEY != 'YOUR_API_KEY' else '未配置'}")
    print(f"DASHSCOPE_API_KEY: {'已配置' if Config.DASHSCOPE_API_KEY != 'YOUR_API_KEY' else '未配置'}")
