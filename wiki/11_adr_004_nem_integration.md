# ADR-004: Alineación NEM/SEP vía Capa de Integración de Campos Formativos

> **Estado**: Accepted  
> **Fecha**: 2025-06-09  
> **Decisores**: Equipo de Arquitectura  
> **Referencia**: [Alineación NEM/SEP](./10_nem_sep_alineacion.md), [Diseño del Sistema](./09_system_design_textbook_generator.md)

---

## Contexto

El sistema de generación de libros de texto fue diseñado originalmente con un modelo curricular basado en asignaturas aisladas (Español, Matemáticas, etc.). Sin embargo, la **Secretaría de Educación Pública (SEP)** establece a través del **Programa Sintético** (DOF 2023) de la **Nueva Escuela Mexicana (NEM)** que la enseñanza primaria debe organizarse en **4 Campos Formativos integrados**, permeados por **7 Ejes Articuladores** transversales, con contenidos y Procesos de Desarrollo de Aprendizaje (PDA) específicos por fase educativa.

Los requerimientos regulatorios que impulsaron esta decisión:

1. **Campos Formativos integrados**: La SEP exige que una secuencia didáctica vincule múltiples campos (Lenguajes, Saberes y Pensamiento Científico, Ética Naturaleza y Sociedades, De lo Humano y lo Comunitario), no asignaturas aisladas.
2. **Ejes Articuladores transversales**: Los 7 ejes (pensamiento crítico, interculturalidad, igualdad de género, vida saludable, inclusión, lectura/escritura, artes/estética) deben permear cada secuencia didáctica generada.
3. **Programa Sintético obligatorio**: Los contenidos oficiales y los PDA del DOF 2023 deben estar mapeados por fase de aprendizaje, no por grado individual.
4. **Programa Analítico docente**: Los maestros necesitan una capa de contextualización local para adaptar el contenido nacional a su realidad escolar.

Sin esta integración, el sistema genera materiales que no cumplen con la regulación vigente de la SEP y no son viables para uso en escuelas públicas mexicanas.

---

## Decisión

Introducir una **capa de integración NEM** como extensión del dominio existente, sin reemplazar el modelo curricular original:

### 1. Entidades de dominio de primera clase

Nuevas entidades junto a `CurricularRequirement`:

| Entidad | Propósito |
|---------|-----------|
| `CampoFormativo` | Enum con los 4 campos formativos oficiales |
| `EjeArticulador` | Enum con los 7 ejes articuladores transversales |
| `FaseAprendizaje` | Enum con las 6 fases oficiales SEP |
| `ContenidoProgramaSintetico` | Catálogo de contenidos por campo/fase del DOF 2023 |
| `ProcesoDesarrolloAprendizaje` | PDA asociados a cada contenido sintético |
| `EjeArticuladorTransversal` | Mapeo de ejes por secuencia didáctica |
| `ContextoLocal` | Datos del Programa Analítico del docente |

### 2. Interface Segregation: servicio NEM separado

```
TextbookAgentService (existente)
  → Generación de contenido por materia/asignatura

NEMAgentService (nuevo, puerto separado)
  → Generación alineada a Campos Formativos
  → Evaluación de PDA y Ejes Articuladores
  → Contextualización de Programa Analítico
```

### 3. Persistencia con SQLite (consistencia con ADR-002)

`SQLiteNEMRepository` para almacén de seed data de Programa Sintético y PDA, aprovechando la infraestructura SQLite existente y evitando dependencias externas.

### 4. Compatibilidad hacia atrás

Los campos NEM son **opcionales** en el modelo `Secuencia`. El workflow original basado en asignaturas sigue funcionando sin cambios. La integración NEM se activa cuando se especifica un `CampoFormativo` y una `FaseAprendizaje` en la creación del libro.

---

## Alternativas Consideradas

### Alternativa 1: Reemplazar el modelo de asignaturas por completo

**Descripción**: Eliminar `CurricularRequirement` y `subject` en favor de un modelo 100% basado en Campos Formativos.

**Razón de rechazo**: Rompe la compatibilidad hacia atrás. Los usuarios existentes que generan libros por asignatura perderían funcionalidad. La migración forzada de datos existentes es costosa y arriesgada.

### Alternativa 2: Almacenar datos NEM en un servicio externo

**Descripción**: API REST dedicada para catálogo de Programa Sintético y PDA.

**Razón de rechazo**: Añade latencia de red, dependencia de disponibilidad del servicio, y complejidad de deployment innecesaria para un catálogo de datos estático (<1000 registros por fase). Viola el principio de ADR-002 (SQLite para catálogos pequeños).

### Alternativa 3: Usar el mismo `TextbookAgentService` para NEM

**Descripción**: Extender la interfaz existente con métodos NEM.

**Razón de rechazo**: Viola el **Principio de Segregación de Interfaces (ISP)**. Los tipos de salida son fundamentalmente diferentes: el servicio original genera contenido por asignatura, mientras que NEM requiere generación por campos formativos con evaluación de PDA y ejes articuladores. Acoplar ambas responsabilidades en una sola interfaz genera deuda técnica y dificulta el testing independiente.

---

## Consecuencias

### Positivas

- **Cumplimiento SEP real**: El sistema genera materiales alineados al Programa Sintético Fase 2 vigente.
- **Soporte multi-fase**: La arquitectura soporta las 6 fases de aprendizaje SEP sin cambios estructurales.
- **Programa Analítico**: Habilita contextualización docente por escuela, requisito NEM.
- **Integración curricular genuina**: Secuencias que vinculan múltiples campos formativos y ejes articuladores de forma nativa.
- **Evolución incremental**: El modelo crece sin romper funcionalidad existente.

### Negativas

- **Complejidad de dominio aumentada**: 7 nuevas entidades y 2 tablas nuevas por entidad en la capa de infraestructura.
- **Mantenimiento de seed data**: Los datos PDA del Programa Sintético deben actualizarse manualmente cuando la SEP publique cambios al DOF.
- **Superficie de API expandida**: 4 nuevos endpoints (contexto-local, map-contenidos, evaluate-pda, proyecto) + endpoint de exportación CONALITEG.

### Riesgos

- **Desactualización de PDA**: Si la SEP modifica contenidos o PDA, el seed data quedará obsoleto. Mitigación: documentar el proceso de actualización y versionar el seed data.
- **Cobertura incompleta**: Actualmente solo se implementa Fase 2 (1°-2° primaria). El seed data de fases 3-6 debe implementarse incrementalmente.

---

## Enlaces

- [ADR-001: PydanticAI sobre LangChain](./09_system_design_textbook_generator.md)
- [ADR-002: SQLite sobre DB Vectorial](./09_system_design_textbook_generator.md)
- [ADR-003: Estrategia de Caching](./09_system_design_textbook_generator.md)
- [Análisis Gap NEM/SEP](./10_nem_sep_alineacion.md)
- [Domain Models](../textbook_generator/domain/models.py)
- [Seed Data NEM Fase 2](../textbook_generator/infrastructure/database/seed_nem_fase2.py)
