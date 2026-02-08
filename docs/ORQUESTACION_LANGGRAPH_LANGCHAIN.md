# Trabajo en conjunto: LangGraph y LangChain

En el LMS Agent Scraper (v2) se usan **LangGraph** y **LangChain** como orquestadores complementarios. Aquí se explica cómo colaboran.

---

## LangGraph: orquestador del flujo

**LangGraph** define el **grafo de estados** del proceso completo:

- **auth** → **discovery** → **extracción** → **reporte**

Se encarga de **qué paso ejecutar**, en qué orden y cuándo pasar al siguiente (incluyendo condicionales, ramas y reintentos). Es el “director de orquesta” de alto nivel.

## LangChain: capa de interacción con LLMs

**LangChain** aporta las piezas para **hablar con los modelos**:

- **Prompts**: `ChatPromptTemplate` para armar las instrucciones.
- **Mensajes**: `HumanMessage`, `AIMessage`, etc., para el historial de conversación.
- **Integración con LLMs**: llamadas al modelo, manejo de respuestas, tool calling, etc.

Es la “caja de herramientas” para todo lo que involucra lenguaje natural y LLMs.

---

## Cómo se combinan en la práctica

1. **LangGraph** decide **qué paso** toca (por ejemplo: “ahora estamos en discovery” o “ahora en extracción”).
2. **Dentro de cada nodo/estado**, cuando hace falta usar un LLM, se usa **LangChain**:
   - En **discovery**: LangGraph invoca un componente que usa LangChain (prompts + mensajes) para consultar o razonar con el modelo.
   - En **extracción**: LangGraph dispara la extracción; la lógica que “habla” con el LLM (prompts, parsing de salida) se hace con LangChain.
   - En **reporte**: LangGraph activa la generación del reporte; la parte de resumir o generar texto se hace con LangChain (templates, mensajes, llamada al modelo).

**Resumen:** **LangGraph orquesta el flujo** (auth → discovery → extracción → reporte) y **LangChain se usa dentro de esos pasos** cada vez que hay que construir prompts, enviar mensajes e integrar con un LLM. LangGraph es el flujo; LangChain es la capa de “inteligencia” basada en lenguaje en cada etapa.
