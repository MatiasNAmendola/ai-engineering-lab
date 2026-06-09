from abc import ABC, abstractmethod
from typing import List, Tuple
from pydantic import BaseModel, Field
from .models import CurricularRequirement, Lesson, Secuencia

# Helper structures for structured agent outputs defined at domain level
class SequenceOutline(BaseModel):
    number: int = Field(..., description="Sequence number (1-6)")
    title: str = Field(..., description="Title of the sequence")
    objectives: str = Field(..., description="Learning goals and objectives")

class TrimestreOutline(BaseModel):
    number: int = Field(..., description="Trimester number (1, 2, or 3)")
    title: str = Field(..., description="Title of the trimester")
    goals: str = Field(..., description="General goals for the trimester")
    secuencias: List[SequenceOutline] = Field(..., description="List of 6 sequences")

class BookOutline(BaseModel):
    title: str = Field(..., description="Proposed title for the textbook")
    trimestres: List[TrimestreOutline] = Field(..., description="The 3 trimestres of the book")

class EvaluationResult(BaseModel):
    alignment_score: float = Field(..., description="Alignment score from 0.0 to 1.0")
    age_score: float = Field(..., description="Age appropriateness score from 0.0 to 1.0 for 1st grade")
    justification: str = Field(..., description="Justification and feedback for the scores")


class TextbookAgentService(ABC):
    @abstractmethod
    def generate_outline(
        self, subject: str, grade: int, requirements: List[CurricularRequirement]
    ) -> BookOutline:
        """Generate a global textbook structure based on curricular standards."""
        pass

    @abstractmethod
    def generate_sequence_content(
        self, 
        subject: str, 
        grade: int, 
        trimester_num: int,
        seq_num: int, 
        seq_title: str, 
        seq_objectives: str, 
        requirements: List[CurricularRequirement]
    ) -> List[Lesson]:
        """Generate lessons for a specific sequence matching the 3-part layout (Inicio, Desarrollo, Cierre)."""
        pass

    @abstractmethod
    def evaluate_sequence(
        self, secuencia: Secuencia, requirements: List[CurricularRequirement]
    ) -> EvaluationResult:
        """Evaluate a sequence for curricular alignment and age appropriateness."""
        pass
