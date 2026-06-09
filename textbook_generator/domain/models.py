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


class CampoFormativo(str, Enum):
    LENGUAJES = "Lenguajes"
    SABERES_PCIENTIFICO = "Saberes y Pensamiento Científico"
    ETICA_NATURALEZA_SOCIEDADES = "Ética, Naturaleza y Sociedades"
    HUMANO_COMUNITARIO = "De lo Humano y lo Comunitario"


class EjeArticulador(str, Enum):
    PENSAMIENTO_CRITICO = "Pensamiento crítico"
    INTERCULTURALIDAD = "Interculturalidad"
    IGUALDAD_GENERO = "Igualdad de género"
    VIDA_SALUDABLE = "Vida saludable"
    INCLUSION = "Inclusión"
    LECTURA_ESCRITURA = "Lectura y escritura"
    ARTES_ESTETICA = "Artes y experiencias estéticas"


class FaseAprendizaje(str, Enum):
    FASE_1 = "Fase 1 - Preescolar 3°"
    FASE_2 = "Fase 2 - Primaria 1°-2°"
    FASE_3 = "Fase 3 - Primaria 3°-4°"
    FASE_4 = "Fase 4 - Primaria 5°-6°"
    FASE_5 = "Fase 5 - Secundaria 1°-2°"
    FASE_6 = "Fase 6 - Secundaria 3°"


class TipoProyecto(str, Enum):
    AULA = "Proyecto de Aula"
    ESCOLAR = "Proyecto Escolar"
    COMUNITARIO = "Proyecto Comunitario"


class CurricularRequirement(BaseModel):
    id: Optional[int] = None
    code: str = Field(..., description="Unique code of the requirement, e.g. REQ-ESP-1.1")
    description: str = Field(..., description="Text description of the curricular requirement")
    subject: str = Field(..., description="Subject of the curriculum, e.g. Español, Matemáticas")
    grade: int = Field(..., description="Target grade (1-6)")


class ContenidoProgramaSintetico(BaseModel):
    id: Optional[int] = None
    campo_formativo: CampoFormativo = Field(..., description="Campo formativo del Programa Sintético NEM")
    fase: FaseAprendizaje = Field(..., description="Fase de aprendizaje oficial NEM")
    codigo: str = Field(..., description="Código oficial SEP, ej: CF-LNG-F2-C01")
    descripcion: str = Field(..., description="Descripción del contenido del Programa Sintético")


class ProcesoDesarrolloAprendizaje(BaseModel):
    id: Optional[int] = None
    contenido_id: int = Field(..., description="FK a ContenidoProgramaSintetico")
    fase: FaseAprendizaje = Field(..., description="Fase de aprendizaje")
    descripcion: str = Field(..., description="Descripción del PDA oficial")


class ContextoLocal(BaseModel):
    id: Optional[int] = None
    textbook_id: int = Field(..., description="FK al libro de texto")
    comunidad: str = Field(..., description="Tipo: Urbana, Rural, Indígena, Migrante")
    lengua_originaria: Optional[str] = Field(None, description="Lengua originaria si aplica")
    problematica_local: str = Field("", description="Problemática local, ej: Escasez de agua")
    saberes_comunitarios: List[str] = Field(default_factory=list, description="Saberes de la comunidad")
    proyectos_sugeridos: List[str] = Field(default_factory=list, description="Proyectos sugeridos por el docente")


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
    campo_formativo_principal: Optional[CampoFormativo] = Field(None, description="Campo formativo principal NEM")
    campos_formativos_vinculados: List[CampoFormativo] = Field(default_factory=list, description="Campos formativos vinculados")
    contenidos_sinteticos_ids: List[int] = Field(default_factory=list, description="IDs de contenidos del Programa Sintético")
    pda_ids: List[int] = Field(default_factory=list, description="IDs de PDA asociados")
    ejes_articuladores: List[EjeArticulador] = Field(default_factory=list, description="Ejes articuladores transversales")
    proyecto_vinculado: Optional[str] = Field(None, description="Proyecto integrador vinculado")


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
    fase: FaseAprendizaje = Field(FaseAprendizaje.FASE_2, description="Fase de aprendizaje NEM")
    contexto_local: Optional[ContextoLocal] = Field(None, description="Contexto local para Programa Analítico")
