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

# Setup in-memory SQLite DB
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


def test_api_textbook_creation_and_reviews_e2e(db_session):
    """E2E Test: Create a book, run background generation, fetch review queue, approve sequence, and verify final status."""
    # Override get_db dependency
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    # 1. Seed Curricular Guidelines
    res_pop = client.post("/api/admin/requirements/populate")
    assert res_pop.status_code == 200
    assert res_pop.json()["inserted"] > 0

    # 2. Create textbook project (FastAPI background tasks are executed synchronously by TestClient!)
    res_create = client.post("/api/books", json={
        "title": "Aventura Española E2E",
        "subject": "Español",
        "grade": 1
    })
    assert res_create.status_code == 200
    book = res_create.json()
    book_id = book["id"]
    assert book["title"] == "Aventura Española E2E"
    assert book["status"] == "DRAFT"

    # 3. Retrieve book details (should be fully generated now since TestClient runs bg tasks synchronously)
    res_get = client.get(f"/api/books/{book_id}")
    assert res_get.status_code == 200
    book_details = res_get.json()
    
    # Verify the structure has 3 trimestres, each with 6 sequences
    assert len(book_details["trimestres"]) == 3
    assert len(book_details["trimestres"][0]["secuencias"]) == 6
    assert len(book_details["trimestres"][0]["secuencias"][0]["lessons"]) == 3
    
    # The book status should be PENDING_REVIEW because sequence 2 and 5 failed the 0.85 guardrail in mock mode
    assert book_details["status"] == "PENDING_REVIEW"

    # 4. Check review queue
    res_reviews = client.get("/api/reviews")
    assert res_reviews.status_code == 200
    reviews = res_reviews.json()
    # Sequences 2 and 5 from Trimester 1, 2, and 3 should be in queue -> 6 sequences total
    assert len(reviews) == 6

    # 5. Authorize/Approve a sequence from the review queue
    target_seq = reviews[0]
    seq_id = target_seq["id"]
    assert target_seq["status"] == "PENDING_REVIEW"

    res_approve = client.post(f"/api/reviews/{seq_id}", json={
        "approve": True,
        "feedback": "Acceptable for school use"
    })
    assert res_approve.status_code == 200
    approved_seq = res_approve.json()
    assert approved_seq["status"] == "APPROVED"
    assert approved_seq["review_feedback"] == "Approved by educator."

    # 6. Verify that the sequence status updated in the book hierarchy
    res_get_final = client.get(f"/api/books/{book_id}")
    secuencias = []
    for t in res_get_final.json()["trimestres"]:
        secuencias.extend(t["secuencias"])
    
    loaded_seq = next(s for s in secuencias if s["id"] == seq_id)
    assert loaded_seq["status"] == "APPROVED"
