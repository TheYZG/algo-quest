"""parse_json_block 健壮性测试"""
import pytest

from app.graph.utils import parse_json_block


def test_裸JSON():
    assert parse_json_block('{"a": 1}') == {"a": 1}


def test_markdown代码块包裹():
    text = '好的，这是结果：\n```json\n{"a": [1, 2]}\n```\n以上。'
    assert parse_json_block(text) == {"a": [1, 2]}


def test_前后杂文本():
    assert parse_json_block('前置说明 {"a": "b"} 后置说明') == {"a": "b"}


def test_非法输入返回None():
    assert parse_json_block("完全不是 JSON") is None
    assert parse_json_block("") is None
