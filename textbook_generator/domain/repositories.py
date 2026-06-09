from abc import ABC, abstractmethod
from typing import List, Optional
from .models import (
    Textbook, Trimestre, Secuencia, Lesson, CurricularRequirement, GenerationStatus
)

class TextbookRepository(ABC):
    @abstractmethod
    def create_textbook(self, textbook: Textbook) -> Textbook:
        """Create a new textbook record."""
        pass

    @abstractmethod
    def get_textbook(self, textbook_id: int) -> Optional[Textbook]:
        """Retrieve a textbook by ID (including nested trimestres, secuencias, and lessons)."""
        pass

    @abstractmethod
    def update_textbook_status(self, textbook_id: int, status: GenerationStatus) -> None:
        """Update global status of a textbook."""
        pass

    @abstractmethod
    def list_textbooks(self) -> List[Textbook]:
        """List all textbooks."""
        pass

    @abstractmethod
    def create_trimestre(self, trimestre: Trimestre) -> Trimestre:
        """Create a new trimestre under a textbook."""
        pass

    @abstractmethod
    def get_trimestres_by_book(self, textbook_id: int) -> List[Trimestre]:
        """Retrieve trimestres for a textbook."""
        pass

    @abstractmethod
    def create_secuencia(self, secuencia: Secuencia) -> Secuencia:
        """Create a new sequence under a trimestre."""
        pass

    @abstractmethod
    def get_secuencia(self, secuencia_id: int) -> Optional[Secuencia]:
        """Get sequence by ID without lessons."""
        pass

    @abstractmethod
    def get_secuencia_with_lessons(self, secuencia_id: int) -> Optional[Secuencia]:
        """Get sequence by ID with lessons."""
        pass

    @abstractmethod
    def update_secuencia(self, secuencia: Secuencia) -> None:
        """Update a sequence's details, scores, or status."""
        pass

    @abstractmethod
    def get_pending_reviews(self) -> List[Secuencia]:
        """List all sequences currently in PENDING_REVIEW status."""
        pass

    @abstractmethod
    def create_lesson(self, lesson: Lesson) -> Lesson:
        """Create a new lesson under a sequence."""
        pass

    @abstractmethod
    def get_textbook_id_by_secuencia_id(self, secuencia_id: int) -> Optional[int]:
        """Get the textbook ID that owns a given sequence."""
        pass

    @abstractmethod
    def delete_lessons_by_secuencia_id(self, secuencia_id: int) -> None:
        """Delete all lessons for a given sequence."""
        pass

    @abstractmethod
    def get_trimestre_number_by_secuencia_id(self, secuencia_id: int) -> Optional[int]:
        """Get the trimester number for a given sequence."""
        pass


class RequirementRepository(ABC):
    @abstractmethod
    def list_requirements(self, subject: str, grade: int) -> List[CurricularRequirement]:
        """Retrieve curricular standards for a specific subject and grade."""
        pass

    @abstractmethod
    def add_requirement(self, requirement: CurricularRequirement) -> CurricularRequirement:
        """Add a curricular standard to the catalog."""
        pass
