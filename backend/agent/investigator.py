"""
AI Investigator — Gemini adapter with SSE streaming tool-call loop.
Falls back to deterministic offline investigator on any failure.
"""
import json
import hashlib
import logging
from typing import AsyncIterator, Optional, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from google import genai
from google.genai import types

from backend.app.config import settings
from backend.app.agent.schemas import AgentInvestigationResult
from backend.app.agent.prompts import INVESTIGATOR_SYSTEM_PROMPT, wrap_untrusted_text
from backend.app.agent.offline import offline_investigate
from backend.app.agent.tools import (
    tool_get_order,
    tool_get_capture,
    tool_get_transaction_record,
    tool_list_webhook_events,
    tool_get_payment_attempts,
    tool_get_case_messages,
)
from backend.app.paypal.client import ProviderSnapshot

logger = logging.getLogger(__name__)

# Tool declarations for Gemini function calling
TOOL_DECLARATIONS = [
    {
        "name": "get_order",
        "description": "Fetch authoritative order details from PayPal. Returns order status, amount, currency.",
        "parameters": {
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "PayPal order ID"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "get_capture",
        "description": "Fetch authoritative capture details from PayPal. Returns capture status.",
        "parameters": {
            "type": "object",
            "properties": {"capture_id": {"type": "string", "description": "PayPal capture ID"}},
            "required": ["capture_id"],
        },
    },
    {
        "name": "get_transaction_record",
        "description": "Look up a capture in PayPal Transaction Search (S=success, P=pending, D=denied, V=reversed). Reporting data can lag by up to 3 hours, so a missing record is NOT evidence of failure.",
        "parameters": {
            "type": "object",
            "properties": {"capture_id": {"type": "string", "description": "PayPal capture / transaction ID"}},
            "required": ["capture_id"],
        },
    },
    {
        "name": "list_webhook_events",
        "description": "List verified webhook events associated with this order.",
        "parameters": {
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "PayPal order ID"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "get_payment_attempts",
        "description": "Get recorded payment attempts for this order from our database.",
        "parameters": {
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "PayPal order ID"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "get_case_messages",
        "description": "Retrieve buyer/seller messages associated with this case (untrusted user text).",
        "parameters": {
            "type": "object",
            "properties": {"case_id": {"type": "string", "description": "Case ID"}},
            "required": ["case_id"],
        },
    },
]


def compute_input_hash(order_id: str, case_id: str, attempts: list, events: list) -> str:
    key = json.dumps(
        {
            "order_id": order_id,
            "case_id": case_id,
            "attempt_count": len(attempts),
            "event_count": len(events),
        },
        sort_keys=True,
    )
    return hashlib.sha256(key.encode()).hexdigest()


async def stream_investigation(
    order_id: str,
    case_id: str,
    snapshot: Optional[ProviderSnapshot],
    attempts: List[Any],
    events: List[Any],
    messages: Optional[List[str]],
    session: AsyncSession,
    status_report: Optional[dict] = None,
) -> AsyncIterator[dict]:
    """
    Stream SSE events for the investigation:
      {"type": "tool_call",    "name": "get_order", "args": {...}}
      {"type": "tool_result",  "name": "get_order", "result": {...}, "ms": 412}
      {"type": "summary_delta","text": "...chunk..."}
      {"type": "final",        "result": {...AgentInvestigationResult...}}
      {"type": "error",        "message": "..."}
    """
    if settings.AI_PROVIDER == "offline" or not settings.GEMINI_API_KEY:
        result = offline_investigate(snapshot, attempts, events)
        yield {"type": "final", "result": result.model_dump(), "offline": True}
        return

    try:
        import time

        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        evidence_bundle = {
            "order_id": order_id,
            "snapshot": snapshot.to_dict() if snapshot else {},
            "status_report": status_report or {},
            "attempts": [
                {
                    "id": getattr(a, "id", ""),
                    "status": getattr(a, "status", "UNKNOWN"),
                    "is_simulated": getattr(a, "is_simulated", False),
                }
                for a in attempts
            ],
            "events": [
                {
                    "event_type": getattr(e, "event_type", ""),
                    "verified": getattr(e, "verified", False),
                    "is_simulated": getattr(e, "is_simulated", False),
                }
                for e in events
            ],
            "user_messages": [wrap_untrusted_text(m) for m in (messages or [])],
        }

        initial_prompt = f"""Analyze this payment evidence bundle. Use the available tools to gather more data if needed, then produce your structured JSON diagnosis.

Evidence Bundle:
{json.dumps(evidence_bundle, indent=2)}

After calling tools, respond with a JSON object matching exactly:
{{
  "classification": "PENDING|COMPLETED|DEFINITIVE_FAILURE|UNKNOWN|CONFLICT",
  "summary": "plain-language explanation citing evidence",
  "buyer_message": "short reassuring message",
  "seller_message": "short fulfillment guidance",
  "evidence_refs": ["api_snapshot.capture_status"],
  "unknowns": ["..."],
  "recommended_action": "RECONCILE|BLOCK_RETRY|ALLOW_RETRY|ESCALATE",
  "requires_human_approval": true,
  "confidence": 0.0
}}"""

        messages_history = [{"role": "user", "parts": [{"text": initial_prompt}]}]

        # Tool-calling loop (max 5 rounds)
        for _round in range(5):
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=messages_history,
                config=types.GenerateContentConfig(
                    system_instruction=INVESTIGATOR_SYSTEM_PROMPT,
                    tools=[
                        types.Tool(
                            function_declarations=[
                                types.FunctionDeclaration(**t) for t in TOOL_DECLARATIONS
                            ]
                        )
                    ],
                    temperature=0.0,
                    max_output_tokens=2048,
                ),
            )

            candidate = response.candidates[0] if response.candidates else None
            if not candidate:
                break

            # Check for function calls
            function_calls = []
            text_parts = []
            for part in candidate.content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    function_calls.append(part.function_call)
                elif hasattr(part, "text") and part.text:
                    text_parts.append(part.text)

            if function_calls:
                # Process each tool call
                tool_results = []
                for fc in function_calls:
                    fn_name = fc.name
                    fn_args = dict(fc.args) if fc.args else {}
                    yield {"type": "tool_call", "name": fn_name, "args": fn_args}

                    t0 = time.monotonic()
                    try:
                        if fn_name == "get_order":
                            result_data = await tool_get_order(fn_args.get("order_id", order_id))
                        elif fn_name == "get_capture":
                            result_data = await tool_get_capture(fn_args.get("capture_id", ""))
                        elif fn_name == "get_transaction_record":
                            result_data = await tool_get_transaction_record(fn_args.get("capture_id", ""))
                        elif fn_name == "list_webhook_events":
                            result_data = await tool_list_webhook_events(
                                fn_args.get("order_id", order_id), session
                            )
                        elif fn_name == "get_payment_attempts":
                            result_data = await tool_get_payment_attempts(
                                fn_args.get("order_id", order_id), session
                            )
                        elif fn_name == "get_case_messages":
                            result_data = await tool_get_case_messages(
                                fn_args.get("case_id", case_id), session
                            )
                        else:
                            result_data = {"error": f"Unknown tool: {fn_name}"}
                    except Exception as e:
                        result_data = {"error": str(e)}

                    ms = int((time.monotonic() - t0) * 1000)
                    yield {"type": "tool_result", "name": fn_name, "result": result_data, "ms": ms}
                    tool_results.append(
                        {"function_response": {"name": fn_name, "response": result_data}}
                    )

                # Add model response and tool results to history
                messages_history.append({"role": "model", "parts": candidate.content.parts})
                messages_history.append({"role": "user", "parts": tool_results})
                continue

            # No more tool calls — extract text for final answer
            full_text = "\n".join(text_parts)
            if full_text:
                # Stream summary in chunks
                chunk_size = 80
                for i in range(0, len(full_text), chunk_size):
                    yield {"type": "summary_delta", "text": full_text[i : i + chunk_size]}

                # Try to parse structured output
                try:
                    # Find JSON in the text
                    start = full_text.find("{")
                    end = full_text.rfind("}") + 1
                    if start >= 0 and end > start:
                        data = json.loads(full_text[start:end])
                        result = AgentInvestigationResult(**data)
                        yield {"type": "final", "result": result.model_dump(), "offline": False}
                        return
                except Exception:
                    pass
            break

        # Fallback
        result = offline_investigate(snapshot, attempts, events)
        yield {"type": "final", "result": result.model_dump(), "offline": True}

    except Exception as exc:
        logger.warning("Gemini investigation failed: %s — falling back to offline", exc)
        result = offline_investigate(snapshot, attempts, events)
        yield {"type": "error", "message": str(exc)}
        yield {"type": "final", "result": result.model_dump(), "offline": True}


async def run_investigation(
    snapshot: Optional[ProviderSnapshot],
    attempts: List[Any],
    events: List[Any],
    messages: Optional[List[str]] = None,
    status_report: Optional[dict] = None,
) -> AgentInvestigationResult:
    """Run deterministic offline or direct investigation returning an AgentInvestigationResult."""
    return offline_investigate(snapshot, attempts, events)
