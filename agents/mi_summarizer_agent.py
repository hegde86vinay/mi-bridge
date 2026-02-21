from __future__ import annotations

import json

from agents.base_agent import BaseAgent
from models import MISummaryOutput, IncidentContext

_SYSTEM_PROMPT = """\
You are the MI Bridge Summarizer. You are speaking to a live bridge call
with engineers, a VP, and an SRE lead in the room.

Using the alert, impact analysis, similar incidents, on-call roster, and service ownership:

1. Write a one-line headline for the incident ticker (punchy, under 120 chars)
2. Write a 3-4 sentence narrative for management — no technical jargon,
   focus on customer impact and what's being done
3. Build a chronological timeline of events from the data provided
   (format each entry as {"time": "HH:MM UTC", "event": "what happened"})
4. List every team that MUST join this bridge call — include why they're needed
   and who to ping from the on-call roster
   (format: {"team": "...", "reason": "...", "oncall_contact": "...", "slack_channel": "..."})
5. List the immediate next steps in strict priority order (be specific, actionable)

Respond ONLY with valid JSON that exactly matches this schema — no markdown, no explanation outside the JSON:

{
  "headline": "<one punchy line>",
  "narrative": "<3-4 sentence management summary>",
  "timeline": [
    {"time": "<HH:MM UTC>", "event": "<what happened>"}
  ],
  "teams_to_engage": [
    {
      "team": "<team name>",
      "reason": "<why they are needed>",
      "oncall_contact": "<name and slack handle>",
      "slack_channel": "<#channel>"
    }
  ],
  "next_steps": ["<step 1>", "<step 2>", ...]
}
"""


class MISummarizerAgent(BaseAgent):
    name = "SUMMARIZER"

    async def run(self, ctx: IncidentContext) -> None:
        self._log("Building MI bridge summary")
        self._log(
            f"  ↳ Reading from ctx: "
            f"impact_analysis={'✓' if ctx.impact_analysis else '✗ (None)'} | "
            f"similar_incidents={'✓' if ctx.similar_incidents else '✗ (None)'}"
        )

        pagerduty = self.tools["pagerduty"]
        services = ctx.alert.affected_services

        # ── Tool call 1: on-call roster ────────────────────────────────────
        self._log(f"[TOOL] pagerduty.get_oncall_roster({services})")
        roster = await pagerduty.get_oncall_roster(services)
        for svc, r in roster.items():
            self._log(
                f"  ↳ {svc}: oncall={r['oncall_engineer']} "
                f"({r['slack_handle']}) · team={r['team_name']}"
            )

        # ── Tool call 2: service ownership ────────────────────────────────
        self._log(f"[TOOL] pagerduty.get_service_ownership({services})")
        ownership = await pagerduty.get_service_ownership(services)
        for svc, o in ownership.items():
            self._log(
                f"  ↳ {svc}: channel={o['slack_channel']} | "
                f"slo_current={o['slo_current_pct']}% (target={o['slo_target_pct']}%)"
            )

        # Log what context Phase 1 provided
        if ctx.impact_analysis:
            ia = ctx.impact_analysis
            self._log(
                f"  ↳ ImpactAnalysis: ~{ia.estimated_users_impacted:,} users affected | "
                f"{ia.revenue_impact_per_minute}/min | blast={ia.blast_radius}"
            )
        if ctx.similar_incidents:
            top = ctx.similar_incidents.top_match
            self._log(
                f"  ↳ SimilarIncident top: {top.incident_id} (score={top.similarity_score:.2f}) "
                f"resolved in {top.resolution_time_minutes}min"
            )

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

        user_prompt = f"""\
INCIDENT ALERT:
{ctx.alert.model_dump_json(indent=2)}

IMPACT ANALYSIS (from ImpactAnalysisAgent):
{impact_json}

SIMILAR PAST INCIDENTS (from SimilarIncidentAgent):
{similar_json}

ON-CALL ROSTER (from PagerDuty):
{json.dumps(roster, indent=2)}

SERVICE OWNERSHIP (from PagerDuty):
{json.dumps(ownership, indent=2)}

Produce the MI bridge summary. Output ONLY valid JSON matching the schema in your instructions.
"""

        self._log("Sending all context to LLM for bridge summary")
        result = await self._call_llm(_SYSTEM_PROMPT, user_prompt)

        ctx.mi_summary = MISummaryOutput(**result)
        ms = ctx.mi_summary
        self._log(
            f"Complete ✓ — headline: \"{ms.headline[:70]}\" | "
            f"teams={len(ms.teams_to_engage)} | "
            f"timeline_events={len(ms.timeline)} | "
            f"next_steps={len(ms.next_steps)}"
        )
        self._log("  ↳ Teams to engage:")
        for t in ms.teams_to_engage:
            self._log(f"     • {t.get('team')} — {t.get('oncall_contact')} — {t.get('slack_channel')}")
