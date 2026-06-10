import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from textbook_generator.infrastructure.database.db_models import Base
from textbook_generator.main import app
from textbook_generator.infrastructure.http.api import get_db

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


def test_atdd_nem_contextualization_scenario(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    res_seed = client.post("/api/admin/nem/seed-fase2")
    assert res_seed.status_code == 200

    res_pop = client.post("/api/admin/requirements/populate")
    assert res_pop.status_code == 200
    assert res_pop.json()["inserted"] > 0

    res_create = client.post("/api/books", json={
        "title": "Libro Contextualizado",
        "subject": "Español",
        "grade": 1
    })
    assert res_create.status_code == 200
    book_id = res_create.json()["id"]

    res_save_ctx = client.post(f"/api/books/{book_id}/contexto-local", json={
        "comunidad": "Rural",
        "problematica_local": "Escasez de agua",
        "saberes_comunitarios": ["siembra tradicional"],
        "proyectos_sugeridos": ["recoleccion de agua"]
    })
    assert res_save_ctx.status_code == 200
    ctx = res_save_ctx.json()
    assert ctx["comunidad"] == "Rural"
    assert ctx["problematica_local"] == "Escasez de agua"

    res_get_ctx = client.get(f"/api/books/{book_id}/contexto-local")
    assert res_get_ctx.status_code == 200
    assert res_get_ctx.json()["comunidad"] == "Rural"
    assert res_get_ctx.json()["problematica_local"] == "Escasez de agua"

    res_book = client.get(f"/api/books/{book_id}")
    assert res_book.status_code == 200
    first_seq = res_book.json()["trimestres"][0]["secuencias"][0]
    seq_id = first_seq["id"]

    res_map = client.post(f"/api/secuencias/{seq_id}/map-contenidos", json={
        "campo_formativo": "Lenguajes",
        "fase": "Fase 2 - Primaria 1°-2°"
    })
    assert res_map.status_code == 200
    mapped = res_map.json()
    assert mapped["campo_formativo"] == "Lenguajes"
    assert mapped["contenidos_count"] > 0
    assert mapped["pda_count"] > 0

    res_proy = client.post(f"/api/secuencias/{seq_id}/proyecto", json={
        "tipo": "Proyecto Comunitario",
        "nombre": "El agua en mi comunidad",
        "descripcion": "Proyecto comunitario sobre el agua"
    })
    assert res_proy.status_code == 200
    proy = res_proy.json()
    assert "Proyecto Comunitario" in proy["proyecto_vinculado"]

    res_final = client.get(f"/api/books/{book_id}")
    final_seqs = []
    for t in res_final.json()["trimestres"]:
        final_seqs.extend(t["secuencias"])
    updated_seq = next(s for s in final_seqs if s["id"] == seq_id)
    assert updated_seq["campo_formativo_principal"] is not None
    assert len(updated_seq["contenidos_sinteticos_ids"]) > 0
    assert len(updated_seq["pda_ids"]) > 0
    assert updated_seq["proyecto_vinculado"] is not None
