import logging
from typing import Optional
from ..domain.models import TipoProyecto
from ..domain.repositories import TextbookRepository

logger = logging.getLogger(__name__)


class GenerateProyectoIntegradorUseCase:
    def __init__(self, textbook_repo: TextbookRepository):
        self.textbook_repo = textbook_repo

    def execute(self, secuencia_id: int, tipo: TipoProyecto, nombre: str, descripcion: Optional[str] = None) -> dict:
        secuencia = self.textbook_repo.get_secuencia(secuencia_id)
        if not secuencia:
            raise ValueError(f"Secuencia {secuencia_id} not found")

        proyecto_text = f"{tipo.value}: {nombre}"
        if descripcion:
            proyecto_text += f" - {descripcion}"

        secuencia.proyecto_vinculado = proyecto_text
        self.textbook_repo.update_secuencia(secuencia)
        logger.info(f"Proyecto integrador linked to secuencia {secuencia_id}: {proyecto_text}")
        return {"secuencia_id": secuencia_id, "proyecto_vinculado": proyecto_text, "tipo": tipo.value}
