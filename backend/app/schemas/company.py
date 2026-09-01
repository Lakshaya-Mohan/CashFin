from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class CompanySchema(BaseModel):
    id: int
    name: str
    industry: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
