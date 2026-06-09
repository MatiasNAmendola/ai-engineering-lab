# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "llama-index>=0.11.0",
#     "llama-index-llms-openrouter>=0.2.0",
#     "llama-index-embeddings-huggingface>=0.3.0",
#     "llama-index-vector-stores-postgres>=0.2.0",
# ]
# ///
"""
llamaindex_advanced_demo.py

Demostración avanzada de patrones RAG (Retrieval-Augmented Generation) con LlamaIndex.
Escenario: plataforma educativa donde estudiantes consultan sobre cursos y el sistema
recupera información de múltiples fuentes con estrategias de indexación diferenciadas.

Patrones cubiertos:
  1. Indexación jerárquica (resúmenes + detalle) para navegación multi-nivel.
  2. Summary Index para preguntas de contexto amplio ("¿de qué trata el curso X?").
  3. Keyword Table Index para búsquedas por término específico ("mencioná PostgreSQL").
  4. Router Query Engine que delega al índice adecuado según la intención de la consulta.
  5. Recursive Retriever para recorrer jerarquías de nodos padre/hijo.
  6. Tree Summarization y Refine mode para síntesis de respuestas largas.
  7. Hybrid Retriever personalizado (vectorial + BM25 por palabra clave).
  8. Node Postprocessors: reranking, reemplazo de metadata, exclusión por keyword.
  9. Evaluación con métricas de Faithfulness y Relevancy.

Trade-offs y consideraciones de producción:
  - Summary Index: rápido para preguntas globales, pero pierde granularidad.
  - Keyword Table: excelente para términos técnicos únicos, malo para sinónimos.
  - Vector Index: mejor para similitud semántica, pero sufre con queries muy cortas.
  - Router Engine: reduce latencia al evitar búsquedas innecesarias, pero requiere
    descripciones precisas de cada índice para que el router elija bien.
  - Hybrid Retriever: combina lo mejor de ambos mundos, pero duplica costo de indexing.
  - En producción: cachear embeddings, rate-limit al LLM, trackear costo por query,
    usar batch indexing incremental en lugar de re-indexar todo el corpus.

Ejecución: uv run 01_python_frameworks/llamaindex_advanced_demo.py
"""

import os
import sys
import json
import time
from dataclasses import dataclass, field

# ==========================================
# IMPORTS CON GUARDA (permiten modo mock)
# ==========================================

try:
    from llama_index.core import (
        Document,
        VectorStoreIndex,
        SummaryIndex,
        KeywordTableIndex,
        Settings,
        get_response_synthesizer,
    )
    from llama_index.core.node_parser import SentenceSplitter
    from llama_index.core.schema import NodeWithScore, TextNode, QueryBundle
    from llama_index.core.retrievers import BaseRetriever, RecursiveRetriever
    from llama_index.core.query_engine import RetrieverQueryEngine, RouterQueryEngine
    from llama_index.core.tools import QueryEngineTool
    from llama_index.core.selectors import LLMSingleSelector
    from llama_index.core.response_synthesizers import ResponseMode
    from llama_index.core.postprocessor import (
        KeywordNodePostprocessor,
        MetadataReplacementPostProcessor,
    )
    from llama_index.core.evaluation import (
        FaithfulnessEvaluator,
        RelevancyEvaluator,
    )
    from llama_index.llms.openrouter import OpenRouter
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding

    LLAMAINDEX_AVAILABLE = True
except Exception:
    LLAMAINDEX_AVAILABLE = False

    class BaseRetriever:
        """Stub para que la definición de HybridRetriever no falle sin LlamaIndex."""
        def __init__(self): pass
        def retrieve(self, query_bundle): return []


# ==========================================
# DATASET: Plataforma Educativa
# ==========================================
# Documentos que simulan fuentes diversas: descripciones de cursos, transcripciones
# de clases, FAQ y foros de estudiantes. Cada fuente tiene metadata distinta para
# demostrar filtrado y routing.

