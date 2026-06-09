import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...domain.models import Textbook, Secuencia, GenerationStatus, CurricularRequirement
from ...application.use_cases import (
    CreateTextbookUseCase, GenerateBookWorkflowUseCase, ReviewSequenceUseCase
)
from ..database.sqlite_repository import SQLiteTextbookRepository, SQLiteRequirementRepository
from ..agents.pydantic_agents import PydanticTextbookAgentService

logger = logging.getLogger(__name__)

router = APIRouter()

# --- Dependency Injections ---
# These use FastAPI's dependency injection system. The database session is provided
# via request.state.db (set by middleware in main.py) or overridden in tests.

def get_db(request: Request = None) -> Session:
    """Get database session from request state or override."""
    if request is not None and hasattr(request.state, 'db'):
        return request.state.db
    # This will be overridden in tests
    raise NotImplementedError("Database session dependency must be overridden in tests")

def get_textbook_repo(db: Session = Depends(get_db)):
    return SQLiteTextbookRepository(db)

def get_requirement_repo(db: Session = Depends(get_db)):
    return SQLiteRequirementRepository(db)

def get_agent_service():
    return PydanticTextbookAgentService()


# --- API Request / Response Models ---

class CreateTextbookRequest(BaseModel):
    title: str = Field(..., example="Mis Primeros Pasos en Lenguaje")
    subject: str = Field(..., example="Español")
    grade: int = Field(1, ge=1, le=6, example=1)

class ReviewRequest(BaseModel):
    approve: bool = Field(..., example=True)
    feedback: Optional[str] = Field(None, example="Simplificar el vocabulario en la lección 2.")


# --- API Routes ---

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
        # 1. Create textbook project in DRAFT state
        use_case = CreateTextbookUseCase(textbook_repo)
        textbook = use_case.execute(req.title, req.subject, req.grade)
        
        # 2. Trigger pipeline generation in background task
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
    # Retrieve sequence
    secuencia = textbook_repo.get_secuencia(secuencia_id)
    if not secuencia:
        raise HTTPException(status_code=404, detail="Sequence not found")

    # Find the textbook via repository method (no DB model leak)
    textbook_id = textbook_repo.get_textbook_id_by_secuencia_id(secuencia_id)
    if not textbook_id:
        raise HTTPException(status_code=400, detail="Textbook not found for sequence")

    textbook = textbook_repo.get_textbook(textbook_id)
    if not textbook:
        raise HTTPException(status_code=400, detail="Textbook not found")

    # Get trimestre number for the sequence
    trimester_num = textbook_repo.get_trimestre_number_by_secuencia_id(secuencia_id)
    if not trimester_num:
        raise HTTPException(status_code=400, detail="Trimester not found")

    # Delete existing lessons from DB for this sequence
    textbook_repo.delete_lessons_by_secuencia_id(secuencia_id)

    # Trigger background regeneration
    workflow_use_case = GenerateBookWorkflowUseCase(
        textbook_repo=textbook_repo,
        requirement_repo=requirement_repo,
        agent_service=agent_service
    )
    
    # We will pass the review feedback as additional guidelines!
    # To keep the service signatures clean, we can concatenate the feedback to the sequence objectives.
    # E.g., if there's review feedback, append it as a constraint: "REGENERATION GUIDELINE: [feedback]"
    objectives = secuencia.objectives
    if secuencia.review_feedback:
        objectives += f"\n[REGENERATION GUIDELINE: {secuencia.review_feedback}]"

    background_tasks.add_task(
        workflow_use_case.generate_single_sequence,
        textbook,
        secuencia_id,
        trimester_num,
        secuencia.title,
        objectives,
        requirement_repo.list_requirements(textbook.subject, textbook.grade)
    )

    secuencia.status = GenerationStatus.GENERATING
    textbook_repo.update_secuencia(secuencia)
    return secuencia


@router.post("/admin/requirements/populate")
def populate_requirements(
    requirement_repo: SQLiteRequirementRepository = Depends(get_requirement_repo)
):
    # List of initial mock curriculum standards for 1st grade
    requirements = [
        # Español (Language / Communication)
        CurricularRequirement(
            code="REQ-ESP-1.1",
            description="Reconoce y escribe su propio nombre para identificar sus pertenencias y registrar asistencia.",
            subject="Español",
            grade=1
        ),
        CurricularRequirement(
            code="REQ-ESP-1.2",
            description="Identifica la direccionalidad de la lectura (de izquierda a derecha y de arriba a abajo) en textos ilustrados.",
            subject="Español",
            grade=1
        ),
        CurricularRequirement(
            code="REQ-ESP-1.3",
            description="Escribe palabras sencillas utilizando el abecedario e identifica la correspondencia entre sonidos y letras.",
            subject="Español",
            grade=1
        ),
        CurricularRequirement(
            code="REQ-ESP-1.4",
            description="Escucha la lectura de cuentos y expresa opiniones sencillas sobre los personajes y los eventos de la historia.",
            subject="Español",
            grade=1
        ),
        CurricularRequirement(
            code="REQ-ESP-1.5",
            description="Utiliza fórmulas de cortesía sencillas (por favor, gracias, buenos días) de forma oral y escrita en diálogos cotidianos.",
            subject="Español",
            grade=1
        ),
        # Matemáticas
        CurricularRequirement(
            code="REQ-MAT-1.1",
            description="Lee, escribe y ordena números cardinales del 1 al 10 en situaciones reales.",
            subject="Matemáticas",
            grade=1
        ),
        CurricularRequirement(
            code="REQ-MAT-1.2",
            description="Identifica y representa figuras geométricas básicas (círculo, triángulo, cuadrado, rectángulo) en su entorno.",
            subject="Matemáticas",
            grade=1
        ),
        CurricularRequirement(
            code="REQ-MAT-1.3",
            description="Resuelve problemas de suma y resta con números menores a 10 utilizando material concreto (juguetes, semillas, dibujos).",
            subject="Matemáticas",
            grade=1
        ),
        CurricularRequirement(
            code="REQ-MAT-1.4",
            description="Compara longitudes, capacidades y pesos utilizando unidades no convencionales (sus pasos, sus manos, recipientes).",
            subject="Matemáticas",
            grade=1
        ),
        CurricularRequirement(
            code="REQ-MAT-1.5",
            description="Registra información de forma visual utilizando tablas sencillas y pictogramas (caritas, marcas).",
            subject="Matemáticas",
            grade=1
        ),
    ]

    added_count = 0
    for req in requirements:
        try:
            requirement_repo.add_requirement(req)
            added_count += 1
        except Exception:
            # Code is unique, ignore duplicates in seeders
            pass
            
    return {"message": f"Curricular guidelines database seeded successfully.", "inserted": added_count}
