"""
Motor del prototipo "agent as judge": lee la rúbrica en auditor.yaml, normaliza la
entrada y delega en el LLM (JSON mode). Personaliza prompts y cuestionarios en YAML,
no aquí, salvo que necesites otra integración de modelo.
"""
import json
import yaml
import logging
from typing import Dict, List, Optional, Union
from openai import OpenAI
from config import settings

logger = logging.getLogger(__name__)

RawInput = Union[str, List[Dict]]


class AnalysisService:
    """Orquesta las pasadas del juez (resumen, clasificación, cuestionario) vía OpenAI."""

    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
        self.config = self._load_config()

    def _load_config(self) -> dict:
        try:
            with open(settings.EVALUATION_CONFIG, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error al cargar configuración YAML: {e}")
            return {}

    def reload_config(self):
        self.config = self._load_config()

    def get_classification_labels(self) -> List[Dict]:
        return self.config.get("classification_labels") or self.config.get(
            "call_states", []
        )

    def _dialogue_defaults(self) -> Dict:
        return {
            "speaker_labels": {"agent": "Agente", "user": "Contacto"},
            "roles_as_agent": ["agent", "assistant"],
        }

    def format_input(self, raw: RawInput) -> str:
        """Convierte texto libre o lista de turnos {role, message} en un único string."""
        if isinstance(raw, str):
            return raw.strip()

        dialogue = self.config.get("input", {}).get("dialogue", {})
        defaults = self._dialogue_defaults()
        speaker_labels = {**defaults["speaker_labels"], **dialogue.get("speaker_labels", {})}
        roles_agent = dialogue.get("roles_as_agent", defaults["roles_as_agent"])

        lines = []
        for turn in raw:
            role = turn.get("role", "unknown")
            if role in roles_agent:
                label = speaker_labels.get("agent", "Agente")
            elif role in speaker_labels:
                label = speaker_labels[role]
            else:
                label = speaker_labels.get("user", "Contacto")
            lines.append(f"{label}: {turn.get('message', '')}")
        return "\n".join(lines)

    @staticmethod
    def _format_context_block(ctx: Optional[Dict[str, str]]) -> str:
        if not ctx:
            return ""
        return "\n".join(f"{k}: {v}" for k, v in ctx.items())

    def _substitute_prompt(
        self,
        template: str,
        input_text: str,
        *,
        states_block: str = "",
        questions_block: str = "",
        context_block: str = "",
    ) -> str:
        s = template
        for ph, val in (
            ("{input}", input_text),
            ("{transcript}", input_text),
            ("{states}", states_block),
            ("{questions}", questions_block),
            ("{context}", context_block),
        ):
            s = s.replace(ph, val)
        return s

    def _call_openai(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_completion_tokens=15000,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error en llamada a OpenAI: {e}")
            raise

    def generate_summary(
        self, raw: RawInput, additional_context: Optional[Dict[str, str]] = None
    ) -> Dict:
        eval_config = self.config.get("evaluation", {})
        system_prompt = eval_config.get("system_prompt", "")
        summary_prompt = eval_config.get("summary_prompt", "")

        input_text = self.format_input(raw)
        context_block = self._format_context_block(additional_context)
        prompt = self._substitute_prompt(
            summary_prompt, input_text, context_block=context_block
        )

        try:
            result = self._call_openai(system_prompt, prompt)
            return json.loads(result)
        except Exception as e:
            logger.error(f"Error al generar resumen: {e}")
            return {
                "summary": "",
                "call_duration_assessment": "",
                "key_topics": [],
                "highlights": [],
            }

    def classify(
        self,
        raw: RawInput,
        custom_states: Optional[List[Dict[str, str]]] = None,
        additional_context: Optional[Dict[str, str]] = None,
    ) -> Dict:
        eval_config = self.config.get("evaluation", {})
        system_prompt = eval_config.get("system_prompt", "")
        classification_prompt = eval_config.get("classification_prompt", "")

        states = custom_states or self.get_classification_labels()
        states_text = "\n".join(
            f"- {s['name']}: {s.get('description', '')}" for s in states
        )

        input_text = self.format_input(raw)
        context_block = self._format_context_block(additional_context)
        prompt = self._substitute_prompt(
            classification_prompt,
            input_text,
            states_block=states_text,
            context_block=context_block,
        )

        try:
            result = self._call_openai(system_prompt, prompt)
            return json.loads(result)
        except Exception as e:
            logger.error(f"Error al clasificar: {e}")
            return {"classification": "", "confidence": 0.0, "reasoning": ""}

    def evaluate_questionnaire(
        self,
        raw: RawInput,
        questionnaire_name: Optional[str] = None,
        additional_context: Optional[Dict[str, str]] = None,
    ) -> Dict:
        eval_config = self.config.get("evaluation", {})
        system_prompt = eval_config.get("system_prompt", "")
        questionnaire_prompt = eval_config.get("questionnaire_prompt", "")

        name = questionnaire_name or "default"
        questionnaires = self.config.get("questionnaires", {})
        questions_list = questionnaires.get(name)

        if not questions_list:
            logger.warning(
                f"Cuestionario '{name}' no encontrado. Disponibles: {list(questionnaires.keys())}"
            )
            return {"questionnaire_name": name, "answers": {}, "score": None}

        questions_text = "\n".join(questions_list)
        input_text = self.format_input(raw)
        context_block = self._format_context_block(additional_context)
        prompt = self._substitute_prompt(
            questionnaire_prompt,
            input_text,
            questions_block=questions_text,
            context_block=context_block,
        )

        try:
            result = self._call_openai(system_prompt, prompt)
            answers = json.loads(result)

            bool_answers = [v for v in answers.values() if isinstance(v, bool)]
            score = None
            if bool_answers:
                score = round(
                    sum(1 for v in bool_answers if v) / len(bool_answers) * 100, 1
                )

            return {
                "questionnaire_name": name,
                "answers": answers,
                "score": score,
            }
        except Exception as e:
            logger.error(f"Error al evaluar cuestionario: {e}")
            return {"questionnaire_name": name, "answers": {}, "score": None}

    def run_full_audit(
        self,
        raw: RawInput,
        questionnaire_name: Optional[str] = None,
        custom_states: Optional[List[Dict[str, str]]] = None,
        additional_context: Optional[Dict[str, str]] = None,
    ) -> Dict:
        errors = []

        try:
            summary = self.generate_summary(raw, additional_context)
        except Exception as e:
            summary = {}
            errors.append(f"summary: {e}")

        try:
            classification = self.classify(raw, custom_states, additional_context)
        except Exception as e:
            classification = {}
            errors.append(f"classification: {e}")

        try:
            questionnaire = self.evaluate_questionnaire(
                raw, questionnaire_name, additional_context
            )
        except Exception as e:
            questionnaire = {}
            errors.append(f"questionnaire: {e}")

        return {
            "summary": summary,
            "classification": classification,
            "questionnaire": questionnaire,
            "errors": errors,
        }
