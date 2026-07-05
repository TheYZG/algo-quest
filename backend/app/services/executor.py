"""
Python 代码沙箱执行器
使用 subprocess 在隔离环境中执行用户代码，支持超时和输出捕获
"""
import asyncio
import logging
import os
import tempfile
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# 允许的安全内置函数白名单
SAFE_BUILTINS = {
    'abs', 'all', 'any', 'bin', 'bool', 'bytes', 'chr', 'complex',
    'dict', 'divmod', 'enumerate', 'filter', 'float', 'format', 'frozenset',
    'hash', 'hex', 'int', 'isinstance', 'issubclass', 'iter', 'len',
    'list', 'map', 'max', 'min', 'next', 'oct', 'ord', 'pow',
    'print', 'range', 'repr', 'reversed', 'round', 'set', 'slice',
    'sorted', 'str', 'sum', 'tuple', 'type', 'zip',
    'True', 'False', 'None', 'Exception', 'StopIteration',
    'ValueError', 'TypeError', 'KeyError', 'IndexError', 'ZeroDivisionError',
}


@dataclass
class TestResult:
    passed: bool
    input_data: str
    expected: str
    actual: str
    error: str = ""
    runtime_ms: float = 0.0


@dataclass
class ExecutionResult:
    success: bool
    status: str  # "accepted" | "wrong_answer" | "runtime_error" | "timeout" | "compile_error"
    passed: int = 0
    total: int = 0
    test_results: list[TestResult] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    error_message: str = ""
    runtime_ms: float = 0.0


# 安全沙箱包装脚本 (注入到用户代码之前)
SANDBOX_PREAMBLE = '''
import sys
import builtins
import math
import collections
import itertools
import functools
import heapq
import bisect
import re
import random
import json

# 保存原始 stdout（用于输出最终结果 JSON）
_original_stdout = sys.stdout

# 限制危险模块
for _mod in ('os', 'subprocess', 'shutil', 'socket', 'requests', 'urllib'):
    sys.modules[_mod] = None

# 安全 print 捕获（用户代码的 print 输出）
class _Capture:
    def __init__(self):
        self.lines = []
    def write(self, s):
        if s and s.strip():
            self.lines.append(s)
    def flush(self):
        pass

_capture = _Capture()
sys.stdout = _capture

'''


USER_CODE_WRAPPER = '''
# --- 用户代码开始 ---
{user_code}
# --- 用户代码结束 ---

# --- 测试执行 ---
_test_results = []
import time as _time

_tests = {test_cases_json}

# 找到用户定义的 Solution 类
_sol = Solution()
for _tc in _tests:
    _start = _time.perf_counter()
    try:
        # 解析输入
        _input_str = _tc.get("input", "")
        _expected_str = _tc.get("expected", "")

        # 尝试多种解析方式
        _parsed_input = _parse_simple(_input_str)
        _parsed_expected = _parse_simple(_expected_str)

        # 调用对应的入口方法
        _result = _call_entry(_sol, _parsed_input)

        _elapsed = (_time.perf_counter() - _start) * 1000

        # 比较结果
        _passed = _values_equal(_result, _parsed_expected)
        _test_results.append({{
            "passed": _passed,
            "input": _input_str,
            "expected": _expected_str,
            "actual": _format_output(_result),
            "error": "",
            "runtime_ms": round(_elapsed, 2)
        }})
    except Exception as _e:
        _elapsed = (_time.perf_counter() - _start) * 1000
        _test_results.append({{
            "passed": False,
            "input": _tc.get("input", ""),
            "expected": _tc.get("expected", ""),
            "actual": "",
            "error": str(_e),
            "runtime_ms": round(_elapsed, 2)
        }})

# 输出 JSON 结果（会被 stdout 捕获）
import json as _json
_original_stdout.write("__RESULT_JSON__" + _json.dumps(_test_results, ensure_ascii=False))
_original_stdout.flush()
'''


