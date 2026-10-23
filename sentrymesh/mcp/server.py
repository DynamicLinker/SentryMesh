import asyncio
import json
import os
import time
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from sentrymesh.agent.core import SentryMeshAgent
from sentrymesh.decider.types import ActionOutcome


app = FastAPI(
    title="SentryMesh Alexa+ Streamable MCP Server",
    description="Compliant Model Context Protocol (Spec 2025-11-25) server for Alexa+ and Amazon Devices",
    version="1.0.0",
)

# Enable CORS for local web companion
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = SentryMeshAgent()

# Simulated device states
device_state = {
    "smart_lock": {"locked": True, "last_unlocked": None, "state": "ENGAGED"},
    "ring_doorbell": {"online": True, "battery": 94, "motion": False, "live_feed": "active"},
    "fire_tv": {"current_media": "Live Sports: EPL", "hud_active": False, "pip_alert": None},
}


MCP_TOOLS = [
    {
        "name": "sentry_process_visitor",
        "description": "Evaluate incoming visitor audio at the front door using Strands Decider 2B and Bedrock.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "visitor_input": {"type": "string", "description": "Transcribed audio from Ring doorbell"},
                "badge_scanned": {"type": "boolean", "description": "Whether a digital NFC/carrier badge was scanned"},
                "resident_at_home": {"type": "boolean", "description": "Whether the homeowner is detected at home"},
            },
            "required": ["visitor_input"],
        },
    },
    {
        "name": "ring_doorbell_snapshot",
        "description": "Fetch real-time telemetry and camera status from the Ring doorbell.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "firetv_send_hud_alert",
        "description": "Dispatch an ambient Picture-in-Picture notification or decision HUD to Fire TV.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "severity": {"type": "string", "enum": ["INFO", "NOTICE", "CRITICAL"]},
                "message": {"type": "string", "description": "Alert message to render on Fire TV"},
            },
            "required": ["severity", "message"],
        },
    },
    {
        "name": "actuate_smart_lock",
        "description": "Actuate physical smart lock. Fails automatically if blocked by Decider 2B airgap.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["UNLOCK", "LOCK"]},
                "authorization_token": {"type": "string", "description": "Token signed by System 1 guardrail"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "get_audit_ledger",
        "description": "Retrieve recent tamper-proof security decisions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
]


def handle_tool_call(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute MCP tool calls with airgap enforcement."""
    if name == "sentry_process_visitor":
        visitor_input = arguments.get("visitor_input", "")
        context = {
            "badge_scanned": arguments.get("badge_scanned", False),
            "resident_at_home": arguments.get("resident_at_home", True),
        }
        res = agent.process_entry_request(visitor_input, context)

        # Update simulated hardware
        for act in res["device_actions"]:
            if act["device"] == "smart_lock" and act["action"] == "UNLOCK_MOMENTARY":
                device_state["smart_lock"]["locked"] = False
                device_state["smart_lock"]["state"] = "UNLOCKED"
                device_state["smart_lock"]["last_unlocked"] = time.time()
            elif act["device"] == "smart_lock" and act["action"] == "LOCK_ENGAGED":
                device_state["smart_lock"]["locked"] = True
                device_state["smart_lock"]["state"] = "AIRGAP_LOCKED"
            elif act["device"] == "fire_tv":
                device_state["fire_tv"]["hud_active"] = True
                device_state["fire_tv"]["pip_alert"] = {
                    "severity": act.get("severity", "INFO"),
                    "message": act.get("message", ""),
                    "timestamp": time.time(),
                }

        return res

    elif name == "ring_doorbell_snapshot":
        return {
            "status": "online",
            "battery_pct": device_state["ring_doorbell"]["battery"],
            "live_feed_resolution": "1080p_hdr",
            "active_visitors_detected": 1 if device_state["ring_doorbell"]["motion"] else 0,
        }

    elif name == "firetv_send_hud_alert":
        severity = arguments.get("severity", "INFO")
        msg = arguments.get("message", "")
        device_state["fire_tv"]["hud_active"] = True
        device_state["fire_tv"]["pip_alert"] = {"severity": severity, "message": msg, "timestamp": time.time()}
        return {"status": "dispatched_to_firetv", "alert": device_state["fire_tv"]["pip_alert"]}

    elif name == "actuate_smart_lock":
        # Pure physical actuator call
        action = arguments.get("action", "LOCK")
        if action == "UNLOCK":
            token = arguments.get("authorization_token")
            if token != "sentry_airgap_authorized":
                return {"status": "REJECTED", "error": "Hardware lock rejected: Missing airgap signature."}
            device_state["smart_lock"]["locked"] = False
            return {"status": "SUCCESS", "lock_state": "UNLOCKED"}
        else:
            device_state["smart_lock"]["locked"] = True
            return {"status": "SUCCESS", "lock_state": "LOCKED"}

    elif name == "get_audit_ledger":
        limit = arguments.get("limit", 10)
        return {"entries": agent.audit.get_recent_entries(limit)}

    raise HTTPException(status_code=404, detail=f"Tool '{name}' not found")


@app.post("/mcp")
async def mcp_streamable_endpoint(request: Request):
    """MCP Spec 2025-11-25 Streamable HTTP Endpoint for Alexa+ integration."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON-RPC payload")

    jsonrpc_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params", {})

    # Protocol handshake
    if method == "initialize":
        response_body = {
            "jsonrpc": "2.0",
            "id": jsonrpc_id,
            "result": {
                "protocolVersion": "2025-11-25",
                "capabilities": {
                    "tools": {"listChanged": True},
                    "logging": {},
                },
                "serverInfo": {
                    "name": "sentrymesh-alexa-mcp",
                    "version": "1.0.0",
                },
            },
        }
        return Response(
            content=json.dumps(response_body),
            media_type="application/json",
            headers={"MCP-Protocol-Version": "2025-11-25"},
        )

    # Tool discovery
    elif method == "tools/list":
        response_body = {
            "jsonrpc": "2.0",
            "id": jsonrpc_id,
            "result": {"tools": MCP_TOOLS},
        }
        return Response(content=json.dumps(response_body), media_type="application/json")

    # Tool execution
    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        try:
            call_result = handle_tool_call(tool_name, tool_args)
            response_body = {
                "jsonrpc": "2.0",
                "id": jsonrpc_id,
                "result": {
                    "content": [
                        {"type": "text", "text": json.dumps(call_result, indent=2)}
                    ],
                    "isError": False,
                },
            }
        except Exception as e:
            response_body = {
                "jsonrpc": "2.0",
                "id": jsonrpc_id,
                "result": {
                    "content": [{"type": "text", "text": str(e)}],
                    "isError": True,
                },
            }
        return Response(content=json.dumps(response_body), media_type="application/json")

    # Ping / Keepalive
    elif method == "ping":
        return Response(
            content=json.dumps({"jsonrpc": "2.0", "id": jsonrpc_id, "result": {}}),
            media_type="application/json",
        )

    return Response(
        content=json.dumps({
            "jsonrpc": "2.0",
            "id": jsonrpc_id,
            "error": {"code": -32601, "message": f"Method '{method}' not implemented"},
        }),
        media_type="application/json",
        status_code=400,
    )


# REST endpoints for UI simulator
@app.get("/")
@app.get("/dashboard")
def serve_dashboard():
    html_path = os.path.join(os.path.dirname(__file__), "..", "..", "web", "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return {"message": "SentryMesh MCP Server active. Web dashboard not found."}


class EvaluateRequest(BaseModel):
    visitor_input: str
    badge_scanned: bool = False
    resident_at_home: bool = True


@app.post("/api/evaluate")
def api_evaluate(req: EvaluateRequest):
    return handle_tool_call("sentry_process_visitor", req.dict())


@app.get("/api/devices")
def api_devices():
    return device_state


@app.get("/api/audit")
def api_audit():
    return {"entries": agent.audit.get_recent_entries(25)}


@app.post("/api/reset")
def api_reset():
    device_state["smart_lock"] = {"locked": True, "last_unlocked": None, "state": "ENGAGED"}
    device_state["fire_tv"]["hud_active"] = False
    device_state["fire_tv"]["pip_alert"] = None
    return {"status": "reset_successful", "devices": device_state}