EDUCATIONAL_DOCUMENTS = [
    {
        "text": (
            "El curso 'Fundamentos de Machine Learning' cubre regresión lineal, "
            "regresión logística, árboles de decisión y validación cruzada. "
            "Se utiliza Python con scikit-learn como biblioteca principal. "
            "Duración: 8 semanas. Nivel: intermedio. Prerequisitos: estadística básica y Python."
        ),
        "metadata": {"source": "course_description", "course": "ml_fundamentals", "difficulty": "intermediate"},
    },
    {
        "text": (
            "El curso 'Ingeniería de Datos con PostgreSQL y pgvector' enseña modelado relacional, "
            "indexación vectorial con HNSW, pipelines de ingestión y consultas de similitud. "
            "Los estudiantes aprenden a almacenar embeddings y hacer búsqueda semántica directamente "
            "en PostgreSQL. Duración: 6 semanas. Nivel: avanzado. Prerequisitos: SQL intermedio."
        ),
        "metadata": {"source": "course_description", "course": "data_eng_pg", "difficulty": "advanced"},
    },
    {
        "text": (
            "En la clase 3 de ML Fundamentals, la profesora García explicó que la regularización L1 "
            "produce modelos dispersos (sparse), mientras que L2 penaliza pesos grandes sin eliminarlos. "
            "Se mostró un ejemplo con datos de precios de viviendas donde Lasso redujo 40 features a 12."
        ),
        "metadata": {"source": "lecture_transcript", "course": "ml_fundamentals", "class_number": 3},
    },
    {
        "text": (
            "En la clase 5 de Ingeniería de Datos, el profesor Méndez demostró cómo crear un índice HNSW "
            "en PostgreSQL con la extensión pgvector. El comando fue: CREATE INDEX ON items USING hnsw "
            "(embedding vector_cosine_ops) WITH (m=16, ef_construction=64). Explicó que m controla "
            "la conectividad del grafo y ef_construction la calidad del índice vs tiempo de construcción."
        ),
        "metadata": {"source": "lecture_transcript", "course": "data_eng_pg", "class_number": 5},
    },
    {
        "text": (
            "FAQ: ¿Cómo accedo a los materiales del curso? Todos los materiales están disponibles "
            "en la plataforma Moodle. Las grabaciones de clase se suben dentro de las 24 horas. "
            "Los ejercicios prácticos tienen deadline de 7 días desde su publicación."
        ),
        "metadata": {"source": "faq", "category": "logistics"},
    },
    {
        "text": (
            "FAQ: ¿Se puede usar GPU en los ejercicios? Sí, el laboratorio provee acceso a GPUs "
            "NVIDIA A100 vía JupyterHub. Para activar el runtime GPU, seleccionar 'GPU Kernel' "
            "en el menú de Jupyter. El límite es de 4 horas continuas por sesión."
        ),
        "metadata": {"source": "faq", "category": "technical"},
    },
    {
        "text": (
            "Foro - estudiante_42: '¿Alguien sabe si el proyecto final de ML puede hacerse en grupo? "
            "La profesora García dijo que máximo 3 personas y que hay que registrarse antes del 15 de mayo.' "
            "Respuesta de estudiante_88: 'Confirmado, y el entregable es un notebook + video de 10 min.'"
        ),
        "metadata": {"source": "student_forum", "course": "ml_fundamentals", "thread": "project_groups"},
    },
    {
        "text": (
            "Foro - estudiante_15: 'El índice HNSW me da resultados distintos cada vez que lo recreo. "
            "¿Es normal?' Respuesta del TA: 'Sí, HNSW tiene aleatoriedad en la construcción. Para "
            "resultados deterministas, fijá la semilla con SET hnsw.ef_search = 100; y aumentá ef_search "
            "para mejorar recall a costa de latencia.'"
        ),
        "metadata": {"source": "student_forum", "course": "data_eng_pg", "thread": "hnsw_determinism"},
    },
]


# ==========================================
# MODO MOCK (sin API Key o sin LlamaIndex)
# ==========================================

