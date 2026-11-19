from typing import Any
import httpx
from app.core.config import settings


async def prometheus_query(query: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=8) as client:
        response = await client.get(f"{settings.prometheus_url}/api/v1/query", params={"query": query})
        response.raise_for_status()
        return response.json()


async def loki_query(query: str, limit: int = 100) -> dict[str, Any]:
    import time
    end_ns = time.time_ns()
    start_ns = end_ns - 60 * 60 * 1_000_000_000
    async with httpx.AsyncClient(timeout=8) as client:
        response = await client.get(
            f"{settings.loki_url}/loki/api/v1/query_range",
            params={"query": query, "start": str(start_ns), "end": str(end_ns), "limit": limit, "direction": "backward"},
        )
        response.raise_for_status()
        return response.json()


async def jaeger_services() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=8) as client:
        response = await client.get(f"{settings.jaeger_url}/api/services")
        response.raise_for_status()
        return response.json()


async def jaeger_traces(service: str = "monitored-api", lookback: str = "1h", limit: int = 50) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=8) as client:
        response = await client.get(f"{settings.jaeger_url}/api/traces", params={"service": service, "lookback": lookback, "limit": limit})
        response.raise_for_status()
        return response.json()


async def collect_telemetry() -> dict[str, Any]:
    import asyncio
    queries = {
        "cpu": 'rate(container_cpu_usage_seconds_total[5m])',
        "memory": 'container_memory_working_set_bytes',
        "http_errors": 'sum(rate(http_requests_total{status=~"5.."}[5m]))',
        "latency": 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))',
    }
    async def safe_query(name: str, query: str):
        try:
            return name, await prometheus_query(query)
        except Exception as exc:
            return name, {"available": False, "error": str(exc)}
    results = await asyncio.gather(*(safe_query(k, v) for k, v in queries.items()))
    return dict(results)
