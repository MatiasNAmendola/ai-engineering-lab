#!/usr/bin/env python3
"""Tests for 03_agent_runtime_scratch.py"""

import sys
import os
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "00_primitives_scratch"))
_runtime = importlib.import_module("03_agent_runtime_scratch")

ExecutionContext = _runtime.ExecutionContext
EventBus = _runtime.EventBus
TaskScheduler = _runtime.TaskScheduler
MemoryEngine = _runtime.MemoryEngine
AgentRuntime = _runtime.AgentRuntime


def test_context_propagation():
    """Test execution context spawning child contexts with correct trace tracking."""
    root = ExecutionContext(tenant_id="client_123")
    assert root.tenant_id == "client_123"
    assert root.trace_id is not None
    assert root.parent_span_id is None

    child = root.spawn_child()
    assert child.trace_id == root.trace_id
    assert child.tenant_id == "client_123"
    assert child.parent_span_id is not None

    print("✓ test_context_propagation passed")


def test_event_bus():
    """Test publish-subscribe on the event bus."""
    bus = EventBus()
    received_events = []

    def callback(payload, context):
        received_events.append((payload, context))

    ctx = ExecutionContext()
    bus.subscribe("test_event", callback)
    
    bus.publish("test_event", {"data": "hello"}, ctx)
    assert len(received_events) == 1
    assert received_events[0][0]["data"] == "hello"
    assert "timestamp" in received_events[0][0]
    assert received_events[0][1] == ctx

    print("✓ test_event_bus passed")


def test_memory_engine():
    """Test short-term memory lists and long-term synthesis recall."""
    memory = MemoryEngine()
    
    # Test short-term
    memory.add_message("user", "Hello agent")
    assert len(memory.short_term) == 1
    assert memory.short_term[0]["role"] == "user"

    # Test long-term consolidate and recall
    memory.consolidate("database connection", "host=127.0.0.1")
    assert memory.recall("database") == "host=127.0.0.1"
    assert memory.recall("absent_key") is None

    print("✓ test_memory_engine passed")


if __name__ == "__main__":
    test_context_propagation()
    test_event_bus()
    test_memory_engine()
    print("All 03_agent_runtime tests passed!")
