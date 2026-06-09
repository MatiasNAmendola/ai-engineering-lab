from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field

class GenerationStatus(str, Enum):
    DRAFT = "DRAFT"
    GENERATING = "GENERATING"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class CurricularRequirement(BaseModel):
    id: Optional[int] = None
    code: str = Field(..., description="Unique code of the requirement, e.g. REQ-ESP-1.1")
    description: str = Field(..., description="Text description of the curricular requirement")
    subject: str = Field(..., description="Subject of the curriculum, e.g. Español, Matemáticas")
    grade: int = Field(..., description="Target grade (1-6)")

class Lesson(BaseModel):
    id: Optional[int] = None
    secuencia_id: int = Field(..., description="ID of the parent pedagogical sequence")
    number: int = Field(..., description="Lesson number (e.g. 1 to 5)")
    title: str = Field(..., description="Title of the lesson")
    section_inicio: str = Field(..., description="Apertura / Warm-up: 1st grade level context introduction")
    section_desarrollo: str = Field(..., description="Desarrollo / Core Activity: Guided learning & readings")
    section_cierre: str = Field(..., description="Cierre / Assessment: Wrap-up & reflection activities")
    activities: str = Field(..., description="Interactive instructions suitable for 6-year-olds")

class Secuencia(BaseModel):
    id: Optional[int] = None
    trimestre_id: int = Field(..., description="ID of the parent trimester")
    number: int = Field(..., description="Sequence number (1 to 6)")
    title: str = Field(..., description="Title of the pedagogical sequence")
    objectives: str = Field(..., description="Learning objectives for this sequence")
    curricular_alignment_score: Optional[float] = Field(None, description="Automated evaluation score (0.0 to 1.0)")
    age_appropriateness_score: Optional[float] = Field(None, description="Automated age-appropriateness score (0.0 to 1.0)")
    status: GenerationStatus = Field(GenerationStatus.DRAFT, description="Status of this sequence in the pipeline")
    review_feedback: Optional[str] = Field(None, description="Educator feedback if rejected")
    lessons: List[Lesson] = Field(default_factory=list, description="List of lessons within this sequence")

class Trimestre(BaseModel):
    id: Optional[int] = None
    textbook_id: int = Field(..., description="ID of the parent textbook")
    number: int = Field(..., description="Trimester number (1, 2, or 3)")
    title: str = Field(..., description="Title of the trimester")
    goals: str = Field(..., description="Overarching learning goals for this trimester")
    secuencias: List[Secuencia] = Field(default_factory=list, description="Pedagogical sequences inside the trimester")

class Textbook(BaseModel):
    id: Optional[int] = None
    title: str = Field(..., description="Title of the textbook")
    subject: str = Field(..., description="Subject domain, e.g. Español")
    grade: int = Field(..., description="Target grade level")
    status: GenerationStatus = Field(GenerationStatus.DRAFT, description="Global status of the textbook project")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when project was started")
    trimestres: List[Trimestre] = Field(default_factory=list, description="The 3 trimestres of the textbook")
