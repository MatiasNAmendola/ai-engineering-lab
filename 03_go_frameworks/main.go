//gollem_demo.go
//
// Ejemplo de Agente tipado con Gollem (github.com/fugue-labs/gollem).
// Demuestra salida estructurada genérica, herramientas con FuncTool,
// y modo offline con TestModel (sin API key).
//
// Ejecución: go run main.go

package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"

	"github.com/fugue-labs/gollem/core"
)

// 1. Esquema de salida tipado (structured output)
// El agente retornará obligatoriamente una instancia de DatabaseAnalysis.
type DatabaseAnalysis struct {
	Engine        string   `json:"engine" jsonschema:"description=Motor de base de datos recomendado"`
	IsVectorDB    bool     `json:"is_vector_db" jsonschema:"description=Si el motor soporta indexación vectorial"`
	IndexStatus   string   `json:"index_status" jsonschema:"description=Estado actual de los índices"`
	Recommendations []string `json:"recommendations" jsonschema:"description=Recomendaciones de mejora"`
}

// 2. Parámetros de la herramienta FuncTool
type SchemaQueryParams struct {
	TableName string `json:"table_name" jsonschema:"description=Nombre de la tabla a inspeccionar"`
}

// 3. Herramienta tipada que simula consultar el esquema de Postgres
func fetchPostgresSchema(ctx context.Context, params SchemaQueryParams) (string, error) {
	fmt.Printf("   [Herramienta] Consultando esquema de tabla '%s'...\n", params.TableName)
	return fmt.Sprintf("Tabla: %s | Columnas: id(uuid), embedding(vector(1536)), created_at | Índices: hnsw_idx(embedding) ACTIVO", params.TableName), nil
}

func main() {
	fmt.Println("=== Demo de Gollem en Go — Agente con Salida Estructurada ===")
	fmt.Println()

	apiKey := os.Getenv("GEMINI_API_KEY")

	if apiKey == "" {
		fmt.Println("[INFO] No se detectó GEMINI_API_KEY. Usando TestModel (modo offline).")
		fmt.Println()
		runWithTestModel()
	} else {
		fmt.Println("[INFO] GEMINI_API_KEY detectada. Para usar un modelo real,")
		fmt.Println("       descomentar la sección al final del archivo y configurar el provider.")
		fmt.Println()
		runWithTestModel()
	}
}

// runWithTestModel ejecuta el agente con respuestas predefinidas (sin llamadas a LLM).
func runWithTestModel() {
	// 4. TestModel: mock que devuelve respuestas canned sin llamar a ningún LLM
	testModel := core.NewTestModel(
		core.ToolCallResponse("fetch_postgres_schema", `Tabla: embeddings | Columnas: id(uuid), embedding(vector(1536)), created_at | Índices: hnsw_idx(embedding) ACTIVO`),
		core.ToolCallResponse("final_result", `{"engine":"PostgreSQL + pgvector","is_vector_db":true,"index_status":"HNSW activo y saludable","recommendations":["Aumentar ef_search a 100 para mejor recall","Considerar particionado por fecha","Monitorear uso de memoria del índice HNSW"]}`),
	)

	// 5. Herramienta FuncTool con tipado genérico
	schemaTool := core.FuncTool[SchemaQueryParams](
		"fetch_postgres_schema",
		"Consulta el esquema y los índices de una tabla en Postgres",
		fetchPostgresSchema,
	)

	// 6. Agente genérico: NewAgent[DatabaseAnalysis] garantiza salida tipada en compilación
	agent := core.NewAgent[DatabaseAnalysis](testModel,
		core.WithSystemPrompt[DatabaseAnalysis](
			"Eres un experto en bases de datos. Analiza el esquema proporcionado y devuelve un diagnóstico estructurado.",
		),
		core.WithTools[DatabaseAnalysis](schemaTool),
	)

	// 7. Ejecución del agente
	ctx := context.Background()
	result, err := agent.Run(ctx, "Inspeccionar el estado e índices vectoriales de la tabla 'embeddings' en Postgres.")
	if err != nil {
		log.Fatalf("Error al ejecutar el agente: %v", err)
	}

	// 8. Resultado tipado — acceso directo a campos sin type assertions
	fmt.Println("--- Resultado del Análisis ---")
	fmt.Printf("  Motor:           %s\n", result.Output.Engine)
	fmt.Printf("  Es Vector DB:    %v\n", result.Output.IsVectorDB)
	fmt.Printf("  Estado Índices:  %s\n", result.Output.IndexStatus)
	fmt.Println("  Recomendaciones:")
	for i, rec := range result.Output.Recommendations {
		fmt.Printf("    %d. %s\n", i+1, rec)
	}

	// Serialización JSON de verificación
	jsonBytes, _ := json.MarshalIndent(result.Output, "", "  ")
	fmt.Printf("\n--- Salida JSON ---\n%s\n", string(jsonBytes))
}

// ============================================================
// SECCIÓN: Uso con modelo real (requiere GEMINI_API_KEY)
// ============================================================
//
// Para usar con un modelo real de Gemini, descomentar este bloque
// y comentar la llamada a runWithTestModel() arriba.
//
// import "github.com/fugue-labs/gollem/provider/vertexai"
//
// func runWithRealModel(apiKey string) {
//     model := vertexai.New("mi-proyecto-gcp", "us-central1")
//
//     schemaTool := core.FuncTool[SchemaQueryParams](
//         "fetch_postgres_schema",
//         "Consulta el esquema y los índices de una tabla en Postgres",
//         fetchPostgresSchema,
//     )
//
//     agent := core.NewAgent[DatabaseAnalysis](model,
//         core.WithSystemPrompt[DatabaseAnalysis](
//             "Eres un experto en bases de datos. Analiza el esquema y devuelve un diagnóstico.",
//         ),
//         core.WithTools[DatabaseAnalysis](schemaTool),
//     )
//
//     result, err := agent.Run(context.Background(),
//         "Inspeccionar índices vectoriales de la tabla 'embeddings'.")
//     if err != nil {
//         log.Fatal(err)
//     }
//
//     fmt.Printf("Motor: %s\n", result.Output.Engine)
//     fmt.Printf("Recomendaciones: %v\n", result.Output.Recommendations)
// }
