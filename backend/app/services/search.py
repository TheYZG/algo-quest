"""
语义搜索服务
利用 embedding + ChromaDB 实现自然语言搜题
"""
import json
from typing import Optional

from app.vectordb import get_collection
from app.services.embedding import embed_text
from app.schemas.all import ProblemBrief, SearchResult


def semantic_search(
    query: str,
    top_k: int = 10,
    difficulty: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> list[SearchResult]:
    """
    语义搜索题目

    Args:
        query: 自然语言查询（如 "类似背包问题的动态规划题目"）
        top_k: 返回结果数量
        difficulty: 难度过滤
        tags: 标签过滤

    Returns:
        搜索结果列表
    """
    collection = get_collection()

    # 生成查询向量
    query_embedding = embed_text(query)

    # ChromaDB 查询
    # 多取一些结果以便后续过滤
    n_results = min(top_k * 3, 50)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["metadatas", "distances"],
    )

    if not results["ids"] or not results["ids"][0]:
        return []

    search_results = []
    for i, prob_id in enumerate(results["ids"][0]):
        metadata = results["metadatas"][0][i]
        distance = results["distances"][0][i]

        # 相似度转换（cosine距离 → 相似度分数 0-1）
        relevance = 1.0 - (distance / 2.0)
        relevance = max(0.0, min(1.0, relevance))

        tags_list = json.loads(metadata.get("tags", "[]"))

        # 难度过滤
        if difficulty and metadata.get("difficulty") != difficulty:
            continue

        # 标签过滤
        if tags:
            if not any(t in tags_list for t in tags):
                continue

        ac_rate = 0.0
        accepted = metadata.get("accepted", 0)
        submissions = metadata.get("submissions", 1)
        if submissions > 0:
            ac_rate = round(accepted / submissions * 100, 1)

        problem = ProblemBrief(
            id=prob_id,
            number=metadata.get("number", 0),
            title=metadata.get("title", ""),
            title_cn=metadata.get("title_cn", ""),
            difficulty=metadata.get("difficulty", "Medium"),
            tags=tags_list,
            ac_rate=ac_rate,
            kingdom=metadata.get("kingdom", ""),
            kingdom_emoji=metadata.get("kingdom_emoji", ""),
        )

        search_results.append(SearchResult(
            problem=problem,
            relevance=round(relevance, 4),
        ))

    # 截取 top_k
    return search_results[:top_k]
