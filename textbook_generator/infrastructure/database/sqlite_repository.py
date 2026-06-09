from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from ...domain.models import (
    Textbook, Trimestre, Secuencia, Lesson, CurricularRequirement, GenerationStatus
)
from ...domain.repositories import TextbookRepository, RequirementRepository
from .db_models import (
    DBTextbook, DBTrimestre, DBSecuencia, DBLesson, DBCurricularRequirement
)

# --- Mapper Functions ---

def to_domain_requirement(db_req: DBCurricularRequirement) -> CurricularRequirement:
    return CurricularRequirement(
        id=db_req.id,
        code=db_req.code,
        description=db_req.description,
        subject=db_req.subject,
        grade=db_req.grade
    )

def to_db_requirement(req: CurricularRequirement) -> DBCurricularRequirement:
    return DBCurricularRequirement(
        code=req.code,
        description=req.description,
        subject=req.subject,
        grade=req.grade
    )

def to_domain_lesson(db_l: DBLesson) -> Lesson:
    return Lesson(
        id=db_l.id,
        secuencia_id=db_l.secuencia_id,
        number=db_l.number,
        title=db_l.title,
        section_inicio=db_l.section_inicio,
        section_desarrollo=db_l.section_desarrollo,
        section_cierre=db_l.section_cierre,
        activities=db_l.activities
    )

def to_domain_secuencia(db_s: DBSecuencia, include_lessons: bool = True) -> Secuencia:
    lessons = [to_domain_lesson(l) for l in db_s.lessons] if include_lessons and db_s.lessons else []
    return Secuencia(
        id=db_s.id,
        trimestre_id=db_s.trimestre_id,
        number=db_s.number,
        title=db_s.title,
        objectives=db_s.objectives,
        curricular_alignment_score=db_s.curricular_alignment_score,
        age_appropriateness_score=db_s.age_appropriateness_score,
        status=db_s.status,
        review_feedback=db_s.review_feedback,
        lessons=lessons
    )

def to_domain_trimestre(db_t: DBTrimestre, include_secuencias: bool = True) -> Trimestre:
    secuencias = [to_domain_secuencia(s) for s in db_t.secuencias] if include_secuencias and db_t.secuencias else []
    return Trimestre(
        id=db_t.id,
        textbook_id=db_t.textbook_id,
        number=db_t.number,
        title=db_t.title,
        goals=db_t.goals,
        secuencias=secuencias
    )

def to_domain_textbook(db_b: DBTextbook) -> Textbook:
    trimestres = [to_domain_trimestre(t) for t in db_b.trimestres] if db_b.trimestres else []
    return Textbook(
        id=db_b.id,
        title=db_b.title,
        subject=db_b.subject,
        grade=db_b.grade,
        status=db_b.status,
        created_at=db_b.created_at,
        trimestres=trimestres
    )


# --- Repositories Implementations ---

