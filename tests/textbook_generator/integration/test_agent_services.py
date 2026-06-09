import os
import sys

# Add root directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from textbook_generator.domain.models import Secuencia, Lesson
from textbook_generator.infrastructure.agents.pydantic_agents import PydanticTextbookAgentService

def test_agent_outline_generation():
    """Integration Test: Verify agent structure outline generator outputs."""
    service = PydanticTextbookAgentService()
    
    # Run in mock mode (forced by lack of GEMINI_API_KEY during test run)
    outline = service.generate_outline(subject="Español", grade=1, requirements=[])
    
    assert outline.title == "Mi Libro Divertido de Español - Primer Grado"
    assert len(outline.trimestres) == 3
    
    # Every trimester must have exactly 6 sequences
    for t in outline.trimestres:
        assert len(t.secuencias) == 6
        assert t.title is not None
        assert t.goals is not None
        
        for s in t.secuencias:
            assert s.number >= 1 and s.number <= 6
            assert s.title is not None
            assert s.objectives is not None


def test_agent_sequence_content_generation():
    """Integration Test: Verify agent content generator outputs correct lesson structure."""
    service = PydanticTextbookAgentService()
    
    lessons = service.generate_sequence_content(
        subject="Español",
        grade=1,
        trimester_num=1,
        seq_num=1,
        seq_title="Las letras de mi nombre",
        seq_objectives="Identifica letras",
        requirements=[]
    )
    
    # Must generate exactly 3 lessons
    assert len(lessons) == 3
    for idx, lesson in enumerate(lessons):
        assert isinstance(lesson, Lesson)
        # Mock agent now sets lesson numbers (1, 2, 3)
        assert lesson.number == idx + 1
        assert lesson.title == f"Lección {idx + 1}: Jugando con Las letras de mi nombre"
        
        # Verify mandatory 3-part pedagogical layout
        assert "Inicio" in lesson.section_inicio or "explorar" in lesson.section_inicio
        assert "[Ilustración:" in lesson.section_desarrollo
        assert "Cierre" in lesson.section_cierre or "cantamos" in lesson.section_cierre
        assert lesson.activities is not None


def test_agent_evaluation_guardrails():
    """Integration Test: Verify agent evaluation scores and HITL threshold routing logic."""
    service = PydanticTextbookAgentService()
    
    # Sequence 1: Must pass automated quality threshold (>= 0.85)
    seq_1 = Secuencia(trimestre_id=1, number=1, title="S1", objectives="O1")
    eval_1 = service.evaluate_sequence(seq_1, requirements=[])
    assert eval_1.alignment_score >= 0.85
    assert eval_1.age_score >= 0.85
    assert "Excelente" in eval_1.justification

    # Sequence 2: Must fail automated quality threshold (< 0.85) to trigger HITL routing
    seq_2 = Secuencia(trimestre_id=1, number=2, title="S2", objectives="O2")
    eval_2 = service.evaluate_sequence(seq_2, requirements=[])
    assert eval_2.alignment_score < 0.85 or eval_2.age_score < 0.85
    assert "complejos para niños" in eval_2.justification
