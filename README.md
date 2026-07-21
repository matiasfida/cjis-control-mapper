# CJIS Control Mapper

RAG que mapea eventos de auditoría a controles del **CJIS Security Policy v6.0**, citando siempre la sección/control y página de origen.

**Esto no es un motor de veredictos de compliance.** Nunca afirma "cumple" / "no cumple" con un control. Solo identifica qué controles podrían aplicar a un evento y cita la fuente exacta. Cuando no hay evidencia suficiente en el documento, lo declara en vez de completar con conocimiento propio del modelo.

## Documento fuente

- CJIS Security Policy **v6.0**, publicado 27/12/2024.
- No está incluido en el repo (ver `.gitignore`). Hay que colocarlo manualmente en:
  `data/source/CJIS_Security_Policy_v6-0_20241227.pdf`
- Si se actualiza la versión de la política, hay que re-correr `ingest.py` completo — la metadata de sección/control queda atada a esta versión específica del PDF.

## Instalación

Windows + Git Bash (MINGW64):

```bash
python -m venv .venv
source .venv/Scripts/activate
pip install langchain langchain-chroma langchain-text-splitters langchain-groq \
            langchain-anthropic langchain-google-genai pypdf python-dotenv chromadb
```

Copiar `.env.example` a `.env` y completar las API keys que se vayan a usar (el agente por default usa Groq; `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` quedan como alternativas si se cambia el modelo en `agent.py`):

```bash
cp .env.example .env
```

Los embeddings usan el modelo local por default de Chroma (`all-MiniLM-L6-v2`, ONNX, CPU) — no hace falta ninguna API key para indexar ni para el retrieval por sí solo, solo para correr el agente conversacional.

## Uso

### 1. Ingesta (una sola vez, o cada vez que cambie el PDF fuente)

```bash
python ingest.py
```

Extrae texto del PDF, detecta headers de sección/control/apéndice, chunkea y persiste el índice en `./chroma_db` (excluido de git, regenerable en cualquier momento).

### 2. Retrieval directo

```bash
python retrieval.py
```

Corre unas queries de prueba contra el índice y muestra página, sección/control y score de cada resultado. Para usarlo desde código:

```python
from retrieval import search_cjis_policy

hits = search_cjis_policy("password complexity requirements", k=4)
```

### 3. Chequeo de evento sin LLM (`check_event.py`)

Combina dos señales sobre un evento de auditoría, sin invocar ningún modelo:

- **Completitud estructural**: contra los elementos de contenido de audit record citados textualmente de la familia AU (AU-3, AU-8), marca qué campos están presentes/ausentes en el evento. No es un veredicto de compliance, es una checklist con fuente citada para que un humano evalúe qué implica cada ausencia.
- **Controles candidatos**: búsqueda semántica del evento contra el índice, con score de similitud (no correspondencia garantizada).

```bash
python check_event.py
```

### 4. Agente conversacional (`agent.py`, opcional)

Usa `create_agent` de LangChain con `search_cjis_policy` como tool, sobre Groq (`llama-3.3-70b-versatile`) por default. Requiere `GROQ_API_KEY` en `.env`.

```bash
python agent.py
```

El system prompt prohíbe explícitamente veredictos de compliance, exige cita de sección y página en toda afirmación sobre un control, y obliga al agente a declarar falta de confianza en vez de adivinar.

## Arquitectura y decisiones de diseño

Ver [CLAUDE.md](CLAUDE.md) para el detalle de:

- Por qué se usa el embedding local de Chroma en vez de una API externa.
- Cómo se detectan las tres numeraciones distintas del documento (secciones `5.x.y`, IDs de control NIST tipo `AU-2`, apéndices `A-6`) y por qué la sección se arrastra entre páginas.
- Bugs ya encontrados y corregidos en el parser (para no reintroducirlos).
- La limitación conocida en el borde exacto entre dos secciones/controles consecutivos.

## Limitación conocida

En el borde exacto entre dos secciones/controles consecutivos, la asignación de sección puede quedar corrida (un chunk que arranca justo donde empieza el header siguiente puede heredar la sección anterior). Validado en muestra manual: **~83% de precisión** en la asignación de control ID, con el error acotado a esos bordes. La página siempre es confiable; la sección/control no siempre es exacta en el borde.

## Estado actual

- [x] Ingesta (`ingest.py`)
- [x] Retrieval tool (`retrieval.py`)
- [x] Chequeo de evento sin LLM (`check_event.py`)
- [x] Agente conversacional (`agent.py`)
- [x] Eval set (20 casos manuales, `eval_set.py` + `eval.py`) — Hit@5: 80% (16/20), MRR: 0.65
