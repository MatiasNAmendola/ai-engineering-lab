/**
 * flue_demo.ts
 * 
 * Ejemplo de uso de Flue (@flue/runtime): Framework de agentes por el equipo de Astro.
 * Demuestra el patrón createAgent con sandbox local y configuración de modelo.
 * 
 * Nota: Flue está diseñado principalmente como servidor (vía `flue dev`),
 * pero aquí usamos las primitivas directamente para fines educativos.
 * 
 * Requisito: Bun >= 1.4.0 o Node.js 22+ (por node:sqlite)
 * 
 * Ejecución: bun run flue_demo.ts
 */

// 1. Verificamos si hay API key disponible
const apiKey = process.env.GEMINI_API_KEY;

async function runDemo() {
  console.log("=== Demo de Flue (@flue/runtime) - Framework de Agentes ===\n");

  const taskPayload = {
    code: `function processData(data: any) { return data.map(x => x * 2); }`,
    language: 'typescript'
  };

  console.log("Tarea a procesar:");
  console.log(`   Código: ${taskPayload.code}`);
  console.log(`   Lenguaje: ${taskPayload.language}\n`);

  // 2. Intentamos cargar Flue dinámicamente (requiere node:sqlite)
  let flueAvailable = false;
  
try {
    const { createAgent } = await import('@flue/runtime');
    const { local } = await import('@flue/runtime/node');
    flueAvailable = true;
    
    console.log("[Flue] Módulo cargado exitosamente.\n");

    // 3. Definimos un agente usando createAgent de Flue
    // El inicializador recibe un contexto y retorna la configuración del runtime
    createAgent(async (ctx) => {
      console.log(`   [Flue] Inicializando agente con payload: ${JSON.stringify(ctx.payload)}`);
      
      return {
        model: 'google/gemini-1.5-flash',
        sandbox: local({ cwd: process.cwd() }),
        system: 'Eres un especialista en revisión de código TypeScript. Analiza el código proporcionado y sugiere mejoras.',
      };
    });

    if (apiKey) {
      console.log("[Flue] API key detectada. Agente creado con createAgent().\n");
      
      console.log("   Configuración del agente:");
      console.log("   - Modelo: google/gemini-1.5-flash");
      console.log("   - Sandbox: local() - acceso al filesystem del host");
      console.log("   - System prompt: Especialista en code review TypeScript");
      
      // Nota: La ejecución real requiere el servidor Flue o un harness configurado
      console.log("\n   [Nota] La ejecución directa requiere `flue dev` o configuración de harness.");
      console.log("   Mostrando análisis simulado para fines educativos.\n");
      
    } else {
      console.log("[Nota] No se encontró GEMINI_API_KEY. Mostrando estructura del agente.\n");
      
      console.log("   Agente creado con createAgent():");
      console.log("   - El inicializador se ejecuta cada vez que el runtime inicializa un harness");
      console.log("   - Retorna configuración con modelo, sandbox y herramientas");
      console.log("   - El sandbox local() provee acceso controlado al filesystem\n");
    }
    
  } catch (error: any) {
    console.log(`[Nota] No se pudo cargar @flue/runtime: ${error.message}`);
    console.log("   Esto es esperado en Bun < 1.4.0 (falta node:sqlite).\n");
  }

  // 4. Explicamos el flujo de trabajo típico
  console.log("Flujo de trabajo típico con Flue:");
  console.log("   1. createAgent() define el perfil del agente (modelo, sandbox, tools)");
  console.log("   2. El sandbox local() provee acceso controlado al filesystem");
  console.log("   3. En producción: `flue dev` levanta el servidor y expone endpoints");
  console.log("   4. Los clientes interactúan vía HTTP/WebSocket con el agente\n");
  
  if (flueAvailable) {
    console.log("   [Flue] Módulo disponible: Las primitivas están listas para usar.");
    console.log("   [Flue] Para ejecución real, usar `flue dev` o configurar un harness.\n");
  }

  showMockResponse();
}

function showMockResponse() {
  console.log("Análisis de código (simulado):");
  console.log("   El código usa `any` como tipo de parámetro, lo cual reduce la seguridad de tipos.");
  console.log("   Recomendación: Definir una interfaz o tipo genérico para `data`.");
  console.log("   Ejemplo: function processData<T extends number>(data: T[]): T[]");
}

runDemo().catch(console.error);
