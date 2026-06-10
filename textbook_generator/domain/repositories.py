from abc import ABC, abstractmethod
from typing import List, Optional
from .models import (
    Textbook, Trimestre, Secuencia, Lesson, CurricularRequirement, GenerationStatus,
    CampoFormativo, FaseAprendizaje, ContenidoProgramaSintetico,
    ProcesoDesarrolloAprendizaje, ContextoLocal, EjeArticuladorTransversal
)


class TextbookRepository(ABC):
    @abstractmethod
    def create_textbook(self, textbook: Textbook) -> Textbook:
        pass

    @abstractmethod
    def get_textbook(self, textbook_id: int) -> Optional[Textbook]:
        pass

    @abstractmethod
    def update_textbook_status(self, textbook_id: int, status: GenerationStatus) -> None:
        pass

    @abstractmethod
    def list_textbooks(self) -> List[Textbook]:
        pass

    @abstractmethod
    def create_trimestre(self, trimestre: Trimestre) -> Trimestre:
        pass

    @abstractmethod
    def get_trimestres_by_book(self, textbook_id: int) -> List[Trimestre]:
        pass

    @abstractmethod
    def create_secuencia(self, secuencia: Secuencia) -> Secuencia:
        pass

    @abstractmethod
    def get_secuencia(self, secuencia_id: int) -> Optional[Secuencia]:
        pass

    @abstractmethod
    def get_secuencia_with_lessons(self, secuencia_id: int) -> Optional[Secuencia]:
        pass

    @abstractmethod
    def update_secuencia(self, secuencia: Secuencia) -> None:
        pass

    @abstractmethod
    def get_pending_reviews(self) -> List[Secuencia]:
        pass

    @abstractmethod
    def create_lesson(self, lesson: Lesson) -> Lesson:
        pass

    @abstractmethod
    def get_textbook_id_by_secuencia_id(self, secuencia_id: int) -> Optional[int]:
        pass

    @abstractmethod
    def delete_lessons_by_secuencia_id(self, secuencia_id: int) -> None:
        pass

    @abstractmethod
    def get_trimestre_number_by_secuencia_id(self, secuencia_id: int) -> Optional[int]:
        pass

    @abstractmethod
    def update_textbook_fase(self, textbook_id: int, fase: FaseAprendizaje) -> None:
        pass

    @abstractmethod
    def save_contexto_local(self, contexto: ContextoLocal) -> ContextoLocal:
        pass

    @abstractmethod
    def get_contexto_local(self, textbook_id: int) -> Optional[ContextoLocal]:
        pass


class RequirementRepository(ABC):
    @abstractmethod
    def list_requirements(self, subject: str, grade: int) -> List[CurricularRequirement]:
        pass

    @abstractmethod
    def add_requirement(self, requirement: CurricularRequirement) -> CurricularRequirement:
        pass


class NEMRepository(ABC):
    @abstractmethod
    def list_contenidos(self, campo_formativo: Optional[CampoFormativo] = None, fase: Optional[FaseAprendizaje] = None) -> List[ContenidoProgramaSintetico]:
        pass

    @abstractmethod
    def add_contenido(self, contenido: ContenidoProgramaSintetico) -> ContenidoProgramaSintetico:
        pass

    @abstractmethod
    def get_contenido(self, contenido_id: int) -> Optional[ContenidoProgramaSintetico]:
        pass

    @abstractmethod
    def list_pda(self, contenido_id: Optional[int] = None, fase: Optional[FaseAprendizaje] = None) -> List[ProcesoDesarrolloAprendizaje]:
        pass

    @abstractmethod
    def add_pda(self, pda: ProcesoDesarrolloAprendizaje) -> ProcesoDesarrolloAprendizaje:
        pass

    @abstractmethod
    def get_pda(self, pda_id: int) -> Optional[ProcesoDesarrolloAprendizaje]:
        pass

    @abstractmethod
    def save_eje_articulador(self, data: EjeArticuladorTransversal) -> EjeArticuladorTransversal:
        pass

    @abstractmethod
    def get_ejes_by_secuencia(self, secuencia_id: int) -> List[EjeArticuladorTransversal]:
        pass

    @abstractmethod
    def delete_ejes_by_secuencia(self, secuencia_id: int) -> None:
        pass
