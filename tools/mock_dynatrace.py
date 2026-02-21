"""Mock Dynatrace tool — returns realistic but fabricated observability data."""

from __future__ import annotations

import asyncio


async def get_service_metrics(services: list[str]) -> dict:
    """Return per-service performance metrics.

    inventory-service shows severe latency and error-rate degradation consistent
    with DB connection pool exhaustion under flash-sale load.
    """
    await asyncio.sleep(0)  # yield to event loop; no real I/O

    _metrics = {
        "inventory-service": {
            "response_time_p50_ms": 4_200,
            "response_time_p95_ms": 12_800,
            "response_time_p99_ms": 18_340,
            "error_rate_pct": 42.1,
            "throughput_rps": 318,
            "cpu_pct": 61,
            "memory_pct": 74,
            "db_connection_wait_ms": 15_900,
            "db_pool_active": 10,
            "db_pool_idle": 0,
            "db_pool_max": 10,
        },
        "order-service": {
            "response_time_p50_ms": 680,
            "response_time_p95_ms": 17_100,
            "response_time_p99_ms": 21_500,
            "error_rate_pct": 38.7,
            "throughput_rps": 290,
            "cpu_pct": 48,
            "memory_pct": 58,
            "db_connection_wait_ms": 42,
            "db_pool_active": 8,
            "db_pool_idle": 12,
            "db_pool_max": 20,
        },
        "payment-service": {
            "response_time_p50_ms": 210,
            "response_time_p95_ms": 950,
            "response_time_p99_ms": 2_100,
            "error_rate_pct": 11.3,
            "throughput_rps": 180,
            "cpu_pct": 29,
            "memory_pct": 41,
            "db_connection_wait_ms": 18,
            "db_pool_active": 5,
            "db_pool_idle": 15,
            "db_pool_max": 20,
        },
        "api-gateway": {
            "response_time_p50_ms": 580,
            "response_time_p95_ms": 19_200,
            "response_time_p99_ms": 24_700,
            "error_rate_pct": 39.9,
            "throughput_rps": 1_420,
            "cpu_pct": 55,
            "memory_pct": 62,
            "db_connection_wait_ms": 0,
            "db_pool_active": 0,
            "db_pool_idle": 0,
            "db_pool_max": 0,
        },
    }

    return {svc: _metrics[svc] for svc in services if svc in _metrics}


async def get_distributed_traces(services: list[str]) -> list[dict]:
    """Return distributed trace spans.

    Trace 'TRC-8821' is the smoking gun: api-gateway → order-service →
    inventory-service where the span blocks for 16 s acquiring a DB connection
    from the HikariCP pool.
    """
    await asyncio.sleep(0)

    return [
        {
            "trace_id": "TRC-8821",
            "root_service": "api-gateway",
            "endpoint": "POST /checkout",
            "total_duration_ms": 18_420,
            "status": "ERROR",
            "spans": [
                {
                    "span_id": "SPN-001",
                    "service": "api-gateway",
                    "operation": "POST /checkout",
                    "start_offset_ms": 0,
                    "duration_ms": 18_420,
                    "status": "ERROR",
                },
                {
                    "span_id": "SPN-002",
                    "parent_span_id": "SPN-001",
                    "service": "order-service",
                    "operation": "OrderService.createOrder",
                    "start_offset_ms": 12,
                    "duration_ms": 18_395,
                    "status": "ERROR",
                },
                {
                    "span_id": "SPN-003",
                    "parent_span_id": "SPN-002",
                    "service": "inventory-service",
                    "operation": "InventoryService.reserveStock",
                    "start_offset_ms": 24,
                    "duration_ms": 18_370,
                    "status": "ERROR",
                    "tags": {
                        "db.type": "postgresql",
                        "db.operation": "SELECT FOR UPDATE",
                        "hikaricp.pool": "HikariPool-1",
                        "hikaricp.connection_wait_ms": 16_003,
                        "hikaricp.pool_status": "pool_exhausted",
                        "note": "Thread blocked 16003ms waiting for available connection from HikariPool-1 (max-pool-size=10)",
                    },
                    "error": "HikariPool$ConnectionTimeout: HikariPool-1 connection is not available, request timed out after 30000ms",
                },
                {
                    "span_id": "SPN-004",
                    "parent_span_id": "SPN-002",
                    "service": "payment-service",
                    "operation": "PaymentService.authorize",
                    "start_offset_ms": 18_380,
                    "duration_ms": 15,
                    "status": "SKIPPED",
                    "note": "Payment authorization skipped — upstream inventory reservation failed",
                },
            ],
        },
        {
            "trace_id": "TRC-8844",
            "root_service": "api-gateway",
            "endpoint": "POST /checkout",
            "total_duration_ms": 30_001,
            "status": "TIMEOUT",
            "spans": [
                {
                    "span_id": "SPN-101",
                    "service": "api-gateway",
                    "operation": "POST /checkout",
                    "start_offset_ms": 0,
                    "duration_ms": 30_001,
                    "status": "TIMEOUT",
                },
                {
                    "span_id": "SPN-102",
                    "parent_span_id": "SPN-101",
                    "service": "inventory-service",
                    "operation": "InventoryService.reserveStock",
                    "start_offset_ms": 8,
                    "duration_ms": 29_993,
                    "status": "TIMEOUT",
                    "tags": {
                        "hikaricp.pool_status": "pool_exhausted",
                        "hikaricp.pool_size_max": 10,
                        "hikaricp.pool_size_current": 10,
                        "hikaricp.pool_size_idle": 0,
                    },
                },
            ],
        },
        {
            "trace_id": "TRC-8901",
            "root_service": "api-gateway",
            "endpoint": "GET /inventory/check",
            "total_duration_ms": 320,
            "status": "OK",
            "note": "Successful trace — low concurrency window, 1 connection available",
        },
        {
            "trace_id": "TRC-8919",
            "root_service": "api-gateway",
            "endpoint": "POST /checkout",
            "total_duration_ms": 18_780,
            "status": "ERROR",
            "spans": [
                {
                    "span_id": "SPN-201",
                    "service": "inventory-service",
                    "operation": "InventoryService.reserveStock",
                    "duration_ms": 18_750,
                    "status": "ERROR",
                    "error": "HikariPool$ConnectionTimeout: pool exhausted — all 10/10 connections active",
                },
            ],
        },
    ]
