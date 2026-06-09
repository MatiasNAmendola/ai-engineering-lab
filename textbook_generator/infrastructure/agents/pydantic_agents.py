import os
import logging
from typing import List
from pydantic import BaseModel
from pydantic_ai import Agent

from ...domain.models import CurricularRequirement, Lesson, Secuencia
from ...domain.services import (
    TextbookAgentService, BookOutline, TrimestreOutline, SequenceOutline, EvaluationResult
)

logger = logging.getLogger(__name__)

# Enforce structured output models for LLM formatting
class LessonListOutput(BaseModel):
    lessons: List[Lesson]

class PydanticTextbookAgentService(TextbookAgentService):
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.use_live = bool(self.api_key)
        
        # Configure model names
        self.outline_model = "google-gla:gemini-1.5-flash"
        self.content_model = "google-gla:gemini-1.5-flash" # Default to 1.5 flash for reliability
        self.judge_model = "google-gla:gemini-1.5-flash"

        if self.use_live:
            logger.info("Initializing PydanticTextbookAgentService in LIVE mode using Gemini API")
            
            # Setup Outline Agent
            self.outline_agent = Agent(
                self.outline_model,
                output_type=BookOutline,
                system_prompt=(
                    "Eres un experto en diseño curricular pedagógico de educación primaria. "
                    "Tu tarea es diseñar un bosquejo de libro de texto (3 trimestres, con 6 secuencias didácticas cada uno) "
                    "para niños de primer grado (6 años). Debes alinear las secuencias con los lineamientos curriculares "
                    "provistos. Usa títulos atractivos y objetivos de aprendizaje claros y sencillos."
                )
            )
            
            # Setup Content Agent
            self.content_agent = Agent(
                self.content_model,
                output_type=LessonListOutput,
                system_prompt=(
                    "Eres un autor de libros de texto para primaria de primer grado (6 años). "
                    "Tu objetivo es generar un conjunto de 3 lecciones estructuradas para una secuencia didáctica específica. "
                    "Cada lección DEBE tener exactamente tres secciones obligatorias:\n"
                    "1. Inicio: Contexto motivador, preguntas activadoras, vocabulario súper simple.\n"
                    "2. Desarrollo: Actividades prácticas o lecturas muy sencillas acompañadas de sugerencias de dibujos o ilustraciones.\n"
                    "3. Cierre: Actividad reflexiva, repaso o juego grupal sencillo para evaluar.\n\n"
                    "IMPORTANTE: Redacta en un lenguaje extremadamente comprensible para niños que están aprendiendo a leer. "
                    "Usa explicaciones concretas, oraciones cortas y de tono cálido. Agrega descripciones visuales entre corchetes, "
                    "por ejemplo [Ilustración: Un conejo sonriente leyendo un libro], para indicar el soporte visual requerido."
                )
            )
            
            # Setup Judge Agent
            self.judge_agent = Agent(
                self.judge_model,
                output_type=EvaluationResult,
                system_prompt=(
                    "Eres un evaluador pedagógico y auditor de calidad educativa. Analiza la secuencia didáctica y sus lecciones. "
                    "Califica dos aspectos de 0.00 a 1.00:\n"
                    "1. Curricular Alignment: ¿Las lecciones cubren adecuadamente los lineamientos curriculares y objetivos asignados?\n"
                    "2. Age Appropriateness: ¿El lenguaje, complejidad, duración y actividades son adecuados para niños de primer grado (6 años)?\n\n"
                    "Justifica tus puntajes de manera detallada en español. Sé crítico. Si el vocabulario es rebuscado o "
                    "las instrucciones son abstractas, baja la calificación de adecuación de edad por debajo de 0.85."
                )
            )
        else:
            logger.warning("No GEMINI_API_KEY found. PydanticTextbookAgentService will operate in OFFLINE MOCK mode.")

    def generate_outline(self, subject: str, grade: int, requirements: List[CurricularRequirement]) -> BookOutline:
        if not self.use_live:
            return self._mock_generate_outline(subject, grade, requirements)
            
        prompt = f"Asignatura: {subject}. Grado: {grade}. Lineamientos curriculares:\n"
        for r in requirements:
            prompt += f"- [{r.code}]: {r.description}\n"
            
        logger.info("Calling Live Agent for Book Outline...")
        result = self.outline_agent.run_sync(prompt)
        return result.output

    def generate_sequence_content(
        self, subject: str, grade: int, trimester_num: int, seq_num: int, seq_title: str, seq_objectives: str, requirements: List[CurricularRequirement]
    ) -> List[Lesson]:
        if not self.use_live:
            return self._mock_generate_sequence_content(subject, grade, trimester_num, seq_num, seq_title, seq_objectives)
            
        reqs_str = "\n".join([f"- [{r.code}]: {r.description}" for r in requirements])
        prompt = (
            f"Asignatura: {subject}\nGrado: {grade}\nTrimestre: {trimester_num}\n"
            f"Secuencia didáctica {seq_num}: '{seq_title}'\nObjetivos: {seq_objectives}\n"
            f"Lineamientos de referencia:\n{reqs_str}"
        )
        
        logger.info(f"Calling Live Agent for Sequence Content (Seq {seq_num})...")
        result = self.content_agent.run_sync(prompt)
        return result.output.lessons

    def evaluate_sequence(self, secuencia: Secuencia, requirements: List[CurricularRequirement]) -> EvaluationResult:
        if not self.use_live:
            return self._mock_evaluate_sequence(secuencia)
            
        reqs_str = "\n".join([f"- [{r.code}]: {r.description}" for r in requirements])
        lessons_str = ""
        for lesson in secuencia.lessons:
            lessons_str += f"\nLección {lesson.number}: {lesson.title}\nInicio: {lesson.section_inicio}\nDesarrollo: {lesson.section_desarrollo}\nCierre: {lesson.section_cierre}\nActividades: {lesson.activities}\n"
            
        prompt = (
            f"Secuencia: '{secuencia.title}'\nObjetivos: {secuencia.objectives}\n"
            f"Lineamientos curriculares a evaluar:\n{reqs_str}\n"
            f"Contenido Generado:\n{lessons_str}"
        )
        
        logger.info(f"Calling Live Agent for Evaluation (Seq {secuencia.id})...")
        result = self.judge_agent.run_sync(prompt)
        return result.output

    # --- Offline Mock Implementations ---

    def _mock_generate_outline(self, subject: str, grade: int, requirements: List[CurricularRequirement]) -> BookOutline:
        trimestres = []
        titles_map = {
            "Español": [
                # Trimestre 1
                ["Las letras de mi nombre", "Los sonidos de la escuela", "El abecedario divertido", "Mis primeros cuentos", "Describir mi juguete favorito", "Reglas del salón de clases"],
                # Trimestre 2
                ["Palabras mágicas de cortesía", "Juegos de rimas y canciones", "Cuentacuentos en el aula", "Hacer carteles sencillos", "Animales de la comunidad", "Adivina adivinador"],
                # Trimestre 3
                ["Escribir una carta a mi amigo", "Las leyendas de mi pueblo", "Hacer una pequeña obra de teatro", "Recetas fáciles con dibujos", "Crear poemas cortitos", "Inventores de palabras"]
            ],
            "Matemáticas": [
                # Trimestre 1
                ["Contar del 1 al 10", "Figuras en mi salón", "Comparar tamaños", "Los números y yo", "Patrones de colores", "Izquierda y derecha"],
                # Trimestre 2
                ["Sumar juguetes pequeños", "Restar con manzanas", "El calendario y los días", "Monedas y tiendita", "Cuerpos geométricos simples", "Medir con mis pasos"],
                # Trimestre 3
                ["Contar hasta el 50", "Resolver problemas de sumas", "Organizar datos con caritas", "El reloj y las horas", "Búsqueda del tesoro en plano", "Hacer agrupaciones de 10"]
            ]
        }
        
        # Get defaults or fallback
        seq_titles = titles_map.get(subject, [
            [f"Tema {i}" for i in range(1, 7)],
            [f"Tema {i}" for i in range(7, 13)],
            [f"Tema {i}" for i in range(13, 19)]
        ])
        
        for t_num in (1, 2, 3):
            secuencias = []
            for s_num in range(1, 7):
                title = seq_titles[t_num - 1][s_num - 1]
                secuencias.append(
                    SequenceOutline(
                        number=s_num,
                        title=title,
                        objectives=f"Que el estudiante logre comprender, identificar y aplicar conceptos relacionados con '{title}' mediante actividades prácticas."
                    )
                )
            
            trimestres.append(
                TrimestreOutline(
                    number=t_num,
                    title=f"Trimestre {t_num}: Construyendo saberes",
                    goals=f"Desarrollar competencias básicas en {subject} correspondientes al trimestre {t_num}.",
                    secuencias=secuencias
                )
            )
            
        return BookOutline(
            title=f"Mi Libro Divertido de {subject} - Primer Grado",
            trimestres=trimestres
        )

    def _mock_generate_sequence_content(
        self, subject: str, grade: int, trimester_num: int, seq_num: int, seq_title: str, seq_objectives: str
    ) -> List[Lesson]:
        lessons = []
        for l_num in (1, 2, 3):
            lessons.append(
                Lesson(
                    secuencia_id=0, # Will be set by use case
                    number=l_num,
                    title=f"Lección {l_num}: Jugando con {seq_title}",
                    section_inicio=(
                        f"¡Hola! Hoy vamos a explorar '{seq_title}'. "
                        "Mira a tu alrededor en el salón. ¿Puedes encontrar algo relacionado con este tema? "
                        "Platica con tu compañero de banca lo que imaginas de esta lección."
                    ),
                    section_desarrollo=(
                        "¡Manos a la obra! Vamos a realizar una actividad grupal. "
                        "El maestro escribirá palabras mágicas en el pizarrón. "
                        "Dibujaremos una carita feliz por cada palabra que descubramos. "
                        "[Ilustración: Un grupo de niños y niñas sonrientes sentados en círculo en la alfombra, señalando letras de colores]."
                    ),
                    section_cierre=(
                        "Para terminar, nos tomamos de las manos y cantamos una pequeña canción. "
                        "Compártele a tu maestra qué fue lo que más te gustó hacer el día de hoy."
                    ),
                    activities=(
                        "1. Dibuja en tu cuaderno una estrella.\n"
                        "2. Colorea de rojo las palabras de cortesía que aprendiste.\n"
                        "3. Juega con tu familia a encontrar objetos que inicien con la misma letra."
                    )
                )
            )
        return lessons

    def _mock_evaluate_sequence(self, secuencia: Secuencia) -> EvaluationResult:
        # Crucial design choice: We alter the scores based on the sequence ID or number 
        # so that some sequences score 0.95 (auto-approve) and others score 0.80 (route to HITL queue)
        # This allows the developer/user to test both states of the pipeline!
        
        seq_num = secuencia.number
        
        # Make sequence 2 and 5 trigger HITL review by scoring 0.80
        if seq_num in (2, 5):
            return EvaluationResult(
                alignment_score=0.82,
                age_score=0.84,
                justification=(
                    f"La secuencia '{secuencia.title}' cuenta con lecciones pedagógicamente sólidas. "
                    f"Sin embargo, el vocabulario en la lección 2 incluye términos como 'contextualización' "
                    f"y 'cooperativismo', que resultan muy complejos para niños de 6 años. "
                    f"Se recomienda simplificar a términos como 'ayudar' y 'conversar'."
                )
            )
        else:
            return EvaluationResult(
                alignment_score=0.95,
                age_score=0.92,
                justification=(
                    "Excelente secuencia didáctica. Cumple al 100% con los objetivos curriculares. "
                    "El lenguaje es simple, cálido y promueve actividades prácticas y visuales "
                    "perfectamente adaptadas al desarrollo cognitivo de primer grado de primaria."
                )
            )
