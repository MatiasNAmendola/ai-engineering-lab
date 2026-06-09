import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from textbook_generator.domain.models import (
    Textbook, Secuencia, GenerationStatus,
    CampoFormativo, EjeArticulador, FaseAprendizaje,
    ContenidoProgramaSintetico, ProcesoDesarrolloAprendizaje, ContextoLocal
)
from textbook_generator.infrastructure.database.db_models import (
    DBTextbook, DBTrimestre, DBSecuencia, DBLesson, DBCurricularRequirement,
    DBContenidoProgramaSintetico, DBProcesoDesarrolloAprendizaje, DBContextoLocal
)
from textbook_generator.infrastructure.database.sqlite_repository import (
    to_domain_requirement, to_domain_lesson, to_domain_secuencia, 
    to_domain_textbook, to_domain_contenido, to_domain_pda, to_domain_contexto_local
)

def test_domain_models_defaults():
    textbook = Textbook(title="Matemáticas 1", subject="Matemáticas", grade=1)
    
    assert textbook.id is None
    assert textbook.status == GenerationStatus.DRAFT
    assert isinstance(textbook.created_at, datetime)
    assert len(textbook.trimestres) == 0
    assert textbook.fase == FaseAprendizaje.FASE_2

    secuencia = Secuencia(trimestre_id=1, number=2, title="T", objectives="O")
    assert secuencia.status == GenerationStatus.DRAFT
    assert secuencia.curricular_alignment_score is None
    assert secuencia.review_feedback is None
    assert len(secuencia.lessons) == 0
    assert secuencia.campo_formativo_principal is None
    assert secuencia.campos_formativos_vinculados == []
    assert secuencia.ejes_articuladores == []


def test_nem_enums():
    assert CampoFormativo.LENGUAJES.value == "Lenguajes"
    assert CampoFormativo.SABERES_PCIENTIFICO.value == "Saberes y Pensamiento Científico"
    assert len(CampoFormativo) == 4

    assert EjeArticulador.PENSAMIENTO_CRITICO.value == "Pensamiento crítico"
    assert len(EjeArticulador) == 7

    assert FaseAprendizaje.FASE_2.value == "Fase 2 - Primaria 1°-2°"
    assert len(FaseAprendizaje) == 6


def test_nem_domain_models():
    contenido = ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.LENGUAJES,
        fase=FaseAprendizaje.FASE_2,
        codigo="CF-LNG-F2-C01",
        descripcion="Expresa ideas mediante el lenguaje oral."
    )
    assert contenido.campo_formativo == CampoFormativo.LENGUAJES
    assert contenido.fase == FaseAprendizaje.FASE_2

    pda = ProcesoDesarrolloAprendizaje(
        contenido_id=1,
        fase=FaseAprendizaje.FASE_2,
        descripcion="Narra experiencias personales."
    )
    assert pda.contenido_id == 1

    contexto = ContextoLocal(
        textbook_id=1,
        comunidad="Rural",
        problematica_local="Escasez de agua",
        saberes_comunitarios=["Agricultura tradicional"]
    )
    assert contexto.comunidad == "Rural"
    assert len(contexto.saberes_comunitarios) == 1


def test_secuencia_with_nem_fields():
    secuencia = Secuencia(
        trimestre_id=1,
        number=1,
        title="El agua en mi comunidad",
        objectives="Analizar el uso del agua",
        campo_formativo_principal=CampoFormativo.ETICA_NATURALEZA_SOCIEDADES,
        campos_formativos_vinculados=[CampoFormativo.SABERES_PCIENTIFICO],
        ejes_articuladores=[EjeArticulador.PENSAMIENTO_CRITICO, EjeArticulador.VIDA_SALUDABLE],
        proyecto_vinculado="Proyecto de Aula: Cuidemos el agua"
    )
    assert secuencia.campo_formativo_principal == CampoFormativo.ETICA_NATURALEZA_SOCIEDADES
    assert len(secuencia.campos_formativos_vinculados) == 1
    assert len(secuencia.ejes_articuladores) == 2
    assert secuencia.proyecto_vinculado is not None


def test_mapper_curricular_requirement():
    db_req = DBCurricularRequirement(
        id=42,
        code="REQ-1.1",
        description="Identifica palabras",
        subject="Español",
        grade=1
    )
    
    domain_req = to_domain_requirement(db_req)
    assert domain_req.id == 42
    assert domain_req.code == "REQ-1.1"
    assert domain_req.description == "Identifica palabras"
    assert domain_req.subject == "Español"
    assert domain_req.grade == 1


