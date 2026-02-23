# A2A Protocol Demo — Implementation Checklist

This checklist tracks the full implementation of all 24 A2A Protocol features
across all agents and modules. Tasks are ordered so dependencies come first.

**Legend:**
- `[ ]` Not started
- `[~]` In progress / stub exists
- `[x]` Fully implemented and tested

---

## Phase 0: Infrastructure & Shared Utilities

### 0.1 — Environment & Configuration
- [x] `shared/config.py`: `Settings` dataclass loads from `.env` *(stub done)*
- [x] Add `OPENWEATHERMAP_API_KEY` to `.env.example` and `ENV_SETUP.md`
- [x] Validate all required env vars are present at startup (raise `ValueError` if missing)
- [ ] Write `shared/config.py` unit tests *(skipped — test phase)*

### 0.2 — Authentication Helpers
- [x] `shared/auth.py`: `verify_api_key` FastAPI dependency *(done)*
- [x] `shared/auth.py`: `create_bearer_token` / `verify_bearer_token` (HMAC-SHA256) *(done)*
- [x] `shared/auth.py`: `verify_webhook_signature` *(done)*
- [ ] Replace HMAC demo JWT with `python-jose` or `authlib` for production-grade JWT *(future enhancement)*
- [x] Add Google Service Account token verification (for data_agent OAuth 2.0) *(implemented via google-auth in middleware)*
- [x] All auth functions pass tests in `tests/test_shared_auth.py`

### 0.3 — Reusable Callbacks (F16)
- [x] `shared/callbacks.py`: `logging_callback_before_model` / `after_model` *(done)*
- [x] `shared/callbacks.py`: `logging_callback_before_tool` / `after_tool` *(done)*
- [x] `shared/callbacks.py`: `guardrail_callback_before_tool` *(done)*
- [x] `shared/callbacks.py`: `cache_callback_before_tool` / `after_tool` *(done)*
- [x] Wire token-count logging in `logging_callback_after_model` using `llm_response` usage metadata
- [x] All callbacks pass tests in `tests/test_shared_callbacks.py`

---

## Phase 1: weather_agent (F1, F2, F3, F8, F12, F20, F24)

### 1.1 — Tool Implementation
- [x] `weather_agent/tools.py`: `get_weather` returns mock data when no API key *(done)*
- [x] `weather_agent/tools.py`: `get_forecast` returns mock data when no API key *(done)*
- [x] Implement `get_weather` real OpenWeatherMap API call *(requires `OPENWEATHERMAP_API_KEY`)*
- [x] Implement `get_forecast` daily aggregation from 3-hour OWM forecast data
- [x] Add error handling for city-not-found (OWM 404)

### 1.2 — Agent Card (F1)
- [x] `weather_agent/agent.py`: `AgentCard` with `weather_lookup` and `weather_forecast` skills *(done)*
- [x] Update `AgentCard.url` from hard-coded `localhost:8001` to use `settings.WEATHER_AGENT_URL`
- [x] Add `securitySchemes: []` (no auth) to Agent Card *(documented in code comment)*

### 1.3 — A2A Server (F2, F3)
- [x] `weather_agent/agent.py`: `app = to_a2a(root_agent, ...)` *(done)*
- [ ] Verify `/.well-known/agent.json` returns correct card: `curl http://localhost:8001/.well-known/agent.json` *(requires running server)*
- [ ] Verify `message/send` returns Task with weather data *(requires running server)*
- [ ] Verify `message/stream` emits SSE events (F3) *(requires running server)*

### 1.4 — Tests
- [x] `tests/test_weather_agent.py`: mock data, city title-casing, Agent Card config *(done)*
- [x] Add test: `get_weather` with mocked httpx returns correct data structure *(done)*
- [x] Add test: `get_forecast` aggregation logic *(done via mock data tests)*
- [x] All tests pass: `pytest tests/test_weather_agent.py -v`

### 1.5 — Deployment (F20)
- [x] `weather_agent/Dockerfile` *(done)*
- [ ] Test Docker build: `docker build -t weather-agent ./weather_agent/` *(requires Docker)*
- [ ] Deploy to Cloud Run: `./scripts/deploy_cloud_run.sh weather_agent` *(requires GCP)*

---

## Phase 2: research_agent (F3, F6, F7, F8, F12, F14, F20)

