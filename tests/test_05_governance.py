#!/usr/bin/env python3
"""Tests for 05_governance_and_security.py"""

import sys
import os
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "00_primitives_scratch"))
_gov = importlib.import_module("05_governance_and_security")

SystemState = _gov.SystemState
GovernancePolicy = _gov.GovernancePolicy
ToolGater = _gov.ToolGater
BudgetError = _gov.BudgetError
RateLimitError = _gov.RateLimitError


def test_pii_redaction():
    """Test PII Redaction of email and phone numbers."""
    policy = GovernancePolicy(allowed_roles=["admin"])
    
    # Test email redaction
    assert policy.redact_pii("contact john.doe@gmail.com today") == "contact [REDACTED_EMAIL] today"
    
    # Test phone redaction
    assert policy.redact_pii("my number is +1-555-0199.") == "my number is [REDACTED_PHONE]."
    
    # Combined PII
    text = "email: a@b.com, phone: 12345678"
    assert policy.redact_pii(text) == "email: [REDACTED_EMAIL], phone: [REDACTED_PHONE]"

    print("✓ test_pii_redaction passed")


def test_tool_gater():
    """Test role permissions, cost gates, and rate limits in ToolGater."""
    state = SystemState(daily_budget=0.08)  # budget allows 1 call of 0.05
    policy = GovernancePolicy(allowed_roles=["admin", "operator"], max_rate_per_min=2)
    gater = ToolGater(state, policy)

    def dummy_tool(args):
        return f"result: {args}"

    admin_tool = gater.govern("admin", "dummy_tool", dummy_tool)
    viewer_tool = gater.govern("viewer", "dummy_tool", dummy_tool)

    # 1. Test successful admin call
    assert admin_tool("hello") == "result: hello"
    assert state.cumulative_cost == 0.05

    # 2. Test RBAC permissions block
    try:
        viewer_tool("hello")
        assert False, "viewer role should be blocked"
    except PermissionError as e:
        assert "Role 'viewer' lacks permissions" in str(e)

    # 3. Test budget exhaust block (budget is 0.08. 1st call: 0.05, 2nd call: 0.05, 3rd call is blocked)
    assert admin_tool("hello") == "result: hello"
    assert state.cumulative_cost == 0.10

    try:
        admin_tool("hello")
        assert False, "third call should exceed budget"
    except BudgetError as e:
        assert "budget exceeded" in str(e).lower()

    # Reset cost & test rate limits
    state.cumulative_cost = 0.0
    state.daily_budget = 1.0
    state.tool_call_timestamps = []
    
    admin_tool("call1")
    admin_tool("call2")
    
    # 4. Test rate limit block (limit is 2 per minute)
    try:
        admin_tool("call3")
        assert False, "third call should hit rate limit"
    except RateLimitError as e:
        assert "rate limit reached" in str(e).lower()

    print("✓ test_tool_gater passed")


def test_kill_switch():
    """Test emergency kill switch blocks all tool execution regardless of role."""
    state = SystemState(daily_budget=1.0)
    policy = GovernancePolicy(allowed_roles=["admin"])
    gater = ToolGater(state, policy)

    def dummy_tool(args):
        return "ok"

    admin_tool = gater.govern("admin", "dummy_tool", dummy_tool)

    # Normal execution works
    assert admin_tool("ok") == "ok"

    # Engaging kill switch
    state.engage_kill_switch()
    assert state.kill_switch_engaged is True

    # Call should be blocked
    try:
        admin_tool("ok")
        assert False, "should block call when kill switch engaged"
    except PermissionError as e:
        assert "Kill switch engaged" in str(e)

    # Disengage kill switch
    state.disengage_kill_switch()
    assert admin_tool("ok") == "ok"

    print("✓ test_kill_switch passed")


if __name__ == "__main__":
    test_pii_redaction()
    test_tool_gater()
    test_kill_switch()
    print("All 05_governance tests passed!")
