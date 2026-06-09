from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel, Field
from .models import (
    CurricularRequirement, Lesson, Secuencia,
    CampoFormativo, EjeArticulador, FaseAprendizaje,
    ContenidoProgramaSintetico, ProcesoDesarrolloAprendizaje, ContextoLocal
)


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


class NEMSequenceOutline(SequenceOutline):
    campo_formativo_principal: CampoFormativo = Field(..., description="Campo formativo principal")
    campos_formativos_vinculados: List[CampoFormativo] = Field(default_factory=list)
    contenidos_codigos: List[str] = Field(default_factory=list)
    ejes_articuladores: List[EjeArticulador] = Field(default_factory=list)
    proyecto_vinculado: Optional[str] = None


class NEMBookOutline(BaseModel):
    title: str = Field(..., description="Proposed title for the textbook")
    fase: FaseAprendizaje = Field(..., description="Fase de aprendizaje NEM")
    trimestres: List[TrimestreOutline] = Field(..., description="The 3 trimestres of the book")


class PDAResult(BaseModel):
    pda_id: int = Field(..., description="ID del PDA evaluado")
    nivel_logro: str = Field(..., description="En proceso / Logrado / Avanzado")
    justificacion: str = Field(..., description="Justificación del nivel de logro")


class PDACoverageResult(BaseModel):
    pda_results: List[PDAResult] = Field(default_factory=list)
    cobertura_score: float = Field(..., description="Score global de cobertura PDA (0.0-1.0)")
    ejes_score: float = Field(..., description="Score de integración de ejes articuladores (0.0-1.0)")
    justificacion: str = Field(..., description="Justificación general")


class TextbookAgentService(ABC):
    @abstractmethod
    def generate_outline(
        self, subject: str, grade: int, requirements: List[CurricularRequirement]
    ) -> BookOutline:
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
        pass

    @abstractmethod
    def evaluate_sequence(
        self, secuencia: Secuencia, requirements: List[CurricularRequirement]
    ) -> EvaluationResult:
        pass


class NEMAgentService(ABC):
    @abstractmethod
    def generate_nem_outline(
        self,
        campo_formativo: CampoFormativo,
        fase: FaseAprendizaje,
        contenidos: List[ContenidoProgramaSintetico],
        contexto: Optional[ContextoLocal] = None
    ) -> NEMBookOutline:
        pass

    @abstractmethod
    def evaluate_pda_coverage(
        self,
        secuencia: Secuencia,
        pda_list: List[ProcesoDesarrolloAprendizaje],
        ejes: List[EjeArticulador]
    ) -> PDACoverageResult:
        pass
