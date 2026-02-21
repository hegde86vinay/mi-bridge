from __future__ import annotations

import json

from agents.base_agent import BaseAgent
from models import SimilarIncident, SimilarIncidentOutput, IncidentContext

_SYSTEM_PROMPT = """\
You are a Similar Incident Detector for a production operations team.

Given the current incident details and a list of past resolved incidents,
identify the top 3 most similar past incidents.

Score each from 0.0 to 1.0 based on:
- Affected services overlap (high weight)
- Error patterns and exception classes (high weight)
- Symptoms and latency/error-rate profile (medium weight)
- Environment (production vs staging) (low weight)

From the best match, extract the resolution that worked and suggest an
actionable runbook step for the current incident.

Respond ONLY with valid JSON that exactly matches this schema — no markdown, no explanation outside the JSON:

{
  "incidents": [
    {
      "incident_id": "<id>",
      "title": "<title>",
      "similarity_score": <float 0.0-1.0>,
      "root_cause": "<root cause summary>",
      "resolution": "<what fixed it>",
      "resolution_time_minutes": <integer>
    }
  ],
  "top_match": {
    "incident_id": "<id>",
    "title": "<title>",
    "similarity_score": <float>,
    "root_cause": "<root cause>",
    "resolution": "<resolution>",
    "resolution_time_minutes": <integer>
  },
  "suggested_runbook": "<specific action to try first based on the best matching past incident>",
  "reasoning": "<explanation of why you ranked them this way>"
}

The "incidents" array must have exactly 3 items, ranked by similarity_score descending.
"top_match" must be the same object as incidents[0].
"""


class SimilarIncidentAgent(BaseAgent):
    name = "SIMILAR"

    async def run(self, ctx: IncidentContext) -> None:
        self._log("Searching for similar past incidents")

        servicenow = self.tools["servicenow"]

        keywords = (
            ctx.alert.affected_services
            + [ctx.alert.title]
            + ["timeout", "connection pool", "checkout", "flash sale"]
        )

        # ── Tool call: search past incidents ──────────────────────────────
        self._log(f"[TOOL] servicenow.search_past_incidents({len(keywords)} keywords)")
        self._log(f"  ↳ keywords: {keywords}")
        past_incidents = await servicenow.search_past_incidents(keywords)
        self._log(f"  ↳ Retrieved {len(past_incidents)} past incidents from ServiceNow")

        for inc in past_incidents:
            self._log(
                f"  ↳ {inc['incident_id']} [{inc['severity']}] {inc['date']}: "
                f"\"{inc['title']}\""
            )
            self._log(f"     services={inc['affected_services']}  "
                      f"resolved_in={inc['resolution_time_minutes']}min")

        user_prompt = f"""\
CURRENT INCIDENT:
{ctx.alert.model_dump_json(indent=2)}

PAST RESOLVED INCIDENTS (from ServiceNow):
{json.dumps(past_incidents, indent=2)}

Identify the top 3 most similar past incidents and suggest a runbook action.
Output ONLY valid JSON matching the schema in your instructions.
"""

        self._log("Sending past incidents to LLM for similarity analysis")
        result = await self._call_llm(_SYSTEM_PROMPT, user_prompt)

        ctx.similar_incidents = SimilarIncidentOutput(
            incidents=[SimilarIncident(**inc) for inc in result["incidents"]],
            top_match=SimilarIncident(**result["top_match"]),
            suggested_runbook=result["suggested_runbook"],
            reasoning=result["reasoning"],
        )
        top = ctx.similar_incidents.top_match
        self._log(
            f"Complete ✓ — top_match={top.incident_id} "
            f"(score={top.similarity_score:.2f}) | "
            f"resolved_in={top.resolution_time_minutes}min"
        )
        self._log(f"  ↳ Suggested runbook: {top.resolution[:80]}...")
