from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.models import Distance, VectorParams, HnswConfigDiff

from .config import settings

COLLECTION_NAME = "knowledge_chunks"
VECTOR_SIZE = 1024  # bge-large-zh-v1.5 输出维度

_qdrant: QdrantClient | None = None


async def get_qdrant() -> QdrantClient:
    """获取 Qdrant 客户端（懒初始化）"""
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
        _init_collection(_qdrant)
    return _qdrant


def _init_collection(client: QdrantClient) -> None:
    """初始化集合和负载索引"""
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in collections:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            hnsw_config=HnswConfigDiff(m=16, ef_construct=100),
        )
    # 确保负载索引存在
    client.create_payload_index(
        collection_name=COLLECTION_NAME, field_name="kb_id", field_schema=qmodels.PayloadSchemaType.INTEGER
    )
    client.create_payload_index(
        collection_name=COLLECTION_NAME, field_name="doc_id", field_schema=qmodels.PayloadSchemaType.INTEGER
    )
