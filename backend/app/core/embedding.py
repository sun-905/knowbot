import numpy as np
from loguru import logger

from .config import settings

_embedding_model = None


async def get_embedding_model():
    """懒加载 embedding 模型，GPU 优先，CUDA 不可用时自动降级 CPU"""
    global _embedding_model
    if _embedding_model is None:
        import torch
        from FlagEmbedding import FlagModel

        gpu_available = torch.cuda.is_available() and settings.embedding_device == "cuda"
        device_str = "cuda" if gpu_available else "cpu"
        logger.info(f"正在加载 embedding 模型: {settings.embedding_model}，设备: {device_str}")

        if gpu_available:
            try:
                _embedding_model = FlagModel(
                    settings.embedding_model,
                    query_instruction_for_retrieval="为这个句子生成表示以用于检索相关文章：",
                    use_fp16=True,
                )
                logger.info("Embedding 模型已加载到 GPU")
            except Exception as e:
                logger.warning(f"GPU 加载 Embedding 模型失败，降级 CPU: {e}")
                _embedding_model = FlagModel(
                    settings.embedding_model,
                    query_instruction_for_retrieval="为这个句子生成表示以用于检索相关文章：",
                    use_fp16=False,
                )
        else:
            _embedding_model = FlagModel(
                settings.embedding_model,
                query_instruction_for_retrieval="为这个句子生成表示以用于检索相关文章：",
                use_fp16=False,
            )
            logger.info("Embedding 模型已加载到 CPU")
    return _embedding_model


async def encode(texts: list[str]) -> np.ndarray:
    """将文本列表编码为向量"""
    model = await get_embedding_model()
    return model.encode(texts)


async def encode_query(query: str) -> np.ndarray:
    """将查询文本编码为向量"""
    model = await get_embedding_model()
    return model.encode_queries([query])[0]


async def preload():
    """启动时预热：提前加载 embedding 模型，避免首次对话等待"""
    logger.info("正在预热 Embedding 模型...")
    await get_embedding_model()
    logger.info("Embedding 模型预热完成")
