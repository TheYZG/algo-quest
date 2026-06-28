"""
题目数据导入器
从 doocs/leetcode 数据集中解析题目，同时写入 SQLite 和 ChromaDB
- SQLite：完整题目数据（描述、代码模板、解答、统计）
- ChromaDB：向量化索引（语义搜索用）
"""
import logging
import os
import re
import json
import sqlite3
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from app.config import get_settings
from app.vectordb import reset_collection
from app.services.embedding import embed_texts

logger = logging.getLogger(__name__)

settings = get_settings()

# ============================================================
# 标签 → 算法王国 映射
# ============================================================
TAG_TO_KINGDOM: dict[str, tuple[str, str]] = {
    # 排序森林 🌲
    "排序": ("排序森林", "🌲"),
    "归并排序": ("排序森林", "🌲"),
    "快速选择": ("排序森林", "🌲"),
    "堆（优先队列）": ("排序森林", "🌲"),
    "拓扑排序": ("排序森林", "🌲"),
    # 动态规划圣殿 🏛️
    "动态规划": ("动态规划圣殿", "🏛️"),
    "记忆化搜索": ("动态规划圣殿", "🏛️"),
    "背包": ("动态规划圣殿", "🏛️"),
    "状态压缩": ("动态规划圣殿", "🏛️"),
    "树形DP": ("动态规划圣殿", "🏛️"),
    "数位DP": ("动态规划圣殿", "🏛️"),
    # 图论城堡 🏰
    "图": ("图论城堡", "🏰"),
    "深度优先搜索": ("图论城堡", "🏰"),
    "广度优先搜索": ("图论城堡", "🏰"),
    "并查集": ("图论城堡", "🏰"),
    "最短路": ("图论城堡", "🏰"),
    "最小生成树": ("图论城堡", "🏰"),
    "欧拉回路": ("图论城堡", "🏰"),
    "强连通分量": ("图论城堡", "🏰"),
    # 双指针峡谷 🌄
    "双指针": ("双指针峡谷", "🌄"),
    "滑动窗口": ("双指针峡谷", "🌄"),
    "二分查找": ("双指针峡谷", "🌄"),
    "分治": ("双指针峡谷", "🌄"),
    # 数据结构工坊 🔧
    "数组": ("数据结构工坊", "🔧"),
    "链表": ("数据结构工坊", "🔧"),
    "栈": ("数据结构工坊", "🔧"),
    "队列": ("数据结构工坊", "🔧"),
    "哈希表": ("数据结构工坊", "🔧"),
    "树": ("数据结构工坊", "🔧"),
    "二叉树": ("数据结构工坊", "🔧"),
    "二叉搜索树": ("数据结构工坊", "🔧"),
    "线段树": ("数据结构工坊", "🔧"),
    "树状数组": ("数据结构工坊", "🔧"),
    "设计": ("数据结构工坊", "🔧"),
    "前缀和": ("数据结构工坊", "🔧"),
    "有序集合": ("数据结构工坊", "🔧"),
    "单调栈": ("数据结构工坊", "🔧"),
    "单调队列": ("数据结构工坊", "🔧"),
    # 字符串神殿 📜
    "字符串": ("字符串神殿", "📜"),
    "字典树": ("字符串神殿", "📜"),
    "字符串匹配": ("字符串神殿", "📜"),
    # 回溯迷宫 🌀
    "回溯": ("回溯迷宫", "🌀"),
    "递归": ("回溯迷宫", "🌀"),
    "组合数学": ("回溯迷宫", "🌀"),
    # 贪心平原 🌾
    "贪心": ("贪心平原", "🌾"),
    "模拟": ("贪心平原", "🌾"),
    # 位运算星空 ✨
    "位运算": ("位运算星空", "✨"),
    # 数学高塔 🗼
    "数学": ("数学高塔", "🗼"),
    "几何": ("数学高塔", "🗼"),
    "数论": ("数学高塔", "🗼"),
    "概率与统计": ("数学高塔", "🗼"),
    "随机化": ("数学高塔", "🗼"),
    "博弈": ("数学高塔", "🗼"),
    # 混沌领域 🌪️
    "数据库": ("混沌领域", "🌪️"),
    "Shell": ("混沌领域", "🌪️"),
    "多线程": ("混沌领域", "🌪️"),
    "交互": ("混沌领域", "🌪️"),
    "脑筋急转弯": ("混沌领域", "🌪️"),
    "拒绝采样": ("混沌领域", "🌪️"),
    "水塘抽样": ("混沌领域", "🌪️"),
    "计数": ("混沌领域", "🌪️"),
    "计数排序": ("混沌领域", "🌪️"),
    "数据流": ("混沌领域", "🌪️"),
    "迭代器": ("混沌领域", "🌪️"),
    "函数式编程": ("混沌领域", "🌪️"),
    "滚动哈希": ("混沌领域", "🌪️"),
    "快速幂": ("混沌领域", "🌪️"),
}

