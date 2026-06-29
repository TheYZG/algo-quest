"""
Embedding 服务 - 使用 sentence-transformers 生成文本向量
"""
import logging
from functools import lru_cache
from sentence_transformers import SentenceTransformer
from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """懒加载 embedding 模型（单例，首次加载后缓存）"""
    print(f"Loading embedding model: {settings.EMBEDDING_MODEL} ...")
    model = SentenceTransformer(settings.EMBEDDING_MODEL)
    print(f"Model loaded. Dimension: {model.get_sentence_embedding_dimension()}")
    return model


def embed_text(text: str) -> list[float]:
    """将单段文本转为向量"""
    model = get_embedding_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量文本转为向量"""
    model = get_embedding_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()

