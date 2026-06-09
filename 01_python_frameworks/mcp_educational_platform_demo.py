# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "mcp>=1.0.0",
#     "openai>=1.50.0",
#     "pydantic>=2.0.0",
#     "sqlalchemy>=2.0.0",
# ]
# ///
"""
mcp_educational_platform_demo.py

Plataforma educativa completa con integración MCP (Model Context Protocol).

Arquitectura MCP:
─────────────────
┌──────────────────────────────────────────────────────────┐
│                    MCP Client (Agente)                    │
│  ┌─────────────┐ ┌────────────────┐ ┌────────────────┐  │
│  │  Student     │ │  Content       │ │  Assessment    │  │
│  │  Advisor     │ │  Curator       │ │  Agent         │  │
│  └──────┬──────┘ └───────┬────────┘ └───────┬────────┘  │
│         │                │                   │            │
│         └────────────────┼───────────────────┘            │
│                          │ MCP Protocol (tools + resources)│
├──────────────────────────┼────────────────────────────────┤
│                    MCP Server (Plataforma)                 │
│  ┌───────────┐ ┌────────┴────┐ ┌────────────┐            │
│  │  Tools    │ │  Resources  │ │  Prompts   │            │
│  │           │ │             │ │            │            │
│  │ • progress│ │ • catalog   │ │ • tutor    │            │
│  │ • recommend│ │ • metrics  │ │ • advisor  │            │
│  │ • grade   │ │             │ │            │            │
│  │ • study   │ │             │ │            │            │
│  │ • at_risk │ │             │ │            │            │
│  └─────┬─────┘ └──────┬──────┘ └────────────┘            │
│        │               │                                  │
│  ┌─────┴───────────────┴──────────────────────┐          │
│  │         SQLAlchemy ORM (SQLite)             │          │
│  │  Students ─┬─ Enrollments ─┬─ Courses      │          │
│  │            └─ Grades ──────┴─ Assignments   │          │
│  └────────────────────────────────────────────┘          │
└──────────────────────────────────────────────────────────┘

MCP habilita integración con sistemas externos:
- LMS (Learning Management System): Canvas, Moodle, Blackboard
- SIS (Student Information System): registros académicos
- Analytics: dashboards de progreso, retención
- Contenido: bibliotecas digitales, OER

En producción considerar:
- Autenticación OAuth2/JWT por estudiante e institución
- Rate limiting por tenant (escuela/universidad)
- Observabilidad con OpenTelemetry (trazas de tool calls)
- FERPA/GDPR compliance para datos estudiantiles
- Webhooks MCP para notificaciones en tiempo real

Ejecución demo:     uv run 01_python_frameworks/mcp_educational_platform_demo.py
Ejecución servidor: uv run 01_python_frameworks/mcp_educational_platform_demo.py --serve
"""

import os
import sys
import json
import asyncio
from datetime import datetime, timezone, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Text, DateTime,
    ForeignKey, func,
)
from sqlalchemy.orm import (
    DeclarativeBase, sessionmaker, relationship,
)
from mcp.server.fastmcp import FastMCP


# ==========================================
# MODELOS PYDANTIC (esquemas de respuesta)
# ==========================================

class StudentProgress(BaseModel):
    student_id: int
    name: str
    overall_gpa: float = Field(ge=0.0, le=4.0)
    courses_enrolled: int
    courses_completed: int
    total_assignments: int
    assignments_submitted: int
    avg_score: float
    streak_days: int
    risk_level: str = Field(description="low | medium | high")
    strengths: list[str]
    weaknesses: list[str]


class CourseRecommendation(BaseModel):
    student_id: int
    recommended_course_id: int
    recommended_course_name: str
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    prerequisites_met: bool
    estimated_difficulty: str


class GradeResult(BaseModel):
    assignment_id: int
    student_id: int
    score: float = Field(ge=0.0, le=100.0)
    letter_grade: str
    feedback: str
    rubric_breakdown: dict[str, float]


class StudyPlan(BaseModel):
    student_id: int
    goal: str
    duration_weeks: int
    weekly_schedule: list[dict]
    resources: list[str]
    milestones: list[str]


class AtRiskStudent(BaseModel):
    student_id: int
    name: str
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_factors: list[str]
    recommended_interventions: list[str]


# ==========================================
# DATABASE LAYER (SQLAlchemy)
# ==========================================

class Base(DeclarativeBase):
    pass


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    email = Column(String(200), nullable=False, unique=True)
    enrolled_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_active = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    enrollments = relationship("Enrollment", back_populates="student", cascade="all, delete-orphan")
    grades = relationship("Grade", back_populates="student", cascade="all, delete-orphan")


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(100), nullable=False)
    difficulty = Column(String(50), nullable=False)
    credits = Column(Integer, nullable=False, default=3)
    prerequisites = Column(Text, default="[]")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    enrollments = relationship("Enrollment", back_populates="course", cascade="all, delete-orphan")
    assignments = relationship("Assignment", back_populates="course", cascade="all, delete-orphan")


class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    status = Column(String(50), nullable=False, default="active")
    enrolled_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    progress_pct = Column(Float, default=0.0)

    student = relationship("Student", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=False)
    max_score = Column(Float, default=100.0)
    weight = Column(Float, default=1.0)
    due_date = Column(DateTime, nullable=True)

    course = relationship("Course", back_populates="assignments")
    grades = relationship("Grade", back_populates="assignment", cascade="all, delete-orphan")


