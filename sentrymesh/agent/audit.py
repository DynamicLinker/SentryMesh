import json
import os
import time
from typing import Any, Dict, List, Optional


class SecurityAuditLog:
    """Append-only audit ledger recording every visitor interaction and decision."""

    def __init__(self, log_dir: Optional[str] = None):
        self.log_dir = log_dir or os.path.join(os.path.dirname(__file__), "..", "data")
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = os.path.join(self.log_dir, "audit_ledger.jsonl")
        self._memory_entries: List[Dict[str, Any]] = []

    def record_event(
        self,
        visitor_input: str,
        evaluation: Dict[str, Any],
        bedrock_response: Dict[str, Any],
        device_actions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Record an entry to the audit trail."""
        entry = {
            "timestamp": time.time(),
            "iso_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "visitor_input": visitor_input,
            "system_1_decider": {
                "action": evaluation.get("action"),
                "reason": evaluation.get("reason"),
                "latency_ms": evaluation.get("latency_ms"),
                "injection_risk": evaluation.get("injection_risk", {}).get("probability"),
                "policy_category": evaluation.get("policy_category", {}).get("choice"),
            },
            "system_2_bedrock": {
                "response_text": bedrock_response.get("text"),
                "latency_ms": bedrock_response.get("latency_ms"),
                "model_id": bedrock_response.get("model_id"),
            },
            "device_actions": device_actions,
        }

        self._memory_entries.append(entry)

        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass

        return entry

    def get_recent_entries(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return most recent audit records."""
        return self._memory_entries[-limit:]
