import logging
from typing import Optional
from ..domain.models import Secuencia, GenerationStatus
from ..domain.repositories import TextbookRepository

logger = logging.getLogger(__name__)

class ReviewSequenceUseCase:
    def __init__(self, textbook_repo: TextbookRepository):
        self.textbook_repo = textbook_repo

    def execute(self, secuencia_id: int, approve: bool, feedback: Optional[str] = None) -> Secuencia:
        secuencia = self.textbook_repo.get_secuencia_with_lessons(secuencia_id)
        if not secuencia:
            raise ValueError(f"Sequence {secuencia_id} not found")

        if approve:
            logger.info(f"Educator APPROVED sequence ID {secuencia_id}")
            secuencia.status = GenerationStatus.APPROVED
            secuencia.review_feedback = "Approved by educator."
        else:
            logger.info(f"Educator REJECTED sequence ID {secuencia_id}. Feedback: {feedback}")
            secuencia.status = GenerationStatus.REJECTED
            secuencia.review_feedback = feedback

        self.textbook_repo.update_secuencia(secuencia)
        return secuencia
