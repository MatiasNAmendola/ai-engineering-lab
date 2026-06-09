/**
 * pi_demo.ts
 * 
 * Ejemplo de uso de Pi (@earendil-works/pi-coding-agent): SDK para agentes de codificación.
 * Demuestra createAgentSession con persistencia en memoria y suscripción a eventos.
 * 
 * Pi es un agente de codificación terminal-first con herramientas integradas
 * (read, write, edit, bash, grep, find, ls) diseñadas para tareas de desarrollo.
 * 
 * Ejecución: bun run pi_demo.ts
 */

import { 
  createAgentSession,
  AuthStorage,
  ModelRegistry,
  SessionManager,
  SettingsManager 
} from '@earendil-works/pi-coding-agent';

// 1. Verificamos si hay API key disponible
const apiKey = process.env.GEMINI_API_KEY;

async function runDemo() {
  console.log("=== Demo de Pi (@earendil-works/pi-coding-agent) - Agente de Codificación ===\n");

  const taskDescription = "Crear un archivo README.md con documentación básica del proyecto";
  console.log(`Tarea: ${taskDescription}\n`);

  if (apiKey) {
    try {
      console.log("[Pi] API key detectada. Creando sesión real...\n");

      // 2. Configuramos los componentes de la sesión
      console.log("   Configurando componentes:");
      
      const authStorage = AuthStorage.inMemory();
      console.log("   - AuthStorage: almacenamiento de credenciales en memoria");
      
      const modelRegistry = ModelRegistry.create(authStorage);
      console.log("   - ModelRegistry: registro de modelos disponibles");
      
      const sessionManager = SessionManager.inMemory();
      console.log("   - SessionManager: persistencia de sesión en memoria");
      
      const settingsManager = SettingsManager.inMemory();
      console.log("   - SettingsManager: configuración en memoria\n");

      // 3. Creamos la sesión del agente
      console.log("   Creando sesión con createAgentSession()...");
      const { session } = await createAgentSession({
        cwd: process.cwd(),
        authStorage,
        modelRegistry,
        sessionManager,
        settingsManager,
      });
      console.log("   Sesión creada exitosamente\n");

      // 4. Nos suscribimos a los eventos para streaming
      console.log("   Suscribiéndose a eventos de la sesión...");
      const unsubscribe = session.subscribe((event) => {
        switch (event.type) {
          case 'turn_start':
            console.log("   [Evento] Turno iniciado");
            break;
          case 'turn_end':
            console.log("   [Evento] Turno finalizado");
            break;
          case 'tool_execution_start':
            console.log(`   [Evento] Herramienta invocada`);
            break;
          case 'message_update':
            console.log(`   [Mensaje] Actualización recibida`);
            break;
        }
      });
      console.log("   Suscripción activa\n");

      // 5. Enviamos el prompt al agente
      console.log("   Enviando prompt al agente...\n");
      await session.prompt(taskDescription);
      
      console.log("\n   Tarea completada.");
      
      // 6. Limpiamos recursos
      unsubscribe();
      session.dispose();
      console.log("   Sesión finalizada y recursos liberados.\n");

    } catch (error: any) {
      console.log(`\n[Error] ${error.message}`);
      console.log("   Mostrando flujo simulado como fallback...\n");
      showMockResponse();
    }
  } else {
    console.log("[Nota] No se encontró GEMINI_API_KEY. Mostrando flujo simulado.\n");
    
    console.log("Flujo de trabajo típico con Pi:");
    console.log("   1. AuthStorage.inMemory() - Credenciales efímeras para la sesión");
    console.log("   2. ModelRegistry.create() - Descubre modelos configurados");
    console.log("   3. SessionManager.inMemory() - Sesión sin persistencia en disco");
    console.log("   4. SettingsManager.inMemory() - Configuración por defecto");
    console.log("   5. createAgentSession() - Crea la sesión con herramientas integradas");
    console.log("   6. session.subscribe() - Escucha eventos en tiempo real");
    console.log("   7. session.prompt() - Envía tareas al agente");
    console.log("   8. session.dispose() - Libera recursos al finalizar\n");
    
    showMockResponse();
  }
}

function showMockResponse() {
  console.log("Ejecución simulada del agente Pi:");
  console.log("   [Pi] Analizando tarea: Crear README.md");
  console.log("   [Pi] Herramienta: write_file");
  console.log("   [Pi] Escribiendo archivo: README.md");
  console.log("   [Pi] Contenido generado: 45 líneas");
  console.log("   [Pi] Tarea completada exitosamente.");
}

runDemo().catch(console.error);
