import os
import logging
from typing import List, Optional
from pydantic_ai import Agent

from ...domain.models import (
    CampoFormativo, EjeArticulador, FaseAprendizaje,
    ContenidoProgramaSintetico, ProcesoDesarrolloAprendizaje,
    ContextoLocal, Secuencia
)
from ...domain.services import (
    NEMAgentService, NEMBookOutline, NEMSequenceOutline,
    TrimestreOutline, PDACoverageResult, PDAResult
)

logger = logging.getLogger(__name__)

NEM_OUTLINE_SYSTEM_PROMPT = """
Eres un DISEÑADOR CURRICULAR ESPECIALISTA en la Nueva Escuela Mexicana (NEM).
Tu tarea: Generar la macro-estructura de un libro para FASE 2 (1°-2° primaria).

REGLAS OBLIGATORIAS:
1. Estructura: 3 Trimestres × 6 Secuencias = 18 secuencias didácticas
2. Cada secuencia debe:
   - Tener CAMPO FORMATIVO PRINCIPAL (1 de 4) + 1-2 CAMPOS VINCULADOS
   - Mapear CONTENIDOS del Programa Sintético Fase 2 (códigos oficiales)
   - Permear 2-3 EJES ARTICULADORES transversales
   - Vincularse a un PROYECTO (Aula / Escolar / Comunitario)
3. Secuencias NO son "temas aislados": son hitos de un proyecto integrador
4. Títulos deben ser sugerentes, no académicos: "El agua en mi comunidad" no "Propiedades del agua"
5. Objetivos redactados en lenguaje de PDA: "Analiza...", "Construye...", "Propone...", "Comunica..."

CAMPOS FORMATIVOS FASE 2:
- Lenguajes: Oralidad, lectura, escritura, lenguajes artísticos
- Saberes y Pensamiento Científico: Matemáticas, ciencias, tecnología
- Ética, Naturaleza y Sociedades: Historia, geografía, civismo, medio ambiente
- De lo Humano y lo Comunitario: Identidad, convivencia, corporeidad, arte

EJES ARTICULADORES (7): Pensamiento crítico, Interculturalidad, Igualdad de género,
Vida saludable, Inclusión, Lectura y escritura, Artes y experiencias estéticas
"""

NEM_PDA_EVAL_SYSTEM_PROMPT = """
Eres un EVALUADOR ESPECIALISTA en Procesos de Desarrollo de Aprendizaje (PDA) de la NEM.
Evalúa la cobertura de PDA y la integración de ejes articuladores en la secuencia didáctica.

Para cada PDA proporcionado, asigna un nivel de logro:
- "En proceso": El PDA se aborda parcialmente
- "Logrado": El PDA se desarrolla adecuadamente en las lecciones
- "Avanzado": El PDA se desarrolla de forma excepcional con actividades enriquecidas

Evalúa también la integración transversal de los ejes articuladores.
Devuelve scores de 0.0 a 1.0 para cobertura PDA y ejes articuladores.
"""


