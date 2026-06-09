import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...domain.models import (
    Textbook, Secuencia, GenerationStatus, CurricularRequirement,
    CampoFormativo, FaseAprendizaje, TipoProyecto, ContextoLocal
)
from ...application.use_cases import (
    CreateTextbookUseCase, GenerateBookWorkflowUseCase, ReviewSequenceUseCase,
    ContextualizeTextbookUseCase, MapContenidosPDAUseCase,
    EvaluatePDAAlignmentUseCase, GenerateProyectoIntegradorUseCase,
    ExportConalitegFormatUseCase
)
from ..database.sqlite_repository import (
    SQLiteTextbookRepository, SQLiteRequirementRepository, SQLiteNEMRepository
)
from ..agents.pydantic_agents import PydanticTextbookAgentService
from ..agents.nem_agents import PydanticNEMAgentService

logger = logging.getLogger(__name__)

router = APIRouter()


def get_db(request: Request = None) -> Session:
    if request is not None and hasattr(request.state, 'db'):
        return request.state.db
    raise NotImplementedError("Database session dependency must be overridden in tests")


def get_textbook_repo(db: Session = Depends(get_db)):
    return SQLiteTextbookRepository(db)


def get_requirement_repo(db: Session = Depends(get_db)):
    return SQLiteRequirementRepository(db)


def get_nem_repo(db: Session = Depends(get_db)):
    return SQLiteNEMRepository(db)


def get_agent_service():
    return PydanticTextbookAgentService()


def get_nem_agent_service():
    return PydanticNEMAgentService()


class CreateTextbookRequest(BaseModel):
    title: str = Field(..., json_schema_extra={"example": "Mis Primeros Pasos en Lenguaje"})
    subject: str = Field(..., json_schema_extra={"example": "Español"})
    grade: int = Field(1, ge=1, le=6, json_schema_extra={"example": 1})


class ReviewRequest(BaseModel):
    approve: bool = Field(..., json_schema_extra={"example": True})
    feedback: Optional[str] = Field(None, json_schema_extra={"example": "Simplificar el vocabulario."})


class ContextoLocalRequest(BaseModel):
    comunidad: str = Field(..., json_schema_extra={"example": "Urbana"})
    problematica_local: str = Field("", json_schema_extra={"example": "Escasez de agua"})
    lengua_originaria: Optional[str] = None
    saberes_comunitarios: List[str] = Field(default_factory=list)
    proyectos_sugeridos: List[str] = Field(default_factory=list)


class MapContenidosRequest(BaseModel):
    campo_formativo: CampoFormativo
    fase: FaseAprendizaje = FaseAprendizaje.FASE_2


class ProyectoIntegradorRequest(BaseModel):
    tipo: TipoProyecto
    nombre: str = Field(..., json_schema_extra={"example": "El agua en mi comunidad"})
    descripcion: Optional[str] = None


@router.post("/books", response_model=Textbook)
def create_textbook(
    req: CreateTextbookRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    textbook_repo: SQLiteTextbookRepository = Depends(get_textbook_repo),
    requirement_repo: SQLiteRequirementRepository = Depends(get_requirement_repo),
    agent_service: PydanticTextbookAgentService = Depends(get_agent_service)
):
    try:
        use_case = CreateTextbookUseCase(textbook_repo)
        textbook = use_case.execute(req.title, req.subject, req.grade)

        workflow_use_case = GenerateBookWorkflowUseCase(
            textbook_repo=textbook_repo,
            requirement_repo=requirement_repo,
            agent_service=agent_service
        )
        background_tasks.add_task(workflow_use_case.execute, textbook.id)

        return textbook
    except Exception as e:
        logger.exception("Failed to create textbook project")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/books", response_model=List[Textbook])
def list_textbooks(textbook_repo: SQLiteTextbookRepository = Depends(get_textbook_repo)):
    return textbook_repo.list_textbooks()


@router.get("/books/{id}", response_model=Textbook)
def get_textbook(id: int, textbook_repo: SQLiteTextbookRepository = Depends(get_textbook_repo)):
    textbook = textbook_repo.get_textbook(id)
    if not textbook:
        raise HTTPException(status_code=404, detail="Textbook not found")
    return textbook


