"""Mock Splunk tool — returns realistic fabricated log data."""

from __future__ import annotations

import asyncio


async def query_error_logs(services: list[str]) -> list[dict]:
    """Return error log entries for the given services.

    inventory-service logs repeatedly show HikariCP connection pool exhaustion,
    which is the key error pattern linking to the DB pool config change in CR2077.
    """
    await asyncio.sleep(0)

    all_logs = [
        {
            "timestamp": "2024-01-15T14:02:11.334Z",
            "service": "inventory-service",
            "level": "ERROR",
            "thread": "http-nio-8080-exec-47",
            "logger": "com.acme.inventory.service.InventoryService",
            "message": "HikariPool-1 connection is not available, request timed out after 30000ms",
            "exception_class": "com.zaxxer.hikari.pool.HikariPool$PoolTimeoutException",
            "stack_trace_snippet": (
                "com.zaxxer.hikari.pool.HikariPool$PoolTimeoutException: "
                "HikariPool-1 connection is not available, request timed out after 30000ms\n"
                "\tat com.zaxxer.hikari.pool.HikariPool.getConnection(HikariPool.java:213)\n"
                "\tat com.zaxxer.hikari.pool.HikariPool.getConnection(HikariPool.java:163)\n"
                "\tat com.acme.inventory.repository.InventoryRepository.findBySkuForUpdate(InventoryRepository.java:88)\n"
                "\tat com.acme.inventory.service.InventoryService.reserveStock(InventoryService.java:142)"
            ),
            "hikaricp": {
                "pool_name": "HikariPool-1",
                "max_pool_size": 10,
                "active_connections": 10,
                "idle_connections": 0,
                "pending_threads": 143,
            },
        },
        {
            "timestamp": "2024-01-15T14:02:14.891Z",
            "service": "inventory-service",
            "level": "ERROR",
            "thread": "http-nio-8080-exec-51",
            "logger": "com.acme.inventory.service.InventoryService",
            "message": "HikariPool-1 connection is not available, request timed out after 30000ms",
            "exception_class": "com.zaxxer.hikari.pool.HikariPool$PoolTimeoutException",
            "stack_trace_snippet": (
                "com.zaxxer.hikari.pool.HikariPool$PoolTimeoutException: "
                "HikariPool-1 connection is not available, request timed out after 30000ms\n"
                "\tat com.zaxxer.hikari.pool.HikariPool.getConnection(HikariPool.java:213)\n"
                "\tat com.acme.inventory.service.InventoryService.reserveStock(InventoryService.java:142)"
            ),
            "hikaricp": {
                "pool_name": "HikariPool-1",
                "max_pool_size": 10,
                "active_connections": 10,
                "idle_connections": 0,
                "pending_threads": 167,
            },
        },
        {
            "timestamp": "2024-01-15T14:02:18.112Z",
            "service": "order-service",
            "level": "ERROR",
            "thread": "http-nio-8081-exec-22",
            "logger": "com.acme.order.service.OrderService",
            "message": "Upstream call to inventory-service failed: timeout after 18340ms",
            "exception_class": "feign.RetryableException",
            "stack_trace_snippet": (
                "feign.RetryableException: timeout after 18340ms\n"
                "\tat feign.FeignException.errorStatus(FeignException.java:92)\n"
                "\tat com.acme.order.client.InventoryClient.reserveStock(InventoryClient.java:54)\n"
                "\tat com.acme.order.service.OrderService.createOrder(OrderService.java:211)"
            ),
            "upstream_service": "inventory-service",
            "timeout_ms": 18_340,
        },
        {
            "timestamp": "2024-01-15T14:02:21.445Z",
            "service": "inventory-service",
            "level": "ERROR",
            "thread": "http-nio-8080-exec-58",
            "logger": "com.acme.inventory.service.InventoryService",
            "message": "Pool exhausted — pool size max=10 active=10 idle=0 waiting=189 threads. "
                       "Consider increasing maximumPoolSize or reducing connection hold time.",
            "exception_class": "com.zaxxer.hikari.pool.HikariPool$PoolTimeoutException",
            "stack_trace_snippet": (
                "com.zaxxer.hikari.pool.HikariPool$PoolTimeoutException: "
                "connection is not available, request timed out after 30000ms\n"
                "\tat com.zaxxer.hikari.pool.HikariPool.getConnection(HikariPool.java:213)"
            ),
            "hikaricp": {
                "pool_name": "HikariPool-1",
                "max_pool_size": 10,
                "active_connections": 10,
                "idle_connections": 0,
                "pending_threads": 189,
                "connection_timeout_ms": 30_000,
            },
        },
        {
            "timestamp": "2024-01-15T14:02:29.007Z",
            "service": "api-gateway",
            "level": "ERROR",
            "thread": "reactor-http-nio-3",
            "logger": "com.acme.gateway.filter.CircuitBreakerFilter",
            "message": "Circuit breaker OPEN for route inventory-service — "
                       "failure rate 42.1% exceeds threshold 40%",
            "exception_class": "io.github.resilience4j.circuitbreaker.CallNotPermittedException",
            "stack_trace_snippet": (
                "io.github.resilience4j.circuitbreaker.CallNotPermittedException: "
                "CircuitBreaker 'inventory-service' is OPEN and does not permit further calls\n"
                "\tat io.github.resilience4j.circuitbreaker.CircuitBreaker.lambda$decorateSupplier"
            ),
            "circuit_breaker": {
                "name": "inventory-service",
                "state": "OPEN",
                "failure_rate_pct": 42.1,
                "threshold_pct": 40,
                "slow_call_duration_threshold_ms": 5_000,
            },
        },
    ]

    return [entry for entry in all_logs if entry["service"] in services]