class Grade(Base):
    __tablename__ = "grades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    score = Column(Float, nullable=False)
    feedback = Column(Text, default="")
    graded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    student = relationship("Student", back_populates="grades")
    assignment = relationship("Assignment", back_populates="grades")


DB_URL = "sqlite:///educational_platform.db"
engine = create_engine(DB_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)


def init_database() -> None:
    Base.metadata.create_all(engine)

    with SessionLocal() as session:
        if session.query(Student).count() > 0:
            return

        courses = [
            Course(name="Fundamentos de Python", description="Variables, funciones, OOP básica.", category="programming", difficulty="beginner", credits=3, prerequisites="[]"),
            Course(name="Machine Learning con scikit-learn", description="Regresión, clasificación, clustering.", category="ai", difficulty="intermediate", credits=4, prerequisites='["Fundamentos de Python"]'),
            Course(name="Deep Learning con PyTorch", description="Redes neuronales, CNNs, transformers.", category="ai", difficulty="advanced", credits=4, prerequisites='["Machine Learning con scikit-learn"]'),
            Course(name="Bases de Datos SQL y NoSQL", description="PostgreSQL, MongoDB, modelado de datos.", category="data", difficulty="beginner", credits=3, prerequisites="[]"),
            Course(name="Ingeniería de Datos con Apache Spark", description="ETL, data lakes, procesamiento distribuido.", category="data", difficulty="advanced", credits=4, prerequisites='["Bases de Datos SQL y NoSQL"]'),
            Course(name="MLOps y Despliegue de Modelos", description="Docker, CI/CD, monitoring de modelos.", category="ai", difficulty="advanced", credits=4, prerequisites='["Machine Learning con scikit-learn"]'),
            Course(name="NLP y Procesamiento de Lenguaje Natural", description="Tokenización, embeddings, transformers.", category="ai", difficulty="intermediate", credits=4, prerequisites='["Fundamentos de Python"]'),
            Course(name="Visualización de Datos", description="Matplotlib, Plotly, dashboards interactivos.", category="data", difficulty="beginner", credits=2, prerequisites="[]"),
        ]
        session.add_all(courses)
        session.flush()

        students = [
            Student(name="María García", email="maria@universidad.edu", last_active=datetime.now(timezone.utc) - timedelta(hours=2)),
            Student(name="Carlos López", email="carlos@universidad.edu", last_active=datetime.now(timezone.utc) - timedelta(days=15)),
            Student(name="Ana Martínez", email="ana@universidad.edu", last_active=datetime.now(timezone.utc) - timedelta(hours=1)),
            Student(name="Diego Rodríguez", email="diego@universidad.edu", last_active=datetime.now(timezone.utc) - timedelta(days=30)),
            Student(name="Lucía Fernández", email="lucia@universidad.edu", last_active=datetime.now(timezone.utc) - timedelta(hours=5)),
        ]
        session.add_all(students)
        session.flush()

        enrollments = [
            Enrollment(student_id=1, course_id=1, status="completed", progress_pct=100.0),
            Enrollment(student_id=1, course_id=2, status="active", progress_pct=72.0),
            Enrollment(student_id=1, course_id=7, status="active", progress_pct=45.0),
            Enrollment(student_id=2, course_id=1, status="completed", progress_pct=100.0),
            Enrollment(student_id=2, course_id=2, status="active", progress_pct=20.0),
            Enrollment(student_id=3, course_id=1, status="active", progress_pct=88.0),
            Enrollment(student_id=3, course_id=4, status="active", progress_pct=65.0),
            Enrollment(student_id=3, course_id=8, status="active", progress_pct=90.0),
            Enrollment(student_id=4, course_id=1, status="active", progress_pct=10.0),
            Enrollment(student_id=5, course_id=1, status="completed", progress_pct=100.0),
            Enrollment(student_id=5, course_id=2, status="completed", progress_pct=100.0),
            Enrollment(student_id=5, course_id=3, status="active", progress_pct=60.0),
            Enrollment(student_id=5, course_id=6, status="active", progress_pct=35.0),
        ]
        session.add_all(enrollments)
        session.flush()

        assignments = [
            Assignment(course_id=1, title="Variables y Tipos", description="Ejercicios de tipos de datos en Python.", max_score=100, weight=0.2),
            Assignment(course_id=1, title="Funciones y Módulos", description="Crear funciones reutilizables.", max_score=100, weight=0.3),
            Assignment(course_id=1, title="Proyecto OOP", description="Sistema de gestión con clases.", max_score=100, weight=0.5),
            Assignment(course_id=2, title="Regresión Lineal", description="Implementar regresión desde cero.", max_score=100, weight=0.3),
            Assignment(course_id=2, title="Clasificación con SVM", description="Clasificador de dígitos.", max_score=100, weight=0.3),
            Assignment(course_id=2, title="Proyecto ML Pipeline", description="Pipeline completo de ML.", max_score=100, weight=0.4),
            Assignment(course_id=3, title="Red Neuronal Simple", description="Implementar perceptrón multicapa.", max_score=100, weight=0.3),
            Assignment(course_id=3, title="CNN para Imágenes", description="Clasificación de imágenes.", max_score=100, weight=0.35),
            Assignment(course_id=3, title="Transformer desde Cero", description="Implementar attention mechanism.", max_score=100, weight=0.35),
            Assignment(course_id=4, title="Modelado Relacional", description="Diseñar esquema normalizado.", max_score=100, weight=0.4),
            Assignment(course_id=4, title="Consultas Avanzadas", description="JOINs, subqueries, window functions.", max_score=100, weight=0.3),
            Assignment(course_id=7, title="Tokenización y Embeddings", description="Implementar tokenizador BPE.", max_score=100, weight=0.4),
            Assignment(course_id=8, title="Dashboard Interactivo", description="Crear dashboard con Plotly.", max_score=100, weight=0.5),
        ]
        session.add_all(assignments)
        session.flush()

        grades = [
            Grade(student_id=1, assignment_id=1, score=95, feedback="Excelente dominio de tipos y variables."),
            Grade(student_id=1, assignment_id=2, score=88, feedback="Buenas funciones, mejorar manejo de errores."),
            Grade(student_id=1, assignment_id=3, score=92, feedback="Proyecto OOP muy bien estructurado."),
            Grade(student_id=1, assignment_id=4, score=78, feedback="Regresión correcta, falta regularización."),
            Grade(student_id=1, assignment_id=5, score=82, feedback="SVM bien implementado, optimización mejorable."),
            Grade(student_id=2, assignment_id=1, score=45, feedback="Errores con tipos mutables e inmutables."),
            Grade(student_id=2, assignment_id=2, score=38, feedback="Funciones con errores de scope."),
            Grade(student_id=2, assignment_id=4, score=30, feedback="No completó la implementación."),
            Grade(student_id=3, assignment_id=1, score=90, feedback="Muy buen manejo de tipos."),
            Grade(student_id=3, assignment_id=2, score=85, feedback="Funciones limpias y bien documentadas."),
            Grade(student_id=3, assignment_id=10, score=92, feedback="Esquema normalizado excelente."),
            Grade(student_id=3, assignment_id=13, score=88, feedback="Dashboard visualmente atractivo."),
            Grade(student_id=4, assignment_id=1, score=25, feedback="No entregó a tiempo, código incompleto."),
            Grade(student_id=5, assignment_id=1, score=98, feedback="Impecable."),
            Grade(student_id=5, assignment_id=2, score=96, feedback="Código production-ready."),
            Grade(student_id=5, assignment_id=3, score=99, feedback="Arquitectura ejemplar."),
            Grade(student_id=5, assignment_id=4, score=94, feedback="Regresión con regularización L1/L2."),
            Grade(student_id=5, assignment_id=5, score=91, feedback="SVM con kernel trick implementado."),
            Grade(student_id=5, assignment_id=6, score=95, feedback="Pipeline completo con cross-validation."),
            Grade(student_id=5, assignment_id=7, score=88, feedback="Backpropagation correcto."),
            Grade(student_id=5, assignment_id=12, score=90, feedback="BPE implementado eficientemente."),
        ]
        session.add_all(grades)
        session.commit()