def test_mapper_lesson():
    db_lesson = DBLesson(
        id=7,
        secuencia_id=10,
        number=1,
        title="Mi Primera Lección",
        section_inicio="Actividad de apertura",
        section_desarrollo="Actividad principal",
        section_cierre="Actividad de cierre",
        activities="Actividades adicionales"
    )
    
    domain_lesson = to_domain_lesson(db_lesson)
    assert domain_lesson.id == 7
    assert domain_lesson.secuencia_id == 10
    assert domain_lesson.number == 1
    assert domain_lesson.title == "Mi Primera Lección"


def test_mapper_secuencia():
    db_s = DBSecuencia(
        id=5,
        trimestre_id=3,
        number=2,
        title="Secuencia 2",
        objectives="Objetivos 2",
        curricular_alignment_score=0.92,
        age_appropriateness_score=0.88,
        status=GenerationStatus.PENDING_REVIEW,
        review_feedback="Ajustar vocabulario",
        campo_formativo_principal=CampoFormativo.LENGUAJES,
        ejes_articuladores=["Pensamiento crítico", "Inclusión"]
    )
    db_s.lessons = [
        DBLesson(id=1, secuencia_id=5, number=1, title="L1", section_inicio="I", section_desarrollo="D", section_cierre="C", activities="A")
    ]

    s_no_l = to_domain_secuencia(db_s, include_lessons=False)
    assert s_no_l.id == 5
    assert s_no_l.status == GenerationStatus.PENDING_REVIEW
    assert len(s_no_l.lessons) == 0
    assert s_no_l.campo_formativo_principal == CampoFormativo.LENGUAJES
    assert len(s_no_l.ejes_articuladores) == 2

    s_with_l = to_domain_secuencia(db_s, include_lessons=True)
    assert s_with_l.id == 5
    assert len(s_with_l.lessons) == 1


def test_mapper_contenido():
    db_c = DBContenidoProgramaSintetico(
        id=1,
        campo_formativo=CampoFormativo.LENGUAJES,
        fase=FaseAprendizaje.FASE_2,
        codigo="CF-LNG-F2-C01",
        descripcion="Expresa ideas mediante el lenguaje oral."
    )
    domain_c = to_domain_contenido(db_c)
    assert domain_c.id == 1
    assert domain_c.codigo == "CF-LNG-F2-C01"
    assert domain_c.campo_formativo == CampoFormativo.LENGUAJES


def test_mapper_pda():
    db_p = DBProcesoDesarrolloAprendizaje(
        id=1,
        contenido_id=1,
        fase=FaseAprendizaje.FASE_2,
        descripcion="Narra experiencias personales."
    )
    domain_p = to_domain_pda(db_p)
    assert domain_p.id == 1
    assert domain_p.contenido_id == 1
    assert domain_p.fase == FaseAprendizaje.FASE_2


def test_mapper_contexto_local():
    db_c = DBContextoLocal(
        id=1,
        textbook_id=1,
        comunidad="Rural",
        lengua_originaria="Náhuatl",
        problematica_local="Escasez de agua",
        saberes_comunitarios=["Agricultura"],
        proyectos_sugeridos=["Huerto escolar"]
    )
    domain_c = to_domain_contexto_local(db_c)
    assert domain_c.comunidad == "Rural"
    assert domain_c.lengua_originaria == "Náhuatl"
    assert len(domain_c.saberes_comunitarios) == 1


def test_mapper_textbook():
    db_book = DBTextbook(
        id=1,
        title="Libro Completo",
        subject="Español",
        grade=1,
        status=GenerationStatus.APPROVED,
        created_at=datetime(2026, 6, 9, 12, 0, 0),
        fase=FaseAprendizaje.FASE_2
    )
    db_t = DBTrimestre(id=1, textbook_id=1, number=1, title="T1", goals="Metas")
    db_s = DBSecuencia(id=1, trimestre_id=1, number=1, title="S1", objectives="Obj", status=GenerationStatus.APPROVED)
    
    db_t.secuencias = [db_s]
    db_book.trimestres = [db_t]

    domain_book = to_domain_textbook(db_book)
    assert domain_book.id == 1
    assert domain_book.title == "Libro Completo"
    assert domain_book.status == GenerationStatus.APPROVED
    assert domain_book.fase == FaseAprendizaje.FASE_2
    assert len(domain_book.trimestres) == 1
