# NEURAL DESK — AI 智能客服系统

> 基于 RAG（检索增强生成）的企业级 AI 智能客服。上传知识库文档，用户自然语言提问，LLM 生成有据可查的回答。

## 快速开始

```bash
# 1. 启动基础设施 (MySQL + Qdrant)
docker compose up -d

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 3. 启动后端 (Python 3.10+)
cd backend
pip install -r requirements.txt
uvicorn app.main:app --port 8000

# 4. 启动前端 (Node 18+)
cd frontend
npm install && npm run dev
```

浏览器打开 http://localhost:5173，注册账号即可使用。

> 详细步骤见 [运行指南.md](运行指南.md)

## 核心功能

| 功能 | 说明 |
|------|------|
| **RAG 智能问答** | 混合检索（向量 + BM25）+ 重排序 + 上下文守护 + LLM 流式生成 |
| **意图识别** | L1 规则 → L2 向量 → L3 大模型，低置信度自动追问 |
| **知识库管理** | 上传 PDF/MD/TXT 自动解析、切片、向量化，支持多知识库 |
| **反幻觉机制** | 分层摘要 + 类型排序 + 三层生成后验证 + SYSTEM_PROMPT 硬约束 |
| **流式输出** | SSE 逐字显示，无需等待全量生成 |
| **反馈系统** | 点赞/踩 + 可选文字反馈 |
| **管理后台** | 问答统计、反馈统计、意图分布、日均折线图 |
| **多轮对话** | 上下文携带最近 5 轮历史 |
| **LLM 容错** | DeepSeek → Qwen 兜底 → 静态兜底，熔断保护 |

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | React 19 + TypeScript + Ant Design 6 + Vite 8 |
| 后端 | FastAPI (Python 3.10+) + SSE 流式 |
| 数据库 | MySQL 8.0 + Qdrant 向量库 |
| 大模型 | DeepSeek (主) + Qwen (备) |
| 嵌入 | BGE-large-zh-v1.5 (1024 维) |
| 重排序 | BGE-Reranker-v2-m3 |

## 项目结构

```
├── backend/              # FastAPI 后端
├── frontend/             # React 前端
├── docs/                 # 设计文档
│   ├── API文档.md
│   ├── 数据库设计.md
│   ├── AI架构设计.md
│   └── 业务流程说明.md
├── docker-compose.yml    # MySQL + Qdrant
├── 运行指南.md
├── CLAUDE.md
└── 项目说明.md
```

## 文档索引

| 文档 | 说明 |
|------|------|
| [运行指南.md](运行指南.md) | 环境配置、启动步骤、常见问题 |
| [项目说明.md](项目说明.md) | 项目概述与技术架构 |
| [docs/API文档.md](docs/API文档.md) | 全部接口（含 SSE 流式说明） |
| [docs/数据库设计.md](docs/数据库设计.md) | ER 图 + 7 张表结构 |
| [docs/AI架构设计.md](docs/AI架构设计.md) | RAG 管线流程图、关键设计决策 |
| [docs/业务流程说明.md](docs/业务流程说明.md) | 完整问答链路 |
| [RETRIEVAL_THRESHOLD与TOP_K选取说明.md](RETRIEVAL_THRESHOLD与TOP_K选取说明.md) | 超参校准方法 |
| [Prompt优化与反幻觉设计.md](Prompt优化与反幻觉设计.md) | Prompt 设计思路 |

## 许可证

MIT
