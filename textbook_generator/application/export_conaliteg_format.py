import logging
from typing import Dict, Any
from ..domain.repositories import TextbookRepository

logger = logging.getLogger(__name__)

class ExportConalitegFormatUseCase:
    """Export a textbook in a structured JSON payload conforming to CONALITEG / SEP requirements."""

    def __init__(self, textbook_repo: TextbookRepository):
        self.textbook_repo = textbook_repo

    def execute(self, textbook_id: int) -> Dict[str, Any]:
        logger.info(f"Exporting textbook ID: {textbook_id} to CONALITEG format")
        textbook = self.textbook_repo.get_textbook(textbook_id)
        if not textbook:
            raise ValueError(f"Textbook with ID {textbook_id} not found")

        contexto_data = {}
        if textbook.contexto_local:
            contexto_data = {
                "comunidad": textbook.contexto_local.comunidad,
                "lengua_originaria": textbook.contexto_local.lengua_originaria,
                "problematica_local": textbook.contexto_local.problematica_local,
                "saberes_comunitarios": textbook.contexto_local.saberes_comunitarios or [],
                "proyectos_sugeridos": textbook.contexto_local.proyectos_sugeridos or []
            }

        trimestres_list = []
        for t in textbook.trimestres:
            secuencias_list = []
            for s in t.secuencias:
                lessons_list = []
                for lesson in s.lessons:
                    lessons_list.append({
                        "numero": lesson.number,
                        "titulo": lesson.title,
                        "secciones": {
                            "inicio": lesson.section_inicio,
                            "desarrollo": lesson.section_desarrollo,
                            "cierre": lesson.section_cierre
                        },
                        "actividades_sugeridas": lesson.activities
                    })

                secuencias_list.append({
                    "id": s.id,
                    "numero": s.number,
                    "titulo": s.title,
                    "objetivos": s.objectives,
                    "status": s.status.value if s.status else None,
                    "campo_formativo_principal": s.campo_formativo_principal.value if s.campo_formativo_principal else None,
                    "campos_formativos_vinculados": [c.value for c in s.campos_formativos_vinculados] if s.campos_formativos_vinculados else [],
                    "contenidos_sinteticos_ids": s.contenidos_sinteticos_ids or [],
                    "pda_ids": s.pda_ids or [],
                    "ejes_articuladores": [e.value for e in s.ejes_articuladores] if s.ejes_articuladores else [],
                    "proyecto_vinculado": s.proyecto_vinculado,
                    "lecciones": lessons_list
                })

            trimestres_list.append({
                "numero": t.number,
                "titulo": t.title,
                "metas": t.goals,
                "secuencias": secuencias_list
            })

        conaliteg_payload = {
            "metadata_sep": {
                "institucion": "CONALITEG",
                "programa": "Plan de Estudio 2022 (Nueva Escuela Mexicana)",
                "formato_version": "1.0.0",
                "libro_id": textbook.id,
                "titulo": textbook.title,
                "materia_eje": textbook.subject,
                "grado": textbook.grade,
                "fase": textbook.fase.value if textbook.fase else None,
                "estado_general": textbook.status.value if textbook.status else None,
                "fecha_generacion": textbook.created_at.isoformat() if hasattr(textbook.created_at, "isoformat") else str(textbook.created_at),
                "contexto_local": contexto_data
            },
            "estructura_curricular": {
                "total_trimestres": len(trimestres_list),
                "trimestres": trimestres_list
            }
        }

        return conaliteg_payload
