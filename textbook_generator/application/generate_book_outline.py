import logging
from ..domain.models import Trimestre, Secuencia, GenerationStatus
from ..domain.repositories import TextbookRepository, RequirementRepository
from ..domain.services import TextbookAgentService

logger = logging.getLogger(__name__)

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
        
        # 1. Update textbook status to GENERATING
        self.textbook_repo.update_textbook_status(textbook_id, GenerationStatus.GENERATING)
        
        textbook = self.textbook_repo.get_textbook(textbook_id)
        if not textbook:
            logger.error(f"Textbook {textbook_id} not found")
            return

        # 2. Retrieve curricular requirements
        requirements = self.requirement_repo.list_requirements(textbook.subject, textbook.grade)
        logger.info(f"Retrieved {len(requirements)} requirements for outline RAG.")

        # 3. Call Agent to generate outline
        try:
            outline = self.agent_service.generate_outline(textbook.subject, textbook.grade, requirements)
            logger.info(f"Outline generated successfully: '{outline.title}'")
        except Exception:
            logger.exception("Failed to generate textbook outline")
            self.textbook_repo.update_textbook_status(textbook_id, GenerationStatus.REJECTED)
            return

        # 4. Save outline structure to DB
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
                secuencia = Secuencia(
                    trimestre_id=saved_t.id,
                    number=s_outline.number,
                    title=s_outline.title,
                    objectives=s_outline.objectives,
                    status=GenerationStatus.DRAFT
                )
                saved_s = self.textbook_repo.create_secuencia(secuencia)
                created_seqs.append((saved_t.number, saved_s.id, saved_s.title, saved_s.objectives))

        # 5. Return the list of created sequence structures to generate content for
        return created_seqs
