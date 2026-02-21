# MI Bridge — Multi-Agent Major Incident Simulation

A production-quality multi-agent simulation of a Major Incident (MI) Bridge,
built from scratch in Python using only the Anthropic SDK and Pydantic.
**No LangChain, LangGraph, CrewAI, or other agent frameworks.**

---

## Setup

```bash
# Recommended — virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running

```bash
# Full simulation (real LLM calls — requires API key)
export ANTHROPIC_API_KEY=sk-ant-...
python main.py

# Dry-run — no API key needed, full pipeline with pre-baked responses
python main.py --dry-run

# Validate your API key before running the full simulation
export ANTHROPIC_API_KEY=sk-ant-...
python main.py --check-key
```

---

## Scenario

**Incident:** Inventory Service Timeout Cascade — Flash Sale Checkout Failures
**Severity:** P1 · Production
**Affected services:** inventory-service, order-service, payment-service, api-gateway
**Symptom:** 42% error rate on `/checkout`, p99 latency 18 s on inventory-service

The planted root cause — **CR2077** (a HikariCP DB connection pool config reduction
from max-pool-size=20 to 10, deployed 2 h before the incident) — is hidden only in
the mock tool data. The RCA agent must reason its way to it from log patterns,
trace data, and change requests.

---

## Agents

| Agent | File | Tools used | Phase |
|-------|------|-----------|-------|
| **ImpactAnalysisAgent** | `agents/impact_analysis_agent.py` | Dynatrace metrics + traces | 1 (parallel) |
| **SimilarIncidentAgent** | `agents/similar_incident_agent.py` | ServiceNow past incidents | 1 (parallel) |
| **MISummarizerAgent** | `agents/mi_summarizer_agent.py` | PagerDuty roster + ownership | 2 (sequential) |
| **RCAAgent** | `agents/rca_agent.py` | Splunk logs, ServiceNow CRs + past incidents | 3 (sequential) |

### ImpactAnalysisAgent
Reads Dynatrace service metrics and distributed traces to determine blast radius,
customer segments affected, estimated user count, revenue impact per minute, and
whether to escalate/maintain/downgrade the severity. Writes to `ctx.impact_analysis`.

### SimilarIncidentAgent
Searches ServiceNow for past resolved incidents that match the current incident's
services, error patterns, and symptoms. Returns the top 3 ranked by similarity score
and suggests a runbook action from the best match. Writes to `ctx.similar_incidents`.

### MISummarizerAgent
Reads the impact analysis and similar incidents (from Phase 1) plus PagerDuty on-call
and ownership data to produce a bridge-ready summary: headline, management narrative,
event timeline, teams to engage with contacts, and prioritized next steps.
Writes to `ctx.mi_summary`.

### RCAAgent
The analytical centrepiece. Reads Splunk error logs, active ServiceNow change requests,
and past incidents. Follows an explicit reasoning chain: CR audit → log analysis →
cross-reference → historical comparison → ranked causes → remediation steps.
The LLM must discover CR2077 by correlating `HikariPool$PoolTimeoutException` logs with
the CR that reduced `maximum-pool-size` from 20 to 10. Writes to `ctx.rca`.

---

## Architecture

```
main.py
  └─ MIBridgeOrchestrator
       ├─ Phase 1 (asyncio.gather)
       │    ├─ ImpactAnalysisAgent  ──→ ctx.impact_analysis
       │    └─ SimilarIncidentAgent ──→ ctx.similar_incidents
       ├─ Phase 2
       │    └─ MISummarizerAgent    ──→ ctx.mi_summary
       └─ Phase 3
            └─ RCAAgent             ──→ ctx.rca
```

**`IncidentContext`** is the single shared state object — passed to every agent.
No global variables. Agents read prior phases' outputs from it and write their own.

---

## Reading the Log Output

```
HH:MM:SS.mmm  │  AGENT_NAME    │  message
```

| Agent name colour | Meaning |
|---|---|
| Bold blue `ORCHESTRATOR` | Phase lifecycle and error handling |
| Yellow `IMPACT` / `SIMILAR` | Phase 1 agents (timestamps should overlap — parallelism proof) |
| Cyan `SUMMARIZER` | Phase 2 |
| Magenta `RCA` | Phase 3 |
| Dim white | LLM call details (tokens, latency) and phase timings |
| Bold red `ERROR` | Agent failures (context field set to None, simulation continues) |

**Parallelism proof:** In Phase 1, `IMPACT` and `SIMILAR` both log their start
timestamp. These timestamps should be within milliseconds of each other, confirming
`asyncio.gather()` fires them concurrently rather than sequentially.

---

## Mock Tool Data

All tool data is fabricated — zero real API calls to Dynatrace, Splunk, etc.

| Tool | Key signals planted |
|---|---|
| `mock_dynatrace` | inventory-service p99 = 18,340 ms; HikariPool span holds DB connection for 16 s |
| `mock_splunk` | Repeated `HikariPool$PoolTimeoutException` with pool exhausted (max=10, active=10, idle=0) |
| `mock_servicenow` | CR2077: `maximum-pool-size` changed from 20 → 10, deployed 2 h ago |
| `mock_pagerduty` | On-call roster and runbook URLs for all four services |

The RCA agent is **not told** about CR2077. It must find it by reasoning over the data.