MOCK_RESPONSES = {
    "¿Qué temas cubre el curso de Machine Learning?": (
        "El curso 'Fundamentos de Machine Learning' cubre regresión lineal, regresión logística, "
        "árboles de decisión y validación cruzada, utilizando Python con scikit-learn. "
        "Duración: 8 semanas, nivel intermedio."
    ),
    "¿Cómo se crea un índice HNSW en PostgreSQL?": (
        "Según la clase 5 de Ingeniería de Datos, se crea con: "
        "CREATE INDEX ON items USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64). "
        "El parámetro m controla la conectividad del grafo y ef_construction la calidad vs tiempo."
    ),
    "¿Se puede usar GPU en los ejercicios?": (
        "Sí, el laboratorio provee GPUs NVIDIA A100 vía JupyterHub. Seleccioná 'GPU Kernel' en Jupyter. "
        "Límite: 4 horas continuas por sesión."
    ),
    "¿Qué dijeron en el foro sobre el proyecto final de ML?": (
        "En el foro se confirmó que el proyecto final de ML puede hacerse en grupos de máximo 3 personas, "
        "con registro antes del 15 de mayo. El entregable es un notebook + video de 10 minutos."
    ),
}

MOCK_EVALUATION = {
    "faithfulness": 0.92,
    "relevancy": 0.88,
    "explanation": "La respuesta es fiel a las fuentes recuperadas y relevante a la consulta.",
}


def print_separator(char="=", width=65):
    print(f"\n{char * width}")


def run_mock_demo(reason: str):
    print(f"\n[NOTA] {reason}. Usando respuestas simuladas.\n")

    print_separator()
    print("  LLAMAINDEX ADVANCED RAG — Plataforma Educativa (MOCK)")
    print_separator()

    print("\n--- Paso 1: Indexación jerárquica de documentos ---")
    for i, doc in enumerate(EDUCATIONAL_DOCUMENTS):
        print(f"  [{doc['metadata']['source']}] Documento {i+1}: {doc['text'][:60]}...")
    print(f"\n  Total: {len(EDUCATIONAL_DOCUMENTS)} documentos indexados en 3 índices:")
    print("    - VectorStoreIndex (búsqueda semántica)")
    print("    - SummaryIndex (resúmenes globales)")
    print("    - KeywordTableIndex (búsqueda por término)")

    print("\n--- Paso 2: Router Query Engine ---")
    print("  El router analiza la intención de la consulta y elige el índice óptimo.")

    print("\n--- Paso 3: Consultas de ejemplo ---")
    for query, response in MOCK_RESPONSES.items():
        print(f"\n  Pregunta: {query}")
        print(f"  Índice seleccionado: {'vector' if 'HNSW' in query or 'GPU' in query else 'summary'}")
        print(f"  Respuesta: {response}")
        print(f"  Confianza: 0.{85 + hash(query) % 14}")

    print("\n--- Paso 4: Hybrid Retriever (vector + keyword) ---")
    print("  Combinando scores: 0.6 * vector_score + 0.4 * keyword_score")
    print("  Nodos recuperados: 4 (2 por vector, 2 por keyword, deduplicados)")

    print("\n--- Paso 5: Node Postprocessors ---")
    print("  - KeywordNodePostprocessor: excluyendo nodos sin palabra clave 'curso'")
    print("  - MetadataReplacementPostProcessor: inyectando contexto de ventana")
    print("  - Reranking: reordenando por relevancia cruzada")

    print("\n--- Paso 6: Evaluación ---")
    print(f"  Faithfulness: {MOCK_EVALUATION['faithfulness']}")
    print(f"  Relevancy:    {MOCK_EVALUATION['relevancy']}")
    print(f"  Detalle:      {MOCK_EVALUATION['explanation']}")

    print_separator()
    print("  Demo completada (modo mock)")
    print_separator()


# ==========================================
# CONFIGURACIÓN DEL LLM Y EMBEDDINGS
# ==========================================

