import json
import logging
from typing import Dict, Any, Optional, List
from google import genai
from google.genai import types

from backend.app.config import settings
from backend.app.agent.schemas import AgentInvestigationResult
from backend.app.agent.prompts import INVESTIGATOR_SYSTEM_PROMPT
from backend.app.agent.offline import offline_investigate
from backend.app.paypal.client import ProviderSnapshot

logger = logging.getLogger(__name__)


async def run_investigation(
    snapshot: Optional[ProviderSnapshot],
    attempts: List[Any],
    events: List[Any],
    messages: Optional[List[str]] = None,
) -> AgentInvestigationResult:
    """Run AI investigation via configured provider (Gemini) or deterministic offline fallback."""
    # Fallback immediately if provider is offline or API key missing
    if settings.AI_PROVIDER == "offline" or not settings.GEMINI_API_KEY:
        return offline_investigate(snapshot, attempts, events)

    # Attempt online Gemini model call with structured output
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        evidence_bundle = {
            "snapshot": snapshot.to_dict() if snapshot else {},
            "attempts": [
                {"id": getattr(a, "id", str(a)), "status": getattr(a, "status", "UNKNOWN")}
                for a in attempts
            ],
            "events": [
                {"event_type": getattr(e, "event_type", "UNKNOWN"), "description": getattr(e, "description", "")}
                for e in events
            ],
            "user_messages": messages or [],
        }

        prompt = f"""
Analyze the following payment evidence bundle according to the system instructions.

Evidence Bundle:
{json.dumps(evidence_bundle, indent=2)}
"""

        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=INVESTIGATOR_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=AgentInvestigationResult,
                temperature=0.0,
            ),
        )

        if response.text:
            data = json.loads(response.text)
            return AgentInvestigationResult(**data)
        else:
            return offline_investigate(snapshot, attempts, events)
    except Exception as exc:
        logger.warning("Online AI investigation failed or was unavailable (%s). Falling back to offline investigator.", exc)
        return offline_investigate(snapshot, attempts, events)
