#!/usr/bin/env python3
"""
02_rag_postgres_pgvector.py

Karpathy-style, pure-Python RAG and Vector concepts.
Contains zero-dependency math, chunking strategies, PGVector schema designs,
and retrieval quality evaluation (Hit Rate, MRR).
"""

import math
from typing import List, Dict, Any, Tuple

# --- 1. PURE PYTHON VECTOR MATH FROM SCRATCH ---

def dot_product(v1: List[float], v2: List[float]) -> float:
    """Computes dot product between two vectors."""
    if len(v1) != len(v2):
        raise ValueError("Vectors must be of the same dimension.")
    return sum(x * y for x, y in zip(v1, v2))

def magnitude(v: List[float]) -> float:
    """Computes magnitude (Euclidean norm) of a vector."""
    return math.sqrt(sum(x * x for x in v))

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Computes cosine similarity between two vectors."""
    mag1 = magnitude(v1)
    mag2 = magnitude(v2)
    if mag1 == 0.0 or mag2 == 0.0:
        return 0.0
    return dot_product(v1, v2) / (mag1 * mag2)

def cosine_distance(v1: List[float], v2: List[float]) -> float:
    """
    Computes cosine distance (1 - similarity).
    This matches PostgreSQL pgvector '<=>' operator behavior.
    """
    return 1.0 - cosine_similarity(v1, v2)


# --- 2. CHUNKING STRATEGIES FROM SCRATCH ---

def sliding_window_chunking(text: str, window_size: int = 100, overlap: int = 20) -> List[str]:
    """
    Splits text into chunks of `window_size` words with `overlap` words overlapping.
    """
    words = text.split()
    chunks = []
    
    if len(words) <= window_size:
        return [text]
        
    start = 0
    while start < len(words):
        end = start + window_size
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words))
        
        # If we reached the end of the text, stop
        if end >= len(words):
            break
            
        start += (window_size - overlap)
        
    return chunks

def get_mock_embedding(text: str) -> List[float]:
    """
    Generates a deterministic mock embedding (dimension 4) based on text content.
    For educational and testing purposes only.
    """
    # Deterministic mapping based on word counts and character hashing
    words = text.split()
    v = [0.0] * 4
    v[0] = len(text) / 100.0
    v[1] = len(words) / 10.0
    v[2] = sum(ord(c) for c in text[:10]) / 1000.0 if text else 0.0
    v[3] = (text.count(" ") + 1) / 5.0
    
    # Normalize vector to unit length
    mag = magnitude(v)
    if mag > 0:
        v = [x / mag for x in v]
    return v

def semantic_chunking(text: str, similarity_threshold: float = 0.85) -> List[str]:
    """
    Splits text into sentences, computes mock embeddings, and merges sentences
    into chunks until the similarity between adjacent sentences drops below a threshold.
    """
    # Simple sentence splitter on punctuation
    raw_sentences = text.replace("?", ".").replace("!", ".").split(". ")
    sentences = [s.strip() + "." for s in raw_sentences if s.strip()]
    
    if not sentences:
        return []
        
    chunks = []
    current_chunk = [sentences[0]]
    
    for i in range(1, len(sentences)):
        prev_embedding = get_mock_embedding(sentences[i-1])
        curr_embedding = get_mock_embedding(sentences[i])
        
        sim = cosine_similarity(prev_embedding, curr_embedding)
        
        # If they are semantically similar, merge them
        if sim >= similarity_threshold:
            current_chunk.append(sentences[i])
        else:
            # Drop in similarity indicates a topic boundary; finalize current chunk
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentences[i]]
            
    if current_chunk:
        chunks.append(" ".join(current_chunk))
        
    return chunks


# --- 3. PGVECTOR DDL & QUERY PATTERNS (EDUCATIONAL DOCUMENTATION) ---

def print_postgres_pgvector_ddl():
    ddl_schema = """
-- ====================================================================
-- PostgreSQL + PGVector Enterprise Schema
-- ====================================================================

-- 1. Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create the document chunks table with metadata filtering fields
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id VARCHAR(255) NOT NULL,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536), -- 1536 is standard dimension for text-embedding-3-small / text-embedding-ada-002
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- 3. Create indices
-- HNSW Index (Hierarchical Navigable Small World) for cosine distance (<=>)
-- Optimal for fast, approximate nearest neighbor search at scale.
CREATE INDEX ON document_chunks USING hnsw (embedding vector_cosine_ops);

-- B-Tree indices on metadata fields for fast hybrid filtering
CREATE INDEX ON document_chunks USING gin (metadata);
CREATE INDEX ON document_chunks (document_id);

