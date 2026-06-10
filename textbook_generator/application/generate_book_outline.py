import logging
from ..domain.models import (
    Trimestre, Secuencia, GenerationStatus,
    CampoFormativo, EjeArticulador, TipoProyecto
)
from ..domain.repositories import TextbookRepository, RequirementRepository
from ..domain.services import TextbookAgentService

logger = logging.getLogger(__name__)


def _assign_nem_attributes(s_number: int, t_number: int) -> dict:
    all_campos = list(CampoFormativo)
    all_ejes = list(EjeArticulador)
    all_proyectos = list(TipoProyecto)

    campo_principal = all_campos[(s_number - 1) % len(all_campos)]

    vinculados_indices = [(s_number - 1 + 1) % len(all_campos), (s_number - 1 + 2) % len(all_campos)]
    campos_vinculados = [all_campos[i] for i in vinculados_indices if all_campos[i] != campo_principal]

    ejes_start = (s_number * 2) % len(all_ejes)
    ejes_articuladores = [all_ejes[(ejes_start + i) % len(all_ejes)] for i in range(3)]

    proyecto_vinculado = None
    if s_number == 6:
        proyecto_tipo = all_proyectos[(t_number - 1) % len(all_proyectos)]
        proyecto_vinculado = f"Proyecto de Cierre: {proyecto_tipo.value}"

    return {
        "campo_formativo_principal": campo_principal,
        "campos_formativos_vinculados": campos_vinculados,
        "ejes_articuladores": ejes_articuladores,
        "proyecto_vinculado": proyecto_vinculado
    }


class GenerateBookOutlineUseCase:
    def __init__(
        self,
        textbook_repo: TextbookRepository,
        requirement_repo: RequirementRepository,
        agent_service: TextbookAgentService
    ):
        self.textbook_repo = textbook_repo
        self.requirement_repo = requirement_repo
        self.agent_service = agent_service

    def execute(self, textbook_id: int) -> None:
        logger.info(f"Starting outline generation for Textbook ID: {textbook_id}")
        
        self.textbook_repo.update_textbook_status(textbook_id, GenerationStatus.GENERATING)
        
        textbook = self.textbook_repo.get_textbook(textbook_id)
        if not textbook:
            logger.error(f"Textbook {textbook_id} not found")
            return

        requirements = self.requirement_repo.list_requirements(textbook.subject, textbook.grade)
        logger.info(f"Retrieved {len(requirements)} requirements for outline RAG.")

        try:
            outline = self.agent_service.generate_outline(textbook.subject, textbook.grade, requirements)
            logger.info(f"Outline generated successfully: '{outline.title}'")
        except Exception:
            logger.exception("Failed to generate textbook outline")
            self.textbook_repo.update_textbook_status(textbook_id, GenerationStatus.REJECTED)
            return

        created_seqs = []
        for t_outline in outline.trimestres:
            trimestre = Trimestre(
                textbook_id=textbook_id,
                number=t_outline.number,
                title=t_outline.title,
                goals=t_outline.goals
            )
            saved_t = self.textbook_repo.create_trimestre(trimestre)
            
            for s_outline in t_outline.secuencias:
                nem_attrs = _assign_nem_attributes(s_outline.number, saved_t.number)

                secuencia = Secuencia(
                    trimestre_id=saved_t.id,
                    number=s_outline.number,
                    title=s_outline.title,
                    objectives=s_outline.objectives,
                    status=GenerationStatus.DRAFT,
                    campo_formativo_principal=nem_attrs["campo_formativo_principal"],
                    campos_formativos_vinculados=nem_attrs["campos_formativos_vinculados"],
                    ejes_articuladores=nem_attrs["ejes_articuladores"],
                    proyecto_vinculado=nem_attrs["proyecto_vinculado"]
                )
                saved_s = self.textbook_repo.create_secuencia(secuencia)
                created_seqs.append((saved_t.number, saved_s.id, saved_s.title, saved_s.objectives))

        return created_seqs
