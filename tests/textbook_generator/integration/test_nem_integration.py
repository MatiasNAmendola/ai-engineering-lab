import os
import sys
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from textbook_generator.domain.models import (
    Textbook, Trimestre, Secuencia, Lesson,
    CampoFormativo, EjeArticulador, FaseAprendizaje,
    ContenidoProgramaSintetico, ProcesoDesarrolloAprendizaje, ContextoLocal
)
from textbook_generator.infrastructure.database.db_models import Base
from textbook_generator.infrastructure.database.sqlite_repository import (
    SQLiteTextbookRepository, SQLiteNEMRepository
)

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(name="db_session")
def fixture_db_session():
    connection = engine.connect()
    transaction = connection.begin()
    Base.metadata.create_all(bind=connection)
    session = TestingSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def test_nem_contenido_crud(db_session):
    nem_repo = SQLiteNEMRepository(db_session)
    contenido = ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.LENGUAJES, fase=FaseAprendizaje.FASE_2,
        codigo="CF-LNG-F2-C01", descripcion="Expresa ideas mediante el lenguaje oral."
    )
    saved = nem_repo.add_contenido(contenido)
    assert saved.id is not None
    assert saved.codigo == "CF-LNG-F2-C01"

    loaded = nem_repo.get_contenido(saved.id)
    assert loaded is not None
    assert loaded.campo_formativo == CampoFormativo.LENGUAJES

    all_contenidos = nem_repo.list_contenidos(campo_formativo=CampoFormativo.LENGUAJES)
    assert len(all_contenidos) == 1


def test_nem_pda_crud(db_session):
    nem_repo = SQLiteNEMRepository(db_session)
    contenido = nem_repo.add_contenido(ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.LENGUAJES, fase=FaseAprendizaje.FASE_2,
        codigo="CF-LNG-F2-C01", descripcion="Expresa ideas."
    ))
    pda = ProcesoDesarrolloAprendizaje(contenido_id=contenido.id, fase=FaseAprendizaje.FASE_2, descripcion="Narra experiencias personales.")
    saved_pda = nem_repo.add_pda(pda)
    assert saved_pda.id is not None

    pda_list = nem_repo.list_pda(contenido_id=contenido.id)
    assert len(pda_list) == 1


def test_contexto_local_crud(db_session):
    repo = SQLiteTextbookRepository(db_session)
    book = repo.create_textbook(Textbook(title="Test", subject="Español", grade=1))

    contexto = ContextoLocal(
        textbook_id=book.id, comunidad="Rural", lengua_originaria="Náhuatl",
        problematica_local="Escasez de agua", saberes_comunitarios=["Agricultura tradicional"],
        proyectos_sugeridos=["Huerto escolar"]
    )
    saved = repo.save_contexto_local(contexto)
    assert saved.id is not None
    assert saved.comunidad == "Rural"

    loaded = repo.get_contexto_local(book.id)
    assert loaded is not None
    assert loaded.lengua_originaria == "Náhuatl"


def test_secuencia_nem_fields_persistence(db_session):
    repo = SQLiteTextbookRepository(db_session)
    book = repo.create_textbook(Textbook(title="NEM Book", subject="Español", grade=1))
    t = repo.create_trimestre(Trimestre(textbook_id=book.id, number=1, title="T1", goals="G"))

    s = Secuencia(
        trimestre_id=t.id, number=1, title="El agua en mi comunidad",
        objectives="Analizar el uso del agua",
        campo_formativo_principal=CampoFormativo.ETICA_NATURALEZA_SOCIEDADES,
        campos_formativos_vinculados=[CampoFormativo.SABERES_PCIENTIFICO, CampoFormativo.LENGUAJES],
        contenidos_sinteticos_ids=[1, 2, 3], pda_ids=[10, 20],
        ejes_articuladores=[EjeArticulador.PENSAMIENTO_CRITICO, EjeArticulador.VIDA_SALUDABLE],
        proyecto_vinculado="Proyecto de Aula: Cuidemos el agua"
    )
    saved_s = repo.create_secuencia(s)
    assert saved_s.campo_formativo_principal == CampoFormativo.ETICA_NATURALEZA_SOCIEDADES
    assert len(saved_s.campos_formativos_vinculados) == 2
    assert len(saved_s.ejes_articuladores) == 2
    assert saved_s.proyecto_vinculado == "Proyecto de Aula: Cuidemos el agua"

    loaded = repo.get_secuencia(saved_s.id)
    assert loaded.campo_formativo_principal == CampoFormativo.ETICA_NATURALEZA_SOCIEDADES
    assert len(loaded.contenidos_sinteticos_ids) == 3


