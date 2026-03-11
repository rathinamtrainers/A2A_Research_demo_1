# Speaker Notes — A2A Protocol Demo Presentation

> **File**: `A2A_Protocol_Demo.pptx` (34 slides)
> **Estimated delivery time**: 60–75 minutes (with live demo)
> **Audience**: Developers, architects, and technical leads interested in multi-agent systems

---

## Slide 1 — Title Slide

**"A2A Protocol Demo — A Complete Implementation of the Agent-to-Agent Protocol"**

> Welcome everyone. Today I'm going to walk you through a complete, working implementation of the A2A Protocol — that's Agent-to-Agent, Google's open standard for making AI agents talk to each other.
>
> What you're going to see is not a toy example. This is a production-grade system — 9 agents, 4 different authentication schemes, 300 tests, all built on Google ADK version 1.25.1 and ready to deploy to Vertex AI and Cloud Run.
>
> By the end of this session, you'll understand not just what A2A is, but exactly how to build your own multi-agent system using it.

---

## Slide 2 — Agenda

> Here's our roadmap for today. We've got 10 sections.
>
> We'll start with the "why" — why do we even need a protocol for agents? Then we'll cover Google ADK, the framework we're building on.
>
> The middle chunk is where we spend most of our time — the architecture, the agents themselves, how auth works, how callbacks and guardrails work.
>
> We'll wrap up with testing, deployment, and a live demo where you'll see everything running end to end.
>
> Feel free to interrupt with questions at any point. This is meant to be a conversation, not a lecture.

---

## Slide 3 — Why A2A?

**Section title slide**

> So let's start with the problem. Right now, if you build an agent in LangChain, it can't talk to an agent built in CrewAI. An AutoGen agent has no way to discover what a Vertex AI agent can do. Every framework has its own proprietary way of communicating.
>
> Think about what the web was like before HTTP. That's where we are with AI agents today. Everyone has their own protocol, their own format, their own way of doing things. You end up locked into one framework, one vendor.
>
> A2A changes that. It's the HTTP of the agent world — an open protocol that lets any agent talk to any other agent, regardless of how it was built.

---

## Slide 4 — A2A Protocol Core Concepts

> Let me break down the four pillars of the A2A protocol.
>
> First, the **Agent Card**. This is like a business card for your AI agent. It's a JSON document served at a well-known URL — `/.well-known/agent.json` — and it tells the world: here's my name, here are my skills, here's what I can do, and here's how to authenticate with me. Same idea as `.well-known/openid-configuration` if you've worked with OAuth.
>
> Second, **JSON-RPC 2.0**. All communication goes through JSON-RPC. You POST to a single endpoint, and the `method` field tells the server what you want: `message/send` for synchronous calls, `message/stream` for streaming, `tasks/get` to check on a running task.
>
> Third, the **Task Lifecycle**. When you send a message to an agent, it creates a task. That task goes through states: submitted, working, completed — or it could fail, get cancelled, or ask for more input. Seven states total.
>
> And fourth, **Message Parts**. Messages aren't just plain text. They have a `role` — user or agent — and an array of parts. A part can be text, a file, or structured data. This means agents can exchange not just words but files, JSON payloads, images, whatever they need.

---

## Slide 5 — Protocol vs SDK vs Framework

> This is a distinction that trips people up, so let me be really clear about it.
>
> The **A2A Protocol** is the specification. It's like the HTTP spec — it defines the rules. What methods exist, what the Agent Card schema looks like, how JSON-RPC messages are structured.
>
> The **a2a-sdk** is the reference implementation. It's a Python package that gives you data classes, gRPC stubs, and helper functions. It makes it easier to work with the protocol, but you don't *need* it.
>
> And **Google ADK** — the Agent Development Kit — is a full framework that happens to implement A2A. It gives you `LlmAgent`, `RemoteA2aAgent`, `to_a2a()`, and a bunch of other abstractions.
>
> Here's the key insight — and this is on the slide — you can build a fully A2A-compliant agent without ADK. Our `a2a_client/client.py` proves it. It uses nothing but `httpx` — raw HTTP calls. No SDK, no framework. That's the power of having an open protocol.

