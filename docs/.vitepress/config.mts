import { defineConfig } from 'vitepress'
// https://vitepress.dev/reference/site-config

// 1. 获取环境变量并判断
// 如果环境变量 EDGEONE 等于 '1'，说明在 EdgeOne 环境，使用根路径 '/'
// 否则默认是 GitHub Pages 环境，使用仓库子路径 '/easy-data-x-ai/'
const isEdgeOne = process.env.EDGEONE === '1'
const baseConfig = isEdgeOne ? '/' : '/easy-data-x-ai/'

export default defineConfig({
  lang: 'zh-CN',
  title: "Easy Data X AI",
  description: "面向所有 AI 爱好者的 Data 与 AI 基础知识入门教程",
  base: baseConfig,
  markdown: {
    math: true
  },
  themeConfig: {
    // https://vitepress.dev/reference/default-theme-config
    logo: '/datawhale-logo.png',
    nav: [
      { text: 'GitHub 仓库', link: 'https://github.com/datawhalechina/easy-data-x-ai' },
      { text: '社区在线课堂', link: 'https://open.oceanbase.com/course/760' },
    ],
    search: {
      provider: 'local',
      options: {
        translations: {
          button: {
            buttonText: '搜索文档',
            buttonAriaLabel: '搜索文档'
          },
          modal: {
            noResultsText: '无法找到相关结果',
            resetButtonTitle: '清除查询条件',
            footer: {
              selectText: '选择',
              navigateText: '切换'
            }
          }
        }
      }
    },
    sidebar: [
      { text: '《Easy Data X AI 课程介绍》', link: '/course-intro' },
      {
        text: '第一章：公共基础知识',
        collapsed: false,
        items: [
          { text: 'F0：课前闲聊 —— OpenClaw 为什么越用越好用？', link: '/base_knowledge/F0 课程稿：课前闲聊 —— OpenClaw 为什么越用越好用？' },
          { text: 'F1：AI 必知必会（一）—— 大模型的本质与边界', link: '/base_knowledge/F1 课程稿：AI 必知必会（一） —— 大模型的本质与边界' },
          { text: 'F2：AI 必知必会（二）—— AI Agent 全景图', link: '/base_knowledge/F2 课程稿：AI 必知必会（二） —— AI Agent 全景图' }
        ]
      },
      {
        text: '第二章：道篇',
        collapsed: false,
        items: [
          { text: 'P1：AI Agent 场景识别', link: '/pm/P1 课程稿：AI Agent 场景识别' },
          { text: 'P2：Agentic RAG 产品设计', link: '/pm/P2 课程稿：Agentic RAG 产品设计' },
          { text: 'P3：Agent 记忆系统设计', link: '/pm/P3 课程稿：Agent 记忆系统设计' },
          { text: 'P4：Skill 与 Agent 知识管理', link: '/pm/P4 课程稿：Skill 与 Agent 知识管理' },
          { text: 'P5：综合案例与度量', link: '/pm/P5 课程稿：综合案例与度量' }
        ]
      },
      {
        text: '第三章：术篇',
        collapsed: false,
        items: [
          { text: 'D1：大模型 API 基础', link: '/dev/D1 课程稿：大模型 API 工程化基础' },
          { text: 'D2：AI 应用的数据层', link: '/dev/D2 课程稿：AI 应用的数据层' },
          { text: 'D3：Agentic RAG 实战', link: '/dev/D3 课程稿：Agentic RAG 实战' },
          { text: 'D4：Agent 开发与记忆系统', link: '/dev/D4 课程稿：Agent 开发与记忆系统' },
          { text: 'D5：课程总结', link: '/dev/D5 课程稿：课程总结' }
        ]
      },
      {
        text: '第四章：扩展篇（共建招募中）',
        collapsed: false,
        items: [
          { text: 'X1：探究 AI Agent 记忆系统', link: '/extra/X1 探究 AI Agent 记忆系统：从遗忘曲线到永久记忆' },
          { text: 'X2：多 Skill 与上下文工程', link: '/extra/X2 多 Skill 给上下文工程带来的麻烦：如何应对 Agent「爆上下文」' },
          { text: 'X3：混合检索与统一数据基座', link: '/extra/X3 从零到一上手混合检索：AI Native 统一数据基座实战' },
          { text: 'X4：数据湖库与多模数据降本', link: '/extra/X4 海量 AI Agent 多模数据降本：数据湖库登场' },
          { text: 'X5：由你来定！', link: '/extra/X5 由你来定' }
        ]
      }
    ],

    socialLinks: [
      { icon: 'github', link: 'https://github.com/datawhalechina/easy-data-x-ai' }
    ],

    editLink: {
      pattern: 'https://github.com/datawhalechina/easy-data-x-ai/blob/main/docs/:path'
    },

    footer: {
      message: 'Built with VitePress | <a href="https://github.com/datawhalechina/easy-data-x-ai" target="_blank">GitHub 仓库</a>',
      copyright: 'Licensed under CC BY-NC-SA 4.0'
    }
  }
})
