# Playbook de Presentación del System Design para Stakeholders

Este documento proporciona una guía estructurada para presentar y defender el diseño de arquitectura del **Textbook Generator** frente a stakeholders técnicos (CTO, arquitectos) y no técnicos (Founders, Product Managers, directores).

La clave de esta sesión es posicionarte como un **Arquitecto de IA pragmático** que no solo comprende los modelos de lenguaje, sino también el impacto financiero, la estabilidad del producto, la gobernanza de datos y la alineación con los objetivos de negocio.

---

## 🏛️ Filosofía General: El "Traductor" de Arquitectura

Para cada decisión técnica que propongas, debes poder explicarla en dos niveles:

| Concepto Técnico | Traducción para Stakeholders de Negocio |
| :--- | :--- |
| **Clean Architecture (Hexagonal)** | *"Separamos las reglas del negocio de los proveedores de IA. Si mañana Gemini es superado por Claude o queremos usar un modelo local, el reemplazo toma horas en lugar de semanas de refactorización."* |
| **SQLite para Catálogos Relacionales** | *"En lugar de pagar e integrar una costosa base de datos vectorial adicional que introduce latencia de red y respuestas aproximadas, usamos una base local estructurada que garantiza que los contenidos de la SEP se apliquen con 100% de precisión y costo cero."* |
| **PydanticAI (Tipado Estático)** | *"Evitamos el impuesto de complejidad (complexity tax) de frameworks pesados como LangChain. Nuestro código es simple, fácil de depurar por cualquier desarrollador del equipo y asegura que el formato del libro nunca se rompa."* |
| **Context Caching de Gemini** | *"La IA recuerda los lineamientos curriculares en su memoria de corto plazo. Esto reduce los costos de procesamiento en un 80% y reduce el tiempo de espera del usuario final de segundos a milisegundos."* |
| **Human-in-the-Loop (HITL) Queue** | *"Establecemos una red de seguridad. Ningún libro con errores pedagógicos o de lenguaje inapropiado para niños llegará al aula; la IA lo detiene y un docente humano lo aprueba o corrige desde un dashboard."* |

---

## 🗺️ Guía de Presentación en 5 Pasos

Durante la sesión de pizarrón o diseño en vivo, sigue esta estructura lógica para guiar la conversación:

### Paso 1: Acotar el Alcance y Definir el Problema (El "Por qué" y "Para quién")
Antes de proponer tecnologías, demuestra criterio de producto y empatía con el usuario final.

*   **Restricciones Clave:**
    *   **Audiencia:** Niñas y niños de primer grado (6 años). Exige oraciones cortas (≤12 palabras), vocabulario simple y soporte visual muy descriptivo.
    *   **Estructura fija:** 3 Trimestres $\rightarrow$ 6 Secuencias Didácticas por trimestre $\rightarrow$ 3 Fases pedagógicas obligatorias por secuencia (Inicio, Desarrollo, Cierre).
    *   **Riesgo de contexto:** No se puede generar el libro completo en una sola llamada de LLM (se excedería la ventana de contexto, aumentaría la latencia y las alucinaciones).
*   **Mensaje Clave:**
    > *"Para que el contenido sea viable en un aula de primer grado de primaria, estructuramos el workflow de forma determinista mediante código de backend. El código controla las etapas y la jerarquía, mientras que la IA actúa únicamente como un motor creativo de redacción a nivel de lección individual."*

---

### Paso 2: Modelo de Datos y RAG Curricular (La Base de la Confianza)
Cómo garantizamos que el generador cumpla con los lineamientos del Programa Sintético oficial de la SEP mexicana (Nueva Escuela Mexicana).

*   **El Enfoque Pragmático:**
    *   Los contenidos y Procesos de Desarrollo de Aprendizaje (PDA) de la SEP son estáticos durante el ciclo escolar y de volumen acotado (<1000 registros por fase).
    *   Se indexan relacionalmente en una base de datos relacional estándar (SQLite).
    *   Se recuperan semánticamente utilizando filtros exactos de SQL (e.g. `WHERE campo_formativo = 'Lenguajes' AND fase = 'FASE_2'`).
*   **Mensaje Clave:**
    > *"El mayor temor de un colegio es que el material no cumpla con el programa oficial de la SEP. Para garantizar un cumplimiento del 100%, evitamos la imprecisión de las búsquedas vectoriales puras en esta etapa. Usamos una base de datos estructurada local para inyectar al prompt de la IA los objetivos regulatorios específicos que debe cubrir en cada secuencia didáctica."*

---

### Paso 3: Arquitectura de Generación Híbrida (La Estructura)
El balance entre control determinista y razonamiento cognitivo.