---

## Slide 6 — Google ADK Section Title

**Section title slide**

> Now let's look at the tool we're using to build our agents — Google's Agent Development Kit, or ADK.
>
> ADK is open source, it's at version 1.25.1, and it gives us everything we need to build, test, and deploy A2A-compliant agents. Think of it as the Rails of the agent world — opinionated, batteries-included, and designed to get you to production fast.

---

## Slide 7 — ADK Building Blocks

> ADK gives you six main building blocks. Let me walk through each one.
>
> **LlmAgent** — this is the star of the show. It wraps a Gemini model with an instruction prompt, a set of tools, optional sub-agents, and callbacks. Most of our agents are LlmAgents.
>
> **SequentialAgent** — runs sub-agents one after another, like a pipeline. Agent A finishes, then Agent B starts, then Agent C. Deterministic, predictable.
>
> **ParallelAgent** — runs sub-agents at the same time. Fan-out pattern. You give it five agents, all five execute concurrently.
>
> **LoopAgent** — repeats its sub-agents until some exit condition is met, or you hit a maximum iteration count. Think of it as a while loop for agents.
>
> **RemoteA2aAgent** — this is the A2A glue. It's a proxy that represents a remote agent. You give it the URL of the agent's card, and it handles discovery and communication. This is how the orchestrator talks to specialist agents.
>
> And **to_a2a()** — a single function call that converts any ADK agent into a fully A2A-compliant web application. It sets up the Agent Card route, the JSON-RPC dispatcher, everything. One line of code.

---

## Slide 8 — Architecture Overview Section Title

**Section title slide**

> Let's zoom out and look at how all of these pieces fit together. This is the architecture of our demo system — a multi-agent ecosystem with specialist routing.

---

## Slide 9 — Request Flow (Top to Bottom)

> This is the request flow, top to bottom. Follow the arrows with me.
>
> A user asks: "What is the weather in Paris?" That request hits **Layer 1 — the Client**. This can be our httpx client, our gRPC client, or even a plain curl command. Any HTTP client works.
>
> The client sends a JSON-RPC message over HTTP to **Layer 2 — the Orchestrator**. The orchestrator is an LlmAgent with five RemoteA2aAgent sub-agents. It reads their descriptions, and the LLM — Gemini 2.0 Flash — decides: "This is a weather question. I should route it to weather_agent."
>
> Now we're in **Layer 3 — Specialist Agents**. The weather agent runs on port 8001, no auth required. The research agent is on 8002 with JWT auth. Code agent on 8003 with API key. Data agent on 8004 with OAuth. And the async agent on 8005 with push notification support.
>
> All of them sit on top of **Layer 4 — the Shared Foundation**: `config.py` for centralized settings, `auth.py` for the four authentication schemes, and `callbacks.py` for logging, guardrails, and caching. Every agent imports from this shared layer.
>
> Notice the auth headers — the orchestrator creates pre-configured `httpx.AsyncClient` instances with the right headers already set. So when it calls the code agent, the API key is already in the request. When it calls the research agent, the JWT token is already attached. No per-request auth logic needed.

---

## Slide 10 — Architecture Diagram (PNG)

> Here's the same architecture as a visual diagram. You can see the four layers clearly.
>
> At the top, the client layer with both HTTP and gRPC options. Below that, the orchestrator in the centre, fanning out to all five specialist agents. Each agent box shows its port number, its auth scheme, and its key tools.
>
> At the bottom, the shared foundation modules connecting to every agent. And on the right, you can see the supporting systems — the workflow agents and the webhook server for push notifications.
>
> Take a moment to absorb this layout. It's the mental map you'll use for the rest of the presentation.

---

## Slide 11 — Communication Patterns

