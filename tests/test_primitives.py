#!/usr/bin/env python3
"""
Test suite for AI Engineering Lab primitives.
Run with: uv run pytest tests/ -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "00_primitives_scratch"))

if __name__ == "__main__":
    import test_01_llm_inference
    import test_02_rag_pgvector
    import test_03_agent_runtime
    import test_04_observability
    import test_05_governance

    print("Running all primitive test suites...")
    
    # 01 LLM Inference
    test_01_llm_inference.test_cost_tracker()
    test_01_llm_inference.test_json_extraction()
    
    # 02 RAG PGVector
    test_02_rag_pgvector.test_cosine_math()
    test_02_rag_pgvector.test_chunking()
    test_02_rag_pgvector.test_retrieval_metrics()
    
    # 03 Agent Runtime
    test_03_agent_runtime.test_context_propagation()
    test_03_agent_runtime.test_event_bus()
    test_03_agent_runtime.test_memory_engine()
    
    # 04 Observability
    test_04_observability.test_trace_spans()
    test_04_observability.test_eval_metrics()
    
    # 05 Governance
    test_05_governance.test_pii_redaction()
    test_05_governance.test_tool_gater()
    test_05_governance.test_kill_switch()
    
    print("\n🎉 All primitives tested successfully!")