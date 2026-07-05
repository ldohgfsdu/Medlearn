import { defineConfig } from 'vitepress'

const base = '/Medlearn/'

export default defineConfig({
  base,
  lang: 'zh-CN',
  title: 'MedLearn',
  description: '以结构化医学知识为基础的临床思维训练系统',

  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: `${base}logo.svg` }],
    ['meta', { name: 'theme-color', content: '#17332C' }],
    ['meta', { name: 'keywords', content: 'MedLearn,医学教育,医学生,临床推理,病例模拟,医学知识库' }],
  ],

  themeConfig: {
    logo: '/logo.svg',

    nav: [
      { text: '首页', link: '/' },
      { text: '指南', link: '/guide/introduction' },
      { text: '功能详解', link: '/features/knowledge' },
      { text: '开发者', link: '/dev/architecture' },
      { text: 'FAQ', link: '/faq' },
      { text: '更新日志', link: '/changelog' },
    ],

    sidebar: {
      '/guide/': [
        { text: '入门指南', items: [
          { text: '前言', link: '/guide/introduction' },
          { text: '快速上手', link: '/guide/getting-started' },
          { text: '下载安装', link: '/guide/installation' },
          { text: '更新日志', link: '/changelog' },
        ]},
        { text: '产品', items: [
          { text: 'Knowledge 知识库', link: '/guide/knowledge' },
          { text: 'Case Simulator 病例模拟', link: '/guide/case-simulator' },
          { text: '学习模型', link: '/guide/learning-model' },
        ]},
      ],
      '/features/': [
        { text: '功能详解', items: [
          { text: '知识库 (Knowledge)', link: '/features/knowledge' },
          { text: '病例模拟 (Case Simulator)', link: '/features/case-simulator' },
          { text: '搜索与目录', link: '/features/search' },
          { text: '评分与反馈', link: '/features/scoring' },
          { text: '云同步', link: '/features/cloud-sync' },
        ]},
      ],
      '/dev/': [
        { text: '技术文档', items: [
          { text: '技术架构', link: '/dev/architecture' },
          { text: 'API 接口', link: '/dev/api' },
          { text: '教材管线', link: '/dev/textbook-pipeline' },
          { text: '搜索与 RAG', link: '/dev/rag' },
          { text: '远程部署', link: '/dev/deployment' },
        ]},
        { text: '开发指南', items: [
          { text: '开发指南', link: '/dev/development' },
          { text: '项目结构', link: '/dev/project-structure' },
          { text: '验证与测试', link: '/dev/testing' },
          { text: '设计规范', link: '/dev/design-context' },
        ]},
      ],
    },

    search: { provider: 'local', options: { translations: { button: { buttonText: '搜索文档', buttonAriaLabel: '搜索文档' }, modal: { noResultsText: '无法找到相关结果', resetButtonTitle: '清除查询条件', footer: { selectText: '选择', navigateText: '切换', closeText: '关闭' } } } } },
    outline: { label: '页面导航', level: [2, 3] },
    docFooter: { prev: '上一页', next: '下一页' },
    lastUpdated: { text: '最后更新于', formatOptions: { dateStyle: 'short', timeStyle: 'short' } },
    footer: { message: 'MedLearn — 书是基础。框架是核心。推理是终点。', copyright: '© 2026 MedLearn. All rights reserved.' },
    darkModeSwitchLabel: '主题', lightModeSwitchTitle: '切换到浅色模式', darkModeSwitchTitle: '切换到深色模式',
    sidebarMenuLabel: '菜单', returnToTopLabel: '回到顶部',
  },
})
