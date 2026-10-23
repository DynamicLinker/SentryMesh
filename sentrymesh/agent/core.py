import time
from typing import Any, Dict, List, Optional

from sentrymesh.agent.audit import SecurityAuditLog
from sentrymesh.agent.bedrock import BedrockAgentClient
from sentrymesh.decider.guardrail import StrandsZeroTrustGuardrail
from sentrymesh.decider.types import ActionOutcome


class SentryMeshAgent:
    """The central agent orchestrating Strands Decider 2B, Bedrock, and device actions."""

    def __init__(
        self,
        guardrail: Optional[StrandsZeroTrustGuardrail] = None,
        bedrock: Optional[BedrockAgentClient] = None,
        audit_log: Optional[SecurityAuditLog] = None,
    ):
        self.guardrail = guardrail or StrandsZeroTrustGuardrail()
        self.bedrock = bedrock or BedrockAgentClient()
        self.audit = audit_log or SecurityAuditLog()

    def process_entry_request(
        self,
        visitor_input: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Process an incoming front-door event across System 1 and System 2."""
        start_overall = time.perf_counter()
        ctx = context or {}

        # 1. System 1: Strands Decider 2B airgap check (sub-120ms)
        guardrail_eval = self.guardrail.evaluate(visitor_input, ctx)
        eval_dict = guardrail_eval.to_dict()

        device_actions: List[Dict[str, Any]] = []

        # 2. Airgap decision gating
        if guardrail_eval.action == ActionOutcome.DENY:
            device_actions.append({
                "device": "smart_lock",
                "action": "LOCK_ENGAGED",
                "status": "HARDWARE_AIRGAP_BLOCKED",
            })
            device_actions.append({
                "device": "fire_tv",
                "action": "PIP_SECURITY_ALERT",
                "severity": "CRITICAL",
                "message": f"Blocked prompt override: {guardrail_eval.reason}",
            })
        elif guardrail_eval.action == ActionOutcome.PROCEED:
            device_actions.append({
                "device": "smart_lock",
                "action": "UNLOCK_MOMENTARY",
                "status": "ACCESS_AUTHORIZED",
            })
            device_actions.append({
                "device": "fire_tv",
                "action": "PIP_NOTIFICATION",
                "severity": "INFO",
                "message": f"Authorized access: {guardrail_eval.reason}",
            })
        elif guardrail_eval.action == ActionOutcome.CHALLENGE:
            device_actions.append({
                "device": "smart_lock",
                "action": "MAINTAIN_LOCKED",
                "status": "CHALLENGE_ISSUED",
            })
            device_actions.append({
                "device": "ring_doorbell",
                "action": "DISPLAY_KEYPAD_PROMPT",
                "prompt": "Enter 4-digit carrier PIN",
            })
        else:
            device_actions.append({
                "device": "smart_lock",
                "action": "MAINTAIN_LOCKED",
                "status": "AWAITING_RESIDENT",
            })
            device_actions.append({
                "device": "fire_tv",
                "action": "PIP_RESIDENT_DECISION_HUD",
                "severity": "NOTICE",
                "message": "Visitor at front door. Accept or speak over Fire TV remote.",
            })

        # 3. System 2: Amazon Bedrock conversational synthesis
        bedrock_result = self.bedrock.synthesize_response(visitor_input, eval_dict)

        total_latency_ms = (time.perf_counter() - start_overall) * 1000.0

        # 4. Record to immutable audit ledger
        audit_entry = self.audit.record_event(
            visitor_input=visitor_input,
            evaluation=eval_dict,
            bedrock_response=bedrock_result,
            device_actions=device_actions,
        )

        return {
            "visitor_input": visitor_input,
            "system_1_decider": eval_dict,
            "system_2_bedrock": bedrock_result,
            "device_actions": device_actions,
            "total_latency_ms": round(total_latency_ms, 2),
            "audit_id": audit_entry.get("timestamp"),
        }