-- 4. Hybrid query example: Semantic Search + Strict Tenant/Metadata Filter
-- SELECT content, 1 - (embedding <=> :query_embedding) AS similarity
-- FROM document_chunks
-- WHERE metadata->>'tenant_id' = :tenant_id AND metadata->>'status' = 'active'
-- ORDER BY embedding <=> :query_embedding
-- LIMIT 5;
    """
    print(ddl_schema)


# --- 4. RETRIEVAL QUALITY EVALUATION FROM SCRATCH ---

def evaluate_retrieval_quality(
    ground_truth: List[Dict[str, Any]], 
    retrieved_results: List[List[str]], 
    k: int = 3
) -> Tuple[float, float]:
    """
    Calculates Retrieval Quality metrics (Hit Rate and Mean Reciprocal Rank).
    
    Args:
        ground_truth: List of dicts representing the ideal document ID per query.
                      Example: [{"query_id": 1, "expected_doc": "doc_A"}]
        retrieved_results: List of retrieved document lists per query (in ranked order).
                      Example: [["doc_B", "doc_A", "doc_C"]]
        k: Top K elements to evaluate.
        
    Returns:
        (hit_rate_at_k, mrr_at_k)
    """
    hits = 0
    reciprocal_ranks = []
    
    for gt, retrieved in zip(ground_truth, retrieved_results):
        expected = gt["expected_doc"]
        top_k_retrieved = retrieved[:k]
        
        # 1. Hit Rate Calculation
        if expected in top_k_retrieved:
            hits += 1
            
        # 2. Reciprocal Rank Calculation
        if expected in top_k_retrieved:
            rank = top_k_retrieved.index(expected) + 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)
            
    hit_rate = hits / len(ground_truth)
    mrr = sum(reciprocal_ranks) / len(ground_truth)
    
    return hit_rate, mrr


# --- RUNNER & DEMONSTRATION ---

def run_rag_demo():
    print("=== AI Engineering Lab: RAG & Vector Primitives ===")
    
    # Text sample for chunking
    sample_text = (
        "PostgreSQL is a powerful relational database. It is loved for its extensibility. "
        "PGVector is an extension that adds vector support to PostgreSQL. It supports indexing like HNSW. "
        "Agents are autonomous entities. They execute loops to solve goals. "
        "Evaluations determine agent accuracy. They are crucial for production success."
    )
    
    print(f"\n--- Original Text ({len(sample_text.split())} words) ---")
    print(sample_text)
    
    print("\n--- 1. Sliding Window Chunking (size=10, overlap=3) ---")
    sliding_chunks = sliding_window_chunking(sample_text, window_size=10, overlap=3)
    for i, chunk in enumerate(sliding_chunks):
        print(f"Chunk {i+1}: '{chunk}'")
        
    print("\n--- 2. Semantic Chunking (threshold=0.88) ---")
    semantic_chunks = semantic_chunking(sample_text, similarity_threshold=0.88)
    for i, chunk in enumerate(semantic_chunks):
        print(f"Chunk {i+1}: '{chunk}'")
        
    print("\n--- 3. Pure Python Cosine Similarity (Custom Embeddings) ---")
    v1 = get_mock_embedding("PostgreSQL database")
    v2 = get_mock_embedding("PGVector vector search")
    v3 = get_mock_embedding("Autonomous agent loops")
    
    sim_12 = cosine_similarity(v1, v2)
    sim_13 = cosine_similarity(v1, v3)
    
    print(f"v1 (Postgres) mock embedding: {v1}")
    print(f"v2 (PGVector) mock embedding: {v2}")
    print(f"v3 (Agents) mock embedding:   {v3}")
    print(f"Cosine Similarity (v1, v2): {sim_12:.4f} (Cosine Distance: {cosine_distance(v1, v2):.4f})")
    print(f"Cosine Similarity (v1, v3): {sim_13:.4f} (Cosine Distance: {cosine_distance(v1, v3):.4f})")
    
    print("\n--- 4. Retrieval Evaluation Metrics (Hit Rate & MRR) ---")
    # Ground Truth vs Actual Retrieved docs
    ground_truth = [
        {"query_id": 1, "expected_doc": "doc_A"},
        {"query_id": 2, "expected_doc": "doc_B"},
        {"query_id": 3, "expected_doc": "doc_C"}
    ]
    retrieved_results = [
        ["doc_B", "doc_A", "doc_D"],  # doc_A is rank 2 (recip_rank = 1/2)
        ["doc_B", "doc_C", "doc_A"],  # doc_B is rank 1 (recip_rank = 1/1)
        ["doc_X", "doc_Y", "doc_Z"]   # doc_C is absent (recip_rank = 0)
    ]
    
    hit_rate, mrr = evaluate_retrieval_quality(ground_truth, retrieved_results, k=3)
    print(f"Evaluated top 3 retrieved results across 3 test queries:")
    print(f"  Hit Rate @ 3: {hit_rate:.4f} (66.6% hit)")
    print(f"  MRR @ 3:      {mrr:.4f} (Average of [0.5, 1.0, 0.0] = 0.5)")
    
    print("\n--- 5. PostgreSQL + PGVector DDL Schema Reference ---")
    print_postgres_pgvector_ddl()

if __name__ == "__main__":
    run_rag_demo()