class SQLiteTextbookRepository(TextbookRepository):
    def __init__(self, session: Session):
        self.session = session

    def create_textbook(self, textbook: Textbook) -> Textbook:
        db_book = DBTextbook(
            title=textbook.title,
            subject=textbook.subject,
            grade=textbook.grade,
            status=textbook.status,
            created_at=textbook.created_at
        )
        self.session.add(db_book)
        self.session.commit()
        self.session.refresh(db_book)
        return to_domain_textbook(db_book)

    def get_textbook(self, textbook_id: int) -> Optional[Textbook]:
        db_book = (
            self.session.query(DBTextbook)
            .filter(DBTextbook.id == textbook_id)
            .options(
                joinedload(DBTextbook.trimestres)
                .joinedload(DBTrimestre.secuencias)
                .joinedload(DBSecuencia.lessons)
            )
            .first()
        )
        if not db_book:
            return None
        return to_domain_textbook(db_book)

    def update_textbook_status(self, textbook_id: int, status: GenerationStatus) -> None:
        db_book = self.session.query(DBTextbook).filter(DBTextbook.id == textbook_id).first()
        if db_book:
            db_book.status = status
            self.session.commit()

    def list_textbooks(self) -> List[Textbook]:
        db_books = self.session.query(DBTextbook).order_by(DBTextbook.created_at.desc()).all()
        return [to_domain_textbook(b) for b in db_books]

    def create_trimestre(self, trimestre: Trimestre) -> Trimestre:
        db_t = DBTrimestre(
            textbook_id=trimestre.textbook_id,
            number=trimestre.number,
            title=trimestre.title,
            goals=trimestre.goals
        )
        self.session.add(db_t)
        self.session.commit()
        self.session.refresh(db_t)
        return to_domain_trimestre(db_t)

    def get_trimestres_by_book(self, textbook_id: int) -> List[Trimestre]:
        db_ts = (
            self.session.query(DBTrimestre)
            .filter(DBTrimestre.textbook_id == textbook_id)
            .options(joinedload(DBTrimestre.secuencias))
            .all()
        )
        return [to_domain_trimestre(t) for t in db_ts]

    def create_secuencia(self, secuencia: Secuencia) -> Secuencia:
        db_s = DBSecuencia(
            trimestre_id=secuencia.trimestre_id,
            number=secuencia.number,
            title=secuencia.title,
            objectives=secuencia.objectives,
            status=secuencia.status
        )
        self.session.add(db_s)
        self.session.commit()
        self.session.refresh(db_s)
        return to_domain_secuencia(db_s, include_lessons=False)

    def get_secuencia(self, secuencia_id: int) -> Optional[Secuencia]:
        db_s = self.session.query(DBSecuencia).filter(DBSecuencia.id == secuencia_id).first()
        if not db_s:
            return None
        return to_domain_secuencia(db_s, include_lessons=False)

    def get_secuencia_with_lessons(self, secuencia_id: int) -> Optional[Secuencia]:
        db_s = (
            self.session.query(DBSecuencia)
            .filter(DBSecuencia.id == secuencia_id)
            .options(joinedload(DBSecuencia.lessons))
            .first()
        )
        if not db_s:
            return None
        return to_domain_secuencia(db_s, include_lessons=True)

    def update_secuencia(self, secuencia: Secuencia) -> None:
        db_s = self.session.query(DBSecuencia).filter(DBSecuencia.id == secuencia.id).first()
        if db_s:
            db_s.title = secuencia.title
            db_s.objectives = secuencia.objectives
            db_s.curricular_alignment_score = secuencia.curricular_alignment_score
            db_s.age_appropriateness_score = secuencia.age_appropriateness_score
            db_s.status = secuencia.status
            db_s.review_feedback = secuencia.review_feedback
            self.session.commit()

            # Trigger global book status recalculation
            # Walk up: Secuencia -> Trimestre -> Textbook
            db_t = self.session.query(DBTrimestre).filter(DBTrimestre.id == db_s.trimestre_id).first()
            if db_t:
                self.recalculate_textbook_status(db_t.textbook_id)

    def recalculate_textbook_status(self, textbook_id: int) -> None:
        db_ts = (
            self.session.query(DBTrimestre)
            .filter(DBTrimestre.textbook_id == textbook_id)
            .options(joinedload(DBTrimestre.secuencias))
            .all()
        )
        
        all_statuses = []
        for t in db_ts:
            for s in t.secuencias:
                all_statuses.append(s.status)

        db_book = self.session.query(DBTextbook).filter(DBTextbook.id == textbook_id).first()
        if not db_book:
            return

        if any(st == GenerationStatus.REJECTED for st in all_statuses):
            db_book.status = GenerationStatus.REJECTED
        elif any(st == GenerationStatus.PENDING_REVIEW for st in all_statuses):
            db_book.status = GenerationStatus.PENDING_REVIEW
        elif any(st == GenerationStatus.GENERATING for st in all_statuses):
            db_book.status = GenerationStatus.GENERATING
        elif all(st == GenerationStatus.APPROVED for st in all_statuses) and all_statuses:
            db_book.status = GenerationStatus.APPROVED
        else:
            db_book.status = GenerationStatus.DRAFT
        
        self.session.commit()

    def get_pending_reviews(self) -> List[Secuencia]:
        db_ss = (
            self.session.query(DBSecuencia)
            .filter(DBSecuencia.status == GenerationStatus.PENDING_REVIEW)
            .options(joinedload(DBSecuencia.lessons))
            .all()
        )
        return [to_domain_secuencia(s) for s in db_ss]

    def create_lesson(self, lesson: Lesson) -> Lesson:
        db_l = DBLesson(
            secuencia_id=lesson.secuencia_id,
            number=lesson.number,
            title=lesson.title,
            section_inicio=lesson.section_inicio,
            section_desarrollo=lesson.section_desarrollo,
            section_cierre=lesson.section_cierre,
            activities=lesson.activities
        )
        self.session.add(db_l)
        self.session.commit()
        self.session.refresh(db_l)
        return to_domain_lesson(db_l)

    def get_textbook_id_by_secuencia_id(self, secuencia_id: int) -> Optional[int]:
        from .db_models import DBSecuencia, DBTrimestre
        db_s = self.session.query(DBSecuencia).filter(DBSecuencia.id == secuencia_id).first()
        if not db_s:
            return None
        db_t = self.session.query(DBTrimestre).filter(DBTrimestre.id == db_s.trimestre_id).first()
        if not db_t:
            return None
        return db_t.textbook_id

    def delete_lessons_by_secuencia_id(self, secuencia_id: int) -> None:
        from .db_models import DBLesson
        self.session.query(DBLesson).filter(DBLesson.secuencia_id == secuencia_id).delete()
        self.session.commit()

    def get_trimestre_number_by_secuencia_id(self, secuencia_id: int) -> Optional[int]:
        from .db_models import DBSecuencia, DBTrimestre
        db_s = self.session.query(DBSecuencia).filter(DBSecuencia.id == secuencia_id).first()
        if not db_s:
            return None
        db_t = self.session.query(DBTrimestre).filter(DBTrimestre.id == db_s.trimestre_id).first()
        if not db_t:
            return None
        return db_t.number


class SQLiteRequirementRepository(RequirementRepository):
    def __init__(self, session: Session):
        self.session = session

    def list_requirements(self, subject: str, grade: int) -> List[CurricularRequirement]:
        db_reqs = (
            self.session.query(DBCurricularRequirement)
            .filter(
                DBCurricularRequirement.subject.ilike(subject),
                DBCurricularRequirement.grade == grade
            )
            .all()
        )
        return [to_domain_requirement(r) for r in db_reqs]

    def add_requirement(self, requirement: CurricularRequirement) -> CurricularRequirement:
        db_req = to_db_requirement(requirement)
        self.session.add(db_req)
        self.session.commit()
        self.session.refresh(db_req)
        return to_domain_requirement(db_req)
