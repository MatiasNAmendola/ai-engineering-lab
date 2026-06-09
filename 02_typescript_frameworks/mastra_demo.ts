/**
 * mastra_demo.ts
 * 
 * Ejemplo de Agente de IA en TypeScript usando el framework Mastra.
 * Ejecución: bun run mastra_demo.ts
 */

import { Agent } from '@mastra/core/agent';
import { z } from 'zod';

// 1. Definición de una herramienta (Tool) usando Zod para el esquema
const fetchDatabaseSchemaTool = {
  id: 'fetch_database_schema',
  description: 'Obtiene el esquema actual de las tablas de PostgreSQL.',
  inputSchema: z.object({
    table_name: z.string().describe('Nombre de la tabla a inspeccionar.'),
  }),
  execute: async ({ table_name }: { table_name: string }) => {
    console.log(`   [Tool: fetch_database_schema] Leyendo esquema de la tabla: '${table_name}'`);
    return {
      status: 'success',
      columns: ['id (UUID)', 'content (TEXT)', 'embedding (VECTOR_1536)'],
      indices: ['hnsw_vector_idx']
    };
  }
};

// 2. Configuración del Agente de Mastra
const apiKey = process.env.GEMINI_API_KEY;

const agent = new Agent({
  id: 'mastra-architect-agent',
  name: 'MastraArchitectAgent',
  instructions: 'Eres un arquitecto especializado en almacenamiento de datos para Inteligencia Artificial.',
  model: 'google/gemini-1.5-flash',
  tools: {
    // Registramos la herramienta en el agente
    fetch_database_schema: fetchDatabaseSchemaTool,
  }
});

async function runDemo() {
  console.log("=== Demo de Mastra en TypeScript (Ejecutado con Bun) ===");
  
  const prompt = "Revisa el esquema de la tabla document_chunks y recomiéndame si requiere algún índice adicional.";
  console.log(`Consulta del Usuario:\n'${prompt}'\n`);
  
  if (apiKey) {
    try {
      // Si hay API KEY, ejecuta la llamada real usando Mastra
      const response = await agent.generate([{ role: 'user', content: prompt }]);
      console.log("\nRespuesta del Agente Mastra:");
      console.log(response.text);
    } catch (error: any) {
      console.log(`\n[API Error] Ocurrió un error al contactar al proveedor de IA: ${error.message}`);
      showMockResponse();
    }
  } else {
    console.log("\n[NOTE] No se encontró GEMINI_API_KEY. Ejecutando flujo simulado (Mock).");
    await fetchDatabaseSchemaTool.execute({ table_name: 'document_chunks' });
    showMockResponse();
  }
}

function showMockResponse() {
  console.log("\nRespuesta del Agente Mastra (Simulada):");
  console.log(
    "El análisis de la tabla 'document_chunks' indica que posee una columna vectorial " +
    "'embedding' de 1536 dimensiones. Se recomienda aplicar un índice HNSW para optimizar " +
    "la búsqueda por distancia coseno, complementado con un índice GIN sobre la columna " +
    "de metadatos para permitir filtrado híbrido eficiente."
  );
}

runDemo().catch(console.error);
