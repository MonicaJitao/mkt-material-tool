"""GenerationTask schemas（落地方案 §5.4）。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class GenerationTaskOut(BaseModel):
    id: str
    campaign_id: str
    task_type: str
    status: str
    failed_stage: str | None = None
    model: str | None = None
    provider: str | None = None
    input_data: dict[str, Any] | None = None
    prompt_text: str | None = None
    output_data: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
