import logging
from ..domain.models import GenerationStatus, Textbook
from ..domain.repositories import TextbookRepository, RequirementRepository
from ..domain.services import TextbookAgentService
from .generate_book_outline import GenerateBookOutlineUseCase
from .generate_sequence_content import GenerateSequenceContentUseCase

logger = logging.getLogger(__name__)

class GenerateBookWorkflowUseCase:
    def __init__(
        self,
        textbook_repo: TextbookRepository,
        requirement_repo: RequirementRepository,
        agent_service: TextbookAgentService
    ):
        self.textbook_repo = textbook_repo
        self.requirement_repo = requirement_repo
        self.agent_service = agent_service
        
        # Instantiate sub-use cases
        self.outline_use_case = GenerateBookOutlineUseCase(
            textbook_repo=self.textbook_repo,
            requirement_repo=self.requirement_repo,
            agent_service=self.agent_service
        )
        self.content_use_case = GenerateSequenceContentUseCase(
            textbook_repo=self.textbook_repo,
            agent_service=self.agent_service
        )

    def execute(self, textbook_id: int) -> None:
        logger.info(f"Running textbook generation workflow for ID: {textbook_id}")
        
        # 1. Generate Outline
        created_seqs = self.outline_use_case.execute(textbook_id)
        if not created_seqs:
            logger.error("Outline generation yielded no sequences or failed.")
            return

        # Fetch textbook domain model (now updated with skeleton)
        textbook = self.textbook_repo.get_textbook(textbook_id)
        if not textbook:
            return

        # 2. Retrieve requirements for sequence content RAG
        requirements = self.requirement_repo.list_requirements(textbook.subject, textbook.grade)

        # 3. Generate content for each sequence in the outline
        for trimester_num, secuencia_id, title, objectives in created_seqs:
            self.content_use_case.execute(
                textbook=textbook,
                secuencia_id=secuencia_id,
                trimester_num=trimester_num,
                title=title,
                objectives=objectives,
                requirements=requirements
            )

        # 4. Finalize textbook global status
        self.textbook_repo.recalculate_textbook_status(textbook_id)
        logger.info(f"Textbook generation workflow completed for ID: {textbook_id}")

    def generate_single_sequence(
        self,
        textbook: Textbook,
        secuencia_id: int,
        trimester_num: int,
        title: str,
        objectives: str,
        requirements: list
    ) -> None:
        """Generate content for a single sequence (used for regeneration)."""
        logger.info(f"Regenerating single sequence ID: {secuencia_id}")
        self.content_use_case.execute(
            textbook=textbook,
            secuencia_id=secuencia_id,
            trimester_num=trimester_num,
            title=title,
            objectives=objectives,
            requirements=requirements
        )
        # Recalculate textbook status after regeneration
        self.textbook_repo.recalculate_textbook_status(textbook.id)
