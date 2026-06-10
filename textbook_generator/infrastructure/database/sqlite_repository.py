from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from ...domain.models import (
    Textbook, Trimestre, Secuencia, Lesson, CurricularRequirement, GenerationStatus,
    CampoFormativo, EjeArticulador, FaseAprendizaje,
    ContenidoProgramaSintetico, ProcesoDesarrolloAprendizaje, ContextoLocal,
    EjeArticuladorTransversal
)
from ...domain.repositories import TextbookRepository, RequirementRepository, NEMRepository
from .db_models import (
    DBTextbook, DBTrimestre, DBSecuencia, DBLesson, DBCurricularRequirement,
    DBContenidoProgramaSintetico, DBProcesoDesarrolloAprendizaje, DBContextoLocal,
    DBEjeArticuladorTransversal
)


def to_domain_requirement(db_req: DBCurricularRequirement) -> CurricularRequirement:
    return CurricularRequirement(
        id=db_req.id, code=db_req.code, description=db_req.description,
        subject=db_req.subject, grade=db_req.grade
    )


def to_db_requirement(req: CurricularRequirement) -> DBCurricularRequirement:
    return DBCurricularRequirement(
        code=req.code, description=req.description, subject=req.subject, grade=req.grade
    )


def to_domain_lesson(db_l: DBLesson) -> Lesson:
    return Lesson(
        id=db_l.id, secuencia_id=db_l.secuencia_id, number=db_l.number,
        title=db_l.title, section_inicio=db_l.section_inicio,
        section_desarrollo=db_l.section_desarrollo, section_cierre=db_l.section_cierre,
        activities=db_l.activities
    )


def _parse_enum_list(raw, enum_class):
    if not raw:
        return []
    result = []
    for v in raw:
        try:
            result.append(enum_class(v))
        except (ValueError, KeyError):
            pass
    return result


def to_domain_secuencia(db_s: DBSecuencia, include_lessons: bool = True) -> Secuencia:
    lessons = [to_domain_lesson(db_l) for db_l in db_s.lessons] if include_lessons and db_s.lessons else []
    campo_principal = None
    if db_s.campo_formativo_principal:
        try:
            campo_principal = CampoFormativo(db_s.campo_formativo_principal)
        except (ValueError, KeyError):
            campo_principal = None
    return Secuencia(
        id=db_s.id, trimestre_id=db_s.trimestre_id, number=db_s.number,
        title=db_s.title, objectives=db_s.objectives,
        curricular_alignment_score=db_s.curricular_alignment_score,
        age_appropriateness_score=db_s.age_appropriateness_score,
        status=db_s.status, review_feedback=db_s.review_feedback, lessons=lessons,
        campo_formativo_principal=campo_principal,
        campos_formativos_vinculados=_parse_enum_list(db_s.campos_formativos_vinculados, CampoFormativo),
        contenidos_sinteticos_ids=db_s.contenidos_sinteticos_ids or [],
        pda_ids=db_s.pda_ids or [],
        ejes_articuladores=_parse_enum_list(db_s.ejes_articuladores, EjeArticulador),
        proyecto_vinculado=db_s.proyecto_vinculado
    )


def to_domain_trimestre(db_t: DBTrimestre, include_secuencias: bool = True) -> Trimestre:
    secuencias = [to_domain_secuencia(s) for s in db_t.secuencias] if include_secuencias and db_t.secuencias else []
    return Trimestre(
        id=db_t.id, textbook_id=db_t.textbook_id, number=db_t.number,
        title=db_t.title, goals=db_t.goals, secuencias=secuencias
    )


def to_domain_contexto_local(db_c: DBContextoLocal) -> ContextoLocal:
    return ContextoLocal(
        id=db_c.id, textbook_id=db_c.textbook_id, comunidad=db_c.comunidad,
        lengua_originaria=db_c.lengua_originaria, problematica_local=db_c.problematica_local,
        saberes_comunitarios=db_c.saberes_comunitarios or [],
        proyectos_sugeridos=db_c.proyectos_sugeridos or []
    )


