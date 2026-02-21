"""Pre-baked realistic LLM responses for --dry-run mode.

These responses mirror exactly what a real Claude call would return for each agent,
derived from the planted mock data. They let you run the full agent/orchestrator
pipeline — tool calls, data assembly, JSON parsing, Pydantic validation, MI Brief —
without needing a real API key.
"""

from __future__ import annotations

import json

# ─── ImpactAnalysisAgent ──────────────────────────────────────────────────────

IMPACT_ANALYSIS_RESPONSE = json.dumps(
    {
        "blast_radius": [
            "inventory-service",
            "order-service",
            "api-gateway",
            "payment-service",
        ],
        "customer_segments_affected": [
            "Flash sale shoppers (primary — all checkout attempts failing)",
            "Regular checkout customers (secondary — 39% error rate at api-gateway)",
            "Mobile app users (routed through api-gateway circuit breaker)",
            "Guest checkout users (no session fallback — full failure)",
        ],
        "estimated_users_impacted": 47_000,
        "revenue_impact_per_minute": "$18,400",
        "severity_recommendation": "ESCALATE",
        "confidence": 0.94,
        "reasoning": (
            "inventory-service is showing catastrophic degradation: p99 latency of 18,340ms "
            "(threshold 500ms), error rate 42.1% (threshold 5%), and DB connection pool "
            "fully saturated (active=10/max=10, idle=0, 143+ threads waiting). "
            "The distributed trace TRC-8821 confirms the blast path: api-gateway → order-service "
            "→ inventory-service, where SPN-003 blocks for 16,003ms on a HikariCP pool connection "
            "acquisition. Circuit breaker at api-gateway has opened for inventory-service "
            "(failure rate 42.1% > 40% threshold). order-service inherits the timeout cascade "
            "(p99 21,500ms, 38.7% error). payment-service is secondarily affected (11.3% errors) "
            "because order creation fails before payment is reached. At 1,420 rps on api-gateway "
            "and a 42% failure rate, approximately 596 checkout attempts fail per second. "
            "Assuming average order value of ~$52 and 3s average checkout window, revenue impact "
            "is ~$18,400/min. ESCALATE is warranted — this is a full checkout system outage "
            "during an active flash sale event."
        ),
    }
)

# ─── SimilarIncidentAgent ─────────────────────────────────────────────────────

SIMILAR_INCIDENT_RESPONSE = json.dumps(
    {
        "incidents": [
            {
                "incident_id": "INC-1843",
                "title": "inventory-service degradation during Black Friday flash sale",
                "similarity_score": 0.97,
                "root_cause": (
                    "DB connection pool starvation: maximumPoolSize was 10, "
                    "insufficient for 8× normal traffic during Black Friday sale."
                ),
                "resolution": (
                    "Increased HikariCP maximumPoolSize from 10 to 30 via Kubernetes ConfigMap "
                    "update and triggered rolling restart of inventory-service pods. "
                    "Full recovery in 12 minutes."
                ),
                "resolution_time_minutes": 28,
            },
            {
                "incident_id": "INC-1701",
                "title": "api-gateway 503 storm — upstream pool exhaustion",
                "similarity_score": 0.71,
                "root_cause": (
                    "user-service connection pool to Redis exhausted during promotional campaign. "
                    "api-gateway circuit breaker opened, causing 503 cascade."
                ),
                "resolution": (
                    "Scaled user-service Redis connection pool from 5 to 25. "
                    "Reset circuit breaker manually after pool recovered."
                ),
                "resolution_time_minutes": 41,
            },
            {
                "incident_id": "INC-2014",
                "title": "payment-service latency spike — DB deadlock storm",
                "similarity_score": 0.38,
                "root_cause": (
                    "Missing index on payments.transaction_id caused full table scans "
                    "under concurrent writes, leading to row-level lock contention."
                ),
                "resolution": "Added composite index on (transaction_id, status). Latency normalized within 5 minutes.",
                "resolution_time_minutes": 19,
            },
        ],
        "top_match": {
            "incident_id": "INC-1843",
            "title": "inventory-service degradation during Black Friday flash sale",
            "similarity_score": 0.97,
            "root_cause": (
                "DB connection pool starvation: maximumPoolSize was 10, "
                "insufficient for 8× normal traffic during Black Friday sale."
            ),
            "resolution": (
                "Increased HikariCP maximumPoolSize from 10 to 30 via Kubernetes ConfigMap "
                "update and triggered rolling restart of inventory-service pods. "
                "Full recovery in 12 minutes."
            ),
            "resolution_time_minutes": 28,
        },
        "suggested_runbook": (
            "IMMEDIATE: Increase inventory-service HikariCP maximumPoolSize — "
            "edit the Kubernetes ConfigMap (spring.datasource.hikari.maximum-pool-size), "
            "set value to at least 30, then trigger a rolling restart of inventory-service pods. "
            "Monitor HikariPool-1 idle count — when idle > 0, the pool has recovered. "
            "Reference: https://wiki.company.com/runbooks/inventory-service"
        ),
        "reasoning": (
            "INC-1843 scores 0.97: identical service (inventory-service), identical event type "
            "(flash sale), identical symptom profile (42% error rate, >15s p99 latency), and "
            "identical exception class (HikariPool connection pool exhaustion). The maximumPoolSize "
            "was also 10 in that incident. INC-1701 scores 0.71: same pattern (connection pool "
            "exhaustion causing api-gateway circuit breaker to open) but different service and "
            "technology stack (Redis vs PostgreSQL/HikariCP). INC-2014 scores 0.38: shares DB "
            "latency symptom and payment-service involvement but root cause is unrelated "
            "(index/deadlock vs pool exhaustion)."
        ),
    }
)

