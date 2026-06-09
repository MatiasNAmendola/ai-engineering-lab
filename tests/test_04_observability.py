#!/usr/bin/env python3
"""Tests for 04_observability_and_evals.py"""

import sys
import os
import json
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "00_primitives_scratch"))
_obs = importlib.import_module("04_observability_and_evals")

TraceSpan = _obs.TraceSpan
compute_exact_match = _obs.compute_exact_match
compute_f1_token_overlap = _obs.compute_f1_token_overlap
construct_g_eval_prompt = _obs.construct_g_eval_prompt


def test_trace_spans():
    """Test TraceSpan nested contexts and hierarchical/flat serialization."""
    with TraceSpan("Root", span_type="agent", inputs={"query": "test"}) as root:
        assert root.name == "Root"
        assert len(root.children) == 0

        with TraceSpan("Child1", span_type="tool") as child1:
            child1.set_outputs({"result": "done"})

        with TraceSpan("Child2", span_type="llm") as child2:
            child2.set_outputs({"text": "hello"})

        root.set_outputs({"status": "success"})

    # Check hierarchy
    assert len(root.children) == 2
    assert root.children[0].name == "Child1"
    assert root.children[0].outputs["result"] == "done"
    assert root.children[1].name == "Child2"
    assert root.children[1].parent == root

    # Verify duration
    assert root.duration >= 0.0

    # Test dictionary export
    dict_repr = root.to_dict()
    assert dict_repr["name"] == "Root"
    assert len(dict_repr["children"]) == 2
    assert dict_repr["children"][0]["name"] == "Child1"

    # Test Langfuse flat serialization
    langfuse_json = root.serialize_langfuse_format()
    langfuse_data = json.loads(langfuse_json)
    assert "trace" in langfuse_data
    assert len(langfuse_data["trace"]) == 3  # Root + Child1 + Child2

    print("✓ test_trace_spans passed")


def test_eval_metrics():
    """Test exact match and token overlap F1 metrics."""
    # Exact match tests
    assert compute_exact_match(" Hello ", "hello") == 1.0
    assert compute_exact_match("apple", "banana") == 0.0

    # Token overlap F1 tests
    # Perfect match
    assert compute_f1_token_overlap("hello world", "hello world") == 1.0
    # Complete mismatch
    assert compute_f1_token_overlap("apple pie", "banana split") == 0.0
    # Partial overlap: Pred has 2 tokens, Ref has 2 tokens, 1 matches ("hello")
    # precision = 1/2, recall = 1/2 -> F1 = 0.5
    assert compute_f1_token_overlap("hello world", "hello friend") == 0.5

    # G-Eval prompt constructor testing
    prompt = construct_g_eval_prompt("Criteria description", "Input text", "AI Response")
    assert "[Evaluation Task: G-Eval]" in prompt
    assert "Criteria description" in prompt
    assert "Input text" in prompt

    print("✓ test_eval_metrics passed")


if __name__ == "__main__":
    test_trace_spans()
    test_eval_metrics()
    print("All 04_observability tests passed!")