@router.get("/reviews", response_model=List[Secuencia])
def list_pending_reviews(textbook_repo: SQLiteTextbookRepository = Depends(get_textbook_repo)):
    return textbook_repo.get_pending_reviews()


@router.post("/reviews/{secuencia_id}", response_model=Secuencia)
def review_secuencia(
    secuencia_id: int,
    req: ReviewRequest,
    textbook_repo: SQLiteTextbookRepository = Depends(get_textbook_repo)
):
    try:
        use_case = ReviewSequenceUseCase(textbook_repo)
        return use_case.execute(secuencia_id, req.approve, req.feedback)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Failed to complete educator review")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/secuencias/{secuencia_id}/regenerate", response_model=Secuencia)
def regenerate_secuencia(
    secuencia_id: int,
    background_tasks: BackgroundTasks,
    textbook_repo: SQLiteTextbookRepository = Depends(get_textbook_repo),
    requirement_repo: SQLiteRequirementRepository = Depends(get_requirement_repo),
    agent_service: PydanticTextbookAgentService = Depends(get_agent_service)
):
    secuencia = textbook_repo.get_secuencia(secuencia_id)
    if not secuencia:
        raise HTTPException(status_code=404, detail="Sequence not found")

    textbook_id = textbook_repo.get_textbook_id_by_secuencia_id(secuencia_id)
    if not textbook_id:
        raise HTTPException(status_code=400, detail="Textbook not found for sequence")

    textbook = textbook_repo.get_textbook(textbook_id)
    if not textbook:
        raise HTTPException(status_code=400, detail="Textbook not found")

    trimester_num = textbook_repo.get_trimestre_number_by_secuencia_id(secuencia_id)
    if not trimester_num:
        raise HTTPException(status_code=400, detail="Trimester not found")

    textbook_repo.delete_lessons_by_secuencia_id(secuencia_id)

    workflow_use_case = GenerateBookWorkflowUseCase(
        textbook_repo=textbook_repo,
        requirement_repo=requirement_repo,
        agent_service=agent_service
    )

    objectives = secuencia.objectives
    if secuencia.review_feedback:
        objectives += f"\n[REGENERATION GUIDELINE: {secuencia.review_feedback}]"

    # Update status immediately so that background task does not get overwritten
    secuencia.status = GenerationStatus.GENERATING
    textbook_repo.update_secuencia(secuencia)
    
    background_tasks.add_task(
        workflow_use_case.generate_single_sequence,
        textbook,
        secuencia_id,
        trimester_num,
        secuencia.title,
        objectives,
        requirement_repo.list_requirements(textbook.subject, textbook.grade)
    )
    
    return secuencia


