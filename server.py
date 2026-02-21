"""MI Bridge Web Dashboard — FastAPI server.

Run:
    python server.py
    # or:
    uvicorn server:app --host 0.0.0.0 --port 8000

Then open: http://localhost:8000
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone

# Make the project root importable (same pattern as main.py)
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from models import RawAlert, IncidentContext
from orchestrator import MIBridgeOrchestrator
from tools import mock_dynatrace, mock_splunk, mock_servicenow, mock_pagerduty
from utils.llm_client import DryRunLLMClient
from utils.logger import _log_sink

# ─── App setup ───────────────────────────────────────────────────────────────

app = FastAPI(title="MI Bridge Dashboard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ─── Phase annotation ─────────────────────────────────────────────────────────

_AGENT_PHASE: dict[str, int] = {
    "IMPACT": 1,
    "SIMILAR": 1,
    "SUMMARIZER": 2,
    "RCA": 3,
}


def _annotate_phases(raw_logs: list[dict]) -> list[dict]:
    """Assign a phase number (1/2/3) to each log entry so the frontend can
    reveal them incrementally as the user steps through phases."""
    annotated = []
    for entry in raw_logs:
        agent = entry["agent"]
        phase = _AGENT_PHASE.get(agent)

        # Orchestrator boundary messages — infer from text
        if agent == "ORCHESTRATOR" and phase is None:
            msg = entry["message"]
            if "PHASE 1" in msg:
                phase = 1
            elif "PHASE 2" in msg:
                phase = 2
            elif "PHASE 3" in msg:
                phase = 3
            # else: None — pre-run / post-run orchestrator messages

        annotated.append({**entry, "phase": phase})
    return annotated


# ─── Alert + tools factory (mirrors main.py) ─────────────────────────────────

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
            "triggered_by": "Response time anomaly on /checkout",
            "alert_events": [
                {"name": "Response time degraded", "service": "inventory-service",
                 "value": "18340ms p99", "threshold": "500ms"},
                {"name": "Error rate anomaly", "service": "inventory-service",
                 "value": "42.1%", "threshold": "5%"},
                {"name": "Circuit breaker open", "service": "api-gateway",
                 "target": "inventory-service"},
            ],
        },
    )


def _build_tools() -> dict:
    return {
        "dynatrace": mock_dynatrace,
        "splunk": mock_splunk,
        "servicenow": mock_servicenow,
        "pagerduty": mock_pagerduty,
    }


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.get("/")
async def serve_dashboard() -> FileResponse:
    html_path = os.path.join(_HERE, "static", "index.html")
    return FileResponse(html_path, media_type="text/html")


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "mode": "dry-run", "version": "1.0.0"}


@app.post("/api/run")
async def run_simulation() -> JSONResponse:
    """Run the full MI Bridge dry-run pipeline and return structured JSON.

    Returns the complete IncidentContext (all phase outputs + phase timings)
    plus a `log_entries` list of annotated agent log lines for the sidebar.
    """
    # Set up the log capture sink for this request
    log_entries: list[dict] = []
    token = _log_sink.set(log_entries)

    wall_start = time.perf_counter()
    try:
        alert = _build_alert()
        tools = _build_tools()
        llm = DryRunLLMClient()
        orchestrator = MIBridgeOrchestrator(llm=llm, tools=tools)
        ctx: IncidentContext = await orchestrator.handle_alert(alert)
    finally:
        _log_sink.reset(token)

    wall_total = time.perf_counter() - wall_start

    # Serialize IncidentContext — Pydantic v2 handles datetime → ISO str, etc.
    result = ctx.model_dump(mode="json")

    # Attach annotated logs (phase field added so frontend can filter by phase)
    result["log_entries"] = _annotate_phases(log_entries)
    result["wall_total_seconds"] = round(wall_total, 3)

    return JSONResponse(content=result)


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("\n  MI Bridge Dashboard  →  http://localhost:8000\n")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
