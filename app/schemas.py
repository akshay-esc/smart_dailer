from pydantic import BaseModel, Field
from typing import Literal

ProviderName = Literal["fast", "flaky"]

class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    status: Literal["AVAILABLE", "OFFLINE", "PAUSED"] = "AVAILABLE"

class BulkCreate(BaseModel):
    count: int = Field(ge=1, le=10000)

class BorrowerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=3, max_length=30)

class AgentStatusUpdate(BaseModel):
    status: Literal["AVAILABLE", "OFFLINE", "PAUSED"]

class DialRequest(BaseModel):
    campaign_id: str = "default"
    provider: ProviderName = "fast"
    max_calls: int = Field(default=10, ge=1, le=1000)

class PredictiveDialRequest(BaseModel):
    campaign_id: str = "default"
    provider: ProviderName = "fast"
    max_requested: int = Field(default=10, ge=1, le=1000)

class ProviderEventIn(BaseModel):
    provider: ProviderName
    event_id: str = Field(min_length=1, max_length=120)
    call_id: str
    status: Literal["RINGING", "ANSWERED", "CONNECTED", "COMPLETED", "FAILED", "CANCELLED"]

class ProviderHealthUpdate(BaseModel):
    health: Literal["healthy", "unhealthy"]
