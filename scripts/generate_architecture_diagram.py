#!/usr/bin/env python3
"""Generate the A2A Protocol Demo architecture diagram."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# ── Theme ────────────────────────────────────────────────────────────────────
BG = "#0F172A"
CARD_BG = "#1E293B"
CARD_BORDER = "#334155"
BLUE = "#4285F4"
GREEN = "#34A853"
YELLOW = "#FBBC04"
RED = "#EA4335"
CYAN = "#00BCD4"
ORANGE = "#FF9800"
PURPLE = "#A78BFA"
WHITE = "#FFFFFF"
LIGHT_GRAY = "#94A3B8"
MID_GRAY = "#64748B"
DIM = "#475569"

fig, ax = plt.subplots(1, 1, figsize=(20, 14))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.set_xlim(0, 20)
ax.set_ylim(0, 14)
ax.axis("off")


def draw_box(x, y, w, h, fill, border, label, sublabel="", label_color=WHITE,
             sublabel_color=LIGHT_GRAY, fontsize=11, sublabel_size=9,
             label_bold=True, radius=0.3):
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0.05,rounding_size={radius}",
        facecolor=fill, edgecolor=border, linewidth=1.5,
        transform=ax.transData, zorder=2,
    )
    ax.add_patch(box)
    if sublabel:
        ax.text(x + w / 2, y + h / 2 + 0.18, label, ha="center", va="center",
                fontsize=fontsize, color=label_color,
                fontweight="bold" if label_bold else "normal",
                fontfamily="sans-serif", zorder=3)
        ax.text(x + w / 2, y + h / 2 - 0.22, sublabel, ha="center", va="center",
                fontsize=sublabel_size, color=sublabel_color,
                fontfamily="sans-serif", zorder=3)
    else:
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center",
                fontsize=fontsize, color=label_color,
                fontweight="bold" if label_bold else "normal",
                fontfamily="sans-serif", zorder=3)
    return box


def draw_arrow(x1, y1, x2, y2, color=DIM, style="-|>", lw=1.5, ls="-"):
    arrow = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle=style, color=color,
        linewidth=lw, linestyle=ls,
        mutation_scale=14, zorder=1,
        connectionstyle="arc3,rad=0",
    )
    ax.add_patch(arrow)


def draw_label(x, y, text, color=MID_GRAY, fontsize=9, ha="center"):
    ax.text(x, y, text, ha=ha, va="center", fontsize=fontsize, color=color,
            fontfamily="sans-serif", fontstyle="italic", zorder=3)


def draw_layer_label(y, text, color):
    ax.text(0.4, y, text, ha="left", va="center", fontsize=10, color=color,
            fontweight="bold", fontfamily="sans-serif", zorder=3,
            bbox=dict(boxstyle="round,pad=0.3", facecolor=color + "18",
                      edgecolor=color + "40", linewidth=1))


# ═══════════════════════════════════════════════════════════════════════════
# LAYER 1 — CLIENT
# ═══════════════════════════════════════════════════════════════════════════
draw_layer_label(13.15, "LAYER 1 — CLIENT", CYAN)

# User
draw_box(7.5, 12.6, 5.0, 0.9, "#0E2A4A", CYAN, "User / External System",
         '"What is the weather in Paris?"', CYAN, LIGHT_GRAY, fontsize=12)

# Client box
draw_box(6.0, 11.2, 3.5, 0.9, CARD_BG, CYAN, "a2a_client", "HTTP / httpx",
         WHITE, LIGHT_GRAY, fontsize=11)
draw_box(10.5, 11.2, 3.5, 0.9, CARD_BG, CYAN, "grpc_client", "gRPC / protobuf",
         WHITE, LIGHT_GRAY, fontsize=11)

# Arrows: user -> clients
draw_arrow(9.2, 12.6, 7.75, 12.15, CYAN)
draw_arrow(10.8, 12.6, 12.25, 12.15, CYAN)

# Protocol label
draw_label(10.0, 10.75, "JSON-RPC 2.0 over HTTP  /  gRPC over HTTP/2", LIGHT_GRAY, 9)
draw_arrow(7.75, 11.2, 10.0, 10.2, CYAN, lw=2)
draw_arrow(12.25, 11.2, 10.0, 10.2, CYAN, lw=2)

# ═══════════════════════════════════════════════════════════════════════════
# LAYER 2 — ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════
draw_layer_label(10.15, "LAYER 2 — ORCHESTRATOR", BLUE)

draw_box(7.0, 9.2, 6.0, 1.0, "#0E2050", BLUE, "orchestrator_agent",
         "LlmAgent  |  Gemini 2.0 Flash  |  5 RemoteA2aAgent sub-agents",
         WHITE, LIGHT_GRAY, fontsize=13, sublabel_size=9)

# Arrow label
draw_label(10.0, 8.75, "LLM reads descriptions, picks the right specialist", LIGHT_GRAY, 9)

# Fan-out arrows from orchestrator to 5 agents
agent_xs = [2.0, 5.2, 8.4, 11.6, 14.8]
for ax_pos in agent_xs:
    draw_arrow(10.0, 9.2, ax_pos + 1.3, 8.05, BLUE, lw=1.2)

# ═══════════════════════════════════════════════════════════════════════════
# LAYER 3 — SPECIALIST AGENTS
# ═══════════════════════════════════════════════════════════════════════════
draw_layer_label(8.15, "LAYER 3 — SPECIALIST AGENTS", GREEN)

agents = [
    ("weather_agent",  ":8001", "No Auth",    "get_weather, get_forecast",  GREEN),
    ("research_agent", ":8002", "Bearer JWT", "google_search, memory",      PURPLE),
    ("code_agent",     ":8003", "API Key",    "code_exec, guardrails",      YELLOW),
    ("data_agent",     ":8004", "OAuth 2.0",  "CSV artifacts, stats",       ORANGE),
    ("async_agent",    ":8005", "No Auth",    "push notify, SSE",           RED),
]

for i, (name, port, auth, tools, color) in enumerate(agents):
    x = agent_xs[i]
    # Main agent box
    draw_box(x, 6.7, 2.6, 1.3, CARD_BG, color, name, port,
             color, MID_GRAY, fontsize=10, sublabel_size=9)
    # Auth badge
    draw_box(x + 0.05, 6.05, 2.5, 0.5, color + "15", color, f"{auth}  |  {tools}",
             label_color=color, fontsize=7, label_bold=False, radius=0.15)

# Agent Card discovery label
draw_label(10.0, 8.45, "A2A Protocol: Agent Card discovery at /.well-known/agent.json  +  JSON-RPC dispatch", LIGHT_GRAY, 8.5)

# ═══════════════════════════════════════════════════════════════════════════
# LAYER 4 — SHARED FOUNDATION
# ═══════════════════════════════════════════════════════════════════════════
draw_layer_label(5.15, "LAYER 4 — SHARED FOUNDATION", YELLOW)

# Connection lines from agents down to shared
for ax_pos in agent_xs:
    draw_arrow(ax_pos + 1.3, 6.0, ax_pos + 1.3, 5.05, DIM, lw=0.8, ls="--")

# Shared modules
draw_box(3.0, 4.1, 3.5, 0.8, CARD_BG, YELLOW, "shared/config.py",
         "Settings dataclass  |  .env  |  fail-fast", WHITE, LIGHT_GRAY, fontsize=10)
draw_box(7.0, 4.1, 3.5, 0.8, CARD_BG, YELLOW, "shared/auth.py",
         "4 auth schemes  |  JWT  |  HMAC  |  API Key", WHITE, LIGHT_GRAY, fontsize=10)
draw_box(11.0, 4.1, 4.5, 0.8, CARD_BG, YELLOW, "shared/callbacks.py",
         "6 ADK hooks  |  logging  |  guardrails  |  cache", WHITE, LIGHT_GRAY, fontsize=10)

# Horizontal connector between shared modules
ax.plot([4.75, 13.25], [4.5, 4.5], color=YELLOW + "30", linewidth=1, zorder=0, linestyle="--")

# ═══════════════════════════════════════════════════════════════════════════
# SUPPORTING SYSTEMS (bottom)
# ═══════════════════════════════════════════════════════════════════════════
draw_layer_label(3.3, "SUPPORTING SYSTEMS", MID_GRAY)

# Workflow agents
draw_box(1.5, 1.8, 2.4, 0.8, CARD_BG, BLUE, "pipeline_agent",
         "SequentialAgent", WHITE, LIGHT_GRAY, fontsize=9, sublabel_size=8)
draw_box(4.2, 1.8, 2.4, 0.8, CARD_BG, GREEN, "parallel_agent",
         "ParallelAgent", WHITE, LIGHT_GRAY, fontsize=9, sublabel_size=8)
draw_box(6.9, 1.8, 2.4, 0.8, CARD_BG, YELLOW, "loop_agent",
         "LoopAgent", WHITE, LIGHT_GRAY, fontsize=9, sublabel_size=8)

# Webhook server
draw_box(10.5, 1.8, 2.8, 0.8, CARD_BG, RED, "webhook_server",
         ":9000  |  HMAC verify", WHITE, LIGHT_GRAY, fontsize=9, sublabel_size=8)

# Tests
draw_box(14.0, 1.8, 2.5, 0.8, CARD_BG, CYAN, "tests/",
         "pytest  |  zero GCP calls", WHITE, LIGHT_GRAY, fontsize=9, sublabel_size=8)

# Arrow from async_agent to webhook
draw_arrow(16.1, 6.0, 12.6, 2.65, RED, lw=1.0, ls="--")
draw_label(15.0, 4.3, "push notifications", RED, 8)

# Workflow agents arrows to weather_agent and async_agent
draw_arrow(2.7, 2.65, 3.3, 6.0, BLUE, lw=0.8, ls="--")
draw_arrow(5.4, 2.65, 3.3, 6.0, GREEN, lw=0.8, ls="--")
draw_arrow(8.1, 2.65, 16.1, 6.0, YELLOW, lw=0.8, ls="--")

# ═══════════════════════════════════════════════════════════════════════════
# TITLE
# ═══════════════════════════════════════════════════════════════════════════
ax.text(10.0, 0.7, "A2A Protocol Demo — Architecture",
        ha="center", va="center", fontsize=14, color=LIGHT_GRAY,
        fontweight="bold", fontfamily="sans-serif",
        bbox=dict(boxstyle="round,pad=0.4", facecolor=BG, edgecolor=DIM, linewidth=1))

# ═══════════════════════════════════════════════════════════════════════════
# LEGEND (bottom-right)
# ═══════════════════════════════════════════════════════════════════════════
legend_x, legend_y = 17.2, 2.0
ax.text(legend_x, legend_y + 1.4, "Protocol", ha="left", va="center",
        fontsize=8, color=LIGHT_GRAY, fontweight="bold")
items = [
    ("Agent Card", "/.well-known/agent.json"),
    ("JSON-RPC", "message/send, /stream"),
    ("SSE", "Server-Sent Events"),
    ("Push", "Webhook notifications"),
]
for i, (label, desc) in enumerate(items):
    y = legend_y + 0.9 - i * 0.35
    ax.text(legend_x, y, f"{label}: ", ha="left", va="center",
            fontsize=7, color=WHITE, fontweight="bold")
    ax.text(legend_x + 1.4, y, desc, ha="left", va="center",
            fontsize=7, color=MID_GRAY)

# Save
plt.tight_layout(pad=0.5)
output = "/home/sandbox1/A2A_Research_demo_1/docs/architecture_diagram.png"
import os
os.makedirs(os.path.dirname(output), exist_ok=True)
fig.savefig(output, dpi=200, facecolor=BG, bbox_inches="tight")
plt.close()
print(f"Saved: {output}")
print(f"Size: {os.path.getsize(output) / 1024:.0f} KB")