> A2A supports multiple communication patterns, and our demo implements all of them.
>
> **Synchronous request/response** — you send "Weather in Paris?" and you get a complete answer back in one response. This uses `message/send`. Simplest pattern.
>
> **SSE Streaming** — the server sends tokens or progress events as they're generated. Uses `message/stream`. The client gets an event stream and processes events as they arrive. Great for long-running LLM calls where you want to show output incrementally.
>
> **Async with Push Notifications** — you send a request, the server immediately returns a task ID, then works in the background. When it's done, it POSTs a notification to your webhook. This is how the async agent works for 20-second simulations.
>
> **Polling** — the loop agent uses this. Start a task, then periodically call `tasks/get` to check the status. Still working? Wait and check again. Done? Grab the result.
>
> **Cancellation** — you can cancel a running task with `tasks/cancel`. The async agent supports this.
>
> And **multi-turn conversations** — send a second message with the same `taskId` to continue a conversation. The research agent uses this for deep-dive research sessions.

---

## Slide 12 — Project Structure Section Title

**Section title slide**

> Now let's look at how the code is organized. The directory layout, the shared infrastructure, and how configuration flows through the system.

---

## Slide 13 — Directory Layout

> Here's the project tree. Each agent lives in its own directory — that's a deliberate design choice. In production, each of these could be a separate microservice, a separate repo, maintained by a separate team.
>
> On the left: `shared/` has the cross-cutting code that every agent needs. Then the agents themselves — weather, research, code, data, async, and the orchestrator. Plus the three workflow agents: pipeline, parallel, and loop.
>
> On the right: the standalone clients in `a2a_client/`, the webhook server for receiving push notifications, evaluation datasets in `evals/`, gRPC proto definitions, startup/shutdown scripts, and the test suite — 300 tests in the `tests/` directory.
>
> At the root: `.env` for runtime configuration and `requirements.txt` with pinned dependencies.
>
> The key thing to notice is the separation of concerns. Agent code is separate from shared infrastructure. Client code is separate from server code. Tests are separate from production code. Each piece has a clear home.

---

## Slide 14 — Shared Config

> Let's drill into the shared layer, starting with `config.py`.
>
> This is a Python dataclass — `Settings` — with 14 fields. Every environment variable the system needs is defined here with a sensible default. The GCP project ID, the Gemini model name, URLs for all five agents, API keys, JWT secrets.
>
> The `validate()` method runs at startup and checks that required fields are set. If you forgot to set your GCP project, the app tells you immediately instead of failing at some random point later. Fail fast.
>
> There's one clever detail here — the test guard. `if "pytest" not in sys.modules: settings.validate()`. During test collection, pytest imports your modules but hasn't set up mock environment variables yet. Without this guard, your tests would crash during collection because settings validation would fail. It's a small thing, but it matters.
>
> Every agent in the system does `from shared.config import settings`. One import, one source of truth, one place to change configuration.

---

## Slide 15 — Agent Deep Dives Section Title

**Section title slide**

> Now we get to the fun part — the agents themselves. We'll start with the simplest one, the weather agent, and build up from there.

---

## Slide 16 — weather_agent — The Minimal A2A Agent Pattern

> The weather agent is the "hello world" of A2A. It demonstrates the minimal pattern for creating an A2A agent, and it takes just three steps.
>
> **Step 1**: Define the Agent Card. This is where you declare your agent's name, its skills, and its capabilities. Our weather agent has two skills — get weather and get forecast — and it supports streaming.
>
> **Step 2**: Create the LLM Agent. Give it a model — Gemini 2.0 Flash — an instruction telling it it's a weather assistant, and the tools it can call. That's it. The agent knows how to use those tools because ADK generates JSON schemas from the function signatures and docstrings.
>
> **Step 3**: Call `to_a2a()`. One function call, and ADK creates a complete web application with two routes: `GET /.well-known/agent.json` for the Agent Card, and `POST /` for the JSON-RPC dispatcher.
>
> Three steps. Agent Card, LLM Agent, `to_a2a()`. That's the pattern you'll use for every agent you build with ADK. Everything else — auth, callbacks, streaming — is layered on top of this foundation.

