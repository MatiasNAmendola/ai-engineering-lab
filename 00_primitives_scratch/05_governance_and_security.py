#!/usr/bin/env python3
"""
05_governance_and_security.py

Karpathy-style, zero-dependency Agent Governance and Security.
Demonstrates:
1. Tool execution gating via a policy engine wrapper.
2. PII Redaction (regex-free string scanning & simple regex fallback).
3. Cost / Budget gates.
4. Kill switches (emergency halts).
5. Role-based permissions matching tools to agent roles.
"""

import re
import time
from typing import List, Callable


# --- 1. GOVERNANCE STATE & DATABASE ---

class SystemState:
    """Tracks global runtime telemetry: budgets, kill-switches, and rate limits."""
    def __init__(self, daily_budget: float = 1.00):
        self.cumulative_cost: float = 0.0
        self.daily_budget: float = daily_budget
        self.kill_switch_engaged: bool = False
        self.tool_call_timestamps: List[float] = []

    def log_cost(self, cost: float):
        self.cumulative_cost += cost

    def check_budget(self) -> bool:
        return self.cumulative_cost <= self.daily_budget

    def engage_kill_switch(self):
        self.kill_switch_engaged = True
        print("\n🚨 [SYSTEM ALERT] EMERGENCY KILL SWITCH ENGAGED! All tool actions blocked.")

    def disengage_kill_switch(self):
        self.kill_switch_engaged = False

    def throttle_check(self, limit_per_minute: int = 5) -> bool:
        """Rate limit checker: sliding window of timestamps."""
        now = time.time()
        # Keep only timestamps within last 60 seconds
        self.tool_call_timestamps = [t for t in self.tool_call_timestamps if now - t < 60]
        if len(self.tool_call_timestamps) >= limit_per_minute:
            return False
        self.tool_call_timestamps.append(now)
        return True


# --- 2. SECURITY POLICY RULES ---

class GovernancePolicy:
    """Defines limits, permission clearances, and privacy configurations."""
    def __init__(self, allowed_roles: List[str], max_rate_per_min: int = 5):
        self.allowed_roles = allowed_roles
        self.max_rate_per_min = max_rate_per_min

    def redact_pii(self, text: str) -> str:
        """
        Scans strings and replaces PII (emails, phone numbers) with mask tokens.
        """
        # Simple robust patterns for emails and phones
        email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
        phone_pattern = r'\+?\d{1,3}[-.\s]?\(?\d{1,4}?\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}'
        
        masked = re.sub(email_pattern, "[REDACTED_EMAIL]", text)
        masked = re.sub(phone_pattern, "[REDACTED_PHONE]", masked)
        return masked


# --- 3. THE GATING WRAPPER ---

class ToolGater:
    """
    Wraps tools to intercept and govern execution parameters.
    Similar to Microsoft's Agent Governance Toolkit wrapping mechanisms.
    """
    def __init__(self, state: SystemState, policy: GovernancePolicy):
        self.state = state
        self.policy = policy

    def govern(self, agent_role: str, tool_name: str, fn: Callable[[str], str]) -> Callable[[str], str]:
        """
        Returns a protected function that performs security checks before calling the tool.
        """
        def protected_tool(args: str) -> str:
            # Check 1: Kill Switch
            if self.state.kill_switch_engaged:
                raise PermissionError(f"Block: Kill switch engaged. Action '{tool_name}' forbidden.")

            # Check 2: RBAC / Permissions Check
            if agent_role not in self.policy.allowed_roles:
                raise PermissionError(
                    f"Block: Role '{agent_role}' lacks permissions for tool '{tool_name}'. "
                    f"Requires one of: {self.policy.allowed_roles}"
                )

            # Check 3: Budget check
            if not self.state.check_budget():
                raise BudgetError(
                    f"Block: Operation budget exceeded! Cumulative Cost: ${self.state.cumulative_cost:.4f} "
                    f"exceeds limit ${self.state.daily_budget:.2f}"
                )

            # Check 4: Rate Limiting
            if not self.state.throttle_check(self.policy.max_rate_per_min):
                raise RateLimitError(
                    f"Block: Rate limit reached ({self.policy.max_rate_per_min} calls/min)."
                )

            # Check 5: Data Privacy / PII Filtering
            clean_args = self.policy.redact_pii(args)
            if clean_args != args:
                print("  🔒 [PII GUARD] Intercepted sensitive input. Masked arguments sent to tool.")

            # Execute Tool (simulate cost logging)
            result = fn(clean_args)
            
            # Record execution metadata
            self.state.log_cost(cost=0.05) # Simulate cost of $0.05 per action
            return result

        return protected_tool


# --- CUSTOM EXCEPTIONS ---

class BudgetError(Exception):
    pass

class RateLimitError(Exception):
    pass


# --- SAMPLE TOOLS ---

def create_system_user_tool(args: str) -> str:
    return f"Database user created successfully. Connection Details: {args}"


# --- RUNNER & DEMONSTRATION ---

def run_governance_demo():
    print("=== AI Engineering Lab: Agent Governance & Security ===")
    
    # 1. Establish state and policy limits
    state = SystemState(daily_budget=0.12)  # Budget allows max 2 tool calls ($0.05 * 2 = $0.10)
    policy = GovernancePolicy(allowed_roles=["admin", "operator"], max_rate_per_min=3)
    gater = ToolGater(state, policy)
    
    # Wrap tool with governance for an "admin" agent
    admin_tool_executor = gater.govern(
        agent_role="admin", 
        tool_name="create_system_user", 
        fn=create_system_user_tool
    )
    
    # Wrap tool with governance for a "viewer" agent (lacks permissions)
    viewer_tool_executor = gater.govern(
        agent_role="viewer",
        tool_name="create_system_user",
        fn=create_system_user_tool
    )

    # Demo 1: PII Filtering
    print("\n--- Demo 1: PII Scanning & Redaction ---")
    sensitive_input = "username=johndoe, email=john.doe@gmail.com, phone=+1-555-0199"
    print(f"Input Args:  {sensitive_input}")
    output = admin_tool_executor(sensitive_input)
    print(f"Tool Output: {output}")

    # Demo 2: Permission Gating (RBAC)
    print("\n--- Demo 2: Role-based Permissions ---")
    try:
        print("Attempting to run tool using 'viewer' role...")
        viewer_tool_executor("username=guest")
    except PermissionError as e:
        print(f"❌ Security Blocked: {e}")

    # Demo 3: Budget Gating
    print("\n--- Demo 3: Cumulative Cost Gating ---")
    print(f"Current Cumulative Cost: ${state.cumulative_cost:.2f}")
    try:
        print("Making 2nd allowed tool execution ($0.05 cost)...")
        admin_tool_executor("username=operator1")
        print(f"Current Cumulative Cost: ${state.cumulative_cost:.2f}")
        
        print("Making 3rd tool execution (Expected budget exhaust)...")
        admin_tool_executor("username=operator2")
    except BudgetError as e:
        print(f"❌ Security Blocked: {e}")

    # Demo 4: Kill Switch Operation
    print("\n--- Demo 4: Emergency Kill Switch ---")
    # Reset budget for this demo
    state.cumulative_cost = 0.0
    print("Engaging emergency kill switch...")
    state.engage_kill_switch()
    
    try:
        print("Attempting tool call post-kill switch...")
        admin_tool_executor("username=admin_override")
    except PermissionError as e:
        print(f"❌ Security Blocked: {e}")

if __name__ == "__main__":
    run_governance_demo()
