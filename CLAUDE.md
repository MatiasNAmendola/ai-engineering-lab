# Guía de Mantenimiento de la Wiki (CLAUDE.md)

Este archivo define los lineamientos operativos y arquitectónicos para cualquier Agente de IA que interactúe con este repositorio. Está diseñado siguiendo la metodología de **LLM Wiki / Obsidian Vault** de Andrej Karpathy.

---

## 🗂️ Estructura del Directorio (Vault Schema)

El conocimiento se organiza estrictamente en las siguientes carpetas:
*   `/raw`: Carpeta de entrada inmutable. Contiene las notas brutas, transcripciones de YouTube, requisitos de clientes o textos de origen sin procesar. No se debe modificar su contenido histórico, solo agregar nuevas entradas.
*   `/wiki`: El núcleo procesado y enlazado. Contiene los artículos de Markdown estructurados y limpios creados y actualizados por la IA.
    *   Los archivos en `/wiki` deben usar enlaces relativos (e.g., `[RAG y PGVector](./02_rag_postgres_pgvector.md)`) para referenciar otras notas.
    *   No deben contener rutas de sistemas locales absolutas (como `/Users/...`).
*   `/external`: Carpeta ignorada en Git (`.gitignore`). Contiene los clones de repositorios de código de referencia de terceros para análisis local.

---

## 🧠 Flujo de Compilación (Compile Workflow)

1.  **Ingesta (Intake)**: Leer nuevos archivos añadidos a `/raw`.
2.  **Destilación e Indexación**: Identificar conceptos técnicos clave, frameworks o arquitecturas.
3.  **Compilación**: Crear o actualizar los artículos correspondientes en `/wiki`.
    *   **Enlazar**: Crear enlaces bidireccionales (*backlinks*) hacia otras páginas de la `/wiki`.
    *   **Conectar al Código**: Si un concepto técnico está implementado en las primitivas o frameworks, añadir un enlace relativo al archivo de código (e.g., `[01_llm_inference_scratch.py](./00_primitives_scratch/01_llm_inference_scratch.py)`).
4.  **Mantener Coherencia**: Si una actualización en `/raw` contradice o complementa información existente en `/wiki`, se debe fusionar y reescribir el archivo de la wiki correspondiente para mantener una versión consolidada de la verdad (*"Stop Retrieving, Start Compiling"*).

---

## 💻 Guías de Codificación (AI Coding Rules)

Al interactuar con los scripts de Python en `00_primitives_scratch/` o `01_python_frameworks/`, el agente debe seguir las reglas de desarrollo asistido por IA de Karpathy:

1.  **Think First**: Antes de modificar cualquier archivo, proponer un plan de acción y confirmar suposiciones. Preguntar al usuario ante cualquier ambigüedad.
2.  **Simplicidad**: Escribir el mínimo código posible. Cero abstracciones especulativas o arquitecturas complejas de clases vacías.
3.  **Cambios Quirúrgicos**: Modificar estrictamente las líneas de código asociadas al objetivo. Respetar el formato y no alterar comentarios de código adyacente.
4.  **Consistencia**: Mimetizar el estilo y las convenciones del código existente en el repositorio.

---

## ⚙️ Comandos de Ejecución de Referencia

Al asistir al desarrollador en pruebas locales, utilizar obligatoriamente los siguientes comandos según el entorno:

*   **Python (uv)**:
    *   Ejecutar script: `uv run <ruta_al_script.py>`
    *   No instalar virtualenvs manualmente; `uv run` resuelve las dependencias inline.
*   **TypeScript/Node (bun)**:
    *   Instalar dependencias: `bun install`
    *   Ejecutar script: `bun run <ruta_al_script.ts>`
*   **Go (goenv / go)**:
    *   Ejecutar módulo: `go run <ruta_al_archivo.go>` o `go build` en el directorio.

