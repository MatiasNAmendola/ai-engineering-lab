from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import declarative_base, relationship
from ...domain.models import GenerationStatus

Base = declarative_base()

class DBCurricularRequirement(Base):
    __tablename__ = "curricular_requirements"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    grade = Column(Integer, nullable=False)


class DBTextbook(Base):
    __tablename__ = "textbooks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    grade = Column(Integer, nullable=False)
    status = Column(SQLEnum(GenerationStatus), default=GenerationStatus.DRAFT, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    trimestres = relationship("DBTrimestre", back_populates="textbook", cascade="all, delete-orphan")


class DBTrimestre(Base):
    __tablename__ = "trimestres"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    textbook_id = Column(Integer, ForeignKey("textbooks.id"), nullable=False)
    number = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    goals = Column(String, nullable=False)
    
    textbook = relationship("DBTextbook", back_populates="trimestres")
    secuencias = relationship("DBSecuencia", back_populates="trimestre", cascade="all, delete-orphan")


class DBSecuencia(Base):
    __tablename__ = "secuencias"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    trimestre_id = Column(Integer, ForeignKey("trimestres.id"), nullable=False)
    number = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    objectives = Column(String, nullable=False)
    curricular_alignment_score = Column(Float, nullable=True)
    age_appropriateness_score = Column(Float, nullable=True)
    status = Column(SQLEnum(GenerationStatus), default=GenerationStatus.DRAFT, nullable=False)
    review_feedback = Column(String, nullable=True)
    
    trimestre = relationship("DBTrimestre", back_populates="secuencias")
    lessons = relationship("DBLesson", back_populates="secuencia", cascade="all, delete-orphan")


class DBLesson(Base):
    __tablename__ = "lessons"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    secuencia_id = Column(Integer, ForeignKey("secuencias.id"), nullable=False)
    number = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    section_inicio = Column(String, nullable=False)
    section_desarrollo = Column(String, nullable=False)
    section_cierre = Column(String, nullable=False)
    activities = Column(String, nullable=False)
    
    secuencia = relationship("DBSecuencia", back_populates="lessons")
