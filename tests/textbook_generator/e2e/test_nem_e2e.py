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


def test_nem_full_workflow_e2e(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    res_seed = client.post("/api/admin/nem/seed-fase2")
    assert res_seed.status_code == 200
    assert "message" in res_seed.json()

    res_pop = client.post("/api/admin/requirements/populate")
    assert res_pop.status_code == 200
    assert res_pop.json()["inserted"] > 0

    res_create = client.post("/api/books", json={
        "title": "Libro NEM E2E",
        "subject": "Español",
        "grade": 1
    })
    assert res_create.status_code == 200
    book_id = res_create.json()["id"]

    res_save_ctx = client.post(f"/api/books/{book_id}/contexto-local", json={
        "comunidad": "Rural",
        "problematica_local": "Escasez de agua",
        "saberes_comunitarios": ["cosecha de lluvia"],
        "proyectos_sugeridos": ["huerto comunitario"]
    })
    assert res_save_ctx.status_code == 200
    ctx = res_save_ctx.json()
    assert ctx["comunidad"] == "Rural"
    assert ctx["problematica_local"] == "Escasez de agua"
    assert ctx["textbook_id"] == book_id

    res_get_ctx = client.get(f"/api/books/{book_id}/contexto-local")
    assert res_get_ctx.status_code == 200
    ctx_get = res_get_ctx.json()
    assert ctx_get["comunidad"] == "Rural"
    assert ctx_get["problematica_local"] == "Escasez de agua"

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
    assert mapped["secuencia_id"] == seq_id
    assert mapped["campo_formativo"] == "Lenguajes"
    assert mapped["contenidos_count"] > 0
    assert mapped["pda_count"] > 0

    res_proy = client.post(f"/api/secuencias/{seq_id}/proyecto", json={
        "tipo": "Proyecto Comunitario",
        "nombre": "El agua en mi comunidad",
        "descripcion": "Proyecto sobre el cuidado del agua"
    })
    assert res_proy.status_code == 200
    proy = res_proy.json()
    assert proy["secuencia_id"] == seq_id
    assert "Proyecto Comunitario" in proy["proyecto_vinculado"]
    assert "El agua en mi comunidad" in proy["proyecto_vinculado"]

    res_pda = client.post(f"/api/secuencias/{seq_id}/evaluate-pda")
    assert res_pda.status_code == 200
    pda = res_pda.json()
    assert "cobertura_score" in pda
    assert "ejes_score" in pda
    assert isinstance(pda["cobertura_score"], float)

    res_final = client.get(f"/api/books/{book_id}")
    assert res_final.status_code == 200
    final_book = res_final.json()
    final_seqs = []
    for t in final_book["trimestres"]:
        final_seqs.extend(t["secuencias"])
    updated_seq = next(s for s in final_seqs if s["id"] == seq_id)
    assert updated_seq["campo_formativo_principal"] is not None
    assert len(updated_seq["contenidos_sinteticos_ids"]) > 0
    assert len(updated_seq["pda_ids"]) > 0
    assert updated_seq["proyecto_vinculado"] is not None
