# 后端服务 — AI 智能客服系统

## 技术栈

- Python 3.10+
- FastAPI (异步 Web 框架)
- SQLAlchemy 2.0 (异步 ORM)
- MySQL 8.0 + Qdrant (向量数据库)

## 快速启动

### 1. 启动基础设施

```bash
# 在项目根目录
docker compose up -d mysql qdrant
```

### 2. 安装依赖

```bash
cd backend
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. 配置环境变量

复制项目根目录的 `.env.example` 为 `.env`，填入你的 DeepSeek API Key。

### 4. 启动开发服务器

```bash
uvicorn app.main:app --reload --port 8000
```

API 文档自动生成在 http://localhost:8000/docs

## 项目结构

```
backend/
├── app/
│   ├── api/          # API 路由层
│   ├── models/       # SQLAlchemy 模型
│   ├── services/     # 业务逻辑层
│   ├── core/         # 配置与客户端
│   ├── middleware/   # 中间件（JWT、限流）
│   └── main.py       # FastAPI 入口
├── sql/
│   └── init.sql      # 建表语句
├── tests/            # 测试用例
└── requirements.txt  # Python 依赖
```