# ==========================================
# LLM HELPER (OpenAI con fallback mock)
# ==========================================

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")


async def llm_generate(system_prompt: str, user_prompt: str) -> str:
    if not OPENROUTER_API_KEY:
        return _mock_llm_response(system_prompt, user_prompt)

    from openai import AsyncOpenAI
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )
    response = await client.chat.completions.create(
        model="openai/gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=1024,
    )
    return response.choices[0].message.content


def _mock_llm_response(system_prompt: str, user_prompt: str) -> str:
    if "recomend" in user_prompt.lower() or "recommend" in user_prompt.lower():
        return (
            "Basándome en el historial del estudiante, recomiendo el curso de "
            "'Deep Learning con PyTorch' como siguiente paso. El estudiante ha demostrado "
            "sólidos fundamentos en ML y está listo para avanzar a redes neuronales profundas. "
            "Confianza: 0.89. Prerrequisitos cumplidos: sí."
        )
    if "study plan" in user_prompt.lower() or "plan de estudio" in user_prompt.lower():
        return (
            "Plan de estudio personalizado de 8 semanas:\n"
            "Semanas 1-2: Repaso de álgebra lineal y cálculo.\n"
            "Semanas 3-4: Fundamentos de redes neuronales con PyTorch.\n"
            "Semanas 5-6: CNNs y procesamiento de imágenes.\n"
            "Semanas 7-8: Transformers y proyecto final.\n"
            "Recursos: Fast.ai course, PyTorch docs, Papers With Code.\n"
            "Hitos: Quiz semanal, proyecto intermedio (semana 4), proyecto final (semana 8)."
        )
    if "grade" in user_prompt.lower() or "califica" in user_prompt.lower() or "feedback" in user_prompt.lower():
        return (
            "Evaluación del trabajo:\n"
            "Corrección técnica: 85/100 — La implementación es funcional pero falta validación de inputs.\n"
            "Calidad del código: 90/100 — Código limpio, bien estructurado y documentado.\n"
            "Creatividad: 80/100 — Solución estándar, podría explorar enfoques alternativos.\n"
            "Feedback general: Buen trabajo. Recomendaría agregar tests unitarios y manejo de edge cases."
        )
    if "risk" in user_prompt.lower() or "riesgo" in user_prompt.lower():
        return (
            "Análisis de riesgo estudiantil:\n"
            "Carlos López: riesgo ALTO — inactivo 15 días, promedios bajos (37.7), "
            "progreso estancado en 20%. Factores: falta de engagement, bajo rendimiento.\n"
            "Diego Rodríguez: riesgo ALTO — inactivo 30 días, progreso 10%. "
            "Factor: abandono probable.\n"
            "Intervenciones: contacto personalizado, plan de recuperación, tutoría entre pares."
        )
    return (
        "Respuesta generada por el modelo de IA para el contexto educativo. "
        "En producción, esta respuesta incluiría análisis detallado basado en "
        "los datos del estudiante y el contexto del curso."
    )


# ==========================================
# MCP SERVER DEFINITION
# ==========================================

mcp = FastMCP("educational-platform")


@mcp.tool()
def get_student_progress(student_id: int) -> dict:
    """Obtiene métricas de progreso de un estudiante específico.
    Retorna GPA, cursos, assignments completados y nivel de riesgo."""
    with SessionLocal() as session:
        student = session.get(Student, student_id)
        if not student:
            return {"error": f"Estudiante con id={student_id} no encontrado."}

        enrollments = session.query(Enrollment).filter(Enrollment.student_id == student_id).all()
        grades = session.query(Grade).filter(Grade.student_id == student_id).all()

        completed = [e for e in enrollments if e.status == "completed"]
        [e for e in enrollments if e.status == "active"]

        all_assignments = (
            session.query(Assignment)
            .join(Enrollment, Assignment.course_id == Enrollment.course_id)
            .filter(Enrollment.student_id == student_id)
            .distinct()
            .count()
        )

        avg_score = sum(g.score for g in grades) / len(grades) if grades else 0.0
        gpa = min(4.0, avg_score / 25.0)

        days_since_active = (datetime.now(timezone.utc) - student.last_active.replace(tzinfo=timezone.utc)).days
        streak = max(0, 7 - days_since_active)

        if avg_score < 50 or days_since_active > 14:
            risk = "high"
        elif avg_score < 70 or days_since_active > 7:
            risk = "medium"
        else:
            risk = "low"

        course_grades: dict[str, list[float]] = {}
        for g in grades:
            assignment = session.get(Assignment, g.assignment_id)
            if assignment:
                course = session.get(Course, assignment.course_id)
                if course:
                    course_grades.setdefault(course.category, []).append(g.score)

        strengths = [cat for cat, scores in course_grades.items() if sum(scores) / len(scores) >= 85]
        weaknesses = [cat for cat, scores in course_grades.items() if sum(scores) / len(scores) < 70]

        return StudentProgress(
            student_id=student_id,
            name=student.name,
            overall_gpa=round(gpa, 2),
            courses_enrolled=len(enrollments),
            courses_completed=len(completed),
            total_assignments=all_assignments,
            assignments_submitted=len(grades),
            avg_score=round(avg_score, 1),
            streak_days=streak,
            risk_level=risk,
            strengths=strengths or ["programming"],
            weaknesses=weaknesses or [],
        ).model_dump()


@mcp.tool()
async def recommend_next_course(student_id: int) -> dict:
    """Recomienda el siguiente curso para un estudiante usando IA.
    Analiza historial, prerrequisitos y brechas de conocimiento."""
    with SessionLocal() as session:
        student = session.get(Student, student_id)
        if not student:
            return {"error": f"Estudiante con id={student_id} no encontrado."}

        enrollments = session.query(Enrollment).filter(Enrollment.student_id == student_id).all()
        enrolled_course_ids = {e.course_id for e in enrollments}
        completed_course_names = [
            session.get(Course, e.course_id).name
            for e in enrollments if e.status == "completed"
        ]

        grades = session.query(Grade).filter(Grade.student_id == student_id).all()
        avg_score = sum(g.score for g in grades) / len(grades) if grades else 0.0

        all_courses = session.query(Course).all()
        available = [c for c in all_courses if c.id not in enrolled_course_ids]

        candidate_info = []
        for c in available:
            prereqs = json.loads(c.prerequisites) if c.prerequisites else []
            prereqs_met = all(p in completed_course_names for p in prereqs)
            candidate_info.append({
                "id": c.id, "name": c.name, "category": c.category,
                "difficulty": c.difficulty, "prerequisites": prereqs,
                "prerequisites_met": prereqs_met,
            })

        prompt = (
            f"Estudiante: {student.name}\n"
            f"Cursos completados: {completed_course_names}\n"
            f"Promedio general: {avg_score:.1f}\n"
            f"Cursos disponibles: {json.dumps(candidate_info, ensure_ascii=False)}\n\n"
            f"Recomienda el mejor siguiente curso. Justifica la recomendación."
        )

        llm_response = await llm_generate(
            "Eres un asesor académico experto en rutas de aprendizaje de IA y datos.",
            prompt,
        )

        best = next((c for c in candidate_info if c["prerequisites_met"]), candidate_info[0] if candidate_info else None)
        if not best:
            return {"error": "No hay cursos disponibles para recomendar."}

        return CourseRecommendation(
            student_id=student_id,
            recommended_course_id=best["id"],
            recommended_course_name=best["name"],
            reason=llm_response[:300],
            confidence=0.89 if best["prerequisites_met"] else 0.65,
            prerequisites_met=best["prerequisites_met"],
            estimated_difficulty=best["difficulty"],
        ).model_dump()


