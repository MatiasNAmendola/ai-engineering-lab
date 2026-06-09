#!/usr/bin/env python3
"""Tests for 01_llm_inference_scratch.py"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "00_primitives_scratch"))

import importlib
_llm_inference = importlib.import_module("01_llm_inference_scratch")
CostTracker = _llm_inference.CostTracker
extract_and_parse_json = _llm_inference.extract_and_parse_json


def test_cost_tracker():
    """Test CostTracker token estimation and cost calculation."""
    tracker = CostTracker("gemini-1.5-flash")
    
    # Test token estimation
    assert tracker.estimate_tokens("hello world") == 2  # 11 chars // 4 = 2
    assert tracker.estimate_tokens("") == 1  # min 1
    
    # Test tracking
    tracker.track_request("test prompt")
    assert tracker.input_tokens > 0
    assert tracker.total_cost > 0
    
    tracker.track_response("test response")
    assert tracker.output_tokens > 0
    
    # Test report
    report = tracker.get_report()
    assert "gemini-1.5-flash" in report
    assert "Tokens:" in report
    assert "Cost:" in report
    assert "$" in report
    
    print("✓ CostTracker tests passed")


def test_json_extraction():
    """Test JSON extraction from LLM responses."""
    # Simple JSON
    text = 'Here is the result: {"status": "ok", "value": 42}'
    result = extract_and_parse_json(text)
    assert result["status"] == "ok"
    assert result["value"] == 42
    
    # JSON in code block
    text = '```json\n{"key": "value"}\n```'
    result = extract_and_parse_json(text)
    assert result["key"] == "value"
    
    # Error cases
    try:
        extract_and_parse_json("no json here")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
    
    print("✓ JSON extraction tests passed")


if __name__ == "__main__":
    test_cost_tracker()
    test_json_extraction()
    print("All 01_llm_inference tests passed!")