def test_textbook_fase_persistence(db_session):
    repo = SQLiteTextbookRepository(db_session)
    book = repo.create_textbook(Textbook(title="Fase 3 Book", subject="Español", grade=3, fase=FaseAprendizaje.FASE_3))
    assert book.fase == FaseAprendizaje.FASE_3

    repo.update_textbook_fase(book.id, FaseAprendizaje.FASE_4)
    reloaded = repo.get_textbook(book.id)
    assert reloaded.fase == FaseAprendizaje.FASE_4


def test_seed_nem_fase2(db_session):
    from textbook_generator.infrastructure.database.seed_nem_fase2 import seed_nem_fase2
    nem_repo = SQLiteNEMRepository(db_session)
    result = seed_nem_fase2(nem_repo)

    assert result["contenidos_inserted"] > 0
    assert result["pda_inserted"] > 0

    all_contenidos = nem_repo.list_contenidos(fase=FaseAprendizaje.FASE_2)
    assert len(all_contenidos) >= 20

    lenguajes = nem_repo.list_contenidos(campo_formativo=CampoFormativo.LENGUAJES)
    assert len(lenguajes) >= 5


def test_export_conaliteg_format(db_session):
    from textbook_generator.application.export_conaliteg_format import ExportConalitegFormatUseCase
    repo = SQLiteTextbookRepository(db_session)
    book = repo.create_textbook(Textbook(title="Libro Export", subject="Español", grade=1, fase=FaseAprendizaje.FASE_2))
    
    # Save a ContextoLocal
    repo.save_contexto_local(ContextoLocal(
        textbook_id=book.id, comunidad="Indígena", lengua_originaria="Mayo",
        problematica_local="Falta de luz", saberes_comunitarios=["Medicina tradicional"],
        proyectos_sugeridos=["Huerto escolar"]
    ))
    
    # Create Trimestre & Secuencia
    t = repo.create_trimestre(Trimestre(textbook_id=book.id, number=1, title="T1", goals="M1"))
    s = Secuencia(
        trimestre_id=t.id, number=1, title="Secuencia 1", objectives="O1",
        campo_formativo_principal=CampoFormativo.LENGUAJES,
        campos_formativos_vinculados=[CampoFormativo.HUMANO_COMUNITARIO],
        contenidos_sinteticos_ids=[1], pda_ids=[1],
        ejes_articuladores=[EjeArticulador.VIDA_SALUDABLE],
        proyecto_vinculado="Proyecto Aula 1"
    )
    saved_s = repo.create_secuencia(s)
    
    # Create a Lesson
    repo.create_lesson(Lesson(
        secuencia_id=saved_s.id, number=1, title="Lección 1",
        section_inicio="I", section_desarrollo="D", section_cierre="C", activities="A"
    ))
    
    # Run the export use case
    nem_repo = SQLiteNEMRepository(db_session)
    use_case = ExportConalitegFormatUseCase(repo, nem_repo)
    result = use_case.execute(book.id)
    
    assert result["metadata_sep"]["libro_id"] == book.id
    assert result["metadata_sep"]["titulo"] == "Libro Export"
    assert result["metadata_sep"]["fase"] == FaseAprendizaje.FASE_2.value
    assert result["metadata_sep"]["contexto_local"]["lengua_originaria"] == "Mayo"
    
    trimestres = result["estructura_curricular"]["trimestres"]
    assert len(trimestres) == 1
    assert trimestres[0]["numero"] == 1
    
    secuencias = trimestres[0]["secuencias"]
    assert len(secuencias) == 1
    assert secuencias[0]["titulo"] == "Secuencia 1"
    assert secuencias[0]["campo_formativo_principal"] == CampoFormativo.LENGUAJES.value
    
    lecciones = secuencias[0]["lecciones"]
    assert len(lecciones) == 1
    assert lecciones[0]["titulo"] == "Lección 1"

