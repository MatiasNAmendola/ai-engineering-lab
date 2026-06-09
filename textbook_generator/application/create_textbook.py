import logging
from ..domain.models import Textbook, GenerationStatus
from ..domain.repositories import TextbookRepository

logger = logging.getLogger(__name__)

class CreateTextbookUseCase:
    def __init__(self, textbook_repo: TextbookRepository):
        self.textbook_repo = textbook_repo

    def execute(self, title: str, subject: str, grade: int) -> Textbook:
        logger.info(f"Initializing textbook project: '{title}' ({subject}, Grade {grade})")
        textbook = Textbook(
            title=title,
            subject=subject,
            grade=grade,
            status=GenerationStatus.DRAFT
        )
        return self.textbook_repo.create_textbook(textbook)
