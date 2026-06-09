import logging
from typing import List
from ..domain.models import CampoFormativo, FaseAprendizaje, ProcesoDesarrolloAprendizaje
from ..domain.repositories import NEMRepository, TextbookRepository

logger = logging.getLogger(__name__)


class MapContenidosPDAUseCase:
    def __init__(self, nem_repo: NEMRepository, textbook_repo: TextbookRepository):
        self.nem_repo = nem_repo
        self.textbook_repo = textbook_repo

    def execute(self, secuencia_id: int, campo_formativo: CampoFormativo, fase: FaseAprendizaje = FaseAprendizaje.FASE_2) -> dict:
        secuencia = self.textbook_repo.get_secuencia(secuencia_id)
        if not secuencia:
            raise ValueError(f"Secuencia {secuencia_id} not found")

        contenidos = self.nem_repo.list_contenidos(campo_formativo=campo_formativo, fase=fase)
        contenido_ids = [c.id for c in contenidos if c.id is not None]

        pda_list: List[ProcesoDesarrolloAprendizaje] = []
        for c_id in contenido_ids:
            pdas = self.nem_repo.list_pda(contenido_id=c_id, fase=fase)
            pda_list.extend(pdas)

        pda_ids = [p.id for p in pda_list if p.id is not None]

        secuencia.campo_formativo_principal = campo_formativo
        secuencia.contenidos_sinteticos_ids = contenido_ids
        secuencia.pda_ids = pda_ids
        self.textbook_repo.update_secuencia(secuencia)

        logger.info(f"Mapped {len(contenido_ids)} contenidos and {len(pda_ids)} PDA to secuencia {secuencia_id}")
        return {"secuencia_id": secuencia_id, "campo_formativo": campo_formativo.value, "contenidos_count": len(contenido_ids), "pda_count": len(pda_ids)}
