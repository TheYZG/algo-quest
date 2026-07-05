"""
测试用例管理服务
为题目提供测试用例，支持预定义用例和从题目描述中提取
"""
import json
import logging
import re
import os
import glob
from typing import Optional

logger = logging.getLogger(__name__)

# LeetCode 题解数据集根目录
SOLUTION_ROOT = os.environ.get(
    "SOLUTION_ROOT",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "solution")
)

# ============================================================
# 预定义测试用例 — 覆盖 25 个冒险关卡 + 常用题目
# ============================================================
PREDEFINED_TEST_CASES: dict[str, list[dict]] = {
    # 1. Two Sum
    "0001": [
        {"input": "[2,7,11,15], 9", "expected": "[0,1]"},
        {"input": "[3,2,4], 6", "expected": "[1,2]"},
        {"input": "[3,3], 6", "expected": "[0,1]"},
    ],
    # 20. Valid Parentheses
    "0020": [
        {"input": '"()"', "expected": "true"},
        {"input": '"()[]{}"', "expected": "true"},
        {"input": '"(]"', "expected": "false"},
        {"input": '"([])"', "expected": "true"},
    ],
    # 9. Palindrome Number
    "0009": [
        {"input": "121", "expected": "true"},
        {"input": "-121", "expected": "false"},
        {"input": "10", "expected": "false"},
    ],
    # 11. Container With Most Water
    "0011": [
        {"input": "[1,8,6,2,5,4,8,3,7]", "expected": "49"},
        {"input": "[1,1]", "expected": "1"},
    ],
    # 704. Binary Search
    "0704": [
        {"input": "[-1,0,3,5,9,12], 9", "expected": "4"},
        {"input": "[-1,0,3,5,9,12], 2", "expected": "-1"},
    ],
    # 70. Climbing Stairs
    "0070": [
        {"input": "2", "expected": "2"},
        {"input": "3", "expected": "3"},
        {"input": "4", "expected": "5"},
    ],
    # 121. Best Time to Buy and Sell Stock
    "0121": [
        {"input": "[7,1,5,3,6,4]", "expected": "5"},
        {"input": "[7,6,4,3,1]", "expected": "0"},
    ],
    # 53. Maximum Subarray
    "0053": [
        {"input": "[-2,1,-3,4,-1,2,1,-5,4]", "expected": "6"},
        {"input": "[1]", "expected": "1"},
        {"input": "[5,4,-1,7,8]", "expected": "23"},
    ],
    # 206. Reverse Linked List
    "0206": [
        {"input": "[1,2,3,4,5]", "expected": "[5,4,3,2,1]"},
        {"input": "[1,2]", "expected": "[2,1]"},
        {"input": "[]", "expected": "[]"},
    ],
    # 3. Longest Substring Without Repeating Characters
    "0003": [
        {"input": '"abcabcbb"', "expected": "3"},
        {"input": '"bbbbb"', "expected": "1"},
        {"input": '"pwwkew"', "expected": "3"},
    ],
    # 94. Binary Tree Inorder Traversal
    "0094": [
        {"input": "[1,null,2,3]", "expected": "[1,3,2]"},
        {"input": "[]", "expected": "[]"},
        {"input": "[1]", "expected": "[1]"},
    ],
    # 104. Maximum Depth of Binary Tree
    "0104": [
        {"input": "[3,9,20,null,null,15,7]", "expected": "3"},
        {"input": "[1,null,2]", "expected": "2"},
    ],
    # 200. Number of Islands
    "0200": [
        {"input": '[["1","1","1","1","0"],["1","1","0","1","0"],["1","1","0","0","0"],["0","0","0","0","0"]]', "expected": "1"},
        {"input": '[["1","1","0","0","0"],["1","1","0","0","0"],["0","0","1","0","0"],["0","0","0","1","1"]]', "expected": "3"},
    ],
    # 146. LRU Cache (特殊处理 — 用简化的测试)
    "0146": [
        {"input": "2", "expected": "null"},
    ],
    # 15. 3Sum
    "0015": [
        {"input": "[-1,0,1,2,-1,-4]", "expected": "[[-1,-1,2],[-1,0,1]]"},
        {"input": "[0,1,1]", "expected": "[]"},
        {"input": "[0,0,0]", "expected": "[[0,0,0]]"},
    ],
    # 49. Group Anagrams
    "0049": [
        {"input": '["eat","tea","tan","ate","nat","bat"]', "expected": '[["bat"],["nat","tan"],["ate","eat","tea"]]'},
        {"input": '[""]', "expected": '[[""]]'},
        {"input": '["a"]', "expected": '[["a"]]'},
    ],
    # 198. House Robber
    "0198": [
        {"input": "[1,2,3,1]", "expected": "4"},
        {"input": "[2,7,9,3,1]", "expected": "12"},
    ],
    # 55. Jump Game
    "0055": [
        {"input": "[2,3,1,1,4]", "expected": "true"},
        {"input": "[3,2,1,0,4]", "expected": "false"},
    ],
    # 33. Search in Rotated Sorted Array
    "0033": [
        {"input": "[4,5,6,7,0,1,2], 0", "expected": "4"},
        {"input": "[4,5,6,7,0,1,2], 3", "expected": "-1"},
        {"input": "[1], 0", "expected": "-1"},
    ],
    # 236. LCA of Binary Tree
    "0236": [
        {"input": "[3,5,1,6,2,0,8,null,null,7,4], 5, 1", "expected": "3"},
        {"input": "[3,5,1,6,2,0,8,null,null,7,4], 5, 4", "expected": "5"},
    ],
    # 300. Longest Increasing Subsequence
    "0300": [
        {"input": "[10,9,2,5,3,7,101,18]", "expected": "4"},
        {"input": "[0,1,0,3,2,3]", "expected": "4"},
        {"input": "[7,7,7,7,7,7,7]", "expected": "1"},
    ],
    # 207. Course Schedule
    "0207": [
        {"input": "2, [[1,0]]", "expected": "true"},
        {"input": "2, [[1,0],[0,1]]", "expected": "false"},
    ],
    # 322. Coin Change
    "0322": [
        {"input": "[1,2,5], 11", "expected": "3"},
        {"input": "[2], 3", "expected": "-1"},
        {"input": "[1], 0", "expected": "0"},
    ],
    # 42. Trapping Rain Water
    "0042": [
        {"input": "[0,1,0,2,1,0,1,3,2,1,2,1]", "expected": "6"},
        {"input": "[4,2,0,3,2,5]", "expected": "9"},
    ],
    # 76. Minimum Window Substring
    "0076": [
        {"input": '"ADOBECODEBANC", "ABC"', "expected": '"BANC"'},
        {"input": '"a", "a"', "expected": '"a"'},
        {"input": '"a", "aa"', "expected": '""'},
    ],
    # 4. Median of Two Sorted Arrays
    "0004": [
        {"input": "[1,3], [2]", "expected": "2.0"},
        {"input": "[1,2], [3,4]", "expected": "2.5"},
    ],
}

