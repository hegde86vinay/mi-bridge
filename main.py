"""Entry point for the MI Bridge multi-agent simulation.

Usage:
    python main.py               # real LLM calls (requires ANTHROPIC_API_KEY)
    python main.py --dry-run     # full pipeline with pre-baked responses, no API key needed
    python main.py --check-key   # validate your ANTHROPIC_API_KEY and exit
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime, timezone

# Ensure the project root is on sys.path so relative imports work
sys.path.insert(0, os.path.dirname(__file__))

from models import RawAlert
from orchestrator import MIBridgeOrchestrator
from tools import mock_dynatrace, mock_splunk, mock_servicenow, mock_pagerduty
from utils.llm_client import DryRunLLMClient, LLMClient
from utils.logger import log

_RST = "\033[0m"
_BOLD = "\033[1m"
_GREEN = "\033[1;32m"
_YLW = "\033[33m"
_RED = "\033[1;31m"


def _build_alert() -> RawAlert:
    return RawAlert(
        incident_id="INC-2077-FLASHSALE",
        source="dynatrace",
        severity="P1",
        title="Inventory Service Timeout Cascade — Flash Sale Checkout Failures",
        affected_services=[
            "inventory-service",
            "order-service",
            "payment-service",
            "api-gateway",
        ],
        environment="production",
        timestamp=datetime.now(timezone.utc),
        error_rate=0.42,
        raw_payload={
            "source_system": "Dynatrace",
            "management_zone": "Production — E-Commerce",
            "problem_id": "P-8821",
            "status": "OPEN",
            "impact": "APPLICATION",
            "root_cause_entity": "inventory-service",
            "affected_entities": [
                "inventory-service",
                "order-service",
                "payment-service",
                "api-gateway",
            ],
            "triggered_by": "Response time anomaly on /checkout",
            "alert_events": [
                {
                    "name": "Response time degraded",
                    "service": "inventory-service",
                    "value": "18340ms p99",
                    "threshold": "500ms",
                },
                {
                    "name": "Error rate anomaly",
                    "service": "inventory-service",
                    "value": "42.1%",
                    "threshold": "5%",
                },
                {
                    "name": "Circuit breaker open",
                    "service": "api-gateway",
                    "target": "inventory-service",
                },
            ],
            "dynatrace_link": "https://company.live.dynatrace.com/problems/P-8821",
        },
    )


def _build_tools() -> dict:
    return {
        "dynatrace": mock_dynatrace,
        "splunk": mock_splunk,
        "servicenow": mock_servicenow,
        "pagerduty": mock_pagerduty,
    }


async def _check_key(api_key: str) -> None:
    """Run a minimal API probe and report the result, then exit."""
    print(f"\n{_BOLD}Checking ANTHROPIC_API_KEY ...{_RST}")
    masked = api_key[:12] + "..." + api_key[-4:] if len(api_key) > 16 else "***"
    print(f"  Key (masked): {masked}")
    print(f"  Length:       {len(api_key)} chars")
    ok_prefix = api_key.startswith("sk-ant-")
    print(
        f"  Prefix check: "
        + (f"{_GREEN}✓ starts with sk-ant-{_RST}" if ok_prefix
           else f"{_RED}✗ unexpected prefix — expected sk-ant-...{_RST}")
    )

    llm = LLMClient(api_key=api_key)
    ok, message = await llm.check_key()
    icon = f"{_GREEN}✓{_RST}" if ok else f"{_RED}✗{_RST}"
    print(f"  API probe:    {icon} {message}\n")
    sys.exit(0 if ok else 1)


async def main() -> None:
    dry_run = "--dry-run" in sys.argv
    check_key_mode = "--check-key" in sys.argv

    if dry_run:
        print(
            f"\n{_YLW}{_BOLD}━━━  DRY-RUN MODE  ━━━{_RST}{_YLW}\n"
            f"No real LLM calls. Pre-baked realistic responses used for every agent.\n"
            f"Tool calls to Dynatrace/Splunk/ServiceNow/PagerDuty still execute normally.\n"
            f"The full pipeline — phased execution, parallelism, Pydantic validation, "
            f"MI Brief — runs as normal.{_RST}\n"
        )
        llm: LLMClient | DryRunLLMClient = DryRunLLMClient()
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            print(
                f"\n{_RED}{_BOLD}ERROR{_RST}: ANTHROPIC_API_KEY is not set.\n\n"
                "Options:\n"
                f"  1. Set your key:     export ANTHROPIC_API_KEY=sk-ant-...\n"
                f"  2. Validate a key:   python main.py --check-key\n"
                f"  3. Run without key:  python main.py --dry-run\n"
            )
            sys.exit(1)

        if check_key_mode:
            await _check_key(api_key)
            return

        if not api_key.startswith("sk-ant-"):
            print(
                f"{_YLW}WARNING{_RST}: Key prefix is '{api_key[:8]}...' — expected 'sk-ant-'.\n"
                f"Run 'python main.py --check-key' to validate before the full simulation.\n"
            )

        llm = LLMClient(api_key=api_key)

    alert = _build_alert()
    tools = _build_tools()
    orchestrator = MIBridgeOrchestrator(llm=llm, tools=tools)

    wall_start = time.perf_counter()
    await orchestrator.handle_alert(alert)
    wall_total = time.perf_counter() - wall_start

    mode_tag = " [dry-run]" if dry_run else ""
    log("ORCHESTRATOR", f"Simulation complete{mode_tag} — total wall time: {wall_total:.2f}s")


if __name__ == "__main__":
    if "--check-key" in sys.argv and not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        print(
            f"\n{_RED}ERROR{_RST}: --check-key requires ANTHROPIC_API_KEY to be set first.\n"
            f"  export ANTHROPIC_API_KEY=sk-ant-...\n"
            f"  python main.py --check-key\n"
        )
        sys.exit(1)
    asyncio.run(main())
