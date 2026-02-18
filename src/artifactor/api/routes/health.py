"""Health check endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from artifactor.api.dependencies import get_data_service
from artifactor.services.data_service import DataService

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Basic health check for load balancers."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/health/detailed")
async def health_detailed(
    data_service: DataService = Depends(get_data_service),
) -> dict[str, object]:
    """Detailed health check with component-level status."""
    db_healthy = await data_service.check_connection()
    vector_healthy = await data_service.check_vector_store()
    mermaid_available = data_service.check_mermaid_cli()

    components = {
        "database": {
            "status": "connected" if db_healthy else "disconnected"
        },
        "vector_store": {
            "status": "connected" if vector_healthy else "disconnected"
        },
        "mermaid_cli": {
            "status": "available" if mermaid_available else "unavailable"
        },
    }

    all_healthy = all(
        c["status"] in ("connected", "available")
        for c in components.values()
    )

    return {
        "status": "healthy" if all_healthy else "degraded",
        "version": "0.1.0",
        "components": components,
        "timestamp": datetime.now(UTC).isoformat(),
    }