# ============================================================
# 从 README.md 中解析输入/输出对
# ============================================================
_INPUT_PATTERN = re.compile(r'<strong>输入[：:]</strong>\s*(.+?)(?:\n|</p>|</pre>|$)', re.DOTALL)
_OUTPUT_PATTERN = re.compile(r'<strong>输出[：:]</strong>\s*(.+?)(?:\n|</p>|</pre>|$)', re.DOTALL)
_VAR_ASSIGN_PATTERN = re.compile(r'^\w+\s*=\s*')
# 匹配 pre 标签内的完整示例块
_PRE_BLOCK_PATTERN = re.compile(r'<pre>\s*<strong>输入[：:]</strong>\s*(.+?)\s*<strong>输出[：:]</strong>\s*(.+?)\s*</pre>', re.DOTALL)
# 匹配带 <strong> 标签分隔的连续输入/输出对
_TAG_IO_PATTERN = re.compile(r'<strong>输入[：:]</strong>\s*(.+?)\s*<strong>输出[：:]</strong>\s*(.+?)(?=<strong>|<p>|</pre>|$)', re.DOTALL)


def get_test_cases(problem_id: str) -> list[dict]:
    """
    获取题目的测试用例

    优先级:
    1. 预定义测试用例
    2. 从 README.md 题目描述中自动解析

    Args:
        problem_id: 题目 ID (如 "11" 或 "0011")

    Returns:
        测试用例列表 [{"input": "...", "expected": "..."}]
    """
    pid = str(problem_id).zfill(4)
    if pid in PREDEFINED_TEST_CASES:
        return PREDEFINED_TEST_CASES[pid]

    # 尝试从 LeetCode README.md 中解析示例
    cases = _extract_from_description(pid)
    if cases:
        # 缓存到预定义字典中，避免重复解析
        PREDEFINED_TEST_CASES[pid] = cases
    return cases


def get_all_test_case_ids() -> list[str]:
    """获取所有有预定义测试用例的题目 ID"""
    return list(PREDEFINED_TEST_CASES.keys())


