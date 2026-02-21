from __future__ import annotations

import json

from agents.base_agent import BaseAgent
from models import RCAOutput, IncidentContext

_SYSTEM_PROMPT = """\
You are the Root Cause Analysis (RCA) agent for production incidents.
You have access to error logs, distributed traces, active Change Requests,
and past incident history.

Follow this reasoning process STEP BY STEP — be explicit in your thinking:

1. CHANGE REQUEST AUDIT
   - Scan Change Requests deployed within 3 hours of the incident start time.
   - For each CR touching an affected service, flag it as a SUSPECT.
   - Note what was changed: configuration, code, infrastructure.

2. ERROR LOG ANALYSIS
   - What exception classes appear most frequently?
   - What do the stack traces point to? (connection pools, timeouts, specific libraries)
   - Do any log messages contain configuration parameters or pool names?

3. CROSS-REFERENCE
   - Does the exception class or error pattern match anything a recent CR changed?
   - Example: If logs show "HikariPool timeout" and a CR changed HikariCP config — that is a strong correlation.

4. HISTORICAL COMPARISON
   - Has this failure mode appeared in past incidents?
   - If yes, what was the root cause and resolution then?

5. RANK YOUR CAUSES
   - Rank 1-3 probable causes with evidence for each.
   - If a CR is your #1 cause, set it as rollback_candidate.

6. REMEDIATION
   - Provide specific, ordered remediation steps.
   - Cite the rollback procedure if one exists.

For EVERY conclusion, cite the SOURCE (splunk_logs / servicenow_crs / past_incidents / dynatrace_traces)
and the specific FINDING that supports it.

Respond ONLY with valid JSON that exactly matches this schema — no markdown, no explanation outside the JSON:

{
  "probable_root_causes": [
    {
      "rank": 1,
      "cause": "<specific description>",
      "evidence": "<what data supports this>",
      "confidence_pct": <integer 0-100>
    }
  ],
  "correlated_change_requests": [
    {
      "cr_id": "<id>",
      "service": "<service>",
      "deployed_at": "<ISO timestamp>",
      "deployed_by": "<email>",
      "description": "<what changed>"
    }
  ],
  "recommended_resolution": "<clear recommended fix>",
  "rollback_candidate": "<cr_id or null>",
  "remediation_steps": ["<step 1>", "<step 2>", ...],
  "evidence_trail": [
    {
      "source": "<splunk_logs | servicenow_crs | past_incidents | dynatrace_traces>",
      "query_or_action": "<what was queried or examined>",
      "finding": "<what was found>"
    }
  ]
}
"""


class RCAAgent(BaseAgent):
    name = "RCA"

    async def run(self, ctx: IncidentContext) -> None:
        self._log("Starting root cause analysis")
        self._log(
            f"  ↳ Prior context: "
            f"impact={'✓' if ctx.impact_analysis else '✗'} | "
            f"similar={'✓' if ctx.similar_incidents else '✗'} | "
            f"summary={'✓' if ctx.mi_summary else '✗'}"
        )

        splunk = self.tools["splunk"]
        servicenow = self.tools["servicenow"]
        services = ctx.alert.affected_services

        # ── Tool call 1: error logs ────────────────────────────────────────
        self._log(f"[TOOL] splunk.query_error_logs({services})")
        error_logs = await splunk.query_error_logs(services)
        self._log(f"  ↳ Retrieved {len(error_logs)} error log entries")

        # Surface exception classes prominently
        exc_counts: dict[str, int] = {}
        for entry in error_logs:
            exc = entry.get("exception_class", "unknown")
            exc_counts[exc] = exc_counts.get(exc, 0) + 1
        for exc, count in sorted(exc_counts.items(), key=lambda x: -x[1]):
            self._log(f"  ↳ exception: {exc}  ×{count}")

        # Surface HikariCP pool state at worst point
        for entry in error_logs:
            pool = entry.get("hikaricp")
            if pool:
                self._log(
                    f"  ↳ ⚠ HikariCP pool state: "
                    f"active={pool['active_connections']}/max={pool['max_pool_size']}  "
                    f"idle={pool['idle_connections']}  "
                    f"pending_threads={pool['pending_threads']}"
                )

        # ── Tool call 2: change requests ──────────────────────────────────
        self._log(f"[TOOL] servicenow.get_active_change_requests({services})")
        change_requests = await servicenow.get_active_change_requests(services)
        self._log(f"  ↳ Retrieved {len(change_requests)} active CRs")
        for cr in change_requests:
            self._log(
                f"  ↳ {cr['cr_id']} [{cr['status']}] deployed {cr['deployed_at']} "
                f"by {cr['deployed_by']}"
            )
            self._log(f"     service={cr['service']} | \"{cr['title']}\"")
            if "config_change" in cr:
                cfg = cr["config_change"]
                self._log(
                    f"     config: {cfg['parameter']} "
                    f"{cfg['old_value']} → {cfg['new_value']}"
                )

        # ── Tool call 3: past incidents ───────────────────────────────────
        keywords = ["connection pool", "timeout", "HikariCP"] + services
        self._log(f"[TOOL] servicenow.search_past_incidents({len(keywords)} keywords)")
        past_incidents = await servicenow.search_past_incidents(keywords)
        self._log(f"  ↳ Retrieved {len(past_incidents)} past incidents for historical comparison")
        for inc in past_incidents:
            self._log(f"  ↳ {inc['incident_id']}: {inc['title'][:60]}")

        # ── Assemble full context for the LLM ─────────────────────────────
        impact_json = (
            ctx.impact_analysis.model_dump_json(indent=2)
            if ctx.impact_analysis
            else "null"
        )
        similar_json = (
            ctx.similar_incidents.model_dump_json(indent=2)
            if ctx.similar_incidents
            else "null"
        )
        summary_json = (
            ctx.mi_summary.model_dump_json(indent=2) if ctx.mi_summary else "null"
        )

        user_prompt = f"""\
INCIDENT ALERT:
{ctx.alert.model_dump_json(indent=2)}

PRIOR ANALYSIS CONTEXT:
- Impact Analysis: {impact_json}
- Similar Incidents: {similar_json}
- MI Summary: {summary_json}

EVIDENCE TO ANALYSE:

[1] ERROR LOGS (from Splunk — last 30 minutes):
{json.dumps(error_logs, indent=2)}

[2] ACTIVE CHANGE REQUESTS (from ServiceNow — deployed within 24h):
{json.dumps(change_requests, indent=2)}

[3] PAST SIMILAR INCIDENTS (from ServiceNow):
{json.dumps(past_incidents, indent=2)}

Now perform a full root cause analysis following the step-by-step process in your instructions.
Output ONLY valid JSON matching the schema.
"""

        self._log(
            f"Sending {len(error_logs)} logs + {len(change_requests)} CRs + "
            f"{len(past_incidents)} past incidents to LLM for RCA"
        )
        result = await self._call_llm(_SYSTEM_PROMPT, user_prompt)

        ctx.rca = RCAOutput(**result)
        rca = ctx.rca

        # Log the verdict
        self._log(f"Complete ✓ — {len(rca.probable_root_causes)} probable causes identified")
        for cause in rca.probable_root_causes:
            self._log(
                f"  ↳ #{cause['rank']} ({cause['confidence_pct']}% confidence): "
                f"{cause['cause'][:70]}"
            )
        self._log(f"  ↳ Rollback candidate: {rca.rollback_candidate}")
        self._log(
            f"  ↳ Evidence trail: {len(rca.evidence_trail)} items | "
            f"CRs correlated: {[c['cr_id'] for c in rca.correlated_change_requests]}"
        )