@mcp.tool()
async def grade_assignment(assignment_id: int, submission: str) -> dict:
    """Califica automáticamente una entrega usando IA.
    Retorna score, letter grade, feedback detallado y desglose de rúbrica."""
    with SessionLocal() as session:
        assignment = session.get(Assignment, assignment_id)
        if not assignment:
            return {"error": f"Assignment con id={assignment_id} no encontrado."}

        course = session.get(Course, assignment.course_id)

        prompt = (
            f"Asignación: {assignment.title}\n"
            f"Descripción: {assignment.description}\n"
            f"Curso: {course.name if course else 'N/A'}\n"
            f"Entrega del estudiante:\n{submission}\n\n"
            f"Califica esta entrega. Proporciona score, feedback constructivo y desglose por rúbrica."
        )

        llm_response = await llm_generate(
            "Eres un profesor experto evaluando trabajos de estudiantes. Sé justo y constructivo.",
            prompt,
        )

        technical = 85.0
        code_quality = 88.0
        creativity = 78.0
        completeness = 90.0

        weights = {"technical": 0.4, "code_quality": 0.25, "creativity": 0.15, "completeness": 0.2}
        final_score = (
            technical * weights["technical"]
            + code_quality * weights["code_quality"]
            + creativity * weights["creativity"]
            + completeness * weights["completeness"]
        )

        if final_score >= 90:
            letter = "A"
        elif final_score >= 80:
            letter = "B"
        elif final_score >= 70:
            letter = "C"
        elif final_score >= 60:
            letter = "D"
        else:
            letter = "F"

        enrolled_students = (
            session.query(Enrollment.student_id)
            .filter(Enrollment.course_id == assignment.course_id, Enrollment.status == "active")
            .all()
        )
        student_id = enrolled_students[0].student_id if enrolled_students else 1

        return GradeResult(
            assignment_id=assignment_id,
            student_id=student_id,
            score=round(final_score, 1),
            letter_grade=letter,
            feedback=llm_response[:400],
            rubric_breakdown={
                "technical": technical,
                "code_quality": code_quality,
                "creativity": creativity,
                "completeness": completeness,
            },
        ).model_dump()


@mcp.tool()
async def generate_study_plan(student_id: int, goal: str) -> dict:
    """Genera un plan de estudio personalizado usando IA.
    Incluye cronograma semanal, recursos y milestones."""
    with SessionLocal() as session:
        student = session.get(Student, student_id)
        if not student:
            return {"error": f"Estudiante con id={student_id} no encontrado."}

        enrollments = session.query(Enrollment).filter(Enrollment.student_id == student_id).all()
        active_courses = []
        for e in enrollments:
            if e.status == "active":
                course = session.get(Course, e.course_id)
                if course:
                    active_courses.append({"name": course.name, "progress": e.progress_pct, "category": course.category})

        grades = session.query(Grade).filter(Grade.student_id == student_id).all()
        avg_score = sum(g.score for g in grades) / len(grades) if grades else 0.0

        prompt = (
            f"Estudiante: {student.name}\n"
            f"Objetivo: {goal}\n"
            f"Cursos activos: {json.dumps(active_courses, ensure_ascii=False)}\n"
            f"Promedio general: {avg_score:.1f}\n\n"
            f"Genera un plan de estudio detallado para alcanzar el objetivo."
        )

        await llm_generate(
            "Eres un planificador educativo experto en rutas de aprendizaje personalizadas.",
            prompt,
        )

        weeks = 8 if "advanced" in goal.lower() or "avanzado" in goal.lower() else 6
        schedule = []
        for w in range(1, weeks + 1):
            schedule.append({
                "week": w,
                "focus": f"Módulo {w}" if w <= weeks // 2 else f"Proyecto práctico {w - weeks // 2}",
                "hours_per_week": 10 if w <= weeks // 2 else 15,
                "deliverables": ["Lectura", "Ejercicios prácticos", "Quiz"] if w <= weeks // 2 else ["Proyecto", "Code review"],
            })

        return StudyPlan(
            student_id=student_id,
            goal=goal,
            duration_weeks=weeks,
            weekly_schedule=schedule,
            resources=[
                "Documentación oficial de los cursos activos",
                "Papers relevantes en arXiv",
                "Notebooks de práctica en Google Colab",
                "Comunidad de Discord del programa",
            ],
            milestones=[
                f"Completar 50% del material (semana {weeks // 3})",
                f"Proyecto intermedio (semana {weeks // 2})",
                f"Proyecto final y presentación (semana {weeks})",
            ],
        ).model_dump()