DIFFICULTY_MAP = {
    "简单": "Easy",
    "中等": "Medium",
    "困难": "Hard",
}

# ============================================================
# 王国视觉配置 — 每个王国的完整元数据（前端从此获取所有渲染参数）
# ============================================================
KINGDOM_CONFIG: dict[str, dict] = {
    "数据结构工坊": {
        "id": "datastruct", "emoji": "🔧",
        "color": "#a78bfa", "bg": "#1a1428", "glow": "rgba(167,139,250,.25)",
        "chaos": False,
    },
    "排序森林": {
        "id": "sort", "emoji": "🌲",
        "color": "#4ade80", "bg": "#101e14", "glow": "rgba(74,222,128,.25)",
        "chaos": False,
    },
    "动态规划圣殿": {
        "id": "dp", "emoji": "🏛️",
        "color": "#f472b6", "bg": "#281020", "glow": "rgba(244,114,182,.25)",
        "chaos": False,
    },
    "图论城堡": {
        "id": "graph", "emoji": "🏰",
        "color": "#fb923c", "bg": "#241808", "glow": "rgba(251,146,60,.25)",
        "chaos": False,
    },
    "双指针峡谷": {
        "id": "search", "emoji": "🌄",
        "color": "#facc15", "bg": "#241e08", "glow": "rgba(250,204,21,.25)",
        "chaos": False,
    },
    "字符串神殿": {
        "id": "string", "emoji": "📜",
        "color": "#5eeadb", "bg": "#0e2428", "glow": "rgba(94,234,219,.25)",
        "chaos": False,
    },
    "回溯迷宫": {
        "id": "backtrack", "emoji": "🌀",
        "color": "#e879f9", "bg": "#200824", "glow": "rgba(232,121,249,.25)",
        "chaos": False,
    },
    "贪心平原": {
        "id": "greedy", "emoji": "🌾",
        "color": "#f87171", "bg": "#281414", "glow": "rgba(248,113,113,.25)",
        "chaos": False,
    },
    "位运算星空": {
        "id": "bitwise", "emoji": "✨",
        "color": "#60a5fa", "bg": "#0a1a28", "glow": "rgba(96,165,250,.25)",
        "chaos": False,
    },
    "数学高塔": {
        "id": "math", "emoji": "🗼",
        "color": "#c084fc", "bg": "#181028", "glow": "rgba(192,132,252,.25)",
        "chaos": False,
    },
    "混沌领域": {
        "id": "chaos", "emoji": "🌪️",
        "color": "rainbow", "bg": "#0d0d0d", "glow": "rgba(255,107,107,.15)",
        "chaos": True,
    },
}


def _get_sqlite_db_path() -> str:
    """计算 SQLite 数据库的绝对路径（与 database.py 保持一致）"""
    # importer.py 在 app/services/ 下，需要向上 3 层到 backend/
    _base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(_base_dir, settings.DATABASE_PATH)


def _slugify(dir_name: str) -> str:
    """从目录名生成 URL slug: '0001.Two Sum' -> 'two-sum'"""
    match = re.match(r'\d+\.(.+)', dir_name)
    if match:
        name = match.group(1)
    else:
        name = dir_name
    # 转小写、空格转连字符、去除非字母数字连字符
    slug = name.lower().replace(" ", "-")
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug


# ============================================================
# 数据结构
# ============================================================
@dataclass
class ProblemData:
    """解析后的题目数据"""
    id: str
    number: int
    title: str
    title_cn: str
    slug: str = ""
    difficulty: str = "Medium"
    tags: list[str] = field(default_factory=list)
    description_html: str = ""
    description_cn_html: str = ""
    hints: list[str] = field(default_factory=list)
    solutions: dict[str, str] = field(default_factory=dict)
    likes: int = 0
    dislikes: int = 0
    accepted: int = 0
    submissions: int = 0
    kingdom: str = ""
    kingdom_emoji: str = ""
    kingdoms: list = field(default_factory=list)  # [(name, emoji), ...]

    @property
    def text_for_embedding(self) -> str:
        """生成用于向量化的文本"""
        parts = [
            f"题目: {self.title_cn or self.title}",
            f"难度: {self.difficulty}",
            f"标签: {', '.join(self.tags)}",
            f"王国: {self.kingdom}",
        ]
        if self.description_cn_html:
            text = re.sub(r'<[^>]+>', ' ', self.description_cn_html)
            text = re.sub(r'\s+', ' ', text).strip()
            parts.append(f"描述: {text[:500]}")
        return "\n".join(parts)


