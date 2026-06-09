import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add root directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from textbook_generator.infrastructure.database.db_models import Base
from textbook_generator.main import app
from textbook_generator.infrastructure.http.api import get_db

# Setup test DB
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


def test_atdd_educator_textbook_creation_and_quality_correction_loop(db_session):
    """
    ATDD Scenario: Educator starts a textbook generation project, rejects a sequence 
    violating quality standards, and triggers a feedback-guided regeneration.
    """
    # Override get_db dependency
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    # -------------------------------------------------------------
    # GIVEN: the curricular guidelines database is seeded
    # -------------------------------------------------------------
    res_seed = client.post("/api/admin/requirements/populate")
    assert res_seed.status_code == 200
    assert res_seed.json()["inserted"] > 0

    # -------------------------------------------------------------
    # WHEN: an educator requests the creation of a Spanish book
    # -------------------------------------------------------------
    res_create = client.post("/api/books", json={
        "title": "Aventura de Sílabas",
        "subject": "Español",
        "grade": 1
    })
    assert res_create.status_code == 200
    book_id = res_create.json()["id"]

    # -------------------------------------------------------------
    # THEN: the system generates a 3-trimester, 18-sequence skeleton
    # -------------------------------------------------------------
    res_get = client.get(f"/api/books/{book_id}")
    book_details = res_get.json()
    assert len(book_details["trimestres"]) == 3
    assert len(book_details["trimestres"][0]["secuencias"]) == 6
    assert book_details["status"] == "PENDING_REVIEW"

    # -------------------------------------------------------------
    # AND: sequence 2 is routed to the review queue due to low scores (0.80)
    # -------------------------------------------------------------
    res_reviews = client.get("/api/reviews")
    reviews = res_reviews.json()
    assert len(reviews) > 0
    
    # Locate sequence 2 from the review queue
    seq_2 = next(s for s in reviews if s["number"] == 2 and s["status"] == "PENDING_REVIEW")
    assert seq_2["age_appropriateness_score"] < 0.85

    # -------------------------------------------------------------
    # WHEN: the educator rejects sequence 2 with feedback
    # -------------------------------------------------------------
    feedback_text = "El vocabulario es muy avanzado. Simplificar palabras a sílabas simples."
    res_reject = client.post(f"/api/reviews/{seq_2['id']}", json={
        "approve": False,
        "feedback": feedback_text
    })
    assert res_reject.status_code == 200
    rejected_seq = res_reject.json()
    
    # -------------------------------------------------------------
    # THEN: sequence 2 moves to REJECTED status and stores the feedback
    # -------------------------------------------------------------
    assert rejected_seq["status"] == "REJECTED"
    assert rejected_seq["review_feedback"] == feedback_text

    # -------------------------------------------------------------
    # WHEN: the educator triggers a regeneration for sequence 2
    # -------------------------------------------------------------
    res_regen = client.post(f"/api/secuencias/{seq_2['id']}/regenerate")
    assert res_regen.status_code == 200
    regenerating_seq = res_regen.json()

    # -------------------------------------------------------------
    # THEN: sequence 2 status is set back to GENERATING
    # -------------------------------------------------------------
    assert regenerating_seq["status"] == "GENERATING"

    # Verify database state
    res_get_final = client.get(f"/api/books/{book_id}")
    secuencias = []
    for t in res_get_final.json()["trimestres"]:
        secuencias.extend(t["secuencias"])
    
    reloaded_seq_2 = next(s for s in secuencias if s["id"] == seq_2["id"])
    # Mock agent always routes sequence 2 to HITL (scores 0.82/0.84 < 0.85)
    # even after regeneration with feedback, so status remains PENDING_REVIEW
    assert reloaded_seq_2["status"] == "PENDING_REVIEW"
    assert reloaded_seq_2["review_feedback"] is not None