---

## Slide 17 — Function Tools

> Let's look at how the weather agent's tools actually work.
>
> This is `get_weather()`. It's just a Python async function with type hints and a docstring. That's all ADK needs. It reads the type hints and generates a JSON Schema that tells the LLM: "This function takes a `city` parameter, which is a string." It reads the docstring and tells the LLM what the function does.
>
> When the LLM decides to call `get_weather("London")`, ADK invokes this function with the city argument. The function calls the OpenWeatherMap API, parses the response, and returns a dictionary.
>
> Notice the fallback pattern. If there's no API key configured — `if not settings.OPENWEATHERMAP_API_KEY` — it returns mock data instead. This is critical for demos and testing. The demo works out of the box, no API keys needed. No external dependencies that could break your presentation.
>
> And it's async by design. `httpx.AsyncClient` makes non-blocking HTTP calls. ADK handles async tools natively, so the event loop stays responsive while waiting for the weather API.

---

## Slide 18 — orchestrator_agent — The Router

> The orchestrator is the brain of the system. It's the hub in our hub-and-spoke architecture.
>
> Look at the code. First, we create pre-configured httpx clients with auth headers. The code agent client has the API key. The research agent client has a JWT Bearer token. Each client also has a 120-second timeout — because the default 5 seconds is way too short when you're waiting for an LLM to think and then make tool calls.
>
> Then we create `RemoteA2aAgent` instances — one for each specialist. Each one gets a name, a description, the Agent Card URL, and optionally the auth-configured httpx client.
>
> The descriptions are critical. Those descriptions are what the LLM reads when it decides where to route. "Handles weather queries for any city" — that's how Gemini knows to send weather questions to the weather agent. If your descriptions are vague, your routing will be bad.
>
> Finally, we assemble the root agent. It's an LlmAgent with all five RemoteA2aAgents as sub-agents, plus two local tools for introspection — `list_available_agents` and `get_agent_status`. The LLM can check if an agent is alive before trying to route to it.
>
> There's no `if/else` routing logic anywhere. The LLM reads the system instruction, reads the descriptions, reads the user's message, and makes its own judgment call. That's the "LLM-as-router" pattern. It's flexible, it handles ambiguity gracefully, and it scales to any number of agents.

---

## Slide 19 — async_agent — Custom A2A (No ADK)

> The async agent is special. It's the only agent in this demo that does NOT use ADK. It's built with raw FastAPI, implementing the A2A protocol by hand.
>
> Why? Because ADK's default handler doesn't support several things we need: background task execution — imagine a 20-second simulation running while the client does other things. Push notifications — sending webhook updates when a task completes. Task cancellation — aborting a running task. SSE streaming with progress updates. And cursor-based pagination for listing tasks.
>
> The architecture is all in-memory: a task store for task state, a webhook store for notification configs, a running tasks dictionary for active asyncio tasks, and SSE queues for connected streaming clients.
>
> The request flow goes like this: client sends a message. Server creates a task, kicks off a background coroutine with `asyncio.create_task()`, and immediately returns the task ID to the client. The client can then poll for status, stream updates via SSE, or register a webhook. Meanwhile, the background task simulates 20 seconds of work with progress updates at 25% intervals.
>
> This agent proves that A2A is truly framework-agnostic. You don't need ADK. You don't even need the a2a-sdk. If you can serve HTTP and parse JSON, you can implement A2A.

---

## Slide 20 — Workflow Agents

> These three agents demonstrate ADK's deterministic orchestration patterns. Unlike the LLM-powered orchestrator that makes routing decisions, these follow fixed workflows.
>
> The **pipeline agent** uses `SequentialAgent`. Three sub-agents run in order: fetch, analyze, report. Each one writes to a session state key — `raw_data`, `analysis`, `final_report` — and the next agent reads from the previous one's output. It's a deterministic assembly line.
>
> The **parallel agent** uses `ParallelAgent` wrapped in a `SequentialAgent`. First, it fans out five RemoteA2aAgent calls to the weather agent — one for London, one for Tokyo, one for New York, Sydney, and Paris. All five run concurrently. Then a summary agent aggregates the results into a single comparison table. Fan-out, fan-in.
>
> The **loop agent** uses `LoopAgent`. It starts an async task, then loops: poll the task status, check if it's done. If it's still working, loop again. If it's completed or failed, exit. Maximum 10 iterations so it doesn't loop forever.
>
> Three patterns, three ADK agent types, zero LLM routing decisions. These are for when you know the exact workflow you want.

