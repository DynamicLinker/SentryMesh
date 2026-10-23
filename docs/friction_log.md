# Developer Friction Logs (10% Bonus Documentation)

**Project:** SentryMesh  
**Author:** DynamicLinker  
**Context:** Hands-on integration notes across Alexa+ MCP (Spec 2025-11-25), Strands Decider 2B, and Fire TV / Vega OS.

---

### Friction Entry 1: Streamable HTTP Content-Type and Chunked Transfer in MCP Spec 2025-11-25

* **Task Attempted:**  
  Implementing a compliant Streamable HTTP MCP endpoint (`POST /mcp`) using Python/FastAPI that can handle both single JSON-RPC responses and chunked tool streaming.
* **Steps Taken:**  
  1. Configured FastAPI router to accept incoming JSON-RPC payloads.
  2. Attempted to return `text/event-stream` for tool execution events as described in early preview guides.
  3. Found that certain MCP client runners expected `application/json` for non-streaming calls and rejected SSE event wrappers when `tools/call` returned a single object.
* **Expected vs. Actual:**  
  * *Expected:* A unified HTTP response mode where SSE streams can transparently carry JSON-RPC envelopes regardless of whether streaming is actively occurring.
  * *Actual:* Strict header mismatch errors (`415 Unsupported Media Type` or parse errors on the client side when SSE wrappers were returned for standard `initialize` calls).
* **Severity:** **Medium** (blocked initial client handshake for ~2 hours).
* **Workaround Used:**  
  Implemented dynamic content negotiation: return standard `application/json` for `initialize`, `tools/list`, and atomic tool calls, while keeping SSE streams strictly on a dedicated streaming subpath (`/mcp/events`).
* **Actionable Suggestion:**  
  Update the MCP Streamable HTTP specification documentation with an explicit transport state machine diagram showing exactly which endpoints/methods must return `application/json` versus `text/event-stream`.

---

### Friction Entry 2: Shared Prefix KV Cache Batching in Strands Decider 2B

* **Task Attempted:**  
  Scoring three questions (`injection_risk`, `policy_category`, `actuator_grounding`) against the same visitor state in a single batch pass to keep latency near 100ms.
* **Steps Taken:**  
  1. Sent a dictionary containing three questions in a single `/v1/decide` call.
  2. When evaluating locally without GPU acceleration, sequential scoring of each question ran in three separate forward passes (~340ms total).
* **Expected vs. Actual:**  
  * *Expected:* Built-in KV cache prefix reuse for multi-question requests across all runtime targets.
  * *Actual:* On standard CPU runners, without manual KV cache management, each question in the dictionary incurred token re-encoding.
* **Severity:** **Medium** (raised p50 latency from 110ms to ~340ms on small machines).
* **Workaround Used:**  
  Cached the prompt state embeddings and shared the prefix tensor across all questions in the local fallback evaluator, bringing p50 latency back down to 112.5ms.
* **Actionable Suggestion:**  
  Provide an official `strands-decider` Python helper utility that wraps KV prefix caching automatically on CPU environments so builders don't have to roll their own embedding cache.

---

### Friction Entry 3: Picture-in-Picture (PIP) Window Sizing and D-Pad Stealing on Fire OS / Vega OS

* **Task Attempted:**  
  Displaying an ambient security HUD overlay on Fire TV when a visitor arrives, allowing the viewer to press [Select] on the remote to approve entry without pausing ongoing media playback.
* **Steps Taken:**  
  1. Dispatched an ambient HUD alert over the MCP server.
  2. In simulated TV environments, displaying a modal dialog automatically took focus away from the background media player, causing audio stutter or video pause.
* **Expected vs. Actual:**  
  * *Expected:* A non-intrusive PIP overlay that renders in the corner of the screen while leaving remote focus with the primary media stream until the user presses an explicit shortcut.
  * *Actual:* Standard Android/Vega dialogs steal focus by default.
* **Severity:** **Low to Medium** (impacts viewing experience in living room scenarios).
* **Workaround Used:**  
  Configured the notification layer as a non-focusable secondary window (`FLAG_NOT_FOCUSABLE`), only requesting focus if the user taps the designated remote trigger.
* **Actionable Suggestion:**  
  Amazon Fire TV Developer Portal should provide an official "Ambient Notification SDK" template showing best practices for non-intrusive PIP focus management during live 4K playback.

---

## Feature Requests for Amazon Developer Tools

1. **Dedicated MCP Error Code for Guardrail Rejections (Urgency: Important):**  
   Standardize a JSON-RPC error code (e.g. `-32005 SafetyInterventionBlocked`) so conversational agents know the tool call was deliberately stopped by a security policy, rather than failing due to a server crash or timeout.
2. **Offline Decider 2B Package for Ring Edge Silicon (Urgency: Critical):**  
   Release a quantized ONNX / TensorRT-LLM export of Strands Decider 2B suitable for running on localized NPU chips inside Ring hardware.
3. **Fire TV Remote Macro Events for Alexa+ Skills (Urgency: Nice-to-have):**  
   Allow background MCP skills to register dedicated remote key shortcuts (e.g., long-press Play/Pause) to instantly toggle ambient overlays.
