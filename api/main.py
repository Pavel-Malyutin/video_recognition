import logging
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List

import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from models import Task, TaskSegment
from repositories import (
    TaskRepository,
    TaskSegmentRepository,
    RecognitionResultRepository, get_session,
)
from rmq_utils import rmq
from s3_utils import save_file_to_s3, create_buckets_if_not_exists
from schemas import (
    UploadResponse,
    TaskResponse,
    TaskSegmentResponse,
    SegmentDetailResponse,
    RecognitionResultResponse,
)
from settings import settings
import events

logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format='{"time": "%(asctime)-s", "message": "%(message)s"}',
    datefmt="%d-%m-%Y %H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await rmq.create_queue(settings.recognition_queue)
    await rmq.create_queue(settings.video_processing_queue)
    await create_buckets_if_not_exists()
    yield


app = FastAPI(
    title="Recognition API",
    lifespan=lifespan
)


@app.post("/analysis", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    task_id = str(uuid.uuid4())
    file_type = "video" if "video" in file.content_type else "photo"

    input_file_path = f"input-files/{task_id}/{file.filename}"
    file_content = await file.read()
    await save_file_to_s3(file_content, input_file_path)

    task_repo = TaskRepository(session)
    new_task = Task(
        id=task_id,
        user_id=None,  # Update if user authentication is implemented
        file_type=file_type,
        status="queued",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        input_file_url=input_file_path,
        error_message=None,
    )
    await task_repo.create_task(new_task)

    if file_type == "video":
        queue_name = settings.video_processing_queue
        message = {
            "task_id": task_id,
            "file_type": file_type,
            "input_file_url": input_file_path,
        }
        await rmq.post_message(message, queue_name)
    else:
        queue_name = settings.recognition_queue
        segment_id = str(uuid.uuid4())

        task_segment_repo = TaskSegmentRepository(session)
        segment = TaskSegment(
            id=segment_id,
            task_id=task_id,
            start_time=None,
            end_time=None,
            status="queued",
            segment_file_url=input_file_path,  # Используем существующий путь
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            error_message=None,
        )
        await task_segment_repo.create_segment(segment)

        message = {
            "segment_id": segment_id,
            "task_id": task_id,
            "image_file_url": input_file_path,
        }
        await rmq.post_message(message, queue_name)

    return UploadResponse(task_id=task_id)


@app.get("/analysis/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, session: AsyncSession = Depends(get_session)):
    task_repo = TaskRepository(session)
    task = await task_repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.model_validate(task)


@app.get("/analysis/{task_id}/segments", response_model=List[TaskSegmentResponse])
async def get_task_segments(task_id: str, session: AsyncSession = Depends(get_session)):
    task_segment_repo = TaskSegmentRepository(session)
    segments = await task_segment_repo.get_segments_by_task_id(task_id)
    if not segments:
        raise HTTPException(status_code=404, detail="No segments found for this task")
    return [TaskSegmentResponse.model_validate(segment) for segment in segments]


@app.get("/analysis/{task_id}/segments/{segment_id}", response_model=SegmentDetailResponse)
async def get_segment_details(
    task_id: str, segment_id: str, session: AsyncSession = Depends(get_session)
):
    task_segment_repo = TaskSegmentRepository(session)
    recognition_result_repo = RecognitionResultRepository(session)

    segment = await task_segment_repo.get_segment(task_id, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    recognition_results = await recognition_result_repo.get_results_by_segment_id(
        segment_id
    )
    recognition_results_pydantic = [
        RecognitionResultResponse.model_validate(res) for res in recognition_results
    ]

    segment_response = SegmentDetailResponse(
        id=segment.id,
        start_time=segment.start_time,
        end_time=segment.end_time,
        status=segment.status,
        created_at=segment.created_at,
        updated_at=segment.updated_at,
        error_message=segment.error_message,
        recognition_results=recognition_results_pydantic,
    )
    return segment_response


@app.delete("/analysis/{task_id}", response_model=TaskResponse)
async def delete_task(task_id: str, session: AsyncSession = Depends(get_session)):
    task_repo = TaskRepository(session)
    task = await task_repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    await task_repo.delete_task(task)

    return TaskResponse.model_validate(task, from_attributes=True)


if __name__ == '__main__':
    uvicorn.run("main:app", host="localhost", port=8888)