---

## Slide 21 — Authentication Schemes Section Title

**Section title slide**

> Let's talk about security. One of the most important aspects of any production system is authentication, and our demo implements four different schemes — from zero security to full OAuth 2.0.

---

## Slide 22 — Four Authentication Schemes

> Here's the comparison table.
>
> **No Auth** — the weather agent. Completely open. Anyone can call it. This is fine for public information services where there's no sensitive data and no cost concern.
>
> **API Key** — the code agent. You put a shared secret in the `X-API-Key` header, and middleware validates it. Simple, effective for internal services where you control both ends. But API keys are static — if one leaks, you have to rotate it everywhere.
>
> **Bearer JWT** — the research agent. We sign a JSON Web Token with HMAC-SHA256, put it in the `Authorization: Bearer` header. The server verifies the signature and checks the expiry. JWTs are time-limited, so a leaked token expires on its own. More secure than static API keys.
>
> **OAuth 2.0** — the data agent. In production, this uses GCP service account tokens verified against Google's token info endpoint. The most robust scheme — identity-based, short-lived tokens, standard infrastructure.
>
> There's one cross-cutting rule that applies to all of them: **discovery is always public**. Look at this code: `if request.url.path == "/.well-known/agent.json": return await call_next(request)`. The Agent Card is never behind auth. This is essential for A2A — agents need to discover each other before they can authenticate.

---

## Slide 23 — Callbacks & Safety Section Title

**Section title slide**

> ADK has a powerful callback system — six hooks that let you intercept and modify the agent's behaviour at every stage of the pipeline. We use them for logging, safety guardrails, and caching.

---

## Slide 24 — The Callback Chain

> This diagram shows the callback pipeline. Every time the agent processes a request, it flows through these hooks.
>
> First, `before_model_callback` fires before the LLM call. We use it to log which agent is being called and how many messages are in the context.
>
> Then the LLM runs — Gemini processes the request.
>
> `after_model_callback` fires after the LLM responds. We log token usage here — prompt tokens, completion tokens, total. In production, you'd send these to Cloud Monitoring for cost tracking.
>
> If the LLM decides to call a tool, `before_tool_callback` fires. This is where the guardrail lives. We check the code argument for dangerous patterns: `os.system`, `subprocess`, `eval()`, `exec()`, `shutil.rmtree`. If any are found, we block the call by returning an error dict instead of None. The tool never executes.
>
> The tool runs, and then `after_tool_callback` fires. We log the result and optionally cache it.
>
> Here's the key thing to understand: returning `None` from a callback means "pass through, don't modify anything." Returning a value means "intercept — use this instead of the normal behaviour." This is the fundamental mechanism. Observe or intercept, that's the choice.
>
> The guardrail is string-matching, which is intentionally simple for a demo. In production, you'd use AST parsing or a sandboxed execution environment. But the *pattern* is correct: intercept before execution, check against a policy, block if violated.

---

## Slide 25 — Testing Section Title

**Section title slide**

> 300 tests, about 4 seconds to run, and zero GCP API calls. That last part is important — our tests run in CI without any cloud credentials.

---

## Slide 26 — Test Architecture

> Here's what we test and how we test it.
>
> Config tests verify that the Settings dataclass handles defaults, validation errors, and environment variable overrides correctly.
>
> Auth tests cover all four schemes — API key validation, JWT signing and verification, HMAC signature generation.
>
> Callback tests check that logging callbacks don't crash, guardrails block dangerous code, and cache callbacks hit and miss correctly.
>
> Then we have tests for each agent — weather, async, webhook, client, data, orchestrator — each with standard and extended test files.
>
> The total: about 300 tests across the suite. They run in parallel, they're fast, and they mock everything external.

