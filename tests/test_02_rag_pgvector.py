#!/usr/bin/env python3
"""Tests for 02_rag_postgres_pgvector.py"""

import sys
import os
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "00_primitives_scratch"))
_rag = importlib.import_module("02_rag_postgres_pgvector")

dot_product = _rag.dot_product
magnitude = _rag.magnitude
cosine_similarity = _rag.cosine_similarity
cosine_distance = _rag.cosine_distance
sliding_window_chunking = _rag.sliding_window_chunking
semantic_chunking = _rag.semantic_chunking
evaluate_retrieval_quality = _rag.evaluate_retrieval_quality


def test_cosine_math():
    """Test pure-Python dot product, magnitude, similarity, and distance."""
    v1 = [1.0, 0.0, 0.0]
    v2 = [0.0, 1.0, 0.0]
    v3 = [1.0, 1.0, 0.0]

    assert dot_product(v1, v2) == 0.0
    assert dot_product(v1, v3) == 1.0
    assert magnitude(v1) == 1.0
    
    # Cosine similarity of orthogonal vectors is 0
    assert cosine_similarity(v1, v2) == 0.0
    # Cosine distance is 1.0
    assert cosine_distance(v1, v2) == 1.0

    # Identical vectors similarity is 1
    assert cosine_similarity(v1, v1) == 1.0
    assert cosine_distance(v1, v1) == 0.0

    # Error on mismatched dimensions
    try:
        dot_product([1.0], [1.0, 2.0])
        assert False, "Should raise ValueError"
    except ValueError:
        pass

    print("✓ test_cosine_math passed")


def test_chunking():
    """Test sliding window and semantic chunking."""
    text = "One two three four five six seven eight nine ten."
    
    # Window size 5, overlap 2
    chunks = sliding_window_chunking(text, window_size=5, overlap=2)
    assert len(chunks) > 1
    assert "One two three four five" in chunks[0]

    # Semantic chunking on single sentence should yield 1 chunk
    sem_chunks = semantic_chunking(text)
    assert len(sem_chunks) == 1

    print("✓ test_chunking passed")


def test_retrieval_metrics():
    """Test Hit Rate and MRR evaluation scorers."""
    ground_truth = [
        {"query_id": 1, "expected_doc": "doc_A"},
        {"query_id": 2, "expected_doc": "doc_B"},
    ]
    retrieved_results = [
        ["doc_B", "doc_A"],  # doc_A is index 1 -> rank 2 -> MRR 0.5
        ["doc_X", "doc_Y"],  # doc_B is absent -> MRR 0.0
    ]

    hit_rate, mrr = evaluate_retrieval_quality(ground_truth, retrieved_results, k=2)
    # 1 out of 2 queries hit (query 1 hit doc_A at rank 2, query 2 missed doc_B)
    assert hit_rate == 0.5
    # Reciprocal ranks are [0.5, 0.0] -> average is 0.25
    assert mrr == 0.25

    print("✓ test_retrieval_metrics passed")


if __name__ == "__main__":
    test_cosine_math()
    test_chunking()
    test_retrieval_metrics()
    print("All 02_rag_pgvector tests passed!")