def to_domain_textbook(db_b: DBTextbook) -> Textbook:
    trimestres = [to_domain_trimestre(t) for t in db_b.trimestres] if db_b.trimestres else []
    fase = FaseAprendizaje.FASE_2
    if db_b.fase:
        try:
            fase = FaseAprendizaje(db_b.fase)
        except (ValueError, KeyError):
            fase = FaseAprendizaje.FASE_2
    contexto = None
    if hasattr(db_b, 'contexto_local_rel') and db_b.contexto_local_rel:
        contexto = to_domain_contexto_local(db_b.contexto_local_rel)
    return Textbook(
        id=db_b.id, title=db_b.title, subject=db_b.subject, grade=db_b.grade,
        status=db_b.status, created_at=db_b.created_at, trimestres=trimestres,
        fase=fase, contexto_local=contexto
    )


def to_domain_eje_articulador_transversal(db_e: DBEjeArticuladorTransversal) -> EjeArticuladorTransversal:
    return EjeArticuladorTransversal(
        id=db_e.id, secuencia_id=db_e.secuencia_id, eje=db_e.eje,
        grado_profundidad=db_e.grado_profundidad, descripcion_integracion=db_e.descripcion_integracion
    )


def to_domain_contenido(db_c: DBContenidoProgramaSintetico) -> ContenidoProgramaSintetico:
    return ContenidoProgramaSintetico(
        id=db_c.id, campo_formativo=db_c.campo_formativo, fase=db_c.fase,
        codigo=db_c.codigo, descripcion=db_c.descripcion
    )


def to_domain_pda(db_p: DBProcesoDesarrolloAprendizaje) -> ProcesoDesarrolloAprendizaje:
    return ProcesoDesarrolloAprendizaje(
        id=db_p.id, contenido_id=db_p.contenido_id, fase=db_p.fase, descripcion=db_p.descripcion
    )


