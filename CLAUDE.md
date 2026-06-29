# CLAUDE.md

本文件为 Claude Code 提供代码仓库的工作指引。

## 项目概述

基于 RAG（检索增强生成）的 AI 智能客服系统。后端: FastAPI + MySQL + Qdrant。前端: React 19 + Ant Design 6 + Vite 8。大模型: DeepSeek 主用，Qwen 兜底。

## 常用命令

### 基础设施
```bash
docker compose up -d mysql qdrant    # 启动 MySQL 8.0 + Qdrant
docker compose down                   # 停止所有服务
```

### 后端 (Python 3.10+)
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000   # 开发服务器
```

### 前端 (Node 18+)
```bash
cd frontend
npm install
npm run dev                           # localhost:5173
npx tsc --noEmit                      # 类型检查
```

### 测试
```bash
cd backend
python -m pytest tests/unit/ -v              # 单元测试 (86个, mock依赖)
python -m pytest tests/integration/ -v       # 集成测试 (需 Docker)
python -m pytest tests/rag_eval/ -v          # RAG 质量评估
```

## 架构

### 后端分层

```
api/         → 路由处理 (Pydantic 校验、Depends 注入、调用 service)
services/    → 业务逻辑 (RAG 管线、检索、文档入库、认证、意图识别、查询改写、查询分类、Agent)
models/      → SQLAlchemy 2.0 ORM (异步 Mapped 类型, 7 张表)
core/        → 基础设施: config、database、embedding、llm_client、qdrant_client
middleware/  → JWT 鉴权 (get_current_user、require_admin)、IP 限流
```

### RAG 管线 (chat.py → retrieval.py → context_guard.py)

```
用户消息 → 意图识别 (L1规则→L2向量→L3大模型, 置信度<0.7则追问)
  ↓
查询改写: LLM 口语→专业术语 (query_rewriter.py, 5s超时, 闲聊跳过, 失败降级)
  ↓
混合检索: 向量(K=20) ‖ BM25(K=20) → RRF融合 → 前20（使用改写后的查询）
  ↓
查询类型分类: 简单/复杂判断 (query_type.py) → 决定有效 TOP_K
  ↓
重排序: Cross-Encoder (bge-reranker-v2-m3, 8s超时, 分数归一化[0,1], GPU 优先 CPU 兜底)
  ↓
上下文守护: 分层摘要 → 类型排序 (规则>事实>流程) → token预算3000
  ↓
Prompt组装: SYSTEM_PROMPT (分层规则+反幻觉示例) + 历史(5轮) + 知识 + 原始问题
  ↓
LLM 流式生成 (SSE): DeepSeek → Qwen兜底 → 静态兜底
  ↓
生成后验证 (三层: token重叠+实体匹配+否定检查, 全部句子)
  ↓
保存消息 → 追问建议
```

**SSE 事件**: `intent` → `rewritten_query` → `processing`(检索中) → `references` → `delta`(×N) → `done` → `followups`

### 检索架构

- **Qdrant**: 集合 `knowledge_chunks`, 1024维 Cosine 距离, HNSW 索引
- **BM25**: 内存索引, 启动时从 Qdrant 重建, 文档增删时增量维护
- **RRF 融合**: `1/(60+rank)` 公式, 跨来源去重
- **重排序**: `FlagEmbedding.FlagReranker` 加载 `BAAI/bge-reranker-v2-m3`

### 知识库

- 多知识库支持 (knowledge_bases 表), Session 可关联 kb_id
- 文档上传: create_document(秒返, status=processing) → BackgroundTasks.process_document(异步)
- 启动时扫描 status=processing 的文档自动补处理

### 认证与鉴权

- JWT (HS256, 24h 有效期)
- `get_current_user` 依赖 → 401
- `require_admin` 依赖 → 403
- 知识库增删上传 / 管理后台 需要 admin

### LLM 容错

- tenacity 重试 3 次 (1s→2s→4s)
- DeepSeek → Qwen → 静态兜底
- 熔断器: 连续 5 次失败 → 冷却 60s

### 关键配置 (core/config.py, 从 .env 加载)

| 参数 | 值 | 说明 |
|------|-----|------|
| `RETRIEVAL_THRESHOLD` | 0.43 | 纯检索扫描校准, 安全区间 (0.4232, 0.4313] |
| `RETRIEVAL_TOP_K` | 5 | 默认兜底值（K_floor/K_opt 未校准时使用） |
| `RETRIEVAL_TOP_K_FLOOR` | 0 | P95(gt_rank)+1, 简单查询用；0=未校准 |
| `RETRIEVAL_TOP_K_OPT` | 0 | 窄窗消融最优, 复杂查询用；0=未校准 |
| `RETRIEVAL_COARSE_K` | 20 | 混合检索候选数 |
| `INTENT_CLARIFY_THRESHOLD` | 0.7 | 置信度低于此值触发追问 |
| `MAX_CONTEXT_ROUNDS` | 5 | 对话历史轮数 |
| `MAX_QUESTION_LENGTH` | 500 | 单次提问上限 |
| `DAILY_QUOTA_LIMIT` | 100 | 每人每日提问上限 |
| `QUERY_REWRITE_ENABLED` | True | 开启查询改写 |
| `QUERY_REWRITE_TIMEOUT` | 5.0 | 改写 LLM 调用超时（秒） |
| `QUERY_REWRITE_MODEL` | deepseek-chat | 改写专用模型 |
| `EMBEDDING_DEVICE` | cuda | 嵌入模型设备，GPU 不可用时自动降级 CPU |

### 前端状态

- **Zustand store**: `authStore` (user+token, 持久化 localStorage)、`chatStore` (消息/流式/追问/意图)
- **SSE 流式**: `useChatStream` hook 基于 `@microsoft/fetch-event-source`, 支持 AbortController
- **路由守卫**: `useRequireAuth` hook, 无 token 重定向 `/login`
- **会话**: `Chat.tsx` 无 `:sessionId` 时自动创建

### 运行前提

1. Docker Desktop (MySQL + Qdrant)
2. `.env` 中设置 `DEEPSEEK_API_KEY`
3. 首次运行: BGE 模型自动下载 (~1.3GB); 需设 `HF_ENDPOINT=https://hf-mirror.com` 或能访问 huggingface.co
4. BM25 索引每次启动从 Qdrant 重建

### 切勿提交

`.env` 包含真实 API key。`.env.example` 是可提交的安全模板。`.gitignore` 已覆盖。
