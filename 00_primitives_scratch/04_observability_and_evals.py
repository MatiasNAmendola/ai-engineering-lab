#!/usr/bin/env python3
"""
04_observability_and_evals.py

Karpathy-style, zero-dependency tracing engine and evaluation metrics.
Demonstrates:
1. Hierarchical tracing trees (nested runs and spans).
2. JSON serialization structure compatible with LangSmith/LangFuse.
3. Quality Evaluation metrics: Exact Match (EM), F1 Token Overlap,
   and G-Eval LLM-as-a-Judge prompt constructor.
"""

import json
import time
from typing import Dict, Any, List, Optional


# --- 1. OBSERVABILITY: TRACE & SPAN ENGINE ---

class TraceSpan:
    """
    A context manager to capture hierarchical execution trees.
    Supports nesting of spans (e.g. Agent -> Workflow -> Tool -> LLM).
    """
    # Thread-local style stack using class variable
    active_span_stack: List["TraceSpan"] = []

    def __init__(self, name: str, span_type: str = "generic", inputs: Optional[Dict[str, Any]] = None):
        self.name = name
        self.span_type = span_type
        self.inputs = inputs or {}
        self.outputs: Dict[str, Any] = {}
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.duration: float = 0.0
        self.children: List["TraceSpan"] = []
        self.parent: Optional[TraceSpan] = None

    def __enter__(self) -> "TraceSpan":
        self.start_time = time.time()
        # If there is a span currently running, make it the parent of this one
        if TraceSpan.active_span_stack:
            self.parent = TraceSpan.active_span_stack[-1]
            self.parent.children.append(self)
        TraceSpan.active_span_stack.append(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        if exc_type is not None:
            self.outputs = {"status": "error", "error_message": str(exc_val)}
        # Remove from active stack
        TraceSpan.active_span_stack.pop()

    def set_outputs(self, outputs: Dict[str, Any]):
        """Records output dictionary for this execution node."""
        self.outputs = outputs

    def to_dict(self) -> Dict[str, Any]:
        """Serializes current span and all sub-spans recursively."""
        return {
            "name": self.name,
            "type": self.span_type,
            "duration_sec": round(self.duration, 5),
            "inputs": self.inputs,
            "outputs": self.outputs,
            "children": [child.to_dict() for child in self.children]
        }

    def serialize_langfuse_format(self) -> str:
        """
        Formats the hierarchical trace tree into a simplified schema 
        closely matching LangFuse/LangSmith trace models.
        """
        flat_records = []
        
        def flatten(span: "TraceSpan", parent_id: Optional[str] = None) -> str:
            span_id = f"span_{id(span)}"
            flat_records.append({
                "id": span_id,
                "parent_id": parent_id,
                "name": span.name,
                "type": span.span_type,
                "startTime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(span.start_time)),
                "endTime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(span.end_time)),
                "input": span.inputs,
                "output": span.outputs,
                "metadata": {"duration_sec": span.duration}
            })
            for child in span.children:
                flatten(child, parent_id=span_id)
            return span_id

        flatten(self)
        return json.dumps({"trace": flat_records}, indent=2)


# --- 2. EVALUATION METRICS FROM SCRATCH ---

def compute_exact_match(prediction: str, reference: str) -> float:
    """Computes binary exact match score after string normalization."""
    p_clean = prediction.strip().lower()
    r_clean = reference.strip().lower()
    return 1.0 if p_clean == r_clean else 0.0

def compute_f1_token_overlap(prediction: str, reference: str) -> float:
    """
    Computes token-level precision, recall, and F1 score of prediction text
    relative to reference text. Highly used in QA and RAG benchmark evals.
    """
    pred_tokens = prediction.strip().lower().split()
    ref_tokens = reference.strip().lower().split()
    
    if not pred_tokens or not ref_tokens:
        return 1.0 if pred_tokens == ref_tokens else 0.0
        
    common_tokens = set(pred_tokens) & set(ref_tokens)
    num_same = sum(min(pred_tokens.count(t), ref_tokens.count(t)) for t in common_tokens)
    
    if num_same == 0:
        return 0.0
        
    precision = num_same / len(pred_tokens)
    recall = num_same / len(ref_tokens)
    f1 = (2 * precision * recall) / (precision + recall)
    return f1

def construct_g_eval_prompt(criteria: str, input_text: str, model_output: str) -> str:
    """
    Constructs a structured prompt for G-Eval (LLM-as-a-judge).
    Allows scoring generative model quality based on specified attributes.
    """
    prompt = f"""
[Evaluation Task: G-Eval]
You are an expert judge evaluator. You will rate the quality of the AI response below based on the criteria provided.

Criteria description:
{criteria}

Input content:
"{input_text}"

AI Response:
"{model_output}"

Evaluation Steps:
1. Read the criteria, the source input, and the response carefully.
2. Evaluate the response on a scale of 1 to 5, where:
   - 1: Fails criteria completely.
   - 3: Partially meets criteria, major gaps present.
   - 5: Outstanding output, meets all requirements perfectly.
3. Provide a brief explanation of your reasoning followed by the score format EXACTLY as: "Score: [1-5]"

Response:
"""
    return prompt.strip()


# --- RUNNER & DEMONSTRATION ---

def run_observability_demo():
    print("=== AI Engineering Lab: Observability & Evals ===")
    
    # 1. Tracing nested flow execution
    print("\nExecuting sample trace pipeline...")
    with TraceSpan("MainPipeline", span_type="trace", inputs={"task": "rag_answering"}) as trace:
        
        # Simulated Retriever Call
        with TraceSpan("DocumentRetriever", span_type="retrieval", inputs={"query": "RAG systems"}) as retrieval:
            time.sleep(0.05) # simulate latency
            retrieved_docs = ["Doc A: RAG requires database indices.", "Doc B: Vectors improve search."]
            retrieval.set_outputs({"retrieved": retrieved_docs, "retrieval_count": 2})
            
        # Simulated LLM Prompt Building & Call
        with TraceSpan("LLMGenerator", span_type="llm", inputs={"model": "gpt-4o-mini", "docs": retrieved_docs}) as generator:
            
            # Simulated call details
            with TraceSpan("API_Request_Payload", span_type="http", inputs={"endpoint": "chat/completions"}) as api_call:
                time.sleep(0.12)
                api_call.set_outputs({"status": 200})
                
            generator_output = "RAG systems require database indices for fast vector retrieval."
            generator.set_outputs({"generated_text": generator_output})
            
        # Complete main pipeline
        trace.set_outputs({"answer": generator_output, "tokens_estimated": 82})
        
    print("\nGenerated Hierarchical Trace Object:")
    print(json.dumps(trace.to_dict(), indent=2))
    
    print("\nExportable Flat LangFuse Ingestion Format:")
    print(trace.serialize_langfuse_format())
    
    # 2. Evaluation Metrics Demo
    print("\n--- Evaluation Scorers ---")
    prediction = "PostgreSQL with PGVector is the pragmatic choice."
    reference = "PostgreSQL and pgvector represents the pragmatic choice."
    
    em = compute_exact_match(prediction, reference)
    f1 = compute_f1_token_overlap(prediction, reference)
    
    print(f"Prediction: '{prediction}'")
    print(f"Reference:  '{reference}'")
    print(f"  Exact Match (EM) Score:   {em:.4f} (Mismatch due to syntax)")
    print(f"  Token Overlap F1 Score:   {f1:.4f} (High semantic and word overlap)")
    
    # 3. G-Eval Constructor Demo
    print("\n--- G-Eval prompt constructor preview ---")
    criteria = "Relevance: Output should directly address the topic, containing no extra fluff or unrelated facts."
    input_text = "Why use PGVector?"
    model_output = "PGVector runs inside PostgreSQL, avoiding syncing overhead with external vector stores."
    
    g_eval_prompt = construct_g_eval_prompt(criteria, input_text, model_output)
    print(g_eval_prompt)

if __name__ == "__main__":
    run_observability_demo()
