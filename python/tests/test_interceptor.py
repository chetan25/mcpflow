"""Tests for interceptor protocol."""

import pytest
from mcpflow.webmcp.interceptor import (
    DefaultInterceptor,
    CompositeInterceptor,
)


# Mock bridge for testing
class MockSecurityManager:
    def __init__(self):
        self.logs = []

    def check_tool_call(self, origin, tool_name):
        return True, None

    def log_tool_call(self, origin, tool, success, error=None, metadata=None):
        self.logs.append(
            {"origin": origin, "tool": tool, "success": success, "error": error}
        )


class MockBridge:
    def __init__(self):
        self.security = MockSecurityManager()
        self.policy_enforcer = None


@pytest.mark.asyncio
async def test_default_interceptor_creation():
    """Test DefaultInterceptor initialization."""
    bridge = MockBridge()
    interceptor = DefaultInterceptor(bridge)

    assert interceptor.bridge is bridge


@pytest.mark.asyncio
async def test_default_interceptor_before_tool_call_allowed():
    """Test before_tool_call when allowed."""
    bridge = MockBridge()
    interceptor = DefaultInterceptor(bridge)

    allowed, reason = await interceptor.before_tool_call(
        "test.com", "addToCart", {"sku": "123"}
    )

    assert allowed is True
    assert reason is None


@pytest.mark.asyncio
async def test_default_interceptor_after_tool_call_success():
    """Test after_tool_call with successful result."""
    bridge = MockBridge()
    interceptor = DefaultInterceptor(bridge)

    accepted = await interceptor.after_tool_call(
        "test.com",
        "addToCart",
        {"sku": "123"},
        result={"status": "ok"},
    )

    assert accepted is True


@pytest.mark.asyncio
async def test_default_interceptor_after_tool_call_error():
    """Test after_tool_call with error."""
    bridge = MockBridge()
    interceptor = DefaultInterceptor(bridge)

    accepted = await interceptor.after_tool_call(
        "test.com",
        "addToCart",
        {"sku": "123"},
        result=None,
        error="Item out of stock",
    )

    assert accepted is True  # Errors are logged but accepted


@pytest.mark.asyncio
async def test_default_interceptor_cross_origin_same_origin():
    """Test cross_origin_check for same origin."""
    bridge = MockBridge()
    interceptor = DefaultInterceptor(bridge)

    allowed = await interceptor.cross_origin_check(
        "example.com", "example.com", "searchItems"
    )

    assert allowed is True


@pytest.mark.asyncio
async def test_default_interceptor_cross_origin_different():
    """Test cross_origin_check for different origins."""
    bridge = MockBridge()
    interceptor = DefaultInterceptor(bridge)

    allowed = await interceptor.cross_origin_check(
        "shop.example.com", "payment.example.com", "processPayment"
    )

    assert allowed is True  # Default allows with logging


@pytest.mark.asyncio
async def test_default_interceptor_log_event():
    """Test event logging."""
    bridge = MockBridge()
    interceptor = DefaultInterceptor(bridge)

    await interceptor.log_event(
        "tool_call", "test.com", "addItem", {"qty": 5}
    )

    # Verify log entry exists
    assert len(bridge.security.logs) > 0


@pytest.mark.asyncio
async def test_composite_interceptor_single():
    """Test CompositeInterceptor with single interceptor."""
    bridge = MockBridge()
    interceptor1 = DefaultInterceptor(bridge)

    composite = CompositeInterceptor([interceptor1])

    allowed, reason = await composite.before_tool_call(
        "test.com", "test", {}
    )

    assert allowed is True


class MockInterceptorAllow:
    """Mock interceptor that allows."""

    async def before_tool_call(self, origin: str, tool_name: str, arguments: dict):
        return True, None

    async def after_tool_call(
        self, origin: str, tool_name: str, arguments: dict, result, error=None
    ):
        return True

    async def cross_origin_check(
        self,
        source_origin: str,
        target_origin: str,
        tool_name: str,
        data_preview=None,
    ):
        return True

    async def log_event(
        self, event_type: str, origin: str, tool_name: str, details=None
    ):
        pass


@pytest.mark.asyncio
async def test_composite_interceptor_multiple_all_allow():
    """Test CompositeInterceptor with multiple interceptors, all allow."""
    interceptor1 = MockInterceptorAllow()
    interceptor2 = MockInterceptorAllow()

    composite = CompositeInterceptor([interceptor1, interceptor2])

    allowed, reason = await composite.before_tool_call("test.com", "test", {})

    assert allowed is True


class MockInterceptorReject:
    """Mock interceptor that rejects."""

    async def before_tool_call(self, origin: str, tool_name: str, arguments: dict):
        return False, "Rejected by interceptor 1"

    async def after_tool_call(
        self, origin: str, tool_name: str, arguments: dict, result, error=None
    ):
        return True

    async def cross_origin_check(
        self,
        source_origin: str,
        target_origin: str,
        tool_name: str,
        data_preview=None,
    ):
        return True

    async def log_event(
        self, event_type: str, origin: str, tool_name: str, details=None
    ):
        pass


@pytest.mark.asyncio
async def test_composite_interceptor_first_rejects():
    """Test CompositeInterceptor when first interceptor rejects."""
    interceptor1 = MockInterceptorReject()
    interceptor2 = MockInterceptorAllow()

    composite = CompositeInterceptor([interceptor1, interceptor2])

    allowed, reason = await composite.before_tool_call("test.com", "test", {})

    assert allowed is False
    assert reason and "Rejected by interceptor 1" in reason


class MockInterceptorAfter:
    """Mock interceptor for after_tool_call testing."""

    def __init__(self, allow=True):
        self.allow = allow

    async def before_tool_call(self, origin: str, tool_name: str, arguments: dict):
        return True, None

    async def after_tool_call(
        self, origin: str, tool_name: str, arguments: dict, result, error=None
    ):
        return self.allow

    async def cross_origin_check(
        self,
        source_origin: str,
        target_origin: str,
        tool_name: str,
        data_preview=None,
    ):
        return True

    async def log_event(
        self, event_type: str, origin: str, tool_name: str, details=None
    ):
        pass


@pytest.mark.asyncio
async def test_composite_interceptor_after_tool_call():
    """Test composite after_tool_call."""
    composite = CompositeInterceptor(
        [
            MockInterceptorAfter(allow=True),
            MockInterceptorAfter(allow=False),  # This one rejects
            MockInterceptorAfter(allow=True),
        ]
    )

    accepted = await composite.after_tool_call(
        "test.com", "test", {}, {"result": "ok"}
    )

    assert accepted is False


class MockInterceptorCross:
    """Mock interceptor for cross_origin testing."""

    def __init__(self, allow=True):
        self.allow = allow

    async def before_tool_call(self, origin: str, tool_name: str, arguments: dict):
        return True, None

    async def after_tool_call(
        self, origin: str, tool_name: str, arguments: dict, result, error=None
    ):
        return True

    async def cross_origin_check(
        self,
        source_origin: str,
        target_origin: str,
        tool_name: str,
        data_preview=None,
    ):
        return self.allow

    async def log_event(
        self, event_type: str, origin: str, tool_name: str, details=None
    ):
        pass


@pytest.mark.asyncio
async def test_composite_interceptor_cross_origin():
    """Test composite cross_origin_check."""
    composite = CompositeInterceptor(
        [
            MockInterceptorCross(allow=True),
            MockInterceptorCross(allow=False),
            MockInterceptorCross(allow=True),
        ]
    )

    allowed = await composite.cross_origin_check("A.com", "B.com", "test")

    assert allowed is False
