# API 接口文档

> Base URL: `http://localhost:8000` | 自动文档: `/docs` (Swagger UI)

---

## 1. 认证接口 `/auth`

### POST /auth/register — 用户注册

```
Body: { phone: str, email?: str, password: str (≥6位), nickname: str }
Response 201: { access_token, token_type, user }
Error 409: 手机号/邮箱已被注册
Error 422: 参数校验失败
```

### POST /auth/login — 用户登录

```
Body: { account: str (手机号或邮箱), password: str }
Response 200: { access_token, token_type, user }
Error 401: 账号或密码错误 / 账号已禁用
```

### GET /auth/me — 获取当前用户信息

```
Header: Authorization: Bearer <token>
Response 200: { id, phone, email, nickname, avatar_url, daily_quota, is_admin, created_at }
Error 401: token 无效或过期
```

### PATCH /auth/me — 更新当前用户信息

```
Header: Authorization: Bearer <token>
Body: { nickname?: str, avatar_url?: str }
Response 200: User
```

---

## 2. 对话接口

### POST /sessions — 创建会话

```
Header: Authorization: Bearer <token>
Body: { title?: str, kb_id?: int }
Response 201: { id, title, user_id, status, kb_id }
```

### GET /sessions — 会话列表

```
Query: page (default 1), page_size (default 20, max 100)
Response 200: { items: [{id, title, status, kb_id, created_at}], total, page, page_size }
```

### GET /sessions/{id} — 会话详情（含消息记录）

```
Response 200: { id, title, status, kb_id, messages: [{id, role, content, intent, references_json, created_at}] }
Error 403: 无权访问此会话
Error 404: 会话不存在
```

### DELETE /sessions/{id} — 删除会话

```
Response 204
Error 403: 无权删除
Error 404: 会话不存在
```

### POST /sessions/{id}/chat — 发送消息（SSE 流式响应）⭐

```
Header: Authorization: Bearer <token>
Body: { content: str (1-500字) }
Response 200: text/event-stream

SSE 事件序列:
  event: intent          data: { intent, confidence, source, clarify? }
  event: rewritten_query data: { original, rewritten }   ← 口语改写后检索查询
  event: processing      data: { stage: "检索中" }        ← 检索进行中
  event: references      data: [{ doc_name, doc_id, score, snippet }]
  event: delta           data: { content }               ← 逐 token 输出
  event: done            data: { message_id }
  event: followups       data: ["追问1","追问2","追问3"]
  event: error           data: { code, detail }

Error 429: 今日提问次数已用完 / 并发连接数超限
```

---

## 3. 反馈接口

### POST /messages/{message_id}/feedback — 提交反馈

```
Header: Authorization: Bearer <token>
Body: { rating: "like"|"dislike", comment?: str }
Response 201: { id, message_id, rating, comment }
Error 404: 消息不存在
Error 409: 已经评价过
```

---

## 4. 知识库接口 `/knowledge`

### GET /knowledge/bases — 知识库列表

```
无需登录
Response 200: [{ id, name, description, is_default }]
```

### POST /knowledge/bases — 创建知识库（管理员）

```
Header: Authorization: Bearer <token>
Body: { name: str, description?: str }
Response 201: KnowledgeBase
Error 403: 非管理员
```

### DELETE /knowledge/bases/{id} — 删除知识库（管理员）

```
Response 204
Error 400: 不能删除默认知识库
Error 403: 非管理员
```

### POST /knowledge/docs/upload — 上传文档（管理员）

```
Header: Authorization: Bearer <token>
Body: multipart/form-data { file: File, kb_id?: int }
Response 201: { id, kb_id, filename, file_type, file_size, chunk_count, status, error_msg, created_at }
  status: "processing" → 后台异步处理后变为 "ready" 或 "failed"
Error 400: 不支持的文件类型 / 文件过大 (10MB)
Error 403: 非管理员
```

### GET /knowledge/docs — 文档列表

```
Query: page, page_size
Response 200: { items: [KnowledgeDoc], total, page, page_size }
```

### GET /knowledge/docs/{id} — 文档详情

```
Response 200: KnowledgeDoc
Error 404: 文档不存在
```

### DELETE /knowledge/docs/{id} — 删除文档（管理员）

```
Response 204
Error 403: 非管理员
```

---

## 5. 管理后台接口 `/admin`

> 全部需要管理员权限

### GET /admin/stats/daily?days=7 — 每日问答统计

### GET /admin/stats/feedback?days=7 — 反馈统计

### GET /admin/stats/intent?days=7 — 意图分布

### GET /admin/feedback-comments?page=1&page_size=20 — 文字反馈记录

### GET /admin/sessions?page=1&page_size=20 — 全量会话记录

---

## 6. 通用

### GET /health — 健康检查

```
Response 200: { status: "ok" }
```

## 鉴权说明

- 所有需要登录的接口，在请求头中携带 `Authorization: Bearer <token>`
- Token 通过 `/auth/register` 或 `/auth/login` 获取
- Token 有效期 24 小时（可配置）
- 管理员接口额外要求 `is_admin = true`