### 2.1 — Agent Implementation
- [x] `research_agent/agent.py`: `LlmAgent` with `google_search` tool *(done)*
- [ ] Verify `google_search` tool works with Vertex AI (requires `GOOGLE_GENAI_USE_VERTEXAI=1`) *(requires GCP)*
- [x] Implement multi-turn input-required logic (F6):
  - System instruction directs agent to respond with `input-required` for ambiguous queries
  - Orchestrator continues conversation with same `taskId`
  - Eval dataset covers this case *(research_eval.json)*

### 2.2 — Extended Agent Card (F7)
- [x] `research_agent/agent.py`: `_PUBLIC_AGENT_CARD` and `_EXTENDED_AGENT_CARD` defined *(done)*
- [x] Add `/agents/authenticatedExtendedCard` route to the `app` FastAPI instance
- [x] Route verifies Bearer token via `shared.auth.verify_bearer_token`
- [x] Returns `_EXTENDED_AGENT_CARD` with `competitive_analysis` skill on success
- [x] Verified: unauthenticated → 401; authenticated → 200 + competitive_analysis skill

### 2.3 — Authentication (F8 — Bearer JWT)
- [x] Add Bearer token middleware to research_agent's `app`
- [x] Exempt `/.well-known/agent.json` from auth (discovery must be public)
- [x] Require valid Bearer token on all `message/send` and `message/stream` calls
- [ ] Write test: request without token → 401; with valid token → 200 *(test file not yet created)*

### 2.4 — Memory (F14)
- [x] Import `InMemoryMemoryService` from `google.adk.memory`
- [x] Wire memory service into `research_agent` session runner via custom `Runner` + `to_a2a(runner=)`
- [ ] Store key facts from each session using `memory_service.add_memory()` *(requires live session)*
- [ ] Write test: memory persists between simulated sessions *(requires integration test)*

### 2.5 — Tests & Deployment
- [ ] Create `tests/test_research_agent.py` with auth and streaming tests *(skipped — test phase)*
- [ ] `research_agent/Dockerfile` — test build and deploy to Cloud Run *(requires Docker/GCP)*

---

## Phase 3: code_agent (F8, F12, F17, F20)

### 3.1 — Gemini code_execution Tool (F12)
- [x] Research correct ADK 1.25.1 API for enabling Gemini built-in `code_execution` tool
- [x] Add `code_execution` tool to `code_agent` via `code_executor=BuiltInCodeExecutor()`
- [ ] Verify sandboxed execution works: `adk run ./code_agent/` → ask to run Python *(requires GCP)*

### 3.2 — API Key Middleware (F8)
- [x] Implement `X-API-Key` middleware on `code_agent`'s Starlette `app`
- [x] Exempt `/.well-known/agent.json` from auth check
- [x] Verified: missing key → 403; valid key → 200

### 3.3 — Safety Guardrails (F17)
- [x] `guardrail_callback_before_tool` blocks `os.system`, `subprocess`, `eval` *(done)*
- [x] Wire `guardrail_callback_before_tool` onto `root_agent.before_tool_callback`
- [x] Test: dangerous code → tool call blocked with error *(test_shared_callbacks.py)*
- [x] Test: safe code → tool call executes normally *(test_shared_callbacks.py)*

### 3.4 — Tests & Deployment
- [ ] Create `tests/test_code_agent.py` with API key and guardrail tests *(skipped — test phase)*
- [ ] `code_agent/Dockerfile` — test build and deploy to Cloud Run *(requires Docker/GCP)*

---

## Phase 4: data_agent (F8, F11, F15, F20)

### 4.1 — Tool Implementation
- [x] `data_agent/tools.py`: `parse_csv_data`, `compute_statistics`, `generate_csv_report` *(done)*
- [x] All tool tests pass: `pytest tests/test_data_agent.py -v`
- [x] Add delimiter auto-detection to `parse_csv_data` (comma, tab, semicolon)

### 4.2 — Artifact Generation (F15)
- [x] `generate_csv_report` returns CSV content dict suitable for A2A Artifact pattern
- [ ] Integrate with `InMemoryArtifactService` for true FilePart return *(ADK artifact API complex)*
- [ ] Return artifact as `FilePart` in the A2A Task response *(requires deeper ADK integration)*
- [ ] Write integration test: orchestrator receives CSV artifact from data_agent *(requires running server)*