```
                  ┌───────────────────────────────┐
                  │      Orquestador Python       │ (Controla el workflow y la estructura)
                  └──────────────┬────────────────┘
                                 │
                   ┌─────────────┴─────────────┐
                   ▼                           ▼
      ┌─────────────────────────┐ ┌─────────────────────────┐
      │   Agente de Estructura  │ │    Agente Redactor      │
      │    (Diseña el Outline)  │ │  (Genera las Lecciones) │
      └────────────┬────────────┘ └────────────┬────────────┘
                   │                           │
                   ▼                           ▼
        [JSON: 3T x 6 Secuencias]   [JSON: Inicio/Desarrollo/Cierre]
```

*   **Detalles Técnicos:**
    *   **Outline Agent:** Genera la macro-estructura (trimestres y temas).
    *   **Content Generator Agent:** Redacta el contenido estructurado bajo el contrato de Inicio, Desarrollo y Cierre.
    *   **Interface Segregation:** El servicio de agentes NEM (`NEMAgentService`) está separado del servicio original para soportar Campos Formativos y Ejes Articuladores transversales sin acoplamiento.
*   **Mensaje Clave:**
    > *"Dividimos el sistema en dos capas: el control del flujo (esqueleto) es código estructurado Python que garantiza consistencia. La IA (músculo) solo se encarga de rellenar el texto en base a contratos estrictos (schemas de Pydantic). Si la IA alucina, falla la lección individual, pero nunca se desmorona la estructura del libro."*

---

### Paso 4: Garantías de Calidad y Human-in-the-Loop (Mitigación del Riesgo)
Cómo implementamos filtros de seguridad y auditoría en producción.

*   **El Proceso de Calidad:**
    *   **Filtro de Vocabulario:** Análisis heurístico de complejidad de oraciones para asegurar que se adecúe al desarrollo de niños de 6 años.
    *   **LLM-as-a-Judge:** Un agente juez evalúa la alineación curricular de los PDA y ejes transversales.
    *   **Umbral Gating:** Si el score de calidad de la secuencia didáctica cae por debajo de **0.85/1.00**, se rutea de forma asíncrona a la cola `PENDING_REVIEW` y se detiene su disponibilidad.
*   **Mensaje Clave:**
    > *"La IA no publica directamente al aula. Implementamos un 'guardián automático' que evalúa cada lección generada. Si detecta vocabulario muy complejo o falta de cobertura de un objetivo SEP, el sistema desvía la lección a una consola de revisión humana. Un docente pedagogo la corrige y aprueba en minutos. Además, esta corrección humana se guarda para entrenar y mejorar el comportamiento del modelo futuro (flywheel de aprendizaje)."*

---

### Paso 5: Optimización Financiera y Caching (Viabilidad Financiera)
El modelo de negocio y el control de costos operativos de tokens de IA.

*   **La Estrategia de Caching (ADR-003):**
    *   **NO cachear lecciones generadas:** Provoca plagio de contenido entre colegios distintos y persiste errores o alucinaciones pasadas.
    *   **SÍ cachear contexto (Gemini Context Caching):** Dado que secuencias consecutivas inyectan los mismos lineamientos de la SEP, los tokens se mantienen en el servidor de inferencia, cobrando tarifas de lectura de caché un **80% más baratas** y acelerando el tiempo de respuesta.
*   **Mensaje Clave:**
    > *"No queremos que dos colegios reciban exactamente el mismo libro personalizado, por lo que no guardamos las lecciones en caché. En su lugar, cacheamos el contexto normativo de la SEP en los servidores de la IA. Esto acelera el tiempo de carga del usuario final a milisegundos y reduce la factura de tokens en un 80%."*

---

## ⏱️ Guión de Explicación Rápida (Pitch de 5 Minutos)

Este guión sigue la regla de **"1 minuto por paso"**. Úsalo para mantener el control y la atención de la audiencia en una presentación corta:

*   **Minuto 1: El Desafío y el Contexto (Usuario y Regulación)**
    > *"Diseñamos un generador de libros para **niños de 6 años** alineado a la **SEP mexicana**. El gran desafío de ingeniería aquí no es la IA, es la **adecuación pedagógica y el límite físico**. No podemos pedirle a un LLM que escriba un libro entero de un tirón porque alucinaría y rompería la ventana de contexto. Por eso, dividimos el problema en un workflow determinista controlado por código: 3 trimestres, con 6 secuencias didácticas cada uno."*