---

## Slide 27 — Key Testing Techniques

> Let me highlight four testing techniques we use throughout.
>
> **One**: Auto-mock environment. Our `conftest.py` has an `autouse` fixture that sets critical environment variables for every test. `GOOGLE_GENAI_USE_VERTEXAI` is set to `"0"` so tests don't try to call Vertex AI. Weather API key is empty so we get mock data.
>
> **Two**: FastAPI's `TestClient`. Since our agents are Starlette/FastAPI apps, we use `TestClient` which wraps async code in a sync interface. You can POST a JSON-RPC payload and assert on the response, all without starting a real server.
>
> **Three**: `AsyncMock` for httpx. When we test tools that make external API calls, we mock `httpx.AsyncClient` with `AsyncMock`. We control exactly what the mock returns, so our tests are deterministic and fast.
>
> **Four**: Monkeypatching the settings singleton. Instead of mocking the environment, we directly patch `settings.API_KEY = "fake"`. This is more surgical than environment variables and doesn't affect other settings.
>
> The philosophy is: mock at the boundary, test the logic. External APIs, environment variables, and random data are mocked. Everything else runs for real.

---

## Slide 28 — Deployment Section Title

**Section title slide**

> We have three deployment options: local development, Google Cloud Run, and Vertex AI Agent Engine. Let me walk through each.

---

## Slide 29 — Deployment Options

> **Local Dev** — this is what you'd use day to day. Run `./scripts/start_all.sh` and it spins up all five agents on ports 8001 through 8005, plus the webhook server on 9000. Then `adk web` gives you the ADK Dev UI at port 8000 where you can chat with the orchestrator and see routing decisions in real time.
>
> **Cloud Run** — for staging and production. Each agent has its own Dockerfile. The `deploy_cloud_run.sh` script builds containers with Cloud Build and deploys them as Cloud Run services. You get auto-scaling to zero — no traffic, no cost. HTTPS endpoints out of the box. IAM authentication between services.
>
> **Vertex AI Agent Engine** — the managed option. The orchestrator is deployed as a managed Vertex AI agent. It automatically routes to the Cloud Run specialist agents. You get built-in monitoring, OpenTelemetry tracing, and Google handles the infrastructure.
>
> For this demo, we're running locally. But the same code deploys to Cloud Run or Agent Engine with just a configuration change — swap localhost URLs for Cloud Run service URLs, and you're in production.

---

## Slide 30 — All 24 A2A Features

> This is the complete feature matrix. 24 features, and our demo implements every single one.
>
> Let me call out a few highlights. F1 through F5 are the core protocol features — Agent Cards, sync and streaming communication, push notifications, and task lifecycle management.
>
> F8 is the four auth schemes we just discussed. F9 is the LLM-powered routing in the orchestrator. F10 is the workflow agents — sequential, parallel, and loop.
>
> F16 and F17 are the callbacks and guardrails we covered. F21 is gRPC transport — our gRPC client demonstrates the same protocol over a different wire format.
>
> And F24, the one I'm most proud of — cross-framework interoperability. Our standalone httpx client proves that A2A is truly a protocol, not a library. Any HTTP client, in any language, can talk to our agents.
>
> Take a picture of this slide if you want a reference. It maps every feature to the specific file where it's implemented.

---

## Slide 31 — Live Demo Section Title

**Section title slide**

> Alright, let's see this in action. I'll walk you through the commands, and then we'll run the demo.

---

## Slide 32 — Demo Commands

