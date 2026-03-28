import os
from dotenv import load_dotenv

load_dotenv(".env.local")

def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value

class Settings:
    OPENAI_API_KEY: str = _require_env("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-5-nano")

    STORAGE_PATH: str = os.getenv("STORAGE_PATH", "./audits")

    EVALUATION_CONFIG: str = os.getenv("EVALUATION_CONFIG", "auditor.yaml")

    API_TITLE: str = "Auditor Agent (prototype)"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = (
        "Plantilla de agente auditor (juez LLM): entrada de texto o diálogo, "
        "rúbrica en YAML, salida estructurada. Forkear y adaptar."
    )

settings = Settings() 