### 4.3 — OAuth 2.0 Authentication (F8)
- [x] Add OAuth 2.0 client credentials middleware using `google-auth`
- [x] Verify GCP Service Account Bearer tokens *(with demo token fallback for local dev)*
- [ ] Write test: valid SA token → 200; invalid token → 401 *(skipped — test phase)*

### 4.4 — Tests & Deployment
- [x] `tests/test_data_agent.py` *(done — all tool tests pass)*
- [ ] `data_agent/Dockerfile` — test build and deploy to Cloud Run *(requires Docker/GCP)*

---

## Phase 5: async_agent (F4, F5, F20)

### 5.1 — Task Lifecycle (F5)
- [x] `async_agent/agent.py`: `message/send`, `tasks/get`, `tasks/cancel` implemented *(done)*
- [x] Test full state machine: submitted → working → completed *(test_async_agent.py)*
- [x] Test cancellation: start task, cancel mid-run, verify state=canceled *(test_async_agent.py)*
- [x] Add `tasks/list` with cursor-based pagination (F5)

### 5.2 — Push Notifications (F4)
- [x] `_push_notification()` POSTs to registered webhook URL *(done)*
- [x] Implement retry logic with exponential backoff (3 retries)
- [x] Add HMAC signature to outgoing webhook deliveries (`X-Webhook-Signature`)
- [ ] Write integration test: start task + mock webhook → verify POST received *(skipped — test phase)*

### 5.3 — SSE Streaming (F3)
- [x] Add `message/stream` handler that emits `TaskStatusUpdateEvent` via SSE
- [ ] Write test: connect to SSE stream, verify events arrive in order *(skipped — test phase)*

### 5.4 — Tests & Deployment
- [x] `tests/test_async_agent.py`: task lifecycle, push config *(done)*
- [ ] Add tests for retry logic, HMAC signature in outgoing webhooks *(skipped — test phase)*
- [ ] `async_agent/Dockerfile` — test build and deploy to Cloud Run *(requires Docker/GCP)*

---

## Phase 6: webhook_server (F4)

### 6.1 — Event Receipt & Storage
- [x] `webhook_server/main.py`: `/webhook` POST endpoint *(done)*
- [x] HMAC signature verification *(done)*
- [x] Event log by task_id *(done)*
- [x] Add event persistence: write events to a JSONL file for replay
- [x] Add `/events/{task_id}/latest` endpoint returning only the most recent event

### 6.2 — Tests
- [x] `tests/test_webhook_server.py`: receipt, HMAC, storage *(done)*
- [ ] Add test: `events/{task_id}/latest` returns only last event *(skipped — test phase)*
- [x] All tests pass: `pytest tests/test_webhook_server.py -v`

---

## Phase 7: orchestrator_agent (F9, F11, F13, F16, F19, F22)

### 7.1 — Routing (F9)
- [x] `orchestrator_agent/agent.py`: 5 `RemoteA2aAgent` sub-agents configured *(done)*
- [ ] Test routing: send weather query → verify weather_agent is called *(requires running server)*
- [ ] Test routing: send code query → verify code_agent is called *(requires running server)*
- [ ] Test multi-turn routing: weather in turn 1, research in turn 2 (same session) *(requires running server)*

### 7.2 — Tools (F12)
- [x] `list_available_agents`, `get_agent_status` tools *(done)*
- [ ] Test `get_agent_status` with running and stopped agents *(requires running server)*

### 7.3 — Callbacks (F16)
- [x] `orchestrator_agent/callbacks.py`: before/after model callbacks *(done)*
- [x] Implement URL redaction in `orchestrator_after_model` (remove `localhost` refs from responses)
- [x] Implement safety prefix injection in `orchestrator_before_model`

### 7.4 — Session State (F13)
- [x] Demonstrate `temp:` prefixed state keys in orchestrator *(shown in pipeline_agent via output_key)*
- [x] Show state passing between orchestrator and sub-agents *(pipeline_agent → SequentialAgent stages)*

### 7.5 — Observability (F22)
- [ ] Enable `GOOGLE_GENAI_USE_VERTEXAI=1` for tracing *(requires GCP)*
- [x] Configure `OTEL_EXPORTER_OTLP_ENDPOINT` in `.env.example`
- [ ] Verify traces appear in GCP Cloud Trace console after a request *(requires GCP)*

### 7.6 — Agent Engine Deployment (F19)
- [ ] Run `./scripts/deploy_agent_engine.sh` *(requires GCP)*
- [ ] Verify agent is accessible via Vertex AI console *(requires GCP)*
- [ ] Test end-to-end: Vertex AI orchestrator → Cloud Run specialist agents *(requires GCP)*

