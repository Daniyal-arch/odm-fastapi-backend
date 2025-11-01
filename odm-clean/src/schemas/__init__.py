"""
Pydantic Schemas
File: src/schemas/__init__.py
"""

from pydantic import BaseModel
from typing import Optional

class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str

class TaskStatus(BaseModel):
    task_id: str
    status: str
    progress: int
    message: str
    download_url: Optional[str] = None