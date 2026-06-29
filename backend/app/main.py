import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from .api.admin import router as admin_router
from .api.auth import router as auth_router
from .api.chat import router as chat_router
from .api.knowledge import router as knowledge_router
from .api.sessions import router as sessions_router
from .core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动
    import os
    # 设置 HuggingFace 镜像（国内网络环境必须）
    if not os.environ.get("HF_ENDPOINT"):
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

    logger.remove()
    logger.add(
        "logs/app.log",
        rotation="1 day",
        retention="30 days",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
        backtrace=False,
        diagnose=True,
    )
    logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")
    logger.info("正在启动 AI 智能客服系统...")
    logger.info("数据库地址: {}", settings.database_url)
    logger.info("正在补处理遗留文档...")
    from .services.ingestion import process_pending_documents
    try:
        await process_pending_documents()
    except Exception as e:
        logger.warning(f"补处理文档跳过: {e}")

    logger.info("正在从 Qdrant 重建 BM25 索引...")
    from .services.ingestion import rebuild_bm25_from_qdrant
    try:
        await rebuild_bm25_from_qdrant()
    except Exception as e:
        logger.warning(f"BM25 重建跳过（Qdrant 可能尚未就绪）: {e}")

    # 预热模型：并行加载 Embedding + 重排序，首次对话不再等待
    import asyncio
    from .core.embedding import preload as preload_embedding
    from .services.retrieval import preload_reranker
    try:
        await asyncio.gather(preload_embedding(), preload_reranker())
    except Exception as e:
        logger.warning(f"模型预热跳过（可接受，首次对话自动加载）: {e}")

    logger.info("AI 智能客服系统启动完成")
    logger.warning(
        "RETRIEVAL_THRESHOLD={:.2f}, RETRIEVAL_TOP_K={}（默认值），"
        "TOP_K_FLOOR={}, TOP_K_OPT={}（未校准）。"
        "上线前请运行 pure_retrieval_scan 和 calibrate_top_k 进行校准。",
        settings.retrieval_threshold,
        settings.retrieval_top_k,
        settings.retrieval_top_k_floor,
        settings.retrieval_top_k_opt,
    )
    yield
    # 关闭
    logger.info("正在关闭系统...")


app = FastAPI(title="AI智能客服系统", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    logger.error("未捕获异常: {}", exc)
    logger.error("堆栈:\n{}", traceback.format_exc())
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误，请稍后再试"})


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(knowledge_router)
app.include_router(chat_router)
app.include_router(sessions_router)
app.include_router(admin_router)