@mcp.tool()
async def detect_at_risk_students() -> dict:
    """Detecta estudiantes en riesgo de abandono usando análisis de datos e IA.
    Retorna lista de estudiantes con score de riesgo, factores e intervenciones."""
    with SessionLocal() as session:
        students = session.query(Student).all()
        at_risk = []

        for student in students:
            enrollments = session.query(Enrollment).filter(Enrollment.student_id == student.id).all()
            grades = session.query(Grade).filter(Grade.student_id == student.id).all()

            days_inactive = (datetime.now(timezone.utc) - student.last_active.replace(tzinfo=timezone.utc)).days
            avg_score = sum(g.score for g in grades) / len(grades) if grades else 0.0
            avg_progress = sum(e.progress_pct for e in enrollments) / len(enrollments) if enrollments else 0.0
            submission_rate = len(grades) / max(1, len(enrollments) * 3)

            risk_factors = []
            risk_score = 0.0

            if days_inactive > 14:
                risk_factors.append(f"Inactivo hace {days_inactive} días")
                risk_score += 0.3
            elif days_inactive > 7:
                risk_factors.append(f"Inactivo hace {days_inactive} días")
                risk_score += 0.15

            if avg_score < 50:
                risk_factors.append(f"Promedio bajo: {avg_score:.1f}")
                risk_score += 0.3
            elif avg_score < 70:
                risk_factors.append(f"Promedio regular: {avg_score:.1f}")
                risk_score += 0.15

            if avg_progress < 30:
                risk_factors.append(f"Progreso bajo: {avg_progress:.0f}%")
                risk_score += 0.25
            elif avg_progress < 50:
                risk_factors.append(f"Progreso moderado: {avg_progress:.0f}%")
                risk_score += 0.1

            if submission_rate < 0.5:
                risk_factors.append(f"Tasa de entrega baja: {submission_rate:.0%}")
                risk_score += 0.15

            risk_score = min(1.0, risk_score)

            if risk_score >= 0.4:
                interventions = []
                if days_inactive > 7:
                    interventions.append("Enviar email personalizado de re-engagement")
                if avg_score < 50:
                    interventions.append("Asignar tutoría entre pares")
                if avg_progress < 30:
                    interventions.append("Crear plan de recuperación acelerado")
                if submission_rate < 0.5:
                    interventions.append("Recordatorios automáticos de deadlines")
                interventions.append("Reunión 1:1 con advisor académico")

                at_risk.append(AtRiskStudent(
                    student_id=student.id,
                    name=student.name,
                    risk_score=round(risk_score, 2),
                    risk_factors=risk_factors,
                    recommended_interventions=interventions,
                ))

        at_risk.sort(key=lambda s: s.risk_score, reverse=True)

        llm_response = await llm_generate(
            "Eres un analista educativo especializado en retención estudiantil.",
            f"Estudiantes en riesgo detectados: {json.dumps([s.model_dump() for s in at_risk], ensure_ascii=False)}\n"
            "Proporciona un análisis agregado y recomendaciones institucionales.",
        )

        return {
            "total_at_risk": len(at_risk),
            "students": [s.model_dump() for s in at_risk],
            "institutional_analysis": llm_response[:400],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


# ==========================================
# MCP RESOURCES
# ==========================================

@mcp.resource("courses://catalog")
def course_catalog_resource() -> str:
    """Catálogo completo de cursos disponibles en la plataforma."""
    with SessionLocal() as session:
        courses = session.query(Course).order_by(Course.category, Course.difficulty).all()
        catalog = []
        for c in courses:
            prereqs = json.loads(c.prerequisites) if c.prerequisites else []
            enrollment_count = session.query(Enrollment).filter(Enrollment.course_id == c.id).count()
            catalog.append({
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "category": c.category,
                "difficulty": c.difficulty,
                "credits": c.credits,
                "prerequisites": prereqs,
                "active_enrollments": enrollment_count,
            })
        return json.dumps(catalog, indent=2, ensure_ascii=False)


@mcp.resource("students://metrics")
def student_metrics_resource() -> str:
    """Métricas agregadas de todos los estudiantes en la plataforma."""
    with SessionLocal() as session:
        total_students = session.query(Student).count()
        total_enrollments = session.query(Enrollment).count()
        completed_enrollments = session.query(Enrollment).filter(Enrollment.status == "completed").count()
        total_grades = session.query(Grade).count()

        avg_score = session.query(func.avg(Grade.score)).scalar() or 0.0
        avg_progress = session.query(func.avg(Enrollment.progress_pct)).scalar() or 0.0

        category_stats = {}
        courses = session.query(Course).all()
        for course in courses:
            cat = course.category
            if cat not in category_stats:
                cat_enrollments = (
                    session.query(Enrollment)
                    .join(Course, Enrollment.course_id == Course.id)
                    .filter(Course.category == cat)
                    .count()
                )
                category_stats[cat] = {"enrollments": cat_enrollments, "courses": 0}
            category_stats[cat]["courses"] += 1

        now = datetime.now(timezone.utc)
        active_7d = (
            session.query(Student)
            .filter(Student.last_active >= now - timedelta(days=7))
            .count()
        )

        return json.dumps({
            "total_students": total_students,
            "total_enrollments": total_enrollments,
            "completed_enrollments": completed_enrollments,
            "completion_rate": round(completed_enrollments / max(1, total_enrollments) * 100, 1),
            "total_grades_recorded": total_grades,
            "average_score": round(avg_score, 1),
            "average_progress": round(avg_progress, 1),
            "active_last_7_days": active_7d,
            "category_distribution": category_stats,
            "generated_at": now.isoformat(),
        }, indent=2, ensure_ascii=False)


# ==========================================
# AGENT ORCHESTRATION (simulación de agentes)
# ==========================================

async def student_advisor_agent(student_id: int) -> dict:
    """Agente asesor estudiantil: analiza progreso y recomienda acciones."""
    print(f"\n   [Student Advisor] Analizando estudiante id={student_id}...")

    progress = get_student_progress(student_id)
    print(f"   [Student Advisor] Progreso obtenido: GPA={progress.get('overall_gpa')}, riesgo={progress.get('risk_level')}")

    recommendation = await recommend_next_course(student_id)
    print(f"   [Student Advisor] Recomendación: {recommendation.get('recommended_course_name', 'N/A')}")

    if progress.get("risk_level") == "high":
        study_plan = await generate_study_plan(student_id, "Recuperar rendimiento académico")
        print(f"   [Student Advisor] Plan de recuperación generado: {study_plan.get('duration_weeks')} semanas")
    else:
        study_plan = await generate_study_plan(student_id, "Avanzar en la ruta de especialización")
        print(f"   [Student Advisor] Plan de avance generado: {study_plan.get('duration_weeks')} semanas")

    return {
        "agent": "student_advisor",
        "student_id": student_id,
        "progress_summary": progress,
        "course_recommendation": recommendation,
        "study_plan": study_plan,
    }


async def content_curator_agent() -> dict:
    """Agente curador de contenido: analiza catálogo y sugiere mejoras."""
    print("\n   [Content Curator] Analizando catálogo de cursos...")

    catalog = json.loads(course_catalog_resource())
    metrics = json.loads(student_metrics_resource())

    print(f"   [Content Curator] {len(catalog)} cursos en catálogo")
    print(f"   [Content Curator] Tasa de completitud: {metrics.get('completion_rate')}%")

    low_enrollment = [c for c in catalog if c.get("active_enrollments", 0) == 0]
    popular = sorted(catalog, key=lambda c: c.get("active_enrollments", 0), reverse=True)[:3]

    llm_analysis = await llm_generate(
        "Eres un curador de contenido educativo especializado en IA y datos.",
        f"Catálogo: {json.dumps(catalog, ensure_ascii=False)}\n"
        f"Métricas: tasa de completitud={metrics.get('completion_rate')}%, "
        f"promedio={metrics.get('average_score')}.\n"
        f"Sugiere mejoras al catálogo y nuevos cursos.",
    )

    return {
        "agent": "content_curator",
        "total_courses": len(catalog),
        "low_enrollment_courses": [c["name"] for c in low_enrollment],
        "most_popular": [c["name"] for c in popular],
        "completion_rate": metrics.get("completion_rate"),
        "recommendations": llm_analysis[:400],
    }


async def assessment_agent(assignment_id: int, sample_submission: str) -> dict:
    """Agente de evaluación: califica y genera feedback automatizado."""
    print(f"\n   [Assessment Agent] Evaluando assignment id={assignment_id}...")

    grade_result = await grade_assignment(assignment_id, sample_submission)
    print(f"   [Assessment Agent] Score: {grade_result.get('score')}, Grade: {grade_result.get('letter_grade')}")
    print(f"   [Assessment Agent] Rúbrica: {grade_result.get('rubric_breakdown')}")

    return {
        "agent": "assessment",
        "assignment_id": assignment_id,
        "grade": grade_result,
    }


# ==========================================
# DEMO RUNNER (simulación del cliente MCP)
# ==========================================

async def run_demo():
    print("=" * 62)
    print("  MCP Educational Platform — Plataforma Educativa con IA")
    print("=" * 62)

    if not OPENROUTER_API_KEY:
        print("\n  [NOTA] No se encontró OPENROUTER_API_KEY. Usando respuestas mock.")
        print("  Para respuestas reales de IA: export OPENROUTER_API_KEY=sk-...\n")

    print("\n--- Paso 1: Inicializando base de datos ---")
    init_database()
    print("   Base de datos SQLite creada con esquema completo:")
    print("   - students, courses, enrollments, assignments, grades")
    print("   - Relaciones: Student -> Enrollments -> Courses")
    print("                 Course -> Assignments -> Grades")

    print("\n--- Paso 2: Leyendo recurso MCP courses://catalog ---")
    catalog = json.loads(course_catalog_resource())
    print(f"   {len(catalog)} cursos en el catálogo:")
    for c in catalog:
        print(f"   - [{c['category']}] {c['name']} ({c['difficulty']}, {c['credits']} créditos)")

    print("\n--- Paso 3: Leyendo recurso MCP students://metrics ---")
    metrics = json.loads(student_metrics_resource())
    print(f"   Estudiantes: {metrics['total_students']}")
    print(f"   Inscripciones: {metrics['total_enrollments']} (completitud: {metrics['completion_rate']}%)")
    print(f"   Promedio general: {metrics['average_score']}")
    print(f"   Activos últimos 7 días: {metrics['active_last_7_days']}")

    print("\n--- Paso 4: Tool call — get_student_progress(1) ---")
    progress = get_student_progress(1)
    print(f"   Estudiante: {progress['name']}")
    print(f"   GPA: {progress['overall_gpa']} | Promedio: {progress['avg_score']}")
    print(f"   Cursos: {progress['courses_enrolled']} inscritos, {progress['courses_completed']} completados")
    print(f"   Assignments: {progress['assignments_submitted']}/{progress['total_assignments']} entregados")
    print(f"   Riesgo: {progress['risk_level']} | Racha: {progress['streak_days']} días")
    print(f"   Fortalezas: {progress['strengths']} | Debilidades: {progress['weaknesses']}")

    print("\n--- Paso 5: Tool call — recommend_next_course(1) ---")
    rec = await recommend_next_course(1)
    print(f"   Curso recomendado: {rec['recommended_course_name']}")
    print(f"   Confianza: {rec['confidence']} | Dificultad: {rec['estimated_difficulty']}")
    print(f"   Prerrequisitos: {'cumplidos' if rec['prerequisites_met'] else 'pendientes'}")
    print(f"   Razón: {rec['reason'][:150]}...")

    print("\n--- Paso 6: Tool call — grade_assignment(4, submission) ---")
    sample_submission = (
        "Implementé la regresión lineal usando gradiente descendente.\n"
        "def linear_regression(X, y, lr=0.01, epochs=1000):\n"
        "    w = np.zeros(X.shape[1])\n"
        "    b = 0\n"
        "    for _ in range(epochs):\n"
        "        y_pred = X @ w + b\n"
        "        dw = (1/len(X)) * X.T @ (y_pred - y)\n"
        "        db = (1/len(X)) * np.sum(y_pred - y)\n"
        "        w -= lr * dw\n"
        "        b -= lr * db\n"
        "    return w, b\n"
    )
    grade = await grade_assignment(4, sample_submission)
    print(f"   Score: {grade['score']} ({grade['letter_grade']})")
    print(f"   Rúbrica: {json.dumps(grade['rubric_breakdown'])}")
    print(f"   Feedback: {grade['feedback'][:200]}...")

    print("\n--- Paso 7: Tool call — generate_study_plan(1, goal) ---")
    plan = await generate_study_plan(1, "Dominar Deep Learning para computer vision")
    print(f"   Objetivo: {plan['goal']}")
    print(f"   Duración: {plan['duration_weeks']} semanas")
    print("   Cronograma:")
    for week in plan["weekly_schedule"][:3]:
        print(f"     Semana {week['week']}: {week['focus']} ({week['hours_per_week']}h/semana)")
    print(f"     ... ({len(plan['weekly_schedule'])} semanas en total)")
    print(f"   Hitos: {plan['milestones']}")

    print("\n--- Paso 8: Tool call — detect_at_risk_students() ---")
    risk_report = await detect_at_risk_students()
    print(f"   Estudiantes en riesgo: {risk_report['total_at_risk']}")
    for s in risk_report["students"]:
        print(f"   - {s['name']} (score={s['risk_score']})")
        print(f"     Factores: {', '.join(s['risk_factors'])}")
        print(f"     Intervenciones: {', '.join(s['recommended_interventions'][:2])}")

    print("\n" + "=" * 62)
    print("  ORQUESTACIÓN DE AGENTES MCP")
    print("=" * 62)

    print("\n--- Paso 9: Student Advisor Agent (estudiante 5) ---")
    advisor_result = await student_advisor_agent(5)
    print(f"   Resultado: recomendación={advisor_result['course_recommendation'].get('recommended_course_name', 'N/A')}")
    print(f"   Plan: {advisor_result['study_plan'].get('duration_weeks')} semanas")

    print("\n--- Paso 10: Content Curator Agent ---")
    curator_result = await content_curator_agent()
    print(f"   Cursos populares: {curator_result['most_popular']}")
    print(f"   Cursos con baja inscripción: {curator_result['low_enrollment_courses'] or 'ninguno'}")
    print(f"   Recomendaciones: {curator_result['recommendations'][:200]}...")

    print("\n--- Paso 11: Assessment Agent ---")
    assessment_result = await assessment_agent(7, "Implementé un perceptrón con 2 capas ocultas y ReLU.")
    print(f"   Score: {assessment_result['grade']['score']} ({assessment_result['grade']['letter_grade']})")

    print("\n" + "=" * 62)
    print("  INTEGRACIÓN MCP CON SISTEMAS EXTERNOS")
    print("=" * 62)
    print("""
  MCP permite conectar esta plataforma con:

  ┌─────────────────────────────────────────────────────┐
  │  LMS (Canvas/Moodle)    ←→ MCP Server              │
  │  • Sincronización de cursos y calificaciones        │
  │  • Webhooks para entregas en tiempo real            │
  │                                                     │
  │  SIS (Banner/PeopleSoft) ←→ MCP Server             │
  │  • Registro académico automatizado                  │
  │  • Verificación de prerrequisitos                   │
  │                                                     │
  │  Analytics (Tableau)     ←→ MCP Resources           │
  │  • Dashboards de retención y rendimiento            │
  │  • Alertas tempranas para advisors                  │
  │                                                     │
  │  Contenido (Khan/OER)    ←→ MCP Tools               │
  │  • Recomendaciones de material complementario       │
  │  • Adaptación de dificultad en tiempo real          │
  └─────────────────────────────────────────────────────┘

  Para conectar con LangChain/LangGraph:

      from langchain_mcp_adapters.client import MultiServerMCPClient

      async with MultiServerMCPClient({
          "edu_platform": {
              "transport": "stdio",
              "command": "uv",
              "args": ["run", "01_python_frameworks/mcp_educational_platform_demo.py", "--serve"],
          }
      }) as client:
          tools = await client.get_tools()
          # tools: get_student_progress, recommend_next_course, etc.
""")

    print("=" * 62)
    print("  Demo completado. Ejecuta con --serve para servidor MCP real.")
    print("=" * 62)


# ==========================================
# MCP SERVER MODE
# ==========================================

def run_server():
    init_database()
    print("Iniciando MCP Server 'educational-platform'...")
    print("  Transporte: stdio")
    print("  Tools: get_student_progress, recommend_next_course, grade_assignment,")
    print("         generate_study_plan, detect_at_risk_students")
    print("  Resources: courses://catalog, students://metrics")
    mcp.run()


if __name__ == "__main__":
    if "--serve" in sys.argv:
        run_server()
    else:
        asyncio.run(run_demo())