class PydanticNEMAgentService(NEMAgentService):
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.use_live = bool(self.api_key)

        if self.use_live:
            logger.info("Initializing PydanticNEMAgentService in LIVE mode")
            self.outline_agent = Agent(
                "google-gla:gemini-1.5-pro",
                output_type=NEMBookOutline,
                system_prompt=NEM_OUTLINE_SYSTEM_PROMPT
            )
            self.pda_eval_agent = Agent(
                "google-gla:gemini-1.5-flash",
                output_type=PDACoverageResult,
                system_prompt=NEM_PDA_EVAL_SYSTEM_PROMPT
            )
        else:
            logger.warning("No GEMINI_API_KEY found. PydanticNEMAgentService in OFFLINE MOCK mode.")

    def generate_nem_outline(
        self,
        campo_formativo: CampoFormativo,
        fase: FaseAprendizaje,
        contenidos: List[ContenidoProgramaSintetico],
        contexto: Optional[ContextoLocal] = None
    ) -> NEMBookOutline:
        if not self.use_live:
            return self._mock_generate_nem_outline(campo_formativo, fase, contenidos, contexto)

        contenidos_str = "\n".join([f"- [{c.codigo}]: {c.descripcion}" for c in contenidos])
        contexto_str = ""
        if contexto:
            contexto_str = f"\nContexto local: {contexto.comunidad}, problemática: {contexto.problematica_local}"

        prompt = (
            f"Campo formativo principal: {campo_formativo.value}\n"
            f"Fase: {fase.value}\n"
            f"Contenidos del Programa Sintético:\n{contenidos_str}\n"
            f"{contexto_str}\n"
            f"Genera 3 trimestres × 6 secuencias integrando los 4 campos formativos."
        )

        result = self.outline_agent.run_sync(prompt)
        return result.output

    def evaluate_pda_coverage(
        self,
        secuencia: Secuencia,
        pda_list: List[ProcesoDesarrolloAprendizaje],
        ejes: List[EjeArticulador]
    ) -> PDACoverageResult:
        if not self.use_live:
            return self._mock_evaluate_pda_coverage(secuencia, pda_list, ejes)

        pda_str = "\n".join([f"- PDA {i+1}: {p.descripcion}" for i, p in enumerate(pda_list)])
        ejes_str = ", ".join([e.value for e in ejes])
        lessons_str = ""
        for lesson in secuencia.lessons:
            lessons_str += f"\nLección {lesson.number}: {lesson.title}\n{lesson.section_inicio}\n{lesson.section_desarrollo}\n{lesson.section_cierre}\n"

        prompt = (
            f"Secuencia: '{secuencia.title}'\nObjetivos: {secuencia.objectives}\n"
            f"PDA a evaluar:\n{pda_str}\n"
            f"Ejes articuladores: {ejes_str}\n"
            f"Lecciones:\n{lessons_str}"
        )

        result = self.pda_eval_agent.run_sync(prompt)
        return result.output

    def _mock_generate_nem_outline(
        self,
        campo_formativo: CampoFormativo,
        fase: FaseAprendizaje,
        contenidos: List[ContenidoProgramaSintetico],
        contexto: Optional[ContextoLocal] = None
    ) -> NEMBookOutline:
        seq_titles = {
            CampoFormativo.LENGUAJES: [
                ["Las palabras de mi comunidad", "Cuentos de mi familia", "Escribo mi historia", "Canciones y rimas", "Carteles para todos", "Mi primer periódico"],
                ["Leyendas del barrio", "Recetas con palabras", "Teatro de títeres", "Poemas del agua", "Cartas a mis amigos", "El noticiero del salón"],
                ["Mi nombre en grande", "Rondas y juegos", "Cuentos de animales", "Invitaciones festivas", "Adivinanzas divertidas", "El libro del grupo"]
            ],
            CampoFormativo.SABERES_PCIENTIFICO: [
                ["Cuento hasta 20", "Figuras en mi escuela", "Más grande o más pequeño", "Patrones de colores", "Mi calendario", "Los números del mercado"],
                ["Sumo mis juguetes", "Resto con frutas", "Formas escondidas", "Mido con mis pasos", "El reloj del salón", "Gráficas de mi grupo"],
                ["Cuento hasta 50", "Problemas divertidos", "Cuerpos geométricos", "Tablas y caritas", "El plano del salón", "Agrupaciones de 10"]
            ],
            CampoFormativo.ETICA_NATURALEZA_SOCIEDADES: [
                ["Mi familia es diversa", "Tradiciones de mi pueblo", "Cuido el agua", "Normas del salón", "Mi comunidad", "Los seres vivos"],
                ["El campo y la ciudad", "Fiestas y costumbres", "Reciclamos juntos", "Acuerdos de paz", "Mi localidad", "Plantas de mi jardín"],
                ["Todos somos diferentes", "Historias de mi barrio", "Cuido a los animales", "Reglas para convivir", "El mapa de mi escuela", "Nuestro planeta"]
            ],
            CampoFormativo.HUMANO_COMUNITARIO: [
                ["Mis emociones", "Juego con respeto", "Mi cuerpo se mueve", "Soy único", "Hábitos saludables", "Música y danza"],
                ["Expreso lo que siento", "Cooperamos juntos", "Mi identidad", "Juegos de antes", "Como saludable", "Pinto mi mundo"],
                ["Amigos diferentes", "Reglas del juego", "Me muevo y expreso", "Mi familia", "Cuido mi salud", "Teatro escolar"]
            ]
        }

        titles = seq_titles.get(campo_formativo, seq_titles[CampoFormativo.LENGUAJES])
        otros_campos = [c for c in CampoFormativo if c != campo_formativo]
        ejes_base = [EjeArticulador.LECTURA_ESCRITURA, EjeArticulador.PENSAMIENTO_CRITICO]

        trimestres = []
        for t_num in (1, 2, 3):
            secuencias = []
            for s_num in range(6):
                secuencias.append(
                    NEMSequenceOutline(
                        number=s_num + 1,
                        title=titles[t_num - 1][s_num],
                        objectives=f"Desarrollar competencias del campo {campo_formativo.value} mediante actividades integradoras y proyectos colaborativos.",
                        campo_formativo_principal=campo_formativo,
                        campos_formativos_vinculados=[otros_campos[(t_num + s_num) % len(otros_campos)]],
                        contenidos_codigos=[c.codigo for c in contenidos[:2]] if contenidos else [],
                        ejes_articuladores=ejes_base + [EjeArticulador.INCLUSION] if s_num % 2 == 0 else ejes_base,
                        proyecto_vinculado=f"Proyecto de Aula: Explorando {campo_formativo.value} en mi comunidad" if s_num == 5 else None
                    )
                )
            trimestres.append(
                TrimestreOutline(
                    number=t_num,
                    title=f"Trimestre {t_num}: Saberes en acción",
                    goals=f"Integrar aprendizajes del campo {campo_formativo.value} con proyectos de aula y comunitarios.",
                    secuencias=secuencias
                )
            )

        return NEMBookOutline(
            title=f"Mis Saberes de {campo_formativo.value} - Fase 2",
            fase=fase,
            trimestres=trimestres
        )

    def _mock_evaluate_pda_coverage(
        self,
        secuencia: Secuencia,
        pda_list: List[ProcesoDesarrolloAprendizaje],
        ejes: List[EjeArticulador]
    ) -> PDACoverageResult:
        pda_results = []
        for pda in pda_list:
            pda_results.append(PDAResult(
                pda_id=pda.id or 0,
                nivel_logro="Logrado",
                justificacion=f"El PDA '{pda.descripcion[:50]}...' se aborda adecuadamente en las lecciones generadas."
            ))

        num_ejes = len(ejes)
        ejes_score = min(1.0, num_ejes / 3.0) if num_ejes > 0 else 0.5
        cobertura = 0.9 if pda_results else 0.5

        return PDACoverageResult(
            pda_results=pda_results,
            cobertura_score=cobertura,
            ejes_score=ejes_score,
            justificacion=f"La secuencia cubre {len(pda_results)} PDA con nivel 'Logrado'. Se integran {num_ejes} ejes articuladores."
        )