@router.post("/books/{textbook_id}/contexto-local", response_model=ContextoLocal)
def save_contexto_local(
    textbook_id: int,
    req: ContextoLocalRequest,
    textbook_repo: SQLiteTextbookRepository = Depends(get_textbook_repo)
):
    try:
        use_case = ContextualizeTextbookUseCase(textbook_repo)
        return use_case.execute(
            textbook_id=textbook_id,
            comunidad=req.comunidad,
            problematica_local=req.problematica_local,
            lengua_originaria=req.lengua_originaria,
            saberes_comunitarios=req.saberes_comunitarios,
            proyectos_sugeridos=req.proyectos_sugeridos
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/books/{textbook_id}/contexto-local", response_model=ContextoLocal)
def get_contexto_local(
    textbook_id: int,
    textbook_repo: SQLiteTextbookRepository = Depends(get_textbook_repo)
):
    contexto = textbook_repo.get_contexto_local(textbook_id)
    if not contexto:
        raise HTTPException(status_code=404, detail="Contexto local not found")
    return contexto


@router.post("/secuencias/{secuencia_id}/map-contenidos")
def map_contenidos_pda(
    secuencia_id: int,
    req: MapContenidosRequest,
    textbook_repo: SQLiteTextbookRepository = Depends(get_textbook_repo),
    nem_repo: SQLiteNEMRepository = Depends(get_nem_repo)
):
    try:
        use_case = MapContenidosPDAUseCase(nem_repo, textbook_repo)
        return use_case.execute(secuencia_id, req.campo_formativo, req.fase)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/secuencias/{secuencia_id}/evaluate-pda")
def evaluate_pda_alignment(
    secuencia_id: int,
    textbook_repo: SQLiteTextbookRepository = Depends(get_textbook_repo),
    nem_repo: SQLiteNEMRepository = Depends(get_nem_repo),
    nem_agent_service: PydanticNEMAgentService = Depends(get_nem_agent_service)
):
    try:
        use_case = EvaluatePDAAlignmentUseCase(textbook_repo, nem_repo, nem_agent_service)
        return use_case.execute(secuencia_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/secuencias/{secuencia_id}/proyecto")
def link_proyecto_integrador(
    secuencia_id: int,
    req: ProyectoIntegradorRequest,
    textbook_repo: SQLiteTextbookRepository = Depends(get_textbook_repo)
):
    try:
        use_case = GenerateProyectoIntegradorUseCase(textbook_repo)
        return use_case.execute(secuencia_id, req.tipo, req.nombre, req.descripcion)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/books/{textbook_id}/export")
def export_textbook_conaliteg(
    textbook_id: int,
    textbook_repo: SQLiteTextbookRepository = Depends(get_textbook_repo)
):
    try:
        use_case = ExportConalitegFormatUseCase(textbook_repo)
        return use_case.execute(textbook_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/admin/requirements/populate")
def populate_requirements(
    requirement_repo: SQLiteRequirementRepository = Depends(get_requirement_repo)
):
    requirements = [
        CurricularRequirement(code="REQ-ESP-1.1", description="Reconoce y escribe su propio nombre para identificar sus pertenencias y registrar asistencia.", subject="Español", grade=1),
        CurricularRequirement(code="REQ-ESP-1.2", description="Identifica la direccionalidad de la lectura (de izquierda a derecha y de arriba a abajo) en textos ilustrados.", subject="Español", grade=1),
        CurricularRequirement(code="REQ-ESP-1.3", description="Escribe palabras sencillas utilizando el abecedario e identifica la correspondencia entre sonidos y letras.", subject="Español", grade=1),
        CurricularRequirement(code="REQ-ESP-1.4", description="Escucha la lectura de cuentos y expresa opiniones sencillas sobre los personajes y los eventos de la historia.", subject="Español", grade=1),
        CurricularRequirement(code="REQ-ESP-1.5", description="Utiliza fórmulas de cortesía sencillas (por favor, gracias, buenos días) de forma oral y escrita en diálogos cotidianos.", subject="Español", grade=1),
        CurricularRequirement(code="REQ-MAT-1.1", description="Lee, escribe y ordena números cardinales del 1 al 10 en situaciones reales.", subject="Matemáticas", grade=1),
        CurricularRequirement(code="REQ-MAT-1.2", description="Identifica y representa figuras geométricas básicas (círculo, triángulo, cuadrado, rectángulo) en su entorno.", subject="Matemáticas", grade=1),
        CurricularRequirement(code="REQ-MAT-1.3", description="Resuelve problemas de suma y resta con números menores a 10 utilizando material concreto (juguetes, semillas, dibujos).", subject="Matemáticas", grade=1),
        CurricularRequirement(code="REQ-MAT-1.4", description="Compara longitudes, capacidades y pesos utilizando unidades no convencionales (sus pasos, sus manos, recipientes).", subject="Matemáticas", grade=1),
        CurricularRequirement(code="REQ-MAT-1.5", description="Registra información de forma visual utilizando tablas sencillas y pictogramas (caritas, marcas).", subject="Matemáticas", grade=1),
    ]

    added_count = 0
    for req in requirements:
        try:
            requirement_repo.add_requirement(req)
            added_count += 1
        except Exception:
            pass

    return {"message": "Curricular guidelines database seeded successfully.", "inserted": added_count}


@router.post("/admin/nem/seed-fase2")
def seed_nem_fase2_data(
    nem_repo: SQLiteNEMRepository = Depends(get_nem_repo)
):
    from ..database.seed_nem_fase2 import seed_nem_fase2
    result = seed_nem_fase2(nem_repo)
    return {"message": "NEM Fase 2 data seeded.", **result}
