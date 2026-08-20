"""测试夹具：事件循环由 pytest-asyncio auto 模式管理"""
import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"