HELPER_FUNCTIONS = '''
def _parse_simple(s):
    """安全解析输入字符串 — 支持 JSON 和逗号分隔的多参数"""
    import json as _j
    if not s:
        return None
    # 先尝试整体 JSON 解析
    try:
        return _j.loads(s)
    except:
        pass
    # 如果包含括号/引号嵌套，用括号平衡来拆分
    if ('[' in s or '{' in s or '"' in s) and ',' in s:
        parts = _smart_split(s)
        if len(parts) > 1:
            return [_parse_value(p.strip()) for p in parts]
    # 简单逗号分隔
    parts = s.strip().split(",")
    if len(parts) == 1:
        return _parse_value(parts[0].strip())
    return [_parse_value(p.strip()) for p in parts]

def _smart_split(s):
    """智能分割：只在顶层逗号处分割，尊重括号和引号"""
    parts = []
    current = []
    depth = 0
    in_string = False
    string_char = None
    for ch in s:
        if in_string:
            current.append(ch)
            if ch == string_char and (len(current) < 2 or current[-2] != '\\\\'):
                in_string = False
        elif ch == '"' or ch == "'":
            in_string = True
            string_char = ch
            current.append(ch)
        elif ch in '([{':
            depth += 1
            current.append(ch)
        elif ch in ')]}':
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0:
            parts.append(''.join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append(''.join(current))
    return parts

def _parse_value(s):
    """解析单个值"""
    import json as _j
    try:
        return _j.loads(s)
    except:
        pass
    if s.lower() == "true": return True
    if s.lower() == "false": return False
    if s.lower() == "null" or s.lower() == "none": return None
    try:
        if "." in s: return float(s)
        return int(s)
    except:
        return s

def _call_entry(sol, parsed_input):
    """尝试调用 Solution 类的入口方法"""
    # 尝试常见的方法名
    for _name in dir(sol):
        if _name.startswith("_"):
            continue
        _attr = getattr(sol, _name)
        if callable(_attr):
            if parsed_input is None:
                return _attr()
            elif isinstance(parsed_input, list):
                # 先尝试作为单个参数传入（如 maxArea(height_list)）
                try:
                    return _attr(parsed_input)
                except TypeError:
                    # 如果失败，尝试解包（如 twoSum(nums, target)）
                    try:
                        return _attr(*parsed_input)
                    except TypeError:
                        # 最后尝试作为元组传入
                        return _attr(tuple(parsed_input))
            else:
                return _attr(parsed_input)
    return None

def _format_output(val):
    """格式化输出"""
    import json as _j
    if isinstance(val, bool):
        return str(val).lower()
    if val is None:
        return "null"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, str):
        return val
    if isinstance(val, (list, dict)):
        return _j.dumps(val, ensure_ascii=False)
    # ListNode / TreeNode 简单序列化
    if hasattr(val, "val"):
        return _j.dumps(_serialize_linked(val), ensure_ascii=False)
    return str(val)

def _serialize_linked(node):
    """序列化链表节点"""
    if node is None:
        return []
    result = []
    seen = set()
    while node is not None:
        node_id = id(node)
        if node_id in seen:
            result.append("...")
            break
        seen.add(node_id)
        result.append(node.val)
        node = node.next if hasattr(node, "next") else None
    return result

def _values_equal(a, b):
    """比较两个值是否相等"""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    # 浮点数比较
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) < 1e-6
        except:
            pass
    # list 比较
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return False
        return all(_values_equal(x, y) for x, y in zip(a, b))
    return str(a) == str(b)
'''


async def execute_python(
    user_code: str,
    test_cases: list[dict],
    timeout_sec: float = 5.0,
) -> ExecutionResult:
    """
    在沙箱中执行用户 Python 代码

    Args:
        user_code: 用户提交的 Python 代码
        test_cases: 测试用例列表 [{"input": "...", "expected": "..."}]
        timeout_sec: 超时时间（秒）

    Returns:
        ExecutionResult
    """
    if not test_cases:
        return ExecutionResult(
            success=False,
            status="compile_error",
            error_message="没有测试用例",
        )

    import json

    # 组合完整代码
    test_cases_json = json.dumps(test_cases, ensure_ascii=False)
    user_wrapper = USER_CODE_WRAPPER.format(
        user_code=user_code,
        test_cases_json=test_cases_json,
    )
    full_code = SANDBOX_PREAMBLE + HELPER_FUNCTIONS + user_wrapper

    # 写入临时文件
    tmp_dir = tempfile.mkdtemp(prefix="algo_exec_")
    tmp_file = os.path.join(tmp_dir, f"code_{uuid.uuid4().hex[:8]}.py")

    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(full_code)

        # 执行（使用当前 Python 解释器，确保在沙箱环境中可用）
        import sys
        python_exe = sys.executable

        proc = await asyncio.create_subprocess_exec(
            python_exe, tmp_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=tmp_dir,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_sec
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return ExecutionResult(
                success=False,
                status="timeout",
                error_message=f"代码执行超时（>{timeout_sec}秒）",
            )

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        # 解析测试结果
        result_marker = "__RESULT_JSON__"
        if result_marker in stdout:
            _, json_part = stdout.split(result_marker, 1)
            try:
                test_results_raw = json.loads(json_part.strip())
            except json.JSONDecodeError:
                return ExecutionResult(
                    success=False,
                    status="runtime_error",
                    stdout=stdout,
                    stderr=stderr,
                    error_message=f"无法解析测试结果: {json_part[:200]}",
                )
        else:
            # 可能是语法错误或导入错误
            error_msg = stderr.strip() or stdout.strip()[:500]
            # 过滤掉沙箱 preamble 中的 import 噪音
            if "ModuleNotFoundError" in error_msg or "ImportError" in error_msg:
                error_msg = "代码包含不支持的导入或模块引用"
            return ExecutionResult(
                success=False,
                status="compile_error",
                stdout=stdout,
                stderr=stderr,
                error_message=error_msg,
            )

        # 构建结果
        test_results = []
        for tr in test_results_raw:
            test_results.append(TestResult(
                passed=tr.get("passed", False),
                input_data=tr.get("input", ""),
                expected=tr.get("expected", ""),
                actual=tr.get("actual", ""),
                error=tr.get("error", ""),
                runtime_ms=tr.get("runtime_ms", 0.0),
            ))

        passed_count = sum(1 for t in test_results if t.passed)
        all_passed = passed_count == len(test_results)

        return ExecutionResult(
            success=all_passed,
            status="accepted" if all_passed else "wrong_answer",
            passed=passed_count,
            total=len(test_results),
            test_results=test_results,
            stdout=stdout.replace(result_marker + json_part, "").strip(),
            stderr=stderr,
            runtime_ms=sum(t.runtime_ms for t in test_results),
        )

    except Exception as e:
        logger.error(f"Code execution failed: {e}")
        return ExecutionResult(
            success=False,
            status="runtime_error",
            error_message=str(e),
        )
    finally:
        # 清理临时文件
        try:
            os.remove(tmp_file)
            os.rmdir(tmp_dir)
        except OSError:
            pass
