from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum as SQLEnum, JSON, Text
from sqlalchemy.orm import declarative_base, relationship
from ...domain.models import GenerationStatus, CampoFormativo, FaseAprendizaje

Base = declarative_base()


class DBCurricularRequirement(Base):
    __tablename__ = "curricular_requirements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    grade = Column(Integer, nullable=False)


class DBContenidoProgramaSintetico(Base):
    __tablename__ = "contenidos_programa_sintetico"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campo_formativo = Column(SQLEnum(CampoFormativo), nullable=False)
    fase = Column(SQLEnum(FaseAprendizaje), nullable=False)
    codigo = Column(String, unique=True, nullable=False)
    descripcion = Column(Text, nullable=False)

    pda_list = relationship("DBProcesoDesarrolloAprendizaje", back_populates="contenido", cascade="all, delete-orphan")


class DBProcesoDesarrolloAprendizaje(Base):
    __tablename__ = "procesos_desarrollo_aprendizaje"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contenido_id = Column(Integer, ForeignKey("contenidos_programa_sintetico.id"), nullable=False)
    fase = Column(SQLEnum(FaseAprendizaje), nullable=False)
    descripcion = Column(Text, nullable=False)

    contenido = relationship("DBContenidoProgramaSintetico", back_populates="pda_list")


class DBContextoLocal(Base):
    __tablename__ = "contextos_locales"

    id = Column(Integer, primary_key=True, autoincrement=True)
    textbook_id = Column(Integer, ForeignKey("textbooks.id"), nullable=False, unique=True)
    comunidad = Column(String, nullable=False)
    lengua_originaria = Column(String, nullable=True)
    problematica_local = Column(String, nullable=False, default="")
    saberes_comunitarios = Column(JSON, nullable=False, default=list)
    proyectos_sugeridos = Column(JSON, nullable=False, default=list)

    textbook = relationship("DBTextbook", back_populates="contexto_local_rel")


class DBTextbook(Base):
    __tablename__ = "textbooks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    grade = Column(Integer, nullable=False)
    status = Column(SQLEnum(GenerationStatus), default=GenerationStatus.DRAFT, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    fase = Column(SQLEnum(FaseAprendizaje), default=FaseAprendizaje.FASE_2, nullable=False)

    trimestres = relationship("DBTrimestre", back_populates="textbook", cascade="all, delete-orphan")
    contexto_local_rel = relationship("DBContextoLocal", back_populates="textbook", cascade="all, delete-orphan", uselist=False)


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
    campo_formativo_principal = Column(SQLEnum(CampoFormativo), nullable=True)
    campos_formativos_vinculados = Column(JSON, nullable=True, default=list)
    contenidos_sinteticos_ids = Column(JSON, nullable=True, default=list)
    pda_ids = Column(JSON, nullable=True, default=list)
    ejes_articuladores = Column(JSON, nullable=True, default=list)
    proyecto_vinculado = Column(String, nullable=True)

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