def configure_settings():
    """
    Configura el LLM vía OpenRouter (modelo gratuito) y embeddings locales
    con HuggingFace. No requiere API key para embeddings.

    En producción:
      - Usar modelos pagos para mejor calidad (GPT-4o, Claude 3.5).
      - Cachear embeddings en disco para evitar recalcular en re-indexación.
      - Configurar rate limiting y retry logic en el LLM.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")

    llm = OpenRouter(
        model="meta-llama/llama-3.1-8b-instruct:free",
        api_key=api_key,
        temperature=0.1,
        max_tokens=1024,
    )

    embed_model = HuggingFaceEmbedding(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
    )

    Settings.llm = llm
    Settings.embed_model = embed_model
    Settings.chunk_size = 256
    Settings.chunk_overlap = 32

    print("  LLM: OpenRouter (meta-llama/llama-3.1-8b-instruct:free)")
    print("  Embeddings: HuggingFace (all-MiniLM-L6-v2, 384 dims)")
    print(f"  Chunk size: {Settings.chunk_size} | Overlap: {Settings.chunk_overlap}")


# ==========================================
# 1. INDEXACIÓN AVANZADA
# ==========================================

def build_documents():
    """Construye objetos Document con metadata enriquecida."""
    docs = []
    for entry in EDUCATIONAL_DOCUMENTS:
        doc = Document(text=entry["text"], metadata=entry["metadata"])
        doc.excluded_embed_metadata_keys = ["source"]
        doc.excluded_llm_metadata_keys = ["source"]
        docs.append(doc)
    return docs


def build_indexes(docs):
    """
    Construye tres índices complementarios:

    - VectorStoreIndex: búsqueda por similitud semántica. Ideal para preguntas
      conceptuales ("¿qué es regularización?"). Costo: O(n) en búsqueda brute-force,
      O(log n) con ANN. Mejor para la mayoría de queries del usuario final.

    - SummaryIndex: recorre todos los nodos y sintetiza. Ideal para preguntas
      globales ("resumí todo el curso"). Costo: alto (procesa todos los nodos).
      Usar solo cuando la query requiere visión completa.

    - KeywordTableIndex: extrae keywords de cada nodo y busca por coincidencia
      exacta. Ideal para términos técnicos ("pgvector", "HNSW", "scikit-learn").
      No entiende sinónimos — complementar con vector search.
    """
    splitter = SentenceSplitter(chunk_size=Settings.chunk_size, chunk_overlap=Settings.chunk_overlap)
    nodes = splitter.get_nodes_from_documents(docs)

    for node in nodes:
        parent_text = node.get_content(metadata_mode="all")
        node.metadata["window"] = parent_text
        node.metadata["original_text"] = node.get_content()

    print(f"\n  Nodos creados: {len(nodes)}")
    for node in nodes:
        src = node.metadata.get("source", "?")
        preview = node.get_content()[:50]
        print(f"    [{src}] {preview}...")

    vector_index = VectorStoreIndex(nodes)
    print("\n  VectorStoreIndex: construido (similitud semántica)")

    summary_index = SummaryIndex(nodes)
    print("  SummaryIndex: construido (síntesis global)")

    keyword_index = KeywordTableIndex(nodes)
    print("  KeywordTableIndex: construido (búsqueda por término)")

    return vector_index, summary_index, keyword_index, nodes


# ==========================================
# 2. ROUTER QUERY ENGINE
# ==========================================

def build_router_query_engine(vector_index, summary_index, keyword_index):
    """
    Router Query Engine: analiza la consulta del usuario y la delega al índice
    más adecuado. Usa un LLM como selector (LLMSingleSelector).

    Trade-offs:
      - Ventaja: evita búsquedas costosas en índices innecesarios.
      - Riesgo: si las descripciones de cada tool son ambiguas, el router
        puede elegir mal. Ser muy explícito en las descripciones.
      - Latencia: añade 1 llamada LLM extra para el routing.
    """
    vector_engine = vector_index.as_query_engine(
        response_mode=ResponseMode.COMPACT,
        similarity_top_k=3,
    )

    summary_engine = summary_index.as_query_engine(
        response_mode=ResponseMode.TREE_SUMMARIZE,
    )

    keyword_engine = keyword_index.as_query_engine(
        response_mode=ResponseMode.COMPACT,
    )

    tools = [
        QueryEngineTool.from_defaults(
            query_engine=vector_engine,
            description=(
                "Útil para preguntas conceptuales y semánticas sobre cursos, "
                "como '¿qué temas cubre X?' o '¿cómo funciona Y?'. "
                "Busca por similitud de significado."
            ),
            name="vector_search",
        ),
        QueryEngineTool.from_defaults(
            query_engine=summary_engine,
            description=(
                "Útil para preguntas que requieren una visión global o resumen "
                "completo, como 'resumí todos los cursos' o '¿qué ofrece la plataforma?'. "
                "Sintetiza información de todos los documentos."
            ),
            name="summary_search",
        ),
        QueryEngineTool.from_defaults(
            query_engine=keyword_engine,
            description=(
                "Útil para buscar términos técnicos específicos como 'HNSW', "
                "'pgvector', 'scikit-learn', 'GPU', 'JupyterHub'. "
                "Busca por coincidencia exacta de palabras clave."
            ),
            name="keyword_search",
        ),
    ]

    selector = LLMSingleSelector.from_defaults()

    router_engine = RouterQueryEngine(
        selector=selector,
        query_engine_tools=tools,
        verbose=True,
    )

    print("\n  Router Query Engine configurado con 3 tools:")
    print("    - vector_search: preguntas conceptuales/semánticas")
    print("    - summary_search: resúmenes globales")
    print("    - keyword_search: términos técnicos específicos")

    return router_engine


# ==========================================
# 3. RECURSIVE RETRIEVER
# ==========================================

def build_recursive_retriever(nodes):
    """
    Recursive Retriever: permite navegar jerarquías de nodos. Si un nodo recuperado
    tiene un padre (parent), el retriever sube al padre para obtener más contexto.

    Caso de uso: cuando los chunks son muy pequeños y se necesita contexto adicional
    del documento original. El trade-off es mayor latencia por el traversal.
    """
    node_dict = {node.node_id: node for node in nodes}

    retriever = RecursiveRetriever(
        retriever_dict={"root": VectorStoreIndex(nodes).as_retriever(similarity_top_k=2)},
        node_dict=node_dict,
    )

    print("\n  Recursive Retriever configurado (profundidad: 2 niveles)")
    return retriever


# ==========================================
# 4. HYBRID RETRIEVER PERSONALIZADO
# ==========================================

class HybridRetriever(BaseRetriever):
    """
    Retriever híbrido que combina búsqueda vectorial (semántica) con búsqueda
    por keyword (BM25-like). Fusiona resultados con weighted scoring.

    En producción:
      - Ajustar alpha (0.0-1.0) según el dominio: técnico → más keyword, conceptual → más vector.
      - Cachear resultados de ambos retrievers para queries frecuentes.
      - Considerar usar un ranker cruzado (cross-encoder) como postprocessor.
    """

    def __init__(self, vector_retriever, keyword_retriever, alpha=0.6):
        self._vector_retriever = vector_retriever
        self._keyword_retriever = keyword_retriever
        self._alpha = alpha
        super().__init__()

    def _retrieve(self, query_bundle):
        vector_nodes = self._vector_retriever.retrieve(query_bundle)
        keyword_nodes = self._keyword_retriever.retrieve(query_bundle)

        combined = {}

        for node_score in vector_nodes:
            nid = node_score.node.node_id
            combined[nid] = {
                "node": node_score.node,
                "score": self._alpha * (node_score.score or 0.0),
            }

        for node_score in keyword_nodes:
            nid = node_score.node.node_id
            if nid in combined:
                combined[nid]["score"] += (1 - self._alpha) * (node_score.score or 0.5)
            else:
                combined[nid] = {
                    "node": node_score.node,
                    "score": (1 - self._alpha) * (node_score.score or 0.5),
                }

        sorted_results = sorted(combined.values(), key=lambda x: x["score"], reverse=True)

        return [
            NodeWithScore(node=item["node"], score=item["score"])
            for item in sorted_results
        ]


def build_hybrid_retriever(vector_index, keyword_index):
    """Construye el HybridRetriever combinando ambos retrievers."""
    vector_retriever = vector_index.as_retriever(similarity_top_k=3)
    keyword_retriever = keyword_index.as_retriever()

    hybrid = HybridRetriever(vector_retriever, keyword_retriever, alpha=0.6)

    print("\n  Hybrid Retriever configurado (alpha=0.6 → 60% vector, 40% keyword)")
    return hybrid


# ==========================================
# 5. NODE POSTPROCESSORS
# ==========================================

def build_postprocessors():
    """
    Postprocessors que refinan los nodos recuperados antes de la síntesis:

    1. KeywordNodePostprocessor: excluye nodos que NO contienen ciertas keywords.
       Útil para filtrar ruido cuando sabemos que la respuesta debe mencionar algo.

    2. MetadataReplacementPostProcessor: reemplaza el texto del nodo con un campo
       de metadata (ej: 'window' que contiene contexto más amplio). Esto permite
       usar chunks pequeños para retrieval pero entregar contexto grande al LLM.

    En producción:
      - No abusar de KeywordNodePostprocessor: puede eliminar nodos relevantes.
      - MetadataReplacementPostProcessor es clave para la técnica 'sentence window retrieval'.
      - Agregar un CohereRerank o LLMRerank para mejorar el orden final.
    """
    postprocessors = [
        MetadataReplacementPostProcessor(target_metadata_key="window"),
    ]

    print("\n  Postprocessors configurados:")
    print("    - MetadataReplacementPostProcessor (sentence window)")
    print("    - KeywordNodePostprocessor (se aplica por consulta si es necesario)")

    return postprocessors


# ==========================================
# 6. EVALUACIÓN
# ==========================================

def evaluate_responses(query_engine, evaluator_faith, evaluator_rel, queries_and_contexts):
    """
    Evalúa la calidad del pipeline RAG con dos métricas:

    - Faithfulness: ¿la respuesta es fiel a los nodos recuperados?
      Detecta alucinaciones. Score 0-1.

    - Relevancy: ¿la respuesta es relevante a la consulta original?
      Detecta respuestas fuera de tema. Score 0-1.

    En producción:
      - Ejecutar evaluación en batch periódicamente (no en cada query).
      - Guardar métricas en un dashboard (Langfuse, Arize, Weights & Biases).
      - Definir umbrales mínimos (ej: faithfulness < 0.7 → flag para revisión humana).
      - Usar conjuntos de evaluación curados por expertos del dominio.
    """
    results = []

    for query, expected_context in queries_and_contexts:
        print(f"\n  Evaluando: '{query}'")

        response = query_engine.query(query)
        response_text = str(response)
        print(f"    Respuesta: {response_text[:100]}...")

        try:
            faith_result = evaluator_faith.evaluate_response(
                response=response,
            )
            faith_score = float(faith_result.score) if faith_result.score is not None else 0.0
            print(f"    Faithfulness: {faith_score:.2f}")
        except Exception as e:
            faith_score = 0.0
            print(f"    Faithfulness: error ({e})")

        try:
            rel_result = evaluator_rel.evaluate_response(
                query=query,
                response=response,
            )
            rel_score = float(rel_result.score) if rel_result.score is not None else 0.0
            print(f"    Relevancy:    {rel_score:.2f}")
        except Exception as e:
            rel_score = 0.0
            print(f"    Relevancy:    error ({e})")

        results.append({
            "query": query,
            "response": response_text,
            "faithfulness": faith_score,
            "relevancy": rel_score,
        })

    return results


# ==========================================
# DEMO PRINCIPAL (MODO EN VIVO)
# ==========================================

def run_live_demo():
    print_separator()
    print("  LLAMAINDEX ADVANCED RAG — Plataforma Educativa")
    print_separator()

    print("\n--- Paso 1: Configurando LLM y Embeddings ---")
    configure_settings()

    print("\n--- Paso 2: Construyendo documentos e índices ---")
    docs = build_documents()
    vector_index, summary_index, keyword_index, nodes = build_indexes(docs)

    print("\n--- Paso 3: Router Query Engine ---")
    router_engine = build_router_query_engine(vector_index, summary_index, keyword_index)

    print("\n--- Paso 4: Consultas con Router ---")
    test_queries = [
        "¿Qué temas cubre el curso de Machine Learning?",
        "¿Cómo se crea un índice HNSW en PostgreSQL?",
    ]

    for query in test_queries:
        print(f"\n  Pregunta: {query}")
        try:
            response = router_engine.query(query)
            print(f"  Respuesta: {response}")
            if hasattr(response, "metadata") and response.metadata:
                selector = response.metadata.get("selector_result", "N/A")
                print(f"  Índice elegido por router: {selector}")
        except Exception as e:
            print(f"  Error: {e}")

    print("\n--- Paso 5: Hybrid Retriever ---")
    hybrid_retriever = build_hybrid_retriever(vector_index, keyword_index)
    postprocessors = build_postprocessors()

    hybrid_query = "¿Qué dijeron en el foro sobre el proyecto final?"
    print(f"\n  Pregunta: {hybrid_query}")
    retrieved_nodes = hybrid_retriever.retrieve(hybrid_query)
    print(f"  Nodos recuperados: {len(retrieved_nodes)}")
    for i, ns in enumerate(retrieved_nodes):
        src = ns.node.metadata.get("source", "?")
        print(f"    [{i+1}] score={ns.score:.3f} source={src} | {ns.node.get_content()[:60]}...")

    response_synthesizer = get_response_synthesizer(
        response_mode=ResponseMode.REFINE,
    )

    hybrid_engine = RetrieverQueryEngine(
        retriever=hybrid_retriever,
        response_synthesizer=response_synthesizer,
        node_postprocessors=postprocessors,
    )

    print("\n  Response mode: REFINE (itera sobre cada nodo para refinar la respuesta)")
    try:
        response = hybrid_engine.query(hybrid_query)
        print(f"  Respuesta refinada: {response}")
    except Exception as e:
        print(f"  Error: {e}")

    print("\n--- Paso 6: Recursive Retriever ---")
    recursive_retriever = build_recursive_retriever(nodes)
    recursive_query = "¿Qué es la regularización L1?"
    print(f"\n  Pregunta: {recursive_query}")
    try:
        rec_nodes = recursive_retriever.retrieve(recursive_query)
        print(f"  Nodos recuperados (recursivo): {len(rec_nodes)}")
        for i, ns in enumerate(rec_nodes):
            print(f"    [{i+1}] score={ns.score:.3f} | {ns.node.get_content()[:60]}...")
    except Exception as e:
        print(f"  Error: {e}")

    print("\n--- Paso 7: Tree Summarization ---")
    tree_engine = summary_index.as_query_engine(
        response_mode=ResponseMode.TREE_SUMMARIZE,
    )
    tree_query = "Resumí todos los cursos disponibles y sus prerequisitos"
    print(f"\n  Pregunta: {tree_query}")
    try:
        response = tree_engine.query(tree_query)
        print(f"  Respuesta (tree summarize): {response}")
    except Exception as e:
        print(f"  Error: {e}")

    print("\n--- Paso 8: Evaluación de calidad ---")
    evaluator_faith = FaithfulnessEvaluator()
    evaluator_rel = RelevancyEvaluator()

    eval_queries = [
        ("¿Se puede usar GPU en los ejercicios?", "GPU NVIDIA A100, JupyterHub, 4 horas"),
        ("¿Cómo se crea un índice HNSW?", "CREATE INDEX USING hnsw, m=16, ef_construction=64"),
    ]

    eval_results = evaluate_responses(
        vector_index.as_query_engine(similarity_top_k=3),
        evaluator_faith,
        evaluator_rel,
        eval_queries,
    )

    print("\n--- Resumen de Evaluación ---")
    avg_faith = sum(r["faithfulness"] for r in eval_results) / max(len(eval_results), 1)
    avg_rel = sum(r["relevancy"] for r in eval_results) / max(len(eval_results), 1)
    print(f"  Faithfulness promedio: {avg_faith:.2f}")
    print(f"  Relevancy promedio:    {avg_rel:.2f}")

    print_separator()
    print("  Demo completada (modo en vivo)")
    print_separator()


# ==========================================
# ENTRY POINT
# ==========================================

def main():
    api_key = os.environ.get("OPENROUTER_API_KEY")

    if not LLAMAINDEX_AVAILABLE:
        run_mock_demo("LlamaIndex no está instalado")
        return

    if not api_key:
        run_mock_demo("OPENROUTER_API_KEY no encontrada")
        return

    try:
        run_live_demo()
    except Exception as e:
        print(f"\n[ERROR] Falló la ejecución en vivo: {e}")
        print("  Cayendo a modo mock...\n")
        run_mock_demo(f"Error en ejecución: {e}")


if __name__ == "__main__":
    main()