class SQLiteTextbookRepository(TextbookRepository):
    def __init__(self, session: Session):
        self.session = session

    def create_textbook(self, textbook: Textbook) -> Textbook:
        db_book = DBTextbook(
            title=textbook.title, subject=textbook.subject, grade=textbook.grade,
            status=textbook.status, created_at=textbook.created_at, fase=textbook.fase
        )
        self.session.add(db_book)
        self.session.commit()
        self.session.refresh(db_book)
        return to_domain_textbook(db_book)

    def get_textbook(self, textbook_id: int) -> Optional[Textbook]:
        db_book = (
            self.session.query(DBTextbook).filter(DBTextbook.id == textbook_id)
            .options(
                joinedload(DBTextbook.trimestres).joinedload(DBTrimestre.secuencias).joinedload(DBSecuencia.lessons),
                joinedload(DBTextbook.contexto_local_rel)
            ).first()
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
        db_t = DBTrimestre(textbook_id=trimestre.textbook_id, number=trimestre.number, title=trimestre.title, goals=trimestre.goals)
        self.session.add(db_t)
        self.session.commit()
        self.session.refresh(db_t)
        return to_domain_trimestre(db_t)

    def get_trimestres_by_book(self, textbook_id: int) -> List[Trimestre]:
        db_ts = self.session.query(DBTrimestre).filter(DBTrimestre.textbook_id == textbook_id).options(joinedload(DBTrimestre.secuencias)).all()
        return [to_domain_trimestre(t) for t in db_ts]

    def create_secuencia(self, secuencia: Secuencia) -> Secuencia:
        db_s = DBSecuencia(
            trimestre_id=secuencia.trimestre_id, number=secuencia.number,
            title=secuencia.title, objectives=secuencia.objectives, status=secuencia.status,
            campo_formativo_principal=secuencia.campo_formativo_principal,
            campos_formativos_vinculados=[c.value for c in secuencia.campos_formativos_vinculados] if secuencia.campos_formativos_vinculados else [],
            contenidos_sinteticos_ids=secuencia.contenidos_sinteticos_ids,
            pda_ids=secuencia.pda_ids,
            ejes_articuladores=[e.value for e in secuencia.ejes_articuladores] if secuencia.ejes_articuladores else [],
            proyecto_vinculado=secuencia.proyecto_vinculado
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
        db_s = self.session.query(DBSecuencia).filter(DBSecuencia.id == secuencia_id).options(joinedload(DBSecuencia.lessons)).first()
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
            db_s.campo_formativo_principal = secuencia.campo_formativo_principal
            db_s.campos_formativos_vinculados = [c.value for c in secuencia.campos_formativos_vinculados] if secuencia.campos_formativos_vinculados else []
            db_s.contenidos_sinteticos_ids = secuencia.contenidos_sinteticos_ids
            db_s.pda_ids = secuencia.pda_ids
            db_s.ejes_articuladores = [e.value for e in secuencia.ejes_articuladores] if secuencia.ejes_articuladores else []
            db_s.proyecto_vinculado = secuencia.proyecto_vinculado
            self.session.commit()
            db_t = self.session.query(DBTrimestre).filter(DBTrimestre.id == db_s.trimestre_id).first()
            if db_t:
                self.recalculate_textbook_status(db_t.textbook_id)

    def recalculate_textbook_status(self, textbook_id: int) -> None:
        db_ts = self.session.query(DBTrimestre).filter(DBTrimestre.textbook_id == textbook_id).options(joinedload(DBTrimestre.secuencias)).all()
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
        db_ss = self.session.query(DBSecuencia).filter(DBSecuencia.status == GenerationStatus.PENDING_REVIEW).options(joinedload(DBSecuencia.lessons)).all()
        return [to_domain_secuencia(s) for s in db_ss]

    def create_lesson(self, lesson: Lesson) -> Lesson:
        db_l = DBLesson(
            secuencia_id=lesson.secuencia_id, number=lesson.number, title=lesson.title,
            section_inicio=lesson.section_inicio, section_desarrollo=lesson.section_desarrollo,
            section_cierre=lesson.section_cierre, activities=lesson.activities
        )
        self.session.add(db_l)
        self.session.commit()
        self.session.refresh(db_l)
        return to_domain_lesson(db_l)

    def get_textbook_id_by_secuencia_id(self, secuencia_id: int) -> Optional[int]:
        db_s = self.session.query(DBSecuencia).filter(DBSecuencia.id == secuencia_id).first()
        if not db_s:
            return None
        db_t = self.session.query(DBTrimestre).filter(DBTrimestre.id == db_s.trimestre_id).first()
        if not db_t:
            return None
        return db_t.textbook_id

    def delete_lessons_by_secuencia_id(self, secuencia_id: int) -> None:
        self.session.query(DBLesson).filter(DBLesson.secuencia_id == secuencia_id).delete()
        self.session.commit()

    def get_trimestre_number_by_secuencia_id(self, secuencia_id: int) -> Optional[int]:
        db_s = self.session.query(DBSecuencia).filter(DBSecuencia.id == secuencia_id).first()
        if not db_s:
            return None
        db_t = self.session.query(DBTrimestre).filter(DBTrimestre.id == db_s.trimestre_id).first()
        if not db_t:
            return None
        return db_t.number

    def update_textbook_fase(self, textbook_id: int, fase: FaseAprendizaje) -> None:
        db_book = self.session.query(DBTextbook).filter(DBTextbook.id == textbook_id).first()
        if db_book:
            db_book.fase = fase
            self.session.commit()

    def save_contexto_local(self, contexto: ContextoLocal) -> ContextoLocal:
        db_c = self.session.query(DBContextoLocal).filter(DBContextoLocal.textbook_id == contexto.textbook_id).first()
        if db_c:
            db_c.comunidad = contexto.comunidad
            db_c.lengua_originaria = contexto.lengua_originaria
            db_c.problematica_local = contexto.problematica_local
            db_c.saberes_comunitarios = contexto.saberes_comunitarios
            db_c.proyectos_sugeridos = contexto.proyectos_sugeridos
        else:
            db_c = DBContextoLocal(
                textbook_id=contexto.textbook_id, comunidad=contexto.comunidad,
                lengua_originaria=contexto.lengua_originaria, problematica_local=contexto.problematica_local,
                saberes_comunitarios=contexto.saberes_comunitarios, proyectos_sugeridos=contexto.proyectos_sugeridos
            )
            self.session.add(db_c)
        self.session.commit()
        self.session.refresh(db_c)
        return to_domain_contexto_local(db_c)

    def get_contexto_local(self, textbook_id: int) -> Optional[ContextoLocal]:
        db_c = self.session.query(DBContextoLocal).filter(DBContextoLocal.textbook_id == textbook_id).first()
        if not db_c:
            return None
        return to_domain_contexto_local(db_c)


class SQLiteRequirementRepository(RequirementRepository):
    def __init__(self, session: Session):
        self.session = session

    def list_requirements(self, subject: str, grade: int) -> List[CurricularRequirement]:
        db_reqs = self.session.query(DBCurricularRequirement).filter(
            DBCurricularRequirement.subject.ilike(subject), DBCurricularRequirement.grade == grade
        ).all()
        return [to_domain_requirement(r) for r in db_reqs]

    def add_requirement(self, requirement: CurricularRequirement) -> CurricularRequirement:
        db_req = to_db_requirement(requirement)
        self.session.add(db_req)
        self.session.commit()
        self.session.refresh(db_req)
        return to_domain_requirement(db_req)


class SQLiteNEMRepository(NEMRepository):
    def __init__(self, session: Session):
        self.session = session

    def list_contenidos(self, campo_formativo: Optional[CampoFormativo] = None, fase: Optional[FaseAprendizaje] = None) -> List[ContenidoProgramaSintetico]:
        query = self.session.query(DBContenidoProgramaSintetico)
        if campo_formativo:
            query = query.filter(DBContenidoProgramaSintetico.campo_formativo == campo_formativo)
        if fase:
            query = query.filter(DBContenidoProgramaSintetico.fase == fase)
        return [to_domain_contenido(c) for c in query.all()]

    def add_contenido(self, contenido: ContenidoProgramaSintetico) -> ContenidoProgramaSintetico:
        db_c = DBContenidoProgramaSintetico(
            campo_formativo=contenido.campo_formativo, fase=contenido.fase,
            codigo=contenido.codigo, descripcion=contenido.descripcion
        )
        self.session.add(db_c)
        self.session.commit()
        self.session.refresh(db_c)
        return to_domain_contenido(db_c)

    def get_contenido(self, contenido_id: int) -> Optional[ContenidoProgramaSintetico]:
        db_c = self.session.query(DBContenidoProgramaSintetico).filter(DBContenidoProgramaSintetico.id == contenido_id).first()
        if not db_c:
            return None
        return to_domain_contenido(db_c)

    def list_pda(self, contenido_id: Optional[int] = None, fase: Optional[FaseAprendizaje] = None) -> List[ProcesoDesarrolloAprendizaje]:
        query = self.session.query(DBProcesoDesarrolloAprendizaje)
        if contenido_id:
            query = query.filter(DBProcesoDesarrolloAprendizaje.contenido_id == contenido_id)
        if fase:
            query = query.filter(DBProcesoDesarrolloAprendizaje.fase == fase)
        return [to_domain_pda(p) for p in query.all()]

    def add_pda(self, pda: ProcesoDesarrolloAprendizaje) -> ProcesoDesarrolloAprendizaje:
        db_p = DBProcesoDesarrolloAprendizaje(contenido_id=pda.contenido_id, fase=pda.fase, descripcion=pda.descripcion)
        self.session.add(db_p)
        self.session.commit()
        self.session.refresh(db_p)
        return to_domain_pda(db_p)

    def get_pda(self, pda_id: int) -> Optional[ProcesoDesarrolloAprendizaje]:
        db_p = self.session.query(DBProcesoDesarrolloAprendizaje).filter(DBProcesoDesarrolloAprendizaje.id == pda_id).first()
        if not db_p:
            return None
        return to_domain_pda(db_p)

    def save_eje_articulador(self, data: EjeArticuladorTransversal) -> EjeArticuladorTransversal:
        db_e = DBEjeArticuladorTransversal(
            secuencia_id=data.secuencia_id, eje=data.eje,
            grado_profundidad=data.grado_profundidad,
            descripcion_integracion=data.descripcion_integracion
        )
        self.session.add(db_e)
        self.session.commit()
        self.session.refresh(db_e)
        return to_domain_eje_articulador_transversal(db_e)

    def get_ejes_by_secuencia(self, secuencia_id: int) -> List[EjeArticuladorTransversal]:
        db_es = self.session.query(DBEjeArticuladorTransversal).filter(
            DBEjeArticuladorTransversal.secuencia_id == secuencia_id
        ).all()
        return [to_domain_eje_articulador_transversal(e) for e in db_es]

    def delete_ejes_by_secuencia(self, secuencia_id: int) -> None:
        self.session.query(DBEjeArticuladorTransversal).filter(
            DBEjeArticuladorTransversal.secuencia_id == secuencia_id
        ).delete()
        self.session.commit()
