from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorDetail(StrictModel):
    code: str
    message: str
    correlation_id: str
    retryable: bool
    details: dict[str, object] = Field(default_factory=dict)


class ErrorEnvelope(StrictModel):
    error: ErrorDetail
