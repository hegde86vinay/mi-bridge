from __future__ import annotations

import json

from agents.base_agent import BaseAgent
from models import ImpactAnalysisOutput, IncidentContext

_SYSTEM_PROMPT = """\
You are an Impact Analysis agent for production incidents.

Given an alert, service metrics, and distributed traces, determine:
- Which downstream services are in the blast radius (list ALL services experiencing degradation)
- Which customer segments are affected and how severely
- Estimated number of users impacted right now (make a data-driven estimate)
- Revenue impact per minute (make a reasonable estimate based on the service criticality)
- Whether to escalate, maintain, or downgrade the severity

Justify every conclusion with specific data from the metrics/traces provided.

Respond ONLY with valid JSON that exactly matches this schema — no markdown, no explanation outside the JSON:

{
  "blast_radius": ["<service name>", ...],
  "customer_segments_affected": ["<segment>", ...],
  "estimated_users_impacted": <integer>,
  "revenue_impact_per_minute": "<string like '$12,000/min'>",
  "severity_recommendation": "<ESCALATE | MAINTAIN | DOWNGRADE>",
  "confidence": <float 0.0-1.0>,
  "reasoning": "<detailed explanation citing specific metric values>"
}
"""


class ImpactAnalysisAgent(BaseAgent):
    name = "IMPACT"

    async def run(self, ctx: IncidentContext) -> None:
        self._log("Starting impact analysis")

        dynatrace = self.tools["dynatrace"]
        services = ctx.alert.affected_services

        # ── Tool call 1: service metrics ───────────────────────────────────
        self._log(f"[TOOL] dynatrace.get_service_metrics({services})")
        metrics = await dynatrace.get_service_metrics(services)

        # Log the key signals for each service
        for svc, m in metrics.items():
            self._log(
                f"  ↳ {svc}: p99={m['response_time_p99_ms']}ms  "
                f"error_rate={m['error_rate_pct']}%  "
                f"pool={m['db_pool_active']}/{m['db_pool_max']} active"
            )

        # ── Tool call 2: distributed traces ───────────────────────────────
        self._log(f"[TOOL] dynatrace.get_distributed_traces({services})")
        traces = await dynatrace.get_distributed_traces(services)
        self._log(f"  ↳ Retrieved {len(traces)} traces")

        # Surface the smoking-gun span for visibility
        for trace in traces:
            for span in trace.get("spans", []):
                tags = span.get("tags", {})
                if tags.get("hikaricp.pool_status") == "pool_exhausted":
                    self._log(
                        f"  ↳ ⚠ TRACE {trace['trace_id']} span {span['span_id']}: "
                        f"{span['service']} blocked {tags.get('hikaricp.connection_wait_ms', '?')}ms "
                        f"on pool_exhausted (max={tags.get('hikaricp.pool_size_max', tags.get('hikaricp.pool', '?'))})"
                    )

        user_prompt = f"""\
INCIDENT ALERT:
{ctx.alert.model_dump_json(indent=2)}

SERVICE METRICS (from Dynatrace):
{json.dumps(metrics, indent=2)}

DISTRIBUTED TRACES (from Dynatrace):
{json.dumps(traces, indent=2)}

Perform a full impact analysis. Output ONLY valid JSON matching the schema in your instructions.
"""

        self._log("Sending metrics + traces to LLM for impact analysis")
        result = await self._call_llm(_SYSTEM_PROMPT, user_prompt)

        ctx.impact_analysis = ImpactAnalysisOutput(**result)
        ia = ctx.impact_analysis
        self._log(
            f"Complete ✓ — blast_radius={ia.blast_radius} | "
            f"~{ia.estimated_users_impacted:,} users | "
            f"{ia.revenue_impact_per_minute}/min | "
            f"confidence={ia.confidence:.0%} | "
            f"recommendation={ia.severity_recommendation}"
        )
