#!/usr/bin/env python3
"""Tests for MCP servers tool and resource registrations."""

import sys
import os
import asyncio

# Add frameworks directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "01_python_frameworks"))

from mcp_educational_platform_demo import mcp as edu_mcp
from mcp_virtual_wallet_demo import mcp as wallet_mcp


def test_educational_mcp():
    """Verify tools and resources are registered on Educational Platform MCP server."""
    assert edu_mcp.name == "educational-platform"
    
    async def run_check():
        tools = await edu_mcp.list_tools()
        tool_names = [t.name for t in tools]
        assert "get_student_progress" in tool_names
        assert "recommend_next_course" in tool_names
        assert "grade_assignment" in tool_names
        assert "generate_study_plan" in tool_names
        assert "detect_at_risk_students" in tool_names
        
        resources = await edu_mcp.list_resources()
        resource_uris = [str(r.uri) for r in resources]
        assert any("catalog" in r for r in resource_uris)
        assert any("metrics" in r for r in resource_uris)

    asyncio.run(run_check())


def test_wallet_mcp():
    """Verify tools and resources are registered on Virtual Wallet MCP server."""
    assert wallet_mcp.name == "virtual-wallet"
    
    async def run_check():
        tools = await wallet_mcp.list_tools()
        tool_names = [t.name for t in tools]
        assert "analyze_transaction" in tool_names
        assert "get_account_summary" in tool_names
        assert "detect_fraud_patterns" in tool_names
        assert "generate_spending_insights" in tool_names
        assert "block_suspicious_card" in tool_names
        assert "create_dispute" in tool_names

        resources = await wallet_mcp.list_resources()
        resource_uris = [str(r.uri) for r in resources]
        assert any("recent" in r for r in resource_uris)

    asyncio.run(run_check())


if __name__ == "__main__":
    test_educational_mcp()
    test_wallet_mcp()
    print("All MCP server tests passed!")