# ============================================================
# 解析函数
# ============================================================
def parse_frontmatter(content: str) -> dict:
    """解析 YAML frontmatter"""
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except Exception:
        return {}


def extract_body(content: str) -> str:
    """提取正文（去除 frontmatter）"""
    if not content.startswith("---"):
        return content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return content
    return parts[2].strip()


def parse_problem(problem_dir: str) -> Optional[ProblemData]:
    """解析单个题目目录"""
    dir_path = Path(problem_dir)
    readme_cn = dir_path / "README.md"
    readme_en = dir_path / "README_EN.md"

    if not readme_cn.exists():
        return None

    # 解析中文 README
    cn_content = readme_cn.read_text(encoding="utf-8", errors="ignore")
    cn_frontmatter = parse_frontmatter(cn_content)
    cn_body = extract_body(cn_content)

    # 提取中文标题
    title_cn_match = re.search(r'#\s*\[\d+\.\s*(.+?)\]', cn_body)
    title_cn = title_cn_match.group(1) if title_cn_match else dir_path.name

    # 提取英文标题
    title = dir_path.name
    title_match = re.match(r'\d+\.(.+)', dir_path.name)
    if title_match:
        title = title_match.group(1).strip()

    # 生成 slug
    slug = _slugify(dir_path.name)

    # 提取题目编号
    number_match = re.match(r'(\d+)', dir_path.name)
    number = int(number_match.group(1)) if number_match else 0

    # 难度
    raw_difficulty = cn_frontmatter.get("difficulty", "中等")
    difficulty = DIFFICULTY_MAP.get(raw_difficulty, "Medium")

    # 标签
    tags = cn_frontmatter.get("tags", [])

    # 算法王国 — 收集所有匹配的王国（混沌领域作为兜底，始终包含）
    kingdom = "混沌领域"
    kingdom_emoji = "🌪️"
    kingdoms_entries: list[tuple[str, str]] = []
    seen_kingdoms: set[str] = set()
    for tag in tags:
        if tag in TAG_TO_KINGDOM:
            k_name, k_emoji = TAG_TO_KINGDOM[tag]
            if k_name not in seen_kingdoms:
                seen_kingdoms.add(k_name)
                kingdoms_entries.append((k_name, k_emoji))
                if kingdom == "混沌领域":
                    kingdom, kingdom_emoji = k_name, k_emoji

    # 确保所有题都包含混沌领域
    if "混沌领域" not in seen_kingdoms:
        kingdoms_entries.append(("混沌领域", "🌪️"))
    kingdoms_json = json.dumps(kingdoms_entries, ensure_ascii=False)

    # 解析描述（中文）— 使用 <!-- description:start/end --> 标记精确提取
    description_cn_html = ""
    desc_cn_match = re.search(
        r'<!--\s*description:start\s*-->(.*?)<!--\s*description:end\s*-->',
        cn_body, re.DOTALL
    )
    if desc_cn_match:
        description_cn_html = desc_cn_match.group(1).strip()

    # 解析英文描述
    description_html = ""
    if readme_en.exists():
        en_content = readme_en.read_text(encoding="utf-8", errors="ignore")
        en_body = extract_body(en_content)
        en_desc_match = re.search(
            r'<!--\s*description:start\s*-->(.*?)<!--\s*description:end\s*-->',
            en_body, re.DOTALL
        )
        if en_desc_match:
            description_html = en_desc_match.group(1).strip()

    # 提取提示 — 直接匹配 <ul> 中的 <li> 项（紧跟 <strong>提示</strong> 之后）
    hints = []
    hint_ul_match = re.search(
        r'<strong>提示[：:]</strong>.*?<ul>(.*?)</ul>',
        cn_body, re.DOTALL
    )
    if hint_ul_match:
        hint_items = re.findall(r'<li[^>]*>(.*?)</li>', hint_ul_match.group(1), re.DOTALL)
        hints.extend(hint_items)

    # 提取题解代码
    solutions = {}
    for ext, lang in {
        ".py": "python", ".java": "java", ".cpp": "cpp",
        ".go": "go", ".js": "javascript", ".ts": "typescript",
        ".rs": "rust", ".kt": "kotlin", ".swift": "swift",
        ".cs": "csharp", ".rb": "ruby", ".scala": "scala",
        ".php": "php",
    }.items():
        sol_file = None
        for f in dir_path.iterdir():
            if f.name.startswith("Solution") and f.suffix == ext:
                sol_file = f
                break
        if sol_file:
            try:
                code = sol_file.read_text(encoding="utf-8", errors="ignore")
                if len(code) < 20000:
                    solutions[lang] = code
            except Exception:
                pass

    # 统计信息（从英文 README 解析）
    likes, dislikes, accepted, submissions = 0, 0, 0, 0
    if readme_en.exists():
        en_frontmatter = parse_frontmatter(
            readme_en.read_text(encoding="utf-8", errors="ignore")
        )
        likes = en_frontmatter.get("likes", 0) or 0
        dislikes = en_frontmatter.get("dislikes", 0) or 0
        accepted = en_frontmatter.get("accepted", 0) or 0
        submissions = en_frontmatter.get("submissions", 0) or 0

    problem_id = f"{number:04d}"

    return ProblemData(
        id=problem_id,
        number=number,
        title=title,
        title_cn=title_cn,
        slug=slug,
        difficulty=difficulty,
        tags=tags,
        description_html=description_html,
        description_cn_html=description_cn_html,
        hints=hints,
        solutions=solutions,
        likes=likes,
        dislikes=dislikes,
        accepted=accepted,
        submissions=submissions or 1,
        kingdom=kingdom,
        kingdom_emoji=kingdom_emoji,
        kingdoms=kingdoms_entries,
    )


