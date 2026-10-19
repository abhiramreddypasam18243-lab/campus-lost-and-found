from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Health check response schema."""
    model_config = ConfigDict(extra="forbid")

    status: str
    database: str
    worker: str
    version: str
    environment: str