*   **Minuto 2: La Base de Datos y el RAG Curricular (SQLite vs. Vectorial)**
    > *"Para garantizar que el libro cumpla con el programa de la SEP, inyectamos los contenidos oficiales en tiempo real. **Aquí tomamos una decisión pragmática:** en lugar de pagar y configurar una costosa base de datos vectorial (como Pinecone), que introduce latencia de red y respuestas imprecisas, usamos **SQLite local**. Los lineamientos oficiales son estáticos y pequeños (<1000 registros). Al usar filtros relacionales SQL exactos, garantizamos 100% de precisión de objetivos a costo cero."*
*   **Minuto 3: Generación Híbrida y Clean Architecture (PydanticAI)**
    > *"Separamos el sistema usando **Clean Architecture**. La orquestación del flujo y el esqueleto del libro se manejan con código duro Python. Para interactuar con la IA, usamos **PydanticAI** en lugar de LangChain. ¿Por qué? Para evitar el 'complexity tax' (impuesto de complejidad) de LangChain. PydanticAI nos da validación de esquemas (JSON) nativa y tipado estático, asegurando que la IA devuelva exactamente la estructura de lección requerida (Inicio, Desarrollo y Cierre) sin romper el frontend."*
*   **Minuto 4: Control de Calidad y Human-in-the-Loop (HITL)**
    > *"La IA nunca escribe directo al aula. Al generar cada secuencia didáctica, un agente evaluador independiente (**LLM-as-a-Judge**) califica la lección del 0 al 1 en alineación curricular y vocabulario infantil. Si la calificación es menor a **0.85**, el sistema frena la secuencia de forma asíncrona y la envía a una cola de revisión humana. Un docente la corrige desde un dashboard y esa corrección vuelve a alimentar nuestro dataset para mejorar el modelo."*
*   **Minuto 5: Viabilidad Financiera y Context Caching**
    > *"Para producción, decidimos **no cachear lecciones** en Redis para evitar que distintas escuelas tengan libros idénticos y persistir alucinaciones. Sin embargo, como secuencias consecutivas usan las mismas reglas de la SEP, implementamos **Context Caching de Gemini**. La IA mantiene las reglas de la SEP en su memoria de corto plazo, lo que reduce el tiempo de generación a milisegundos y **baja el costo de tokens en un 80%**, haciendo que el negocio sea sumamente rentable."*

---

## 🚨 Respuestas Estratégicas ante Preguntas Difíciles

### 1. "Las IAs alucinan. ¿Cómo aseguramos que las lecciones de matemáticas enseñen sumas correctas?"
> **Respuesta:** *"No delegamos el control del conocimiento a la creatividad del prompt. Primero, inyectamos los datos concretos de las operaciones a realizar desde nuestra base relacional. Segundo, el Agente Juez corre pruebas matemáticas básicas de forma determinista sobre el JSON generado. Tercero, si el score baja de 0.85, el libro se bloquea en la cola de revisión humana hasta que un profesor valide los ejercicios."*

### 2. "¿Por qué usar PydanticAI y no LangChain/LangGraph que ya tiene todo integrado?"
> **Respuesta:** *"LangChain introduce una sobrecarga operativa y una deuda técnica pesada (LCEL, wrappers de mensajes complejos). En un entorno de producción, depurar errores enterrados bajo decenas de abstracciones de LangChain consume horas. PydanticAI nos da tipado estático nativo de Python, validación de schemas directa en Pydantic y stack traces limpios que aceleran el desarrollo. Además, la generación de libros es un flujo jerárquico lineal, no requiere de los ciclos complejos que justificarían pagar el costo de complejidad de LangGraph."*

### 3. "¿Qué pasa si la SEP cambia el programa oficial mañana en el Diario Oficial (DOF)?"
> **Respuesta:** *"Nuestra arquitectura es desacoplada. Todo el catálogo del programa oficial está aislado en un repositorio de infraestructura (`NEMRepository`). Si la SEP publica una reforma curricular, solo tenemos que actualizar el archivo de siembra (`seed_data`) de la base de datos y correr la migración de SQLite. El motor del workflow de la aplicación y las llamadas a los agentes siguen funcionando exactamente igual."*

---

## 🔗 Relación con Documentos del Proyecto

Este playbook consolida el conocimiento técnico detallado en las siguientes guías de la Wiki:
*   [Diseño del Sistema y ADRs (01-03)](./09_system_design_textbook_generator.md): Detalles técnicos de base de datos, caché y orquestación cognitiva.
*   [Análisis de Gap NEM/SEP](./10_nem_sep_alineacion.md): Detalles de la reforma curricular de la SEP mexicana.
*   [ADR-004: Integración NEM](./11_adr_004_nem_integration.md): Justificación y alternativas rechazadas para la capa de alineación oficial.
*   [Gobernanza y Seguridad de Agentes](./05_governance_and_security.md): Patrones de protección de APIs e inyecciones de código.
