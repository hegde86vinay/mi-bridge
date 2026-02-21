"""Mock ServiceNow tool — returns fabricated change request and incident data."""

from __future__ import annotations

import asyncio


async def get_active_change_requests(services: list[str]) -> list[dict]:
    """Return change requests deployed or in-flight within the past 24 hours.

    CR2077 is the key suspect: it reduced HikariCP max-pool-size from 20 → 10
    on inventory-service, deployed exactly 2 hours before the incident.
    CR2081 is a red herring: unrelated CDN change on api-gateway.
    """
    await asyncio.sleep(0)

    all_crs = [
        {
            "cr_id": "CR2077",
            "title": "Tune HikariCP connection pool settings for inventory-service",
            "description": (
                "Reduce maximumPoolSize from 20 to 10 and set minimumIdle to 2 "
                "to reduce idle connection overhead and lower DB memory pressure. "
                "Tested under normal load — p99 latency unchanged at <200ms."
            ),
            "service": "inventory-service",
            "component": "hikaricp-config",
            "config_change": {
                "parameter": "spring.datasource.hikari.maximum-pool-size",
                "old_value": "20",
                "new_value": "10",
            },
            "environment": "production",
            "status": "Deployed",
            "deployed_at": "2024-01-15T12:04:33Z",
            "deployed_by": "james.wu@company.com",
            "approved_by": "sarah.chen@company.com",
            "ticket_url": "https://company.service-now.com/change/CR2077",
            "rollback_plan": "Revert spring.datasource.hikari.maximum-pool-size to 20 via config map update and rolling restart",
        },
        {
            "cr_id": "CR2081",
            "title": "Update CDN origin routing rules for api-gateway",
            "description": (
                "Update CloudFront origin groups to add eu-west-2 as secondary origin. "
                "No application code changes. Purely infrastructure-level routing."
            ),
            "service": "api-gateway",
            "component": "cdn-routing",
            "environment": "production",
            "status": "Deployed",
            "deployed_at": "2024-01-15T08:17:45Z",
            "deployed_by": "priya.nair@company.com",
            "approved_by": "tom.bradley@company.com",
            "ticket_url": "https://company.service-now.com/change/CR2081",
            "rollback_plan": "Revert CloudFront distribution config to previous snapshot",
        },
    ]

    return [cr for cr in all_crs if cr["service"] in services]


async def search_past_incidents(keywords: list[str]) -> list[dict]:
    """Return past resolved incidents relevant to the given keywords."""
    await asyncio.sleep(0)

    return [
        {
            "incident_id": "INC-1843",
            "title": "inventory-service degradation during Black Friday flash sale",
            "date": "2023-11-24",
            "environment": "production",
            "severity": "P1",
            "affected_services": ["inventory-service", "order-service", "api-gateway"],
            "symptoms": "42% error rate on /checkout, p99 latency >15s on inventory-service",
            "root_cause": (
                "DB connection pool starvation: maximumPoolSize was 10, "
                "insufficient for 8× normal traffic during Black Friday sale. "
                "Each checkout holds a DB connection for 200–400ms while processing."
            ),
            "resolution": (
                "Increased HikariCP maximumPoolSize from 10 to 30 via Kubernetes ConfigMap update "
                "and triggered rolling restart of inventory-service pods. Full recovery in 12 minutes."
            ),
            "resolution_time_minutes": 28,
            "post_mortem_url": "https://wiki.company.com/post-mortem/INC-1843",
            "tags": ["hikaricp", "connection-pool", "flash-sale", "inventory-service"],
        },
        {
            "incident_id": "INC-2014",
            "title": "payment-service latency spike — DB deadlock storm",
            "date": "2024-01-03",
            "environment": "production",
            "severity": "P2",
            "affected_services": ["payment-service"],
            "symptoms": "p99 latency 12s, 8% error rate, transaction rollback errors in logs",
            "root_cause": (
                "Missing index on payments.transaction_id caused full table scans "
                "under concurrent writes, leading to row-level lock contention."
            ),
            "resolution": "Added composite index on (transaction_id, status). Latency normalized within 5 minutes.",
            "resolution_time_minutes": 19,
            "post_mortem_url": "https://wiki.company.com/post-mortem/INC-2014",
            "tags": ["deadlock", "database", "payment-service", "index"],
        },
        {
            "incident_id": "INC-1701",
            "title": "api-gateway 503 storm — upstream pool exhaustion",
            "date": "2023-09-11",
            "environment": "production",
            "severity": "P1",
            "affected_services": ["api-gateway", "user-service"],
            "symptoms": "35% HTTP 503s at api-gateway, user-service unresponsive",
            "root_cause": (
                "user-service connection pool to Redis exhausted during promotional campaign. "
                "api-gateway circuit breaker opened, causing 503 cascade."
            ),
            "resolution": (
                "Scaled user-service Redis connection pool from 5 to 25. "
                "Reset circuit breaker manually after pool recovered."
            ),
            "resolution_time_minutes": 41,
            "post_mortem_url": "https://wiki.company.com/post-mortem/INC-1701",
            "tags": ["connection-pool", "redis", "circuit-breaker", "api-gateway"],
        },
    ]
