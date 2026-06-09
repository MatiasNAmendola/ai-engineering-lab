import logging
from typing import Optional
from ..domain.models import ContextoLocal
from ..domain.repositories import TextbookRepository

logger = logging.getLogger(__name__)


class ContextualizeTextbookUseCase:
    def __init__(self, textbook_repo: TextbookRepository):
        self.textbook_repo = textbook_repo

    def execute(
        self,
        textbook_id: int,
        comunidad: str,
        problematica_local: str = "",
        lengua_originaria: Optional[str] = None,
        saberes_comunitarios: Optional[list] = None,
        proyectos_sugeridos: Optional[list] = None
    ) -> ContextoLocal:
        textbook = self.textbook_repo.get_textbook(textbook_id)
        if not textbook:
            raise ValueError(f"Textbook {textbook_id} not found")

        contexto = ContextoLocal(
            textbook_id=textbook_id,
            comunidad=comunidad,
            lengua_originaria=lengua_originaria,
            problematica_local=problematica_local,
            saberes_comunitarios=saberes_comunitarios or [],
            proyectos_sugeridos=proyectos_sugeridos or []
        )

        saved = self.textbook_repo.save_contexto_local(contexto)
        logger.info(f"Contexto local saved for textbook {textbook_id}: {comunidad}")
        return saved
