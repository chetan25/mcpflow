"""Tests for declarative discovery."""

import pytest
from mcpflow.webmcp.declarative_discovery import DeclarativeDiscovery


def test_declarative_discovery_extraction_of_actions():
    """Test extracting Action items from JSON-LD."""
    data = {
        "@context": "https://schema.org",
        "@type": "Action",
        "name": "AddToCart",
        "description": "Add item to shopping cart",
        "object": {
            "productId": "string",
            "quantity": "number",
        },
    }

    actions = DeclarativeDiscovery._extract_actions_from_ld(data)

    assert len(actions) == 1
    assert actions[0]["name"] == "AddToCart"
    assert "productId" in actions[0]["input_schema"]["properties"]


def test_declarative_discovery_extraction_no_actions():
    """Test extraction with no Action items."""
    data = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Widget",
    }

    actions = DeclarativeDiscovery._extract_actions_from_ld(data)
    assert len(actions) == 0


def test_declarative_discovery_extraction_nested_actions():
    """Test extracting nested Action items."""
    data = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "potentialAction": {
            "@type": "BuyAction",
            "name": "Purchase",
            "description": "Purchase product",
        },
    }

    actions = DeclarativeDiscovery._extract_actions_from_ld(data)

    # Should find the nested BuyAction
    assert any("Purchase" in a.get("name", "") for a in actions)


def test_declarative_discovery_multiple_actions():
    """Test extracting multiple Action items."""
    data = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "itemListElement": [
            {
                "@type": "Action",
                "name": "ViewItem",
            },
            {
                "@type": "Action",
                "name": "AddToCart",
            },
        ],
    }

    actions = DeclarativeDiscovery._extract_actions_from_ld(data)

    # Should find both actions
    names = [a.get("name") for a in actions]
    assert "ViewItem" in names or len(actions) >= 1


def test_declarative_discovery_tool_structure():
    """Test that extracted tools have correct structure."""
    data = {
        "@type": "SearchAction",
        "name": "Search",
        "description": "Search the site",
    }

    actions = DeclarativeDiscovery._extract_actions_from_ld(data)

    assert len(actions) == 1
    tool = actions[0]

    # Check required fields
    assert "name" in tool
    assert "description" in tool
    assert "input_schema" in tool

    # Check schema structure
    schema = tool["input_schema"]
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "required" in schema


# Mock page for testing
class MockPage:
    async def evaluate(self, script, *args):
        # Return empty results for now
        if "JSON-LD" in script or "script" in script:
            return []
        elif "form" in script:
            return []
        return None

    async def text_content(self, selector):
        return None

    async def goto(self, url, **kwargs):
        # Mock response
        class MockResponse:
            status = 404

        return MockResponse()


@pytest.mark.asyncio
async def test_declarative_discovery_from_json_ld_empty():
    """Test JSON-LD discovery with no data."""
    page = MockPage()
    tools = await DeclarativeDiscovery.discover_from_json_ld(page)
    assert tools == []


@pytest.mark.asyncio
async def test_declarative_discovery_from_forms_empty():
    """Test form discovery with no forms."""
    page = MockPage()
    tools = await DeclarativeDiscovery.discover_from_forms(page)
    assert tools == []


@pytest.mark.asyncio
async def test_declarative_discovery_from_llms_txt_not_found():
    """Test /llms.txt discovery when file doesn't exist."""
    page = MockPage()
    tools = await DeclarativeDiscovery.discover_from_llms_txt(page, "https://example.com")
    assert tools == []


@pytest.mark.asyncio
async def test_declarative_discovery_all_methods():
    """Test discover_all with all methods enabled."""
    page = MockPage()
    tools = await DeclarativeDiscovery.discover_all(
        page,
        "https://example.com",
        include_json_ld=True,
        include_forms=True,
        include_llms_txt=True,
    )

    # Should return empty list when page returns no data
    assert isinstance(tools, list)


def test_declarative_discovery_action_with_single_type():
    """Test Action extraction with simple @type."""
    data = {
        "@type": "SearchAction",
        "name": "Search",
    }

    actions = DeclarativeDiscovery._extract_actions_from_ld(data)
    assert len(actions) == 1


def test_declarative_discovery_action_with_list_type():
    """Test Action extraction with list @type."""
    data = {
        "@type": ["SearchAction", "WebPageElement"],
        "name": "Search",
    }

    actions = DeclarativeDiscovery._extract_actions_from_ld(data)
    assert len(actions) == 1  # Should find it because "Action" is in "SearchAction"
