from typing import Optional
from pydantic import BaseModel, Field


class DatabaseHealth(BaseModel):
    """Database component health metadata."""

    status: str = Field(..., description="Database status ('ok' or 'unhealthy')")
    postgresql: bool = Field(..., description="PostgreSQL connectivity flag")
    postgis: bool = Field(..., description="PostGIS extension flag")


class HealthResponse(BaseModel):
    """Root lightweight health check response schema."""

    status: str = Field(default="ok", description="Service health status")
    service: str = Field(
        default="property-document-verification-api",
        description="Service identifier",
    )
    version: str = Field(..., description="Service semantic version")


class DetailedHealthResponse(HealthResponse):
    """API v1 detailed health check response schema including database status and Ollama availability."""

    database: DatabaseHealth = Field(
        ..., description="Database and PostGIS health details"
    )
    ollama: Optional[bool] = Field(
        None, description="Ollama service availability flag"
    )