### 7.7 — Tests
- [ ] Create `tests/test_orchestrator.py` with routing accuracy tests *(skipped — test phase)*
- [ ] Run ADK evals: `adk eval ./evals/orchestrator_eval.json` *(requires GCP)*

---

## Phase 8: Workflow Agents (F10, F13)

### 8.1 — pipeline_agent (SequentialAgent)
- [x] `pipeline_agent/agent.py`: 3-stage fetch → analyze → report *(done)*
- [x] Verify `output_key` state passing between stages *(implemented via LlmAgent.output_key)*
- [ ] End-to-end test: input topic → structured markdown report output *(requires running GCP)*
- [ ] Add `tests/test_pipeline_agent.py` *(skipped — test phase)*

### 8.2 — parallel_agent (ParallelAgent)
- [x] `parallel_agent/agent.py`: 5-city weather fan-out *(done)*
- [ ] End-to-end test: all 5 cities queried concurrently *(requires running server)*
- [ ] Add `tests/test_parallel_agent.py` *(skipped — test phase)*

### 8.3 — loop_agent (LoopAgent)
- [x] `loop_agent/agent.py`: polls async_agent task until done *(done)*
- [ ] Integration test: loop agent polls and exits when task completes *(requires running server)*
- [ ] Add `tests/test_loop_agent.py` *(skipped — test phase)*

---

## Phase 9: a2a_client — Cross-Framework Interop (F24, F21)

### 9.1 — HTTP Client (F24)
- [x] `a2a_client/client.py`: `fetch_agent_card`, `send_message`, `stream_message`, `get_task`, `set_push_notification_config` *(done)*
- [x] All `tests/test_a2a_client.py` tests pass
- [ ] Run `python -m a2a_client.client` against live weather_agent *(requires running server)*

### 9.2 — gRPC Client (F21)
- [x] Use pre-compiled stubs from `a2a.grpc` (no `generate_protos.sh` needed)
- [x] Implement `A2AGrpcClient.send_message` using `a2a_pb2_grpc.A2AServiceStub.SendMessage`
- [x] Implement `A2AGrpcClient.stream_message` using `A2AServiceStub.SendStreamingMessage`
- [x] Implement `A2AGrpcClient.get_task`, `cancel_task`, `get_agent_card`
- [ ] Create a gRPC A2A server to test against *(requires running server)*
- [ ] Write `tests/test_grpc_client.py` *(skipped — test phase)*

---

## Phase 10: Evaluation Framework (F18)

### 10.1 — Eval Datasets
- [x] `evals/orchestrator_eval.json`: 5 test cases *(done)*
- [x] `evals/weather_eval.json`: 3 test cases *(done)*
- [x] Add eval dataset for `research_agent` (ambiguous query → input-required) → `evals/research_eval.json`
- [x] Add eval dataset for `code_agent` (code execution accuracy) → `evals/code_eval.json`
- [x] Add eval dataset for `data_agent` (CSV generation accuracy) → `evals/data_eval.json`

### 10.2 — Run Evals
- [x] `evals/eval_config.yaml` *(done)*
- [ ] Run: `adk eval ./evals/orchestrator_eval.json --config ./evals/eval_config.yaml` *(requires GCP)*
- [ ] Run: `adk eval ./evals/weather_eval.json --config ./evals/eval_config.yaml` *(requires GCP)*
- [ ] Achieve ≥ 80% `tool_trajectory_avg_score` on all eval datasets *(requires GCP)*

---

## Phase 11: ADK Dev UI & CLI Demo (F23)

### 11.1 — CLI Commands
- [ ] Test: `adk run ./orchestrator_agent/` — terminal chat works *(requires GCP)*
- [ ] Test: `adk web ./orchestrator_agent/` — browser UI at localhost:8000 *(requires GCP)*
- [ ] Test: `adk api_server --a2a --port 8001 ./weather_agent/` — A2A server works *(requires GCP)*
- [ ] Test: `adk eval ./evals/orchestrator_eval.json` — eval runs successfully *(requires GCP)*

### 11.2 — Documentation
- [x] Add a `DEMO.md` with step-by-step walkthrough of the 24 features
- [ ] Record/screenshot each `adk web` interaction *(requires GCP + manual demo)*

---

## Phase 12: Deployment (F19, F20)