def _find_readme(problem_id: str) -> Optional[str]:
    """根据题目 ID 查找对应的 README.md 文件"""
    num = int(problem_id.lstrip('0') or '0')
    low = (num // 100) * 100
    high = low + 99
    range_dir = f"{low:04d}-{high:04d}"
    dir_path = os.path.join(SOLUTION_ROOT, range_dir)

    if not os.path.isdir(dir_path):
        # Fallback: try to find the range directory
        for d in os.listdir(SOLUTION_ROOT):
            if d.startswith(f"{low:04d}"):
                dir_path = os.path.join(SOLUTION_ROOT, d)
                break
        else:
            return None

    pattern = os.path.join(dir_path, f"{problem_id}.*", "README.md")
    matches = glob.glob(pattern)
    if matches:
        return matches[0]
    return None


def _clean_input(text: str) -> str:
    """清洗输入文本，去掉变量名如 'height = ' """
    text = text.strip()
    # 去掉 HTML 注释和 &nbsp;
    text = re.sub(r'<!--.*?-->', '', text)
    text = text.replace('&nbsp;', '')
    # 如果包含多个变量赋值（如 "nums1 = [1,3], nums2 = [2]"），去掉变量名
    parts = re.split(r',\s*(?=[a-zA-Z_]\w*\s*=)', text)
    if len(parts) == 1:
        # 单变量情况：去掉开头的 "var = "
        text = re.sub(_VAR_ASSIGN_PATTERN, '', parts[0]).strip()
    else:
        # 多变量情况：每个都去掉 "var = "
        text = ', '.join(re.sub(_VAR_ASSIGN_PATTERN, '', p).strip() for p in parts)
    return text


def _clean_output(text: str) -> str:
    """清洗输出文本：去掉 HTML 标签和解释文本"""
    text = text.strip()
    # 去掉 HTML 注释和 &nbsp;
    text = re.sub(r'<!--.*?-->', '', text)
    text = text.replace('&nbsp;', '')
    # 去掉所有 HTML 标签（如 <strong>解释：</strong>）
    text = re.sub(r'<[^>]+>', '', text)
    # 如果是多行，只取第一行（后面的通常是解释）
    text = text.split('\n')[0].strip()
    return text


def _extract_from_description(problem_id: str) -> list[dict]:
    """
    从 LeetCode README.md 题目描述中解析测试用例

    解析策略（按优先级）：
    1. 匹配 <pre> 标签内的完整 输入/输出 对
    2. 匹配连续的 <strong>输入：</strong>xxx<br><strong>输出：</strong>yyy 格式
    3. 分别匹配输入行和输出行，按顺序配对

    Args:
        problem_id: 题目 ID (4位补零格式，如 "0011")

    Returns:
        测试用例列表 [{"input": "...", "expected": "..."}]
    """
    readme_path = _find_readme(problem_id)
    if not readme_path:
        logger.debug(f"题目 {problem_id}: 找不到 README.md 文件")
        return []

    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        logger.warning(f"题目 {problem_id}: 读取 README.md 失败: {e}")
        return []

    test_cases = []

    # 策略 1: 匹配 <pre> 块中的完整 输入/输出 对
    for m in _PRE_BLOCK_PATTERN.finditer(content):
        input_text = _clean_input(m.group(1))
        output_text = _clean_output(m.group(2))
        if input_text and output_text:
            test_cases.append({"input": input_text, "expected": output_text})

    if test_cases:
        logger.info(f"题目 {problem_id}: 从 README.md 解析到 {len(test_cases)} 个测试用例（策略1-pre块）")
        return test_cases

    # 策略 2: 匹配带 <strong> 标签的连续 IO 对
    for m in _TAG_IO_PATTERN.finditer(content):
        input_text = _clean_input(m.group(1))
        output_text = _clean_output(m.group(2))
        # 去掉尾巴上可能出现的下一个标签
        output_text = re.sub(r'<.*$', '', output_text).strip()
        if input_text and output_text:
            test_cases.append({"input": input_text, "expected": output_text})

    if test_cases:
        logger.info(f"题目 {problem_id}: 从 README.md 解析到 {len(test_cases)} 个测试用例（策略2-标签对）")
        return test_cases

    # 策略 3: 分别匹配输入和输出，按顺序配对
    inputs = []
    outputs = []
    for m in _INPUT_PATTERN.finditer(content):
        inp = _clean_input(m.group(1))
        if inp:
            inputs.append(inp)
    for m in _OUTPUT_PATTERN.finditer(content):
        out = _clean_output(m.group(1))
        if out:
            outputs.append(out)

    # 按顺序配对（取较短的）
    n = min(len(inputs), len(outputs))
    for i in range(n):
        test_cases.append({"input": inputs[i], "expected": outputs[i]})

    if test_cases:
        logger.info(f"题目 {problem_id}: 从 README.md 解析到 {len(test_cases)} 个测试用例（策略3-顺序配对）")
    else:
        logger.info(f"题目 {problem_id}: 未能从 README.md 提取到测试用例")

    return test_cases
