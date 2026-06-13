"""
配置管理模块
从 .env 文件加载 API 配置
"""
import os
from pathlib import Path


CODE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CODE_DIR.parent
PLACEHOLDER_VALUES = {
    "",
    "YOUR_API_KEY",
    "your_api_key_here",
    "your_siliconflow_api_key_here",
    "your_dashscope_api_key_here",
    "your_openai_api_key_here",
}


# 尝试加载 python-dotenv
try:
    from dotenv import load_dotenv

    # 优先读取 code/.env；若不存在，再读取仓库根目录 .env，避免依赖运行脚本时的 cwd。
    for env_path in (CODE_DIR / ".env", PROJECT_ROOT / ".env"):
        if env_path.exists():
            load_dotenv(env_path)
            break

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

    @staticmethod
    def _is_placeholder(value):
        """判断配置值是否仍是模板占位符"""
        return not value or value.strip() in PLACEHOLDER_VALUES

    @classmethod
    def check_api_key(cls, key_name="SILICONFLOW_API_KEY"):
        """检查 API Key 是否已配置"""
        key = getattr(cls, key_name)
        if cls._is_placeholder(key):
            print(f"⚠️  警告: {key_name} 未配置！")
            print(f"请在 code/.env 或项目根目录 .env 文件中设置 {key_name}")
            return False
        return True

    @classmethod
    def require_api_key(cls, key_name="SILICONFLOW_API_KEY"):
        """获取 API Key；如果仍是占位符，则提前报错"""
        if not cls.check_api_key(key_name):
            raise ValueError(f"{key_name} 未配置，请先填写 .env 后再运行示例代码")
        return getattr(cls, key_name)

    @classmethod
    def get_siliconflow_config(cls):
        """获取 SiliconFlow 配置"""
        return {
            "base_url": cls.SILICONFLOW_BASE_URL,
            "api_key": cls.require_api_key("SILICONFLOW_API_KEY"),
        }

    @classmethod
    def get_dashscope_config(cls):
        """获取 DashScope 配置"""
        return {
            "base_url": cls.DASHSCOPE_BASE_URL,
            "api_key": cls.require_api_key("DASHSCOPE_API_KEY"),
        }


if __name__ == "__main__":
    # 测试配置
    print("当前配置状态:")
    print(f"SILICONFLOW_API_KEY: {'未配置' if Config._is_placeholder(Config.SILICONFLOW_API_KEY) else '已配置'}")
    print(f"DASHSCOPE_API_KEY: {'未配置' if Config._is_placeholder(Config.DASHSCOPE_API_KEY) else '已配置'}")