# ─── MISummarizerAgent ────────────────────────────────────────────────────────

MI_SUMMARY_RESPONSE = json.dumps(
    {
        "headline": "P1 ACTIVE: Checkout is down for all flash sale users — inventory service DB pool exhausted",
        "narrative": (
            "Our flash sale checkout is currently failing for approximately 47,000 customers, "
            "with a 42% error rate causing an estimated $18,400 in lost revenue every minute. "
            "The inventory service is unable to process stock reservations because its database "
            "connection pool is completely saturated and has been unresponsive for the past "
            "30+ minutes. We have identified a similar incident from our Black Friday event last "
            "year that was resolved in under 30 minutes, and the team is investigating the "
            "same resolution path now."
        ),
        "timeline": [
            {"time": "12:04 UTC", "event": "CR2077 deployed to production: HikariCP pool config change on inventory-service"},
            {"time": "14:00 UTC", "event": "Flash sale traffic begins — 8× normal load hits inventory-service"},
            {"time": "14:02 UTC", "event": "HikariPool-1 exhausted: all 10/10 connections active, 143 threads waiting"},
            {"time": "14:02 UTC", "event": "inventory-service error rate crosses 42% — p99 latency hits 18,340ms"},
            {"time": "14:02 UTC", "event": "order-service begins timing out on inventory calls — 38.7% error rate"},
            {"time": "14:02 UTC", "event": "api-gateway circuit breaker OPENS for inventory-service route"},
            {"time": "14:02 UTC", "event": "Dynatrace alert P-8821 fires — P1 incident INC-2077-FLASHSALE opened"},
            {"time": "14:03 UTC", "event": "MI Bridge activated — impact analysis, RCA, and team engagement in progress"},
        ],
        "teams_to_engage": [
            {
                "team": "Inventory Platform",
                "reason": "Owns inventory-service — root cause service, must action the fix or rollback",
                "oncall_contact": "James Wu (@james.wu) — +1-415-555-0142",
                "slack_channel": "#inventory-platform-incidents",
            },
            {
                "team": "Order Management",
                "reason": "order-service has 38.7% error rate due to inventory cascade — must validate recovery",
                "oncall_contact": "Anika Patel (@anika.patel) — +1-415-555-0219",
                "slack_channel": "#order-mgmt-incidents",
            },
            {
                "team": "Platform Engineering",
                "reason": "Owns api-gateway — circuit breaker is OPEN and must be reset after inventory recovers",
                "oncall_contact": "Lena Fischer (@lena.fischer) — +1-415-555-0471",
                "slack_channel": "#platform-incidents",
            },
            {
                "team": "Payments & Billing",
                "reason": "payment-service showing 11.3% errors — must confirm no payments were double-processed",
                "oncall_contact": "Marcus Johnson (@marcus.johnson) — +1-415-555-0388",
                "slack_channel": "#payments-incidents",
            },
        ],
        "next_steps": [
            "IMMEDIATE — Inventory Platform (James Wu): Increase HikariCP maximumPoolSize from 10 to 30 via ConfigMap patch and rolling restart of inventory-service pods",
            "IMMEDIATE — Inventory Platform: If pool increase takes >5min to stabilise, initiate rollback of CR2077 (revert maximum-pool-size to 20)",
            "PARALLEL — Platform Engineering (Lena Fischer): Monitor api-gateway circuit breaker — reset manually once inventory-service error rate drops below 5%",
            "PARALLEL — Order Management (Anika Patel): Identify and re-queue failed orders from the last 30 minutes; confirm order-service recovery after inventory stabilises",
            "PARALLEL — Payments & Billing (Marcus Johnson): Audit payment logs for any partial or duplicate authorisations during the outage window",
            "POST-RECOVERY — Inventory Platform: Conduct post-mortem on why CR2077 was not load-tested at flash-sale traffic levels before production deploy",
            "POST-RECOVERY — All teams: Update runbook with pool-size recommendations for high-traffic events",
        ],
    }
)

