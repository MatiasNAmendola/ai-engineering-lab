import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from textbook_generator.domain.models import (
    CampoFormativo, EjeArticulador, FaseAprendizaje,
    ContenidoProgramaSintetico, ProcesoDesarrolloAprendizaje, Secuencia, Lesson
)
from textbook_generator.infrastructure.agents.nem_agents import NEMOutlineAgentService


def test_nem_agent_outline_mock():
    service = NEMOutlineAgentService()
    contenidos = [ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.LENGUAJES, fase=FaseAprendizaje.FASE_2,
        codigo="CF-LNG-F2-C01", descripcion="Expresa ideas mediante el lenguaje oral."
    )]
    outline = service.generate_nem_outline(
        campo_formativo=CampoFormativo.LENGUAJES, fase=FaseAprendizaje.FASE_2, contenidos=contenidos
    )
    assert outline.title is not None
    assert outline.fase == FaseAprendizaje.FASE_2
    assert len(outline.trimestres) == 3
    for t in outline.trimestres:
        assert len(t.secuencias) == 6


def test_nem_agent_pda_eval_mock():
    service = NEMOutlineAgentService()
    secuencia = Secuencia(
        trimestre_id=1, number=1, title="El agua en mi comunidad", objectives="Analizar el uso del agua",
        lessons=[Lesson(secuencia_id=1, number=1, title="L1", section_inicio="I", section_desarrollo="D", section_cierre="C", activities="A")]
    )
    pda_list = [
        ProcesoDesarrolloAprendizaje(id=1, contenido_id=1, fase=FaseAprendizaje.FASE_2, descripcion="PDA 1"),
        ProcesoDesarrolloAprendizaje(id=2, contenido_id=1, fase=FaseAprendizaje.FASE_2, descripcion="PDA 2"),
    ]
    ejes = [EjeArticulador.PENSAMIENTO_CRITICO, EjeArticulador.VIDA_SALUDABLE]
    result = service.evaluate_pda_coverage(secuencia, pda_list, ejes)
    assert result.cobertura_score > 0
    assert result.ejes_score > 0
    assert len(result.pda_results) == 2
    assert result.pda_results[0].nivel_logro == "Logrado"


def test_nem_agent_all_campos():
    service = NEMOutlineAgentService()
    for campo in CampoFormativo:
        outline = service.generate_nem_outline(campo_formativo=campo, fase=FaseAprendizaje.FASE_2, contenidos=[])
        assert len(outline.trimestres) == 3
        assert all(len(t.secuencias) == 6 for t in outline.trimestres)
