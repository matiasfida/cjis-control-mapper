# CLAUDE.md

## Qué es este proyecto

RAG que mapea eventos de auditoría a controles del CJIS Security Policy v6.0, citando sección/página fuente.

**Lo que NO es, explícitamente:** un motor de veredictos de compliance. Nunca debe afirmar "cumple" / "no cumple". Solo identifica qué controles aplican y cita la fuente. Si no hay evidencia suficiente, debe decir que no está seguro — no completar con conocimiento propio del modelo.

## Documento fuente

- CJIS Security Policy **v6.0**, publicado 27/12/2024.
- Archivo: `data/source/CJIS_Security_Policy_v6-0_20241227.pdf` (excluido de git, ver `.gitignore`).
- Si en algún momento se actualiza la versión, hay que re-correr `ingest.py` completo y documentar el cambio de versión en el README — la metadata de sección/control queda atada a esta versión específica.

## Arquitectura y decisiones de diseño (con motivo)

- **Embeddings:** modelo local por default de Chroma (`all-MiniLM-L6-v2`, ONNX, CPU). Elegido para que el repo corra sin pedir API keys a quien lo clone. Si la calidad de retrieval se vuelve un problema, considerar migrar a Voyage AI — no antes de tener evidencia concreta de que hace falta.
- **Vectorstore:** Chroma local, persistido en `./chroma_db` (excluido de git, regenerable con `ingest.py`).
- **Chunking:** `RecursiveCharacterTextSplitter`, `chunk_size=1000`, `overlap=150`.
- **Detección de sección/control (la parte no trivial del proyecto):**
    - El documento numera contenido de tres formas distintas: secciones tipo `5.x.y`, IDs de control NIST tipo `AU-2`/`CP-1` (la mayoría del cuerpo real), y apéndices tipo `A-6`.
    - Estrategia: detectar los tres patrones como "headers" posicionales dentro de cada página, y asignarle a cada chunk el último header visto antes de su posición de inicio en el texto. La sección se **arrastra entre páginas** (`last_section` persiste en el loop de `build_documents`) porque la mayoría de las páginas son continuación, no tienen header propio.
    - **Regla de diseño explícita:** preferir página confiable siempre + sección "mejor esfuerzo" (puede quedar `None`) antes que inventar una sección con falsa confianza. Nunca rellenar `section` con un valor adivinado.

## Bugs ya encontrados y corregidos (no reintroducir)

1. **Arrastre indefinido en apéndices:** el regex de sección numérica (`5.x.y`) no matchea en zona de apéndices, y sin un patrón de apéndice explícito, `last_section` quedaba pegado en el último número visto del cuerpo principal durante cientos de páginas. Fix: `APPENDIX_PATTERN` (`[A-Z]-\d+`) detecta el cambio de zona.
2. **Arrastre por numeración equivocada:** el cuerpo principal del documento usa mayormente IDs de control NIST (`AU-2`, `CP-1`), no `5.x.y`. Sin `CONTROL_PATTERN`, la sección quedaba congelada en el último `5.x.y` visto (ej: `5.1.2.1`) durante cientos de páginas de contenido no relacionado. Fix: sumar `CONTROL_PATTERN` (`[A-Z]{2,4}-\d{1,2}` seguido de mayúscula, para no matchear listas tipo "Related Controls: AU-2, AU-8...").
3. **Chroma elimina claves de metadata con valor `None`** en vez de guardarlas como `null`. Cualquier acceso a metadata debe usar `.get("campo")`, nunca `["campo"]` directo — si no, `KeyError` en los ~7 chunks sin sección detectada (portada/índice, antes del primer header).

## Limitación conocida, no resuelta (documentar en README, no ocultar)

En el borde exacto entre dos secciones/controles consecutivos, la asignación puede quedar corrida (ej: un chunk que empieza justo donde arranca el header de la sección siguiente puede heredar la sección anterior). Validado en muestra manual: ~83% de precisión en la asignación de control ID, con el error acotado a bordes exactos. Página siempre confiable, sección/control no siempre exacto en el borde.

**Query de `check_event.py` demasiado pobre para retrieval (detectado corriendo `eval.py`):** `_describe_event_for_search` arma queries tipo `"audit log event: login failed"` — muy cortas y genéricas. Contra el índice real, esto da Hit@5 de solo 25% (5/20 en `eval_set.py`), porque matchea el boilerplate de "policy and procedures" (AU-1, página 67) que se repite casi textual al inicio de cada familia de control, en vez del control específico. Confirmado que el índice/embeddings no son el problema: la misma búsqueda con frase más parecida a la prosa de la política (ej. `"unsuccessful login attempts account lockout"` en vez de `"audit log event: login failed"`) sí encuentra el control correcto (AC-7) en el top-3. Pendiente: mejorar `_describe_event_for_search` para generar descripciones más ricas antes de confiar en `candidate_controls` de `check_event.py`.

## Convenciones del proyecto

- Windows + Git Bash (MINGW64). Activar venv con `source .venv/Scripts/activate`, no `.venv/bin/activate`.
- Nunca commitear: `.venv/`, `chroma_db/`, `.idea/`, `data/source/*.pdf`, `__pycache__/`.
- Antes de aceptar cualquier fix sobre el parser de secciones/controles, validar con muestra manual random contra el texto real (no confiar solo en el % agregado — un % alto puede ocultar arrastre falso, como pasó dos veces).

## Estado actual

- [x] Ingesta (`ingest.py`) — funcionando y validada manualmente.
- [x] Retrieval tool (`retrieval.py`) — funcionando, devuelve página + control + score.
- [x] README — hecho.
- [x] Agente (`create_agent` de LangChain + `search_cjis_policy` como tool) — hecho, ver `agent.py`.
- [x] Eval set (20 casos manuales) — hecho, ver `eval_set.py` (casos) y `eval.py` (runner). Página/control de cada caso verificado leyendo el PDF fuente directamente, no derivado de la metadata de `ingest.py`. Hit@5 actual: 25% (5/20) — ver hallazgo en el bug log de abajo.
- [ ] Mejorar `_describe_event_for_search` (`check_event.py`) — pendiente. Causa raíz del Hit@5 bajo, documentada arriba en "Limitación conocida".

## System prompt de referencia para el agente (cuando se implemente)

Debe prohibir explícitamente veredictos de compliance. Ver system prompt acordado: identifica controles aplicables, cita sección exacta, nunca afirma cumplimiento/incumplimiento, declara falta de confianza cuando corresponda.