def _create_problems_table(conn: sqlite3.Connection):
    """创建 problems 表（先删后建，确保 schema 最新）"""
    conn.execute("DROP TABLE IF EXISTS problems")
    conn.execute("""
        CREATE TABLE problems (
            id TEXT PRIMARY KEY,
            number INTEGER UNIQUE NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            title_cn TEXT NOT NULL DEFAULT '',
            slug TEXT NOT NULL DEFAULT '',
            difficulty TEXT NOT NULL DEFAULT 'Medium',
            tags TEXT NOT NULL DEFAULT '[]',
            kingdom TEXT NOT NULL DEFAULT '混沌领域',
            kingdom_emoji TEXT NOT NULL DEFAULT '🌪️',
            kingdoms TEXT NOT NULL DEFAULT '["混沌领域"]',
            description_html TEXT NOT NULL DEFAULT '',
            description_cn_html TEXT NOT NULL DEFAULT '',
            hints TEXT NOT NULL DEFAULT '[]',
            solutions TEXT NOT NULL DEFAULT '{}',
            likes INTEGER NOT NULL DEFAULT 0,
            dislikes INTEGER NOT NULL DEFAULT 0,
            accepted INTEGER NOT NULL DEFAULT 0,
            submissions_count INTEGER NOT NULL DEFAULT 1,
            ac_rate REAL NOT NULL DEFAULT 0.0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_problems_number ON problems(number)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_problems_difficulty ON problems(difficulty)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_problems_kingdom ON problems(kingdom)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_problems_slug ON problems(slug)")
    conn.commit()


# ============================================================
# 主导入函数
# ============================================================
def import_problems(
    data_dir: str = None,
    batch_size: int = 100,
    progress_callback=None,
) -> dict:
    """
    导入所有题目到 SQLite（完整数据）+ ChromaDB（向量索引）

    注意：此函数在后台线程中执行，SQLite 使用原生 sqlite3 模块（同步）。
    """
    if data_dir is None:
        data_dir = settings.LEETCODE_DATA_DIR

    data_path = Path(data_dir)
    if not data_path.exists():
        raise FileNotFoundError(f"数据集目录不存在: {data_dir}")

    # 收集所有题目目录
    problem_dirs = []
    for subdir in sorted(data_path.iterdir()):
        if subdir.is_dir() and subdir.name[0].isdigit():
            for problem_dir in sorted(subdir.iterdir()):
                if problem_dir.is_dir():
                    problem_dirs.append(str(problem_dir))

    total = len(problem_dirs)
    logger.info("发现 %d 个题目目录，开始导入到 SQLite + ChromaDB...", total)

    # 重建 ChromaDB 集合
    collection = reset_collection()

    # ============================================================
    # 初始化 SQLite（原生同步，适合后台线程）
    # ============================================================
    db_path = _get_sqlite_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _create_problems_table(conn)
    # 清空旧数据
    conn.execute("DELETE FROM problems")
    conn.commit()
    logger.info("SQLite problems 表已清空，准备写入。路径: %s", db_path)

    # 统计
    stats = {
        "total": total,
        "imported": 0,
        "sql_written": 0,
        "skipped": 0,
        "errors": 0,
        "total_solutions": 0,
        "by_difficulty": {"Easy": 0, "Medium": 0, "Hard": 0},
        "by_kingdom": {},
    }

    # 批量导入
    for i in range(0, total, batch_size):
        batch = problem_dirs[i : i + batch_size]
        ids_batch = []
        embeddings_batch = []
        metadatas_batch = []
        documents_batch = []

        # 收集本批的 SQL 数据
        sql_rows = []

        for prob_dir in batch:
            try:
                problem = parse_problem(prob_dir)
                if problem is None:
                    stats["skipped"] += 1
                    continue

                embed_text = problem.text_for_embedding
                ac_rate = round(problem.accepted / problem.submissions * 100, 1) \
                    if problem.submissions > 0 else 0.0

                # ── ChromaDB 数据 ──
                ids_batch.append(problem.id)
                documents_batch.append(embed_text)
                metadatas_batch.append({
                    "number": problem.number,
                    "title": problem.title,
                    "title_cn": problem.title_cn,
                    "slug": problem.slug,
                    "difficulty": problem.difficulty,
                    "tags": json.dumps(problem.tags, ensure_ascii=False),
                    "kingdom": problem.kingdom,
                    "kingdom_emoji": problem.kingdom_emoji,
                    "description_cn": problem.description_cn_html[:1000],
                    "description_en": problem.description_html[:1000],
                    "hints": json.dumps(problem.hints, ensure_ascii=False),
                    "solutions": json.dumps(
                        {k: v[:200] for k, v in problem.solutions.items()},
                        ensure_ascii=False,
                    ),
                    "likes": problem.likes,
                    "dislikes": problem.dislikes,
                    "accepted": problem.accepted,
                    "submissions": problem.submissions,
                })

                # ── SQLite 数据 ──
                kingdoms_data = json.dumps(
                    problem.kingdoms if problem.kingdoms else [("混沌领域", "🌪️")],
                    ensure_ascii=False
                )
                sql_rows.append((
                    problem.id,
                    problem.number,
                    problem.title,
                    problem.title_cn,
                    problem.slug,
                    problem.difficulty,
                    json.dumps(problem.tags, ensure_ascii=False),
                    problem.kingdom,
                    problem.kingdom_emoji,
                    kingdoms_data,
                    problem.description_html,
                    problem.description_cn_html,
                    json.dumps(problem.hints, ensure_ascii=False),
                    json.dumps(problem.solutions, ensure_ascii=False),
                    problem.likes,
                    problem.dislikes,
                    problem.accepted,
                    problem.submissions,
                    ac_rate,
                ))

                stats["imported"] += 1
                stats["total_solutions"] += len(problem.solutions)
                stats["by_difficulty"][problem.difficulty] = (
                    stats["by_difficulty"].get(problem.difficulty, 0) + 1
                )
                stats["by_kingdom"][problem.kingdom] = (
                    stats["by_kingdom"].get(problem.kingdom, 0) + 1
                )

            except Exception as e:
                logger.warning("解析失败: %s - %s", prob_dir, e)
                stats["errors"] += 1

        # ── 写入 SQLite ──
        if sql_rows:
            try:
                conn.executemany(
                    """INSERT OR REPLACE INTO problems
                    (id, number, title, title_cn, slug, difficulty, tags,
                     kingdom, kingdom_emoji, kingdoms, description_html, description_cn_html,
                     hints, solutions, likes, dislikes, accepted, submissions_count, ac_rate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    sql_rows,
                )
                conn.commit()
                stats["sql_written"] += len(sql_rows)
            except Exception as e:
                logger.error("SQLite 写入失败: %s", e)

        # ── 写入 ChromaDB ──
        if ids_batch:
            try:
                embeddings_batch = embed_texts(documents_batch)
                collection.add(
                    ids=ids_batch,
                    embeddings=embeddings_batch,
                    documents=documents_batch,
                    metadatas=metadatas_batch,
                )
            except Exception as e:
                logger.error("ChromaDB 写入失败: %s", e)

        progress = min(i + batch_size, total)
        if progress_callback:
            progress_callback(progress, total, batch[-1] if batch else "")
        logger.info(
            "进度: %d/%d (SQL:%d, 解答:%d)",
            progress, total, stats["sql_written"], stats["total_solutions"],
        )

    # 关闭 SQLite 连接
    conn.close()

    logger.info(
        "导入完成! 成功: %d, SQL写入: %d, 跳过: %d, 错误: %d",
        stats["imported"], stats["sql_written"], stats["skipped"], stats["errors"],
    )
    logger.info("难度分布: %s", stats["by_difficulty"])

    return stats
