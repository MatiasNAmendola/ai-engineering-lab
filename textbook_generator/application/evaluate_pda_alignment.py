import logging
from typing import List
from ..domain.models import ProcesoDesarrolloAprendizaje
from ..domain.repositories import TextbookRepository, NEMRepository
from ..domain.services import NEMAgentService, PDACoverageResult

logger = logging.getLogger(__name__)


class EvaluatePDAAlignmentUseCase:
    def __init__(self, textbook_repo: TextbookRepository, nem_repo: NEMRepository, nem_agent_service: NEMAgentService):
        self.textbook_repo = textbook_repo
        self.nem_repo = nem_repo
        self.nem_agent_service = nem_agent_service

    def execute(self, secuencia_id: int) -> PDACoverageResult:
        secuencia = self.textbook_repo.get_secuencia_with_lessons(secuencia_id)
        if not secuencia:
            raise ValueError(f"Secuencia {secuencia_id} not found")

        pda_list: List[ProcesoDesarrolloAprendizaje] = []
        for pda_id in secuencia.pda_ids:
            pda = self.nem_repo.get_pda(pda_id)
            if pda:
                pda_list.append(pda)

        ejes = secuencia.ejes_articuladores or []
        result = self.nem_agent_service.evaluate_pda_coverage(secuencia, pda_list, ejes)
        logger.info(f"PDA coverage for secuencia {secuencia_id}: cobertura={result.cobertura_score}, ejes={result.ejes_score}")
        return result
