"""
ChromaDB 向量数据库客户端
用于语义搜索题目
"""
import os
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.config import get_settings

settings = get_settings()

# 持久化路径
persist_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_data")
os.makedirs(persist_dir, exist_ok=True)

_client = chromadb.PersistentClient(
    path=persist_dir,
    settings=ChromaSettings(anonymized_telemetry=False),
)


def get_collection():
    """获取或创建题目向量集合"""
    try:
        return _client.get_collection(settings.CHROMA_COLLECTION)
    except Exception:
        return _client.create_collection(
            name=settings.CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )


def reset_collection():
    """重建集合（重新导入时使用）"""
    try:
        _client.delete_collection(settings.CHROMA_COLLECTION)
    except Exception:
        pass
    return _client.create_collection(
        name=settings.CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


def get_collection_stats():
    """获取集合统计"""
    col = get_collection()
    return {
        "count": col.count(),
        "name": settings.CHROMA_COLLECTION,
    }