# ─── RCAAgent ─────────────────────────────────────────────────────────────────

RCA_RESPONSE = json.dumps(
    {
        "probable_root_causes": [
            {
                "rank": 1,
                "cause": (
                    "CR2077 reduced HikariCP maximumPoolSize from 20 to 10 on inventory-service "
                    "2 hours before the flash sale. Under 8× normal load, 10 connections are "
                    "insufficient to serve concurrent checkout requests, causing complete pool "
                    "exhaustion and a connection starvation cascade."
                ),
                "evidence": (
                    "Splunk: HikariPool$PoolTimeoutException repeated across inventory-service "
                    "with pool active=10/max=10, idle=0, pending_threads up to 189. "
                    "Dynatrace trace TRC-8821 SPN-003: 16,003ms blocked on HikariCP connection "
                    "acquisition with tag hikaricp.pool_status=pool_exhausted and max-pool-size=10. "
                    "ServiceNow CR2077: maximumPoolSize changed 20→10, deployed 12:04 UTC by "
                    "james.wu@company.com — exactly 2 hours before incident onset at 14:02 UTC. "
                    "Past incident INC-1843: identical failure mode (pool=10 under flash sale) "
                    "resolved by increasing pool to 30."
                ),
                "confidence_pct": 96,
            },
            {
                "rank": 2,
                "cause": (
                    "Insufficient load testing of CR2077 before flash sale deployment. "
                    "The CR description notes 'tested under normal load' — flash sale generates "
                    "8× normal concurrency, which was not validated."
                ),
                "evidence": (
                    "CR2077 description: 'Tested under normal load — p99 latency unchanged at <200ms.' "
                    "No mention of flash sale traffic simulation in the change approval. "
                    "INC-1843 post-mortem recommended load-testing at 10× normal before sales events."
                ),
                "confidence_pct": 88,
            },
            {
                "rank": 3,
                "cause": (
                    "api-gateway circuit breaker threshold (40%) is too close to the error rate "
                    "at normal load variability, causing it to open before teams can respond, "
                    "amplifying the customer impact."
                ),
                "evidence": (
                    "Splunk log: circuit breaker opened at 42.1% failure rate vs 40% threshold — "
                    "only a 2.1% margin. Dynatrace api-gateway error_rate_pct=39.9% under normal "
                    "conditions is dangerously close to the trip threshold."
                ),
                "confidence_pct": 61,
            },
        ],
        "correlated_change_requests": [
            {
                "cr_id": "CR2077",
                "service": "inventory-service",
                "deployed_at": "2024-01-15T12:04:33Z",
                "deployed_by": "james.wu@company.com",
                "description": (
                    "Tune HikariCP connection pool: reduced maximumPoolSize from 20 to 10 "
                    "and set minimumIdle=2 for memory optimisation. Deployed 2h before incident."
                ),
            },
            {
                "cr_id": "CR2081",
                "service": "api-gateway",
                "deployed_at": "2024-01-15T08:17:45Z",
                "deployed_by": "priya.nair@company.com",
                "description": (
                    "CDN origin routing update — unrelated to incident. "
                    "No application-layer changes. Ruled out as root cause."
                ),
            },
        ],
        "recommended_resolution": (
            "Immediately patch inventory-service Kubernetes ConfigMap to set "
            "spring.datasource.hikari.maximum-pool-size=30, then trigger a rolling restart. "
            "If pool saturation does not clear within 5 minutes, initiate full rollback of CR2077 "
            "(revert to maximum-pool-size=20). After pool recovery, manually reset the api-gateway "
            "circuit breaker for the inventory-service route."
        ),
        "rollback_candidate": "CR2077",
        "remediation_steps": [
            "Inventory Platform on-call (James Wu): kubectl patch configmap inventory-service-config "
            "--patch '{\"data\":{\"HIKARI_MAX_POOL_SIZE\":\"30\"}}' -n production",
            "Trigger rolling restart: kubectl rollout restart deployment/inventory-service -n production",
            "Watch pool recovery: kubectl logs -f deployment/inventory-service -n production | grep HikariPool",
            "If not recovering in 5min — rollback CR2077: revert maximum-pool-size to 20 and restart",
            "Platform Engineering: after inventory error_rate < 5%, run: "
            "curl -X POST https://api-gateway/actuator/circuitbreakers/inventory-service/reset",
            "Order Management: replay failed orders from 14:00–14:35 UTC window via order-service retry queue",
            "Payments: audit payment_events table for any status=PENDING orders in the outage window",
            "Post-incident: add flash-sale load test (10× normal) as mandatory gate for inventory-service CRs",
        ],
        "evidence_trail": [
            {
                "source": "splunk_logs",
                "query_or_action": "query_error_logs(['inventory-service', 'order-service', 'payment-service', 'api-gateway'])",
                "finding": "3 × HikariPool$PoolTimeoutException on inventory-service — pool active=10/max=10 idle=0, "
                           "pending threads growing to 189. Pattern consistent with complete pool exhaustion.",
            },
            {
                "source": "dynatrace_traces",
                "query_or_action": "get_distributed_traces — TRC-8821 SPN-003 inventory-service span",
                "finding": "16,003ms blocked on HikariCP connection acquisition. Tag: "
                           "hikaricp.pool_status=pool_exhausted, max-pool-size=10. "
                           "Thread never acquires connection — throws PoolTimeoutException.",
            },
            {
                "source": "servicenow_crs",
                "query_or_action": "get_active_change_requests(['inventory-service', 'api-gateway'])",
                "finding": "CR2077 deployed at 12:04 UTC (2h before incident): changed "
                           "spring.datasource.hikari.maximum-pool-size from 20 → 10. "
                           "CR2081 (api-gateway CDN change, 6h prior) ruled out — no application-layer changes.",
            },
            {
                "source": "past_incidents",
                "query_or_action": "search_past_incidents(['connection pool', 'timeout', 'HikariCP', 'inventory-service'])",
                "finding": "INC-1843 (Black Friday 2023): identical failure — inventory-service pool=10 "
                           "exhausted under flash sale traffic. Resolved by increasing pool to 30. "
                           "Resolution time: 28 min. This confirms the failure mode and validates the fix.",
            },
            {
                "source": "splunk_logs",
                "query_or_action": "Cross-reference exception class with CR2077 config change",
                "finding": "HikariPool$PoolTimeoutException directly references HikariCP library — "
                           "the same library whose maximumPoolSize config was reduced by CR2077. "
                           "Causal link confirmed: smaller pool + higher flash-sale concurrency = exhaustion.",
            },
        ],
    }
)

# ─── Dispatch map — keyed by agent name ──────────────────────────────────────

DRY_RUN_RESPONSES: dict[str, str] = {
    "IMPACT": IMPACT_ANALYSIS_RESPONSE,
    "SIMILAR": SIMILAR_INCIDENT_RESPONSE,
    "SUMMARIZER": MI_SUMMARY_RESPONSE,
    "RCA": RCA_RESPONSE,
}
