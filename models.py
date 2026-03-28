from pydantic import BaseModel, Field, computed_field, model_validator
from typing import Optional, Dict, List, Any
from datetime import datetime

class TranscriptTurn(BaseModel):
    role: str = Field(..., description="Rol del hablante: 'agent' o 'user'")
    message: str = Field(..., description="Texto del mensaje")

class AuditFromTextRequest(BaseModel):
    """Auditoría sobre texto libre."""
    text: str = Field(..., description="Contenido a auditar")
    questionnaire: Optional[str] = Field(
        default=None,
        description="Nombre del cuestionario en auditor.yaml (usa 'default' si no se envía)",
    )
    custom_states: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="Etiquetas de clasificación personalizadas (override de classification_labels)",
    )
    additional_context: Optional[Dict[str, str]] = Field(
        default=None,
        description="Metadatos adicionales; se inyectan en {context} del prompt",
    )
    external_id: Optional[str] = Field(
        default=None,
        description="Identificador externo para trazabilidad (ticket, sesión, etc.)",
    )

class AuditFromTranscriptRequest(BaseModel):
    """Auditoría sobre diálogo estructurado (lista de turnos role + message)."""
    transcript: List[TranscriptTurn] = Field(
        ..., description="Turnos del diálogo o conversación"
    )
    questionnaire: Optional[str] = Field(
        default=None,
        description="Nombre del cuestionario en auditor.yaml",
    )
    custom_states: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="Etiquetas de clasificación personalizadas",
    )
    additional_context: Optional[Dict[str, str]] = Field(
        default=None,
        description="Metadatos adicionales inyectados en {context}",
    )
    external_id: Optional[str] = Field(
        default=None,
        description="Identificador externo para trazabilidad",
    )

class SummaryResult(BaseModel):
    summary: str = ""
    call_duration_assessment: str = ""
    key_topics: List[str] = []
    highlights: List[str] = []

class ClassificationResult(BaseModel):
    classification: str = ""
    confidence: float = 0.0
    reasoning: str = ""

class QuestionnaireResult(BaseModel):
    questionnaire_name: str = ""
    answers: Dict[str, object] = {}
    score: Optional[float] = Field(
        default=None,
        description="Porcentaje de cumplimiento sobre preguntas sí/no (0–100)",
    )

class AuditResult(BaseModel):
    """Resultado completo de una auditoría."""
    audit_id: str
    external_id: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    input_text: str = ""
    summary: Optional[SummaryResult] = None
    classification: Optional[ClassificationResult] = None
    questionnaire: Optional[QuestionnaireResult] = None
    additional_context: Optional[Dict[str, str]] = None
    errors: List[str] = []

    @model_validator(mode="before")
    @classmethod
    def _legacy_transcript_field(cls, data: Any) -> Any:
        """Retrocompatibilidad con auditorías guardadas antes de input_text."""
        if isinstance(data, dict) and not data.get("input_text") and data.get("transcript_text"):
            return {**data, "input_text": data["transcript_text"]}
        return data

    @computed_field
    @property
    def transcript_text(self) -> str:
        """Alias de input_text para compatibilidad con auditorías guardadas."""
        return self.input_text
