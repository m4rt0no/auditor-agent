# Auditor Agent (prototipo)

Plantilla mínima para un **agente auditor**: un LLM que actúa como **juez** sobre un texto (o diálogo), devolviendo juicios estructurados: resumen, clasificación y checklist con score. El repo está pensado para **forkear**, cambiar `auditor.yaml` y adaptar el código a tu dominio (soporte, compliance, revisión de código, moderación, etc.).

No es un producto cerrado: es un **punto de partida** con API HTTP, persistencia simple en JSON y un flujo claro *entrada → prompts configurables → resultado*.

## Patrón: agent as judge

1. **Entrada**: texto libre o turnos `role`/`message`.
2. **Rúbrica**: definida en `auditor.yaml` (prompts, categorías de clasificación, cuestionarios sí/no).
3. **Salida**: JSON estable (Pydantic) que puedes guardar, mostrar en un dashboard o encadenar a otro sistema.

Tú defines *qué* se evalúa; el servicio se limita a orquestar llamadas al modelo y a exponer endpoints predecibles.

## Qué incluye este prototipo

| Pieza | Rol |
|--------|-----|
| `auditor.yaml` | Criterios del "juez": system prompt, tareas (resumen / clasificación / cuestionario), placeholders `{input}`, `{context}`, `{states}`, `{questions}`. |
| `services/analysis_service.py` | Motor: formatea la entrada, sustituye placeholders y llama a OpenAI en JSON mode. |
| `main.py` | FastAPI: `/audit/text`, `/audit/transcript`, config reload, CRUD de auditorías. |
| `services/storage_service.py` | Guardado local en `./audits` (sustituible por tu base de datos). |

## Arquitectura

```
auditor-agent/
├── main.py                    # API FastAPI
├── config.py                  # Variables de entorno (carga `.env.local`)
├── models.py                  # Contratos Pydantic
├── auditor.yaml               # Rúbrica y prompts (lo que más debes tocar al adaptar)
├── requirements.txt
├── Dockerfile / docker-compose.yml
├── env.example
├── services/
│   ├── analysis_service.py    # Lógica del "juez" (OpenAI)
│   └── storage_service.py     # Persistencia JSON en disco
└── audits/                    # Resultados guardados (configurable)
```

## Configuración

### Variables de entorno

| Variable | Requerida | Default | Descripción |
|----------|-----------|---------|-------------|
| `OPENAI_API_KEY` | Sí | — | API key de OpenAI |
| `OPENAI_MODEL` | No | (ver `config.py`) | Modelo a usar |
| `STORAGE_PATH` | No | `./audits` | Directorio de auditorías |
| `EVALUATION_CONFIG` | No | `auditor.yaml` | Archivo de rúbrica |

El proyecto carga **`.env.local`**. Puedes partir de:

```bash
copy env.example .env.local   # Windows
cp env.example .env.local     # Linux / macOS
```

Edita `.env.local` con tu `OPENAI_API_KEY`.

### Instalación y arranque

```bash
cd auditor-agent
pip install -r requirements.txt
python main.py
```

El servicio escucha en el puerto **8001**.

### Docker

```bash
docker-compose up --build
```

Requiere `.env.local` con al menos `OPENAI_API_KEY`.

## Endpoints

### Auditoría

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/audit/text` | Texto libre → juicio estructurado. |
| `POST` | `/audit/transcript` | Diálogo como lista de turnos (`role` + `message`). |
| `GET` | `/audit/{audit_id}` | Recuperar una auditoría guardada. |
| `GET` | `/audits` | Listar auditorías. |
| `DELETE` | `/audit/{audit_id}` | Borrar una auditoría. |

### Configuración en caliente

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/config/reload` | Recargar `auditor.yaml` sin reiniciar. |
| `GET` | `/config/questionnaires` | Listar cuestionarios definidos. |
| `GET` | `/config/labels` | Listar categorías de clasificación. |

## Uso rápido

### Texto libre

```bash
curl -X POST http://localhost:8001/audit/text \
  -H "Content-Type: application/json" \
  -d '{"text": "El cliente solicita un reembolso porque el pedido llegó dañado.", "questionnaire": "default", "additional_context": {"canal": "email"}}'
```

### Diálogo estructurado

```bash
curl -X POST http://localhost:8001/audit/transcript \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": [
      {"role": "agent", "message": "Hola, le atiende el soporte."},
      {"role": "user", "message": "No puedo iniciar sesión."}
    ],
    "questionnaire": "dialogo_atencion_cliente"
  }'
```

### Respuesta

```json
{
  "audit_id": "a1b2c3d4",
  "external_id": null,
  "timestamp": "2026-03-22T12:00:00",
  "input_text": "El cliente solicita un reembolso...",
  "summary": {
    "summary": "El cliente reporta un problema con su pedido y solicita reembolso.",
    "key_topics": ["reembolso", "pedido dañado"],
    "highlights": []
  },
  "classification": {
    "classification": "RECLAMO",
    "confidence": 0.91,
    "reasoning": "El cliente expresa insatisfacción y pide una acción correctiva."
  },
  "questionnaire": {
    "questionnaire_name": "default",
    "answers": {"1": true, "2": true, "3": true},
    "score": 100.0
  },
  "errors": []
}
```

## Cómo convertirlo en *tu* agente juez

1. **Edita `auditor.yaml`**: cambia el `system_prompt`, las categorías en `classification_labels` y los ítems en `questionnaires`. Usa `{input}` y `{context}` para inyectar texto y metadatos.
2. **Ajusta el contrato de salida** (opcional): si cambias los campos del resumen, alinea `SummaryResult` en `models.py` o relaja los campos con defaults vacíos.
3. **Sustituye el almacenamiento**: `StorageService` es deliberadamente simple; en producción suele ir a una base de datos, S3 o una cola.
4. **Modelo y coste**: ajusta `OPENAI_MODEL` y el límite `max_completion_tokens` en `analysis_service.py` según el tamaño de tus entradas.

## Ideas de extensión

- Segundo paso con herramientas (RAG, búsqueda de políticas) antes de "juzgar".
- Multi-juez: varios modelos o votación mayoritaria.
- Evaluación humana en loop (guardar `audit_id` y mostrar en UI de revisión).
- Tests de regresión sobre fixtures de texto en `tests/`.

## Licencia y expectativas

Úsalo como base de experimentación. Los LLM pueden alucinar criterios si la rúbrica es ambigua: **revisa** `auditor.yaml` y valida en tu dominio antes de decisiones críticas.
