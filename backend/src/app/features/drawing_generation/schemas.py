from pydantic import BaseModel, Field

from .domain.key_plan.config import KeyPlanOptions


class KeyPlanRequest(BaseModel):
    generation_id: str = Field(min_length=32, max_length=32, pattern=r"^[0-9a-f]+$")
    options: KeyPlanOptions = Field(default_factory=KeyPlanOptions)
