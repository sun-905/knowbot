# 前端 — AI 智能客服系统

## 技术栈

- React 19 + TypeScript 6
- Vite 8 (构建工具)
- Ant Design 6 (UI 组件库)
- Zustand 5 (状态管理)
- react-markdown + remark-gfm (Markdown 渲染)
- @microsoft/fetch-event-source (SSE 流式传输)

## 快速启动

```bash
cd frontend
npm install
npm run dev
```

开发服务器默认运行在 http://localhost:5173

## 项目结构

```
frontend/
├── src/
│   ├── api/           # API 调用层（auth, chat, knowledge, client）
│   ├── components/    # 可复用组件（ChatBubble, FeedbackButton, ReferenceCard 等）
│   ├── hooks/         # 自定义 Hook（useChatStream, useAuth）
│   ├── pages/         # 页面（Login, Register, Chat, History, Knowledge, Admin）
│   ├── stores/        # Zustand 状态管理（authStore, chatStore）
│   ├── App.tsx        # 路由 + 主题配置
│   └── main.tsx       # 入口
├── public/            # 静态资源
├── package.json
└── vite.config.ts
```

## 构建

```bash
npm run build   # 产出在 dist/
npm run preview # 预览构建结果
```
