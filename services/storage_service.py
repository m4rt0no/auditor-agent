import json
import os
import logging
from typing import Optional, List, Dict
from datetime import datetime
from config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Servicio para persistir resultados de auditoría en JSON."""

    def __init__(self):
        self.storage_path = settings.STORAGE_PATH
        os.makedirs(self.storage_path, exist_ok=True)

    def save_audit(self, audit_id: str, data: dict) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{audit_id}_{timestamp}.json"
        filepath = os.path.join(self.storage_path, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            logger.info(f"Auditoría guardada: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error al guardar auditoría: {e}")
            raise

    def load_audit(self, audit_id: str) -> Optional[dict]:
        try:
            for filename in sorted(os.listdir(self.storage_path), reverse=True):
                if filename.startswith(audit_id) and filename.endswith(".json"):
                    filepath = os.path.join(self.storage_path, filename)
                    with open(filepath, "r", encoding="utf-8") as f:
                        return json.load(f)
            return None
        except Exception as e:
            logger.error(f"Error al cargar auditoría {audit_id}: {e}")
            return None

    def list_audits(self) -> List[Dict]:
        results = []
        try:
            for filename in sorted(os.listdir(self.storage_path), reverse=True):
                if not filename.endswith(".json"):
                    continue
                filepath = os.path.join(self.storage_path, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    results.append({
                        "audit_id": data.get("audit_id", ""),
                        "conversation_id": data.get("conversation_id"),
                        "timestamp": data.get("timestamp", ""),
                        "classification": (
                            data.get("classification", {}).get("classification", "")
                            if data.get("classification")
                            else ""
                        ),
                        "sentiment": (
                            data.get("sentiment", {}).get("sentiment", "")
                            if data.get("sentiment")
                            else ""
                        ),
                        "score": (
                            data.get("questionnaire", {}).get("score")
                            if data.get("questionnaire")
                            else None
                        ),
                        "filename": filename,
                    })
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"Error al listar auditorías: {e}")
        return results

    def delete_audit(self, audit_id: str) -> bool:
        try:
            for filename in os.listdir(self.storage_path):
                if filename.startswith(audit_id) and filename.endswith(".json"):
                    filepath = os.path.join(self.storage_path, filename)
                    os.remove(filepath)
                    logger.info(f"Auditoría eliminada: {filepath}")
                    return True
            return False
        except Exception as e:
            logger.error(f"Error al eliminar auditoría {audit_id}: {e}")
            return False
