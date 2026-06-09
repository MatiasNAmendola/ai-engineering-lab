# 10. Alineación NEM/SEP: Análisis Gap y Plan de Evolución

> **Estado**: En implementación  
> **Fase objetivo**: Fase 2 (Primaria 1°-2°)  
> **Referencia**: Programa Sintético SEP (DOF 2023), Nueva Escuela Mexicana  

## 1. Contexto

El [Generador de Libros de Texto](./09_system_design_textbook_generator.md) fue diseñado con Clean Architecture, PydanticAI y un pipeline HITL. Sin embargo, el modelo curricular actual trata las materias como asignaturas aisladas, mientras que la **Nueva Escuela Mexicana (NEM)** exige integración transversal a través de 4 Campos Formativos y 7 Ejes Articuladores.

---

## 2. Lo que está BIEN encaminado

| Aspecto | Estado | Comentario |
|---------|--------|------------|
| Arquitectura Clean + Screaming | Excelente | Separación domain/application/infrastructure |
| Estructura 3 Trimestres × 6 Secuencias | Correcto | Alineado con modelo de trabajo |
| Fases Inicio/Desarrollo/Cierre | Correcto | Estructura pedagógica estándar primaria |
| Human-in-the-Loop (HITL) | Crítico | Umbral 0.85 + cola de revisión docente |
| LLM-as-a-Judge (Evaluación dual) | Correcto | Alineación curricular + Adecuación edad |
| Mocks determinísticos para testing | Bueno | Permite CI/CD sin API keys |
| Context Caching strategy (ADR-003) | Visionario | Ahorra 80% costos en producción |

---

## 3. Gaps Críticos vs. Programa Sintético SEP (Fase 2)

### 3.1 Campos Formativos integrados

**Problema**: El modelo trata "Español" como asignatura aislada. NEM exige integración transversal:
- Lenguajes
- Saberes y Pensamiento Científico
- Ética, Naturaleza y Sociedades
- De lo Humano y lo Comunitario

**Solución**: Nuevo enum `CampoFormativo` + campo `campo_formativo_principal` y `campos_formativos_vinculados` en `Secuencia`.

### 3.2 Programa Sintético: Contenidos + PDA

**Problema**: Los `CurricularRequirement` actuales son genéricos. Se necesitan contenidos específicos del Programa Sintético + Procesos de Desarrollo de Aprendizaje (PDA) por campo formativo y fase.

**Solución**: Nuevos modelos `ContenidoProgramaSintetico` y `ProcesoDesarrolloAprendizaje` con seed data real del DOF 2023.

### 3.3 Ejes Articuladores

**Problema**: 7 ejes (pensamiento crítico, interculturalidad, igualdad de género, vida saludable, inclusión, lectura/escritura, artes/estética) deben permear cada secuencia.

**Solución**: Enum `EjeArticulador` + mapeo por secuencia.

### 3.4 Fases de aprendizaje (no grados)

**Problema**: El modelo usa `grade: 1` pero NEM opera en Fase 2 (1°-2° primaria).

**Solución**: Enum `FaseAprendizaje` con 6 fases oficiales.

### 3.5 Programa Analítico (contextualización)

**Problema**: El sistema genera "receta nacional" pero NEM exige que el docente contextualice.

**Solución**: Modelo `ContextoLocal` + caso de uso `ContextualizeTextbookUseCase`.

### 3.6 Evaluación formativa

**Problema**: El juez evalúa alineación/edad pero falta rúbrica de PDA.

**Solución**: Nuevo agente evaluador de PDA + evaluación por proceso.

### 3.7 Libros oficiales NEM 2024-2025

**Problema**: La estructura real usa Proyectos de Aula/Comunitarios/Escolares + Múltiples Lenguajes + Nuestros Saberes. El modelo "1 materia = 1 libro" contradice la integración NEM.

**Solución**: Campo `proyecto_vinculado` en `Secuencia` + caso de uso `GenerateProyectoIntegradorUseCase`.

---

## 4. Diseño Implementado

### 4.1 Modelo de Datos Evolucionado

```
domain/models.py:
  + CampoFormativo (enum: 4 campos)
  + EjeArticulador (enum: 7 ejes)
  + FaseAprendizaje (enum: 6 fases)
  + ContenidoProgramaSintetico (contenido oficial por campo/fase)
  + ProcesoDesarrolloAprendizaje (PDA por contenido)
  + EjeArticuladorTransversal (mapeo ejes por secuencia)
  + ContextoLocal (programa analítico)
  ~ Secuencia (nuevos campos NEM)
```

### 4.2 Pipeline NEM

```
Input: Grado, Campo Formativo, Contexto Escolar
  → Recuperar Programa Sintético Fase 2
  → Seleccionar Contenidos + PDA por Trimestre
  → Agente Outline: 3T × 6S
  → Inyectar Ejes Articuladores + Proyecto
  → Generar Lecciones Inicio/Desarrollo/Cierre
  → Juez: Alineación Contenidos+PDA + Ejes + Edad
  → Score ≥ 0.85? → Aprobado / HITL
```

### 4.3 Nuevos Casos de Uso

| Caso de Uso | Propósito |
|-------------|-----------|
| `ContextualizeTextbookUseCase` | Programa Analítico: adaptar a contexto local |
| `MapContenidosPDAUseCase` | Mapear contenidos sintéticos + PDA a secuencias |
| `EvaluatePDAAlignmentUseCase` | Juez evalúa cobertura PDA + ejes articuladores |
| `GenerateProyectoIntegradorUseCase` | Generar proyecto Aula/Escolar/Comunitario |

### 4.4 Seed Data Real SEP

Archivo `infrastructure/database/seed_nem_fase2.py` con contenidos y PDA extraídos del Programa Sintético Fase 2 (DOF 2023), cubriendo los 4 campos formativos.

---

## 5. Checklist de Validación SEP/NEM (Definition of Done)

| Criterio | Validación |
|----------|------------|
| Cobertura Programa Sintético | 100% contenidos Fase 2 mapeados a ≥1 secuencia |
| PDA desarrollados | Cada secuencia tiene ≥2 PDA asociados |
| Ejes articuladores | Cada eje aparece en ≥3 secuencias |
| Integración curricular | ≥60% secuencias vinculan ≥2 campos formativos |
| Proyecto integrador | Cada trimestre cierra con proyecto |
| Lenguaje 6 años | Oraciones ≤ 12 palabras |
| Ilustraciones | Cada lección tiene ≥2 bracketed visual cues |
| Contextualización | Programa Analítico generado |
| Evaluación formativa | Rúbrica por PDA |

---

## 6. Fixes Técnicos Aplicados

| Archivo | Problema | Fix |
|---------|----------|-----|
| `api.py` | `Field(..., example=...)` deprecated | Migrado a `json_schema_extra` |
| `main.py` | `@app.on_event("startup")` deprecated | Migrado a lifespan async context manager |

---

## 7. Enlaces

- [Diseño del Sistema](./09_system_design_textbook_generator.md)
- [ADR Pipeline](./08_pipeline_architecture_adr.md)
- [Domain Models](../textbook_generator/domain/models.py)
- [Seed NEM Fase 2](../textbook_generator/infrastructure/database/seed_nem_fase2.py)
