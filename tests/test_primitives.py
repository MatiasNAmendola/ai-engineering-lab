#!/usr/bin/env python3
"""
Test suite for AI Engineering Lab primitives.
Run with: uv run pytest tests/ -v
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "00_primitives_scratch"))

from test_01_llm_inference import test_cost_tracker, test_json_extraction
from test_02_rag_pgvector import test_cosine_math, test_chunking, test_retrieval_metrics
from test_03_agent_runtime import test_context_propagation, test_event_bus, test_memory_engine
from test_04_observability import test_trace_spans, test_eval_metrics
from test_05_governance import test_tool_gater, test_pii_redaction


class TestPrimitives:
    """Test all 5 primitive modules."""

    def test_01_llm_inference_cost_tracker(self):
        test_cost_tracker()

    def test_01_llm_inference_json_extraction(self):
        test_json_extraction()

    def test_02_rag_cosine_math(self):
        test_cosine_math()

    def test_02_rag_chunking(self):
        test_chunking()

    def test_02_rag_retrieval_metrics(self):
        test_retrieval_metrics()

    def test_03_agent_context_propagation(self):
        test_context_propagation()

    def test_03_agent_event_bus(self):
        test_event_bus()

    def test_03_agent_memory_engine(self):
        test_memory_engine()

    def test_04_observability_trace_spans(self):
        test_trace_spans()

    def test_04_observability_eval_metrics(self):
        test_eval_metrics()

    def test_05_governance_tool_gater(self):
        test_tool_gater()

    def test_05_governance_pii_redaction(self):
        test_pii_redaction()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])