# Code 目录

本目录包含《Easy Data x AI》课程"术篇"部分的示例代码。

## 目录结构

```
code/
├── config.py          # 统一配置管理
├── .env.example       # 环境变量示例文件
├── requirements.txt   # Python 依赖
├── D1/                # 大模型 API 工程化基础
├── D2/                # AI 应用的数据层
├── D3/                # Agentic RAG 实战
├── D4/                # Agent 开发与记忆系统
├── D5/                # Skill、MCP 与综合项目
└── X2/                # 扩展篇：Skill 结构化管理与按需加载
```

## 快速开始

### 1. 安装依赖

```bash
pip install --upgrade -r requirements.txt
```

### 2. 配置 API Key

复制环境变量示例文件：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填写你的 API Key：

```bash
# SiliconFlow API（用于 Hunyuan-MT-7B, DeepSeek-V3 等）
SILICONFLOW_API_KEY=your_siliconflow_api_key_here

# 阿里云 DashScope API（用于 Qwen 等）
DASHSCOPE_API_KEY=your_dashscope_api_key_here
```

### 3. 运行示例

```bash
cd D1
python d1_1_base.py
```

## 配置说明

所有代码文件都已统一使用 `config.py` 中的配置，无需在每个文件中单独配置 API Key。

- `Config.get_siliconflow_config()` - 获取 SiliconFlow API 配置
- `Config.get_dashscope_config()` - 获取阿里云 DashScope API 配置

## 说明

各章节的代码示例将随着课程内容的完善陆续添加。