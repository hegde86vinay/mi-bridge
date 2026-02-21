from __future__ import annotations

import contextvars
from datetime import datetime

# ANSI color codes
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"

_COLORS: dict[str, str] = {
    "ORCHESTRATOR": "\033[1;34m",   # bold blue
    "IMPACT":       "\033[33m",     # yellow
    "SIMILAR":      "\033[33m",     # yellow
    "SUMMARIZER":   "\033[36m",     # cyan
    "RCA":          "\033[35m",     # magenta
    "PHASE":        "\033[1;37m",   # bold white
    "BRIEF":        "\033[1;32m",   # bold green
    "ERROR":        "\033[1;31m",   # bold red
    "TIMING":       "\033[2;37m",   # dim white
    "LLM":          "\033[2;37m",   # dim white
}

_NAME_WIDTH = 12

# Web dashboard log capture — holds a list[dict] when a web request is active,
# None in CLI mode. Each asyncio request context gets its own isolated copy.
_log_sink: contextvars.ContextVar[list[dict] | None] = contextvars.ContextVar(
    "_log_sink", default=None
)


def log(agent_name: str, message: str) -> None:
    now = datetime.now()
    timestamp = now.strftime("%H:%M:%S") + f".{now.microsecond // 1000:03d}"
    color = _COLORS.get(agent_name.upper(), "")
    padded_name = agent_name.upper().ljust(_NAME_WIDTH)

    # CLI output — unchanged in all modes
    print(f"{_DIM}{timestamp}{_RESET}  │  {color}{padded_name}{_RESET}  │  {message}")

    # Web capture — no-op in CLI mode (sink is None)
    sink = _log_sink.get()
    if sink is not None:
        sink.append({
            "timestamp": timestamp,
            "agent": agent_name.upper(),
            "message": message,
        })
