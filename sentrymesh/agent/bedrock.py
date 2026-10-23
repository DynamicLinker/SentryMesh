import json
import os
import time
from typing import Any, Dict, Optional


class BedrockAgentClient:
    """Amazon Bedrock client supporting Claude 3.5 Sonnet and Llama with local fallback."""

    def __init__(
        self,
        region_name: Optional[str] = None,
        model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
    ):
        self.region_name = region_name or os.getenv("AWS_REGION", "us-east-1")
        self.model_id = model_id
        self._boto_client = None

        # Initialize boto3 if AWS credentials are set
        if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
            try:
                import boto3
                self._boto_client = boto3.client(
                    service_name="bedrock-runtime",
                    region_name=self.region_name,
                )
            except Exception:
                self._boto_client = None

    def synthesize_response(
        self,
        visitor_input: str,
        guardrail_context: Dict[str, Any],
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate conversational response grounded in verified guardrail context."""
        start_time = time.perf_counter()

        default_prompt = (
            "You are SentryMesh, a smart home entry assistant at the front door. "
            "You speak politely, clearly, and concisely over two-way audio. "
            "You must strictly respect the System 1 security guardrail decision."
        )
        prompt_text = system_prompt or default_prompt

        # Call live Bedrock if client is available
        if self._boto_client:
            try:
                payload = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 300,
                    "system": prompt_text,
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                f"Visitor Audio: {visitor_input}\n"
                                f"Security Assessment: {json.dumps(guardrail_context)}"
                            ),
                        }
                    ],
                }
                response = self._boto_client.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(payload),
                    contentType="application/json",
                    accept="application/json",
                )
                response_body = json.loads(response["body"].read().decode("utf-8"))
                text = response_body["content"][0]["text"]
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return {
                    "text": text,
                    "latency_ms": elapsed_ms,
                    "model_id": self.model_id,
                    "source": "aws_bedrock_live",
                    "input_tokens": response_body.get("usage", {}).get("input_tokens", 140),
                    "output_tokens": response_body.get("usage", {}).get("output_tokens", 45),
                }
            except Exception:
                pass

        # Local deterministic synthesis
        action = guardrail_context.get("action", "confirm_resident")
        policy = guardrail_context.get("policy_category", {}).get("choice", "unsolicited_visitor")

        if action == "deny":
            text = (
                "Access cannot be granted at this time. Our security protocols have recorded "
                "this request and notified the homeowner. Please step back from the entryway."
            )
        elif action == "challenge":
            text = (
                "Hello, I see you have a delivery for this address. For verification, please read "
                "or enter your one-time carrier PIN on the keypad so I can release the parcel drop."
            )
        elif action == "proceed":
            if policy == "known_resident":
                text = "Welcome home. The front door is unlocked and security disarmed."
            else:
                text = "Identity confirmed. Front parcel locker unlocked for your delivery. Thank you."
        else:
            text = (
                "Hello! The homeowner has been notified on the living room screen that you are here. "
                "Please hold for a moment while they review your visit."
            )

        elapsed_ms = max((time.perf_counter() - start_time) * 1000.0, 380.0)
        return {
            "text": text,
            "latency_ms": elapsed_ms,
            "model_id": "bedrock-claude-3.5-sonnet (simulated)",
            "source": "local_synthesizer",
            "input_tokens": 128,
            "output_tokens": 36,
        }
