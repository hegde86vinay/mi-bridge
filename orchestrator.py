from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from agents.impact_analysis_agent import ImpactAnalysisAgent
from agents.mi_summarizer_agent import MISummarizerAgent
from agents.rca_agent import RCAAgent
from agents.similar_incident_agent import SimilarIncidentAgent
from models import IncidentContext, RawAlert
from utils.llm_client import LLMClient
from utils.logger import log

# ─── ANSI helpers for the MI Brief ──────────────────────────────────────────
_RST = "\033[0m"
_BOLD = "\033[1m"
_GREEN = "\033[1;32m"
_CYAN = "\033[36m"
_YLW = "\033[33m"
_MAG = "\033[35m"
_DIM = "\033[2;37m"
_RED = "\033[1;31m"


class MIBridgeOrchestrator:
    def __init__(self, llm: LLMClient, tools: dict[str, Any]) -> None:
        self.llm = llm
        self.tools = tools

        self.impact_agent = ImpactAnalysisAgent(llm=llm, tools=tools)
        self.similar_agent = SimilarIncidentAgent(llm=llm, tools=tools)
        self.summarizer_agent = MISummarizerAgent(llm=llm, tools=tools)
        self.rca_agent = RCAAgent(llm=llm, tools=tools)

    async def handle_alert(self, alert: RawAlert) -> IncidentContext:
        log(
            "ORCHESTRATOR",
            f"Incident opened: {alert.incident_id} | {alert.title} | {alert.severity}",
        )

        ctx = IncidentContext(
            incident_id=alert.incident_id,
            alert=alert,
            created_at=datetime.now(timezone.utc),
        )

        total_start = time.perf_counter()

        # ── PHASE 1: Parallel ──────────────────────────────────────────────
        log("ORCHESTRATOR", "━━━  PHASE 1 START  ━━━  (ImpactAnalysis + SimilarIncident in parallel)")
        t0 = time.perf_counter()

        await asyncio.gather(
            self._run_agent(self.impact_agent, ctx),
            self._run_agent(self.similar_agent, ctx),
        )

        ctx.phase_timings["phase_1"] = time.perf_counter() - t0
        log(
            "ORCHESTRATOR",
            f"━━━  PHASE 1 COMPLETE  ━━━  wall_time={ctx.phase_timings['phase_1']:.2f}s",
        )

        # ── PHASE 2: Sequential ────────────────────────────────────────────
        log("ORCHESTRATOR", "━━━  PHASE 2 START  ━━━  (MISummarizer)")
        t1 = time.perf_counter()

        await self._run_agent(self.summarizer_agent, ctx)

        ctx.phase_timings["phase_2"] = time.perf_counter() - t1
        log(
            "ORCHESTRATOR",
            f"━━━  PHASE 2 COMPLETE  ━━━  wall_time={ctx.phase_timings['phase_2']:.2f}s",
        )

        # ── PHASE 3: Sequential ────────────────────────────────────────────
        log("ORCHESTRATOR", "━━━  PHASE 3 START  ━━━  (RCA)")
        t2 = time.perf_counter()

        await self._run_agent(self.rca_agent, ctx)

        ctx.phase_timings["phase_3"] = time.perf_counter() - t2
        log(
            "ORCHESTRATOR",
            f"━━━  PHASE 3 COMPLETE  ━━━  wall_time={ctx.phase_timings['phase_3']:.2f}s",
        )

        ctx.phase_timings["total"] = time.perf_counter() - total_start

        # ── PRINT MI BRIEF ─────────────────────────────────────────────────
        self._print_mi_brief(ctx)

        return ctx

    async def _run_agent(self, agent: Any, ctx: IncidentContext) -> None:
        try:
            await agent.run(ctx)
        except Exception as exc:
            log("ERROR", f"Agent {agent.name} failed: {exc}")
            # Leave the relevant ctx field as None and continue

    def _print_mi_brief(self, ctx: IncidentContext) -> None:
        alert = ctx.alert
        impact = ctx.impact_analysis
        similar = ctx.similar_incidents
        summary = ctx.mi_summary
        rca = ctx.rca
        pt = ctx.phase_timings

        width = 58
        bar = "═" * width

        def section(icon: str, title: str) -> str:
            return f"\n{_BOLD}{icon}  {title}{_RST}"

        print(f"\n{_GREEN}╔{bar}╗")
        title_line = f"  MI BRIEF  ·  {alert.severity}  ·  {alert.title}"
        print(f"║{title_line:<{width}}║")
        print(f"╚{bar}╝{_RST}")

        # ── SUMMARY ──────────────────────────────────────────────────────
        print(section("📋", "SUMMARY"))
        if summary:
            print(f"   {_BOLD}{summary.headline}{_RST}")
            print(f"   {summary.narrative}")
        else:
            print(f"   {_RED}(summary unavailable){_RST}")

        # ── BLAST RADIUS ─────────────────────────────────────────────────
        print(section("💥", "BLAST RADIUS"))
        if impact:
            blast = " → ".join(impact.blast_radius) if impact.blast_radius else "N/A"
            print(f"   Services:        {blast}")
            segs = ", ".join(impact.customer_segments_affected)
            print(f"   Segments:        {segs}")
            print(f"   Users affected:  ~{impact.estimated_users_impacted:,}")
            print(f"   Revenue impact:  {impact.revenue_impact_per_minute}/min")
            print(f"   Confidence:      {impact.confidence * 100:.0f}%")
        else:
            print(f"   {_RED}(impact analysis unavailable){_RST}")

        # ── ROOT CAUSE ───────────────────────────────────────────────────
        print(section("🔍", "ROOT CAUSE"))
        if rca and rca.probable_root_causes:
            top = rca.probable_root_causes[0]
            print(f"   #1  {top.get('cause', 'N/A')}")
            print(f"       Evidence:   {top.get('evidence', 'N/A')}")
            print(f"       Confidence: {top.get('confidence_pct', 'N/A')}%")
        else:
            print(f"   {_RED}(RCA unavailable){_RST}")

        # ── CORRELATED CR ────────────────────────────────────────────────
        print(section("🔧", "CORRELATED CHANGE REQUEST"))
        if rca and rca.correlated_change_requests:
            cr = rca.correlated_change_requests[0]
            rollback_yn = "YES ⚠️" if rca.rollback_candidate == cr.get("cr_id") else "NO"
            print(f"   {_BOLD}{cr.get('cr_id', 'N/A')}{_RST}  ·  {cr.get('description', 'N/A')}")
            print(f"   Deployed:  {cr.get('deployed_at', 'N/A')}  by  {cr.get('deployed_by', 'N/A')}")
            print(f"   Rollback candidate: {rollback_yn}")
        elif rca and rca.rollback_candidate:
            print(f"   Rollback candidate: {rca.rollback_candidate}")
        else:
            print(f"   {_DIM}No correlated CRs identified{_RST}")

        # ── TEAMS ON BRIDGE ──────────────────────────────────────────────
        print(section("👥", "TEAMS ON BRIDGE"))
        if summary and summary.teams_to_engage:
            for team_info in summary.teams_to_engage:
                team = team_info.get("team", "?")
                reason = team_info.get("reason", "?")
                contact = team_info.get("oncall_contact", "?")
                print(f"   • {_BOLD}{team}{_RST} — {reason}")
                print(f"     Contact: {contact}")
        else:
            print(f"   {_RED}(team data unavailable){_RST}")

        # ── NEXT STEPS ───────────────────────────────────────────────────
        print(section("✅", "NEXT STEPS"))
        if summary and summary.next_steps:
            for i, step in enumerate(summary.next_steps, 1):
                print(f"   {i}. {step}")
        else:
            print(f"   {_RED}(next steps unavailable){_RST}")

        # ── SIMILAR PAST INCIDENT ────────────────────────────────────────
        print(section("🔁", "SIMILAR PAST INCIDENT"))
        if similar and similar.top_match:
            top = similar.top_match
            print(f"   {_BOLD}{top.incident_id}{_RST}  ·  {top.title}")
            print(f"   Resolved in: {top.resolution_time_minutes} min")
            print(f"   How: {top.resolution}")
            print(f"   Suggested runbook: {similar.suggested_runbook}")
        else:
            print(f"   {_DIM}No similar incidents found{_RST}")

        # ── PHASE TIMINGS ────────────────────────────────────────────────
        print(section("⏱ ", "PHASE TIMINGS"))
        phase1 = pt.get("phase_1", 0)
        phase2 = pt.get("phase_2", 0)
        phase3 = pt.get("phase_3", 0)
        total = pt.get("total", phase1 + phase2 + phase3)
        print(f"   {_DIM}Phase 1 (parallel):  {phase1:.2f}s")
        print(f"   Phase 2 (summarize): {phase2:.2f}s")
        print(f"   Phase 3 (RCA):       {phase3:.2f}s")
        print(f"   Total:               {total:.2f}s{_RST}")

        print(f"\n{_DIM}{'═' * width}{_RST}\n")
