"""
API HTTP del prototipo auditor: expone el patrón agent-as-judge definido en auditor.yaml.
Dos formas de entrada: texto libre (/audit/text) o diálogo estructurado (/audit/transcript).
"""
from fastapi import FastAPI, HTTPException
from datetime import datetime
import uuid
import logging
from typing import List, Union
from config import settings
from models import (
    AuditFromTextRequest,
    AuditFromTranscriptRequest,
    AuditResult,
    SummaryResult,
    ClassificationResult,
    QuestionnaireResult,
)
from services.analysis_service import AnalysisService
from services.storage_service import StorageService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description=settings.API_DESCRIPTION,
)

analysis_service = AnalysisService()
storage_service = StorageService()


@app.get("/")
async def root():
    return {
        "service": settings.API_TITLE,
        "version": settings.API_VERSION,
        "status": "running",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/audit/text", response_model=AuditResult)
async def audit_from_text(request: AuditFromTextRequest):
    """
    Audita texto libre. Punto de entrada principal para prototipar.
    La rúbrica (prompts, categorías, cuestionario) se define en auditor.yaml.
    """
    try:
        return await _run_audit(
            raw_input=request.text,
            external_id=request.external_id,
            questionnaire=request.questionnaire,
            custom_states=request.custom_states,
            additional_context=request.additional_context,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en /audit/text: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")


@app.post("/audit/transcript", response_model=AuditResult)
async def audit_from_transcript(request: AuditFromTranscriptRequest):
    """
    Audita un diálogo ya transcrito como lista de turnos (role + message).
    Útil para conversaciones, chats o cualquier intercambio estructurado.
    """
    try:
        transcript = [turn.model_dump() for turn in request.transcript]
        return await _run_audit(
            raw_input=transcript,
            external_id=request.external_id,
            questionnaire=request.questionnaire,
            custom_states=request.custom_states,
            additional_context=request.additional_context,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en /audit/transcript: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")


@app.get("/audit/{audit_id}", response_model=AuditResult)
async def get_audit(audit_id: str):
    """Recupera una auditoría guardada."""
    data = storage_service.load_audit(audit_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Auditoría {audit_id} no encontrada")
    return AuditResult(**data)


@app.get("/audits")
async def list_audits():
    """Lista todas las auditorías guardadas."""
    audits = storage_service.list_audits()
    return {"total": len(audits), "audits": audits}


@app.delete("/audit/{audit_id}")
async def delete_audit(audit_id: str):
    """Elimina una auditoría guardada."""
    deleted = storage_service.delete_audit(audit_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Auditoría {audit_id} no encontrada")
    return {"message": "Auditoría eliminada", "audit_id": audit_id}


@app.post("/config/reload")
async def reload_config():
    """Recarga auditor.yaml sin reiniciar el servicio."""
    try:
        analysis_service.reload_config()
        return {"message": "Configuración recargada exitosamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al recargar: {e}")


@app.get("/config/questionnaires")
async def list_questionnaires():
    """Lista los cuestionarios definidos en auditor.yaml."""
    questionnaires = analysis_service.config.get("questionnaires", {})
    return {
        "available": list(questionnaires.keys()),
        "details": {
            name: {"questions_count": len(questions)}
            for name, questions in questionnaires.items()
        },
    }


@app.get("/config/labels")
async def list_labels():
    """Lista las categorías de clasificación definidas en auditor.yaml."""
    return {"labels": analysis_service.get_classification_labels()}


async def _run_audit(
    raw_input: Union[str, List[dict]],
    external_id: str = None,
    questionnaire: str = None,
    custom_states: list = None,
    additional_context: dict = None,
) -> AuditResult:
    audit_id = str(uuid.uuid4())[:8]

    analysis = analysis_service.run_full_audit(
        raw_input=raw_input,
        questionnaire_name=questionnaire,
        custom_states=custom_states,
        additional_context=additional_context,
    )

    result = AuditResult(
        audit_id=audit_id,
        external_id=external_id,
        input_text=analysis_service.format_input(raw_input),
        summary=SummaryResult(**analysis.get("summary", {})),
        classification=ClassificationResult(**analysis.get("classification", {})),
        questionnaire=QuestionnaireResult(**analysis.get("questionnaire", {})),
        additional_context=additional_context,
        errors=analysis.get("errors", []),
    )

    try:
        storage_service.save_audit(audit_id, result.model_dump())
    except Exception as e:
        logger.error(f"Error al guardar auditoría: {e}")
        result.errors.append(f"storage: {e}")

    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
