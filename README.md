<h1 align="center">《Easy Data x AI》</h1>

<h2 align="center">（Alpha 内测版，欢迎各位老师参与共建~）</h2>

<p align="center">
  <em>面向所有 AI 爱好者的 Data 与 AI 基础知识入门教程</em>
</p>

<p align="center">
  <a href="https://datawhalechina.github.io/easy-data-x-ai/">在线阅读</a> &nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://open.oceanbase.com/course/760">社区在线课堂</a>
</p>

---

## 📚 这门课程适合谁？

> 双轨并行，论道与习术

为了满足不同角色的学习需求，我们将课程精心设计为两条路径："道篇"与"术篇"。

### 道篇：悟其道（零基础 AI 爱好者和产品决策者的"心法篇"）

**适合人群：** 零基础 AI 爱好者、产品决策者

**学完收获：**
- 🎯 场景判断力：学会评估"这个需求适不适合做 Agent"，避免在立项之初就走上弯路
- 🔍 归因决策力：获得一套"三层度量框架"，精准定位问题出在数据层、模型层还是业务层
- 🏗️ 系统设计力：理解 RAG、MCP、Skill、Memory 背后的产品设计哲学

### 术篇：用其术（开发者的"功法篇"）

**适合人群：** 已能调用 LLM API 的开发者

**学完收获：**
- 💪 坚实的工程基础：掌握流式输出（Streaming）和工具调用（Tool Use）
- 🗄️ 完整的数据层构建经验：基于轻量级 AI Native 数据库从零搭建数据层
- 📊 看得见的性能差距：通过对比实验见证"混合检索"与"纯向量检索"的效果差异
- 🤖 从零到一的 Agent 构建：为 Agent 加上记忆系统，教会它使用技能

## 📖 课程目录

> 💡 **核心理念**：洞察先行，自然跟随。当你看懂了数据，才是真正看懂了 AI 的未来。

### 公共基础篇

| 课程编号 | 课程标题 |
| --- | --- |
| F1 | 大模型的本质与边界 |
| F2 | AI Agent 的完整图景 |

### 道篇

| 课程编号 | 课程标题 |
| --- | --- |
| P1 | 找准 Agent 的用武之地 —— AI Agent 场景识别 |
| P2 | 让 Agent 会查资料 —— RAG 产品设计 |
| P3 | 让 Agent 真正记住你 —— 记忆系统设计 |
| P4 | 把经验变可复用 —— Skill 与知识管理 |
| P5 | 用数据验证价值 —— 案例与度量 |

### 术篇

| 课程编号 | 课程标题 |
| --- | --- |
| D1 | 打通 Agent 与数据 —— 大模型 API 入门 |
| D2 | 一个系统搞定 —— 统一 AI Native 数据层实战 |
| D3 | 实践出真知 —— Agentic RAG 实战 |
| D4 | 记哪些、忘哪些？—— Agent 记忆系统开发 |
| D5 | 授 AI 以渔 —— 综合实战，从 Skill 开发到 MCP 标准化 |

### Extra Chapter



## 🚀 快速开始

### 在线阅读

访问 [https://datawhalechina.github.io/easy-data-x-ai](https://datawhalechina.github.io/easy-data-x-ai) 在线阅读课程内容。

### 本地阅读

```bash
# 克隆仓库
git clone https://github.com/datawhalechina/easy-data-x-ai.git

cd easy-data-x-ai

# 安装依赖
npm install

# 本地预览
npm run docs:dev
```

### 本地运行示例代码

```bash
cd code

# 安装 Python 依赖
pip install -r requirements.txt

# 配置 API Key
cp .env.example .env
# 编辑 .env 文件，填写你的 API Key

# 运行示例
cd D1
python3 d1_1_base.py
```

## 🤝 参与贡献

- 如果你发现了一些问题，可以提 [Issue](https://github.com/datawhalechina/easy-data-x-ai/issues) 进行反馈
- 如果你想参与贡献本项目，欢迎提 [Pull Request](https://github.com/datawhalechina/easy-data-x-ai/pulls)
- 详细的本地预览、目录约定与提交规范，请阅读[贡献指南 CONTRIBUTING.md](CONTRIBUTING.md)
- 参与共建请遵守[行为准则 CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- 欢迎加入课程共建，一起完善内容

## 模型算力支持

<table>
<tr>
<td width="180" align="center" valign="middle">
<a href="https://cloud.siliconflow.cn/i/Fq9zUwPf" target="_blank" rel="noopener">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/public/images/sponsors/siliconflow-dark.svg" />
    <img src="docs/public/images/sponsors/siliconflow.svg" alt="SiliconFlow 硅基流动" width="150" />
  </picture>
</a>
</td>
<td valign="middle">
本课程的模型算力由 <strong><a href="https://cloud.siliconflow.cn/i/Fq9zUwPf">硅基流动（SiliconFlow）</a></strong> 支持。硅基流动是一站式大模型云服务平台，基于自研推理引擎实现大模型高效推理加速，提供高效能、低成本的多品类 AI 模型服务，让开发者和企业聚焦产品创新，无须担心大规模推广带来的高昂算力成本。
</td>
</tr>
</table>

- 🎁 **新用户福利**：通过 [课程专属注册链接](https://cloud.siliconflow.cn/i/Fq9zUwPf) 注册并完成实名认证，即可获得 **16 元全平台通用代金券**，可用于平台上百余种模型的调用，足够跑通本课程的全部示例。
- 🧪 **实验配额补贴池**：用上面的链接注册时，作者也会获得平台返利。这部分返利会**全额回馈给学员**——汇集成一个「实验配额补贴池」：跟着课程做实验、复现示例时如果额度不够用，可以[联系作者](https://space.bilibili.com/3546900567427713)申请额外的算力配额补贴，把福利转回给真正在动手的同学。

## 🧑‍💻 项目维护者

<table>
  <tr>
    <td align="center">
      <a href="https://github.com/liboyang0730">
        <img src="https://github.com/liboyang0730.png" width="100px;" alt="liboyang0730"/>
        <br />
        <sub><b>Zlatan (liboyang0730)</b></sub>
      </a>
      <br />
      <sub>项目负责人</sub>
    </td>
    <td align="center">
      <a href="https://github.com/webup">
        <img src="https://github.com/webup.png" width="100px;" alt="webup"/>
        <br />
        <sub><b>Haili Zhang (webup)</b></sub>
      </a>
      <br />
      <sub>项目维护者</sub>
    </td>
  </tr>
</table>

## 👥 贡献者墙

> 感谢每一位参与共建的贡献者！下方头像墙由 GitHub Action 自动更新，所有合并过 PR 的同学都会出现在这里（详见 [CONTRIBUTING.md](CONTRIBUTING.md)）。

<!-- contributors:start -->
<table width="100%">
<tr>
<td align="center" valign="top" width="104">
  <a href="https://github.com/liboyang0730" title="liboyang0730">
    <img src="https://avatars.githubusercontent.com/u/13233790?v=4&s=144" width="72" height="72" alt="liboyang0730" style="border-radius:50%;" />
  </a><br />
  <a href="https://github.com/liboyang0730" title="打开 liboyang0730 的 GitHub 主页"><kbd><strong>liboyang073…</strong></kbd></a><br />
  <sub>69 commits</sub>
</td>
<td align="center" valign="top" width="104">
  <a href="https://github.com/hu-qi" title="hu-qi">
    <img src="https://avatars.githubusercontent.com/u/17986122?v=4&s=144" width="72" height="72" alt="hu-qi" style="border-radius:50%;" />
  </a><br />
  <a href="https://github.com/hu-qi" title="打开 hu-qi 的 GitHub 主页"><kbd><strong>hu‑qi</strong></kbd></a><br />
  <sub>1 commit</sub>
</td>
</tr>
</table>
<!-- contributors:end -->

## 关注我们
<div align=center>
<p>欢迎扫描下方二维码加入 Data x AI 课程交流群</p>
<img src="https://raw.githubusercontent.com/datawhalechina/easy-data-x-ai/main/docs/public/images/base_knowledge/F0/F0-20.png" width = "180" height = "180">
</div>

## LICENSE

<a rel="license" href="http://creativecommons.org/licenses/by-nc-sa/4.0/"><img alt="知识共享许可协议" style="border-width:0" src="https://img.shields.io/badge/license-CC%20BY--NC--SA%204.0-lightgrey" /></a><br />本作品采用<a rel="license" href="http://creativecommons.org/licenses/by-nc-sa/4.0/">知识共享署名-非商业性使用-相同方式共享 4.0 国际许可协议</a>进行许可，完整条款详见 [LICENSE](LICENSE) 文件。