> Here are the six commands for the demo.
>
> **Command 1**: Start all agents. `./scripts/start_all.sh` boots up everything in the background with uvicorn.
>
> **Command 2**: Agent discovery. A simple curl to `/.well-known/agent.json`. This is the first thing any client does — discover the agent's capabilities.
>
> **Command 3**: A synchronous `message/send`. Notice the `messageId` field in the message — that's required by A2A v0.3. Without it, you get a validation error. This trips people up.
>
> **Command 4**: The orchestrator via ADK's web UI. The command is `adk web` with a dot for the project root directory. Once it's running, open the browser, and you can chat with the orchestrator. Ask it anything — "Weather in Paris," "Write a Python script," "Research quantum computing" — and watch it route to the right specialist.
>
> **Command 5**: The standalone client. `python -m a2a_client.client` runs the full demo — discovery, sync send, and streaming — all with plain httpx. No ADK.
>
> **Command 6**: Run the tests. `pytest tests/ -v`. 300 tests, about 4 seconds, all green.
>
> [At this point, switch to the terminal and run the demo live.]

---

## Slide 33 — Key Takeaways

> Six things I want you to remember from today.
>
> **A2A is the HTTP of the agent world.** It's an open protocol, not a library. Any agent, any framework, any language.
>
> **Agent Cards enable discovery.** That well-known URL — `/.well-known/agent.json` — is how agents find each other. It's simple, it's standard, it works.
>
> **ADK makes it simple.** Three steps: Agent Card, LlmAgent, `to_a2a()`. You can go from zero to a production A2A server in minutes.
>
> **Security is layered.** Discovery is always public. Operations require authentication. Four schemes from zero to OAuth 2.0, pick the one that fits your threat model.
>
> **Test everything.** 300 tests, mock environment, zero cloud calls. Your CI pipeline should never need GCP credentials to run tests.
>
> **Production-ready patterns.** Callbacks for logging, guardrails for safety, URL redaction for privacy, HMAC signatures for webhook integrity. These are the details that separate a demo from a production system — and we've built them all in.

---

## Slide 34 — Thank You

> Thank you for your time today. Here are the resources if you want to dig deeper.
>
> The A2A Protocol specification is at `a2a-protocol.org`. Google ADK documentation is at `google.github.io/adk-docs/`. And all the project documentation — the README, environment setup guide, demo guide, and the detailed speaker notes — are right in the repository.
>
> I'm happy to take questions. Whether it's about the protocol design, the ADK framework, the testing strategy, or how to deploy this to your own GCP project — fire away.

---

## Timing Guide

| Slides | Section | Suggested Time |
|--------|---------|---------------|
| 1–2 | Title + Agenda | 2 min |
| 3–5 | What is A2A? | 8 min |
| 6–7 | Google ADK | 5 min |
| 8–11 | Architecture | 10 min |
| 12–14 | Project Structure | 5 min |
| 15–20 | Agent Deep Dives | 15 min |
| 21–22 | Authentication | 5 min |
| 23–24 | Callbacks & Safety | 5 min |
| 25–27 | Testing | 5 min |
| 28–29 | Deployment | 5 min |
| 30 | Feature Matrix | 3 min |
| 31–32 | Live Demo | 10–15 min |
| 33–34 | Takeaways + Q&A | 5 min |
| **Total** | | **~75 min** |

---

## Tips for the Presenter

1. **Open two terminals before you start.** One for running agents, one for curl commands and the client demo.

2. **Run `./scripts/start_all.sh` during the Architecture section** (slide 9), so agents are warm by the time you reach the live demo.

3. **The weather agent is the safest demo target.** It's stateless, has no auth, and returns deterministic mock data when no API key is configured.

4. **If an agent fails during the demo**, use it as a teaching moment. Show the error, show `get_agent_status`, talk about error handling in distributed systems.

5. **The architecture diagram (slide 10) is a great reference slide.** Keep it handy or print it. You'll point back to it throughout the presentation.

6. **When explaining callbacks**, draw the pipeline on a whiteboard if you have one. The before/after symmetry clicks better when students see it visually.

7. **Time your live demo in advance.** The agent discovery and sync send take about 5 seconds each. Streaming takes 10–15 seconds. Budget 10–15 minutes for the full demo including explanations.
