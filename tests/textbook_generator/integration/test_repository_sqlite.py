import os
import sys
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add root directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from textbook_generator.domain.models import Textbook, Trimestre, Secuencia, Lesson, GenerationStatus
from textbook_generator.infrastructure.database.db_models import Base, DBTextbook, DBTrimestre, DBSecuencia, DBLesson
from textbook_generator.infrastructure.database.sqlite_repository import SQLiteTextbookRepository

# Setup in-memory SQLite DB for testing connection-scoped transactions
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(name="db_session")
def fixture_db_session():
    # Force single connection to preserve tables in-memory
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


def test_repository_crud_operations(db_session):
    """Integration Test: Create, Read, Update, and List Textbook structures."""
    repo = SQLiteTextbookRepository(db_session)

    # 1. Create textbook
    book = Textbook(title="Lenguaje 1", subject="Español", grade=1)
    saved_book = repo.create_textbook(book)
    assert saved_book.id is not None
    assert saved_book.status == GenerationStatus.DRAFT

    # 2. Add Trimester
    t = Trimestre(textbook_id=saved_book.id, number=1, title="T1", goals="Metas T1")
    saved_t = repo.create_trimestre(t)
    assert saved_t.id is not None
    assert saved_t.textbook_id == saved_book.id

    # 3. Add Sequence
    s = Secuencia(trimestre_id=saved_t.id, number=1, title="S1", objectives="Obj S1")
    saved_s = repo.create_secuencia(s)
    assert saved_s.id is not None
    assert saved_s.trimestre_id == saved_t.id

    # 4. Add Lesson
    lesson = Lesson(secuencia_id=saved_s.id, number=1, title="L1", section_inicio="I", section_desarrollo="D", section_cierre="C", activities="Act")
    saved_l = repo.create_lesson(lesson)
    assert saved_l.id is not None
    assert saved_l.secuencia_id == saved_s.id

    # 5. Load full Textbook relationship hierarchy
    loaded_book = repo.get_textbook(saved_book.id)
    assert loaded_book is not None
    assert len(loaded_book.trimestres) == 1
    assert loaded_book.trimestres[0].id == saved_t.id
    assert len(loaded_book.trimestres[0].secuencias) == 1
    assert loaded_book.trimestres[0].secuencias[0].id == saved_s.id
    assert len(loaded_book.trimestres[0].secuencias[0].lessons) == 1
    assert loaded_book.trimestres[0].secuencias[0].lessons[0].id == saved_l.id


def test_repository_cascade_deletions(db_session):
    """Integration Test: Ensure deleting a textbook cascades to delete trimestres, secuencias, and lessons."""
    repo = SQLiteTextbookRepository(db_session)

    # Set up hierarchy
    book = repo.create_textbook(Textbook(title="A", subject="Español", grade=1))
    t = repo.create_trimestre(Trimestre(textbook_id=book.id, number=1, title="T", goals="G"))
    s = repo.create_secuencia(Secuencia(trimestre_id=t.id, number=1, title="S", objectives="O"))
    _ = repo.create_lesson(Lesson(secuencia_id=s.id, number=1, title="L", section_inicio="I", section_desarrollo="D", section_cierre="C", activities="Act"))

    # Verify rows exist in DB tables
    assert db_session.query(DBTextbook).count() == 1
    assert db_session.query(DBTrimestre).count() == 1
    assert db_session.query(DBSecuencia).count() == 1
    assert db_session.query(DBLesson).count() == 1

    # Delete textbook using DB session
    db_book = db_session.query(DBTextbook).filter(DBTextbook.id == book.id).first()
    db_session.delete(db_book)
    db_session.commit()

    # Verify all nested entities are deleted by database cascade constraints
    assert db_session.query(DBTextbook).count() == 0
    assert db_session.query(DBTrimestre).count() == 0
    assert db_session.query(DBSecuencia).count() == 0
    assert db_session.query(DBLesson).count() == 0


def test_recalculate_textbook_status_logic(db_session):
    """Integration Test: Verify status recalculations at the parent textbook level."""
    repo = SQLiteTextbookRepository(db_session)

    book = repo.create_textbook(Textbook(title="B", subject="Español", grade=1))
    t = repo.create_trimestre(Trimestre(textbook_id=book.id, number=1, title="T", goals="G"))
    
    # Create 3 sequences in different statuses
    s1 = repo.create_secuencia(Secuencia(trimestre_id=t.id, number=1, title="S1", objectives="O", status=GenerationStatus.APPROVED))
    s2 = repo.create_secuencia(Secuencia(trimestre_id=t.id, number=2, title="S2", objectives="O", status=GenerationStatus.PENDING_REVIEW))
    s3 = repo.create_secuencia(Secuencia(trimestre_id=t.id, number=3, title="S3", objectives="O", status=GenerationStatus.DRAFT))

    # Recalculate status - PENDING_REVIEW should take precedence over APPROVED or DRAFT
    repo.recalculate_textbook_status(book.id)
    assert repo.get_textbook(book.id).status == GenerationStatus.PENDING_REVIEW

    # If s2 is approved, but s3 remains in draft, book status becomes DRAFT
    s2.status = GenerationStatus.APPROVED
    repo.update_secuencia(s2)
    assert repo.get_textbook(book.id).status == GenerationStatus.DRAFT

    # If all sequences are approved, textbook status becomes APPROVED
    s3.status = GenerationStatus.APPROVED
    repo.update_secuencia(s3)
    assert repo.get_textbook(book.id).status == GenerationStatus.APPROVED

    # If any sequence is rejected, textbook status becomes REJECTED
    s1.status = GenerationStatus.REJECTED
    repo.update_secuencia(s1)
    assert repo.get_textbook(book.id).status == GenerationStatus.REJECTED