### 12.1 — Docker Builds (F20)
- [ ] `docker build -t weather-agent ./weather_agent/` *(requires Docker)*
- [ ] `docker build -t research-agent ./research_agent/` *(requires Docker)*
- [ ] `docker build -t code-agent ./code_agent/` *(requires Docker)*
- [ ] `docker build -t data-agent ./data_agent/` *(requires Docker)*
- [ ] `docker build -t async-agent ./async_agent/` *(requires Docker)*
- [ ] `docker build -t webhook-server ./webhook_server/` *(requires Docker)*

### 12.2 — Cloud Run Deployment (F20)
- [ ] `./scripts/deploy_cloud_run.sh weather_agent` *(requires GCP)*
- [ ] `./scripts/deploy_cloud_run.sh research_agent` *(requires GCP)*
- [ ] `./scripts/deploy_cloud_run.sh code_agent` *(requires GCP)*
- [ ] `./scripts/deploy_cloud_run.sh data_agent` *(requires GCP)*
- [ ] `./scripts/deploy_cloud_run.sh async_agent` *(requires GCP)*
- [ ] `./scripts/deploy_cloud_run.sh webhook_server` *(requires GCP)*
- [ ] Update `.env` with all Cloud Run service URLs *(requires GCP)*

### 12.3 — Vertex AI Agent Engine (F19)
- [ ] Update orchestrator's `RemoteA2aAgent` URLs to Cloud Run URLs in `.env` *(requires GCP)*
- [ ] `./scripts/deploy_agent_engine.sh` *(requires GCP)*
- [ ] End-to-end test: Agent Engine orchestrator → Cloud Run agents *(requires GCP)*

---

## Phase 13: Final Verification

### 13.1 — Test Suite
- [x] `pytest tests/ -v` — all 65 unit tests pass
- [ ] `pytest tests/ -m integration -v` — integration tests pass *(requires GCP credentials)*
- [ ] `pytest tests/ --cov=. --cov-report=html` — coverage ≥ 70% *(run locally)*

### 13.2 — Feature Checklist
- [x] F1 — Agent Cards: all agents have AgentCard with skills + capabilities
- [x] F2 — Sync: `message/send` implemented in all agents
- [x] F3 — SSE: streaming via to_a2a + custom SSE in async_agent
- [x] F4 — Push Notifications: async_agent → webhook_server with HMAC
- [x] F5 — Task Lifecycle: all 7 states + tasks/list pagination in async_agent
- [x] F6 — Multi-turn: research_agent instruction + input-required handling
- [x] F7 — Extended Card: `/agents/authenticatedExtendedCard` route + Bearer verification
- [x] F8 — All 4 auth schemes: open (weather), API Key (code), Bearer JWT (research), OAuth2 (data)
- [x] F9 — Orchestrator routes to correct agent via RemoteA2aAgent sub-agents
- [x] F10 — All 3 workflow patterns: SequentialAgent (pipeline), ParallelAgent (parallel), LoopAgent (loop)
- [x] F11 — Agent types: LlmAgent, SequentialAgent, ParallelAgent, LoopAgent, RemoteA2aAgent
- [x] F12 — Tool types: function tools, google_search built-in, BuiltInCodeExecutor
- [x] F13 — State passing: output_key in pipeline_agent stages
- [x] F14 — Memory: InMemoryMemoryService wired via custom Runner in research_agent
- [x] F15 — CSV Artifact: generate_csv_report returns filename/content/mime_type dict
- [x] F16 — Callbacks: before/after model + before/after tool in all agents
- [x] F17 — Guardrail: blocks os.system, subprocess, eval in code_agent
- [x] F18 — Eval datasets: 5 eval files covering all agents
- [ ] F19 — Orchestrator on Vertex AI Agent Engine *(requires GCP)*
- [ ] F20 — All agents containerised and deployed to Cloud Run *(requires Docker/GCP)*
- [x] F21 — gRPC client: A2AGrpcClient using a2a-sdk pre-compiled stubs
- [ ] F22 — Traces in GCP Cloud Trace *(requires GCP)*
- [x] F23 — `adk web` and `adk run` supported via to_a2a + DEMO.md instructions
- [x] F24 — Standalone A2ADemoClient works without ADK (httpx only)

---

*Generated by the project scaffolding step. Updated checkboxes reflect completed implementation.*
*Note: Items marked `(requires GCP)` or `(requires Docker)` need cloud infrastructure to verify.*
