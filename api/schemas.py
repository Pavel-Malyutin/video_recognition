from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List
from datetime import datetime


class UploadResponse(BaseModel):
    task_id: str


class TaskResponse(BaseModel):
    id: str = Field(alias="task_id")
    status: str
    file_type: str
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

    @field_validator("id", mode="before")
    def uuid_to_str(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v


class TaskSegmentResponse(BaseModel):
    id: str = Field(alias="segment_id")
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    status: str
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

    @field_validator("id", mode="before")
    def uuid_to_str(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v


class RecognitionResultResponse(BaseModel):
    object_detected: str
    confidence: float
    result_file_url: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class SegmentDetailResponse(BaseModel):
    id: str = Field(alias="segment_id")
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    status: str
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None
    recognition_results: List[RecognitionResultResponse]

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

    @field_validator("id", mode="before")
    def uuid_to_str(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v

