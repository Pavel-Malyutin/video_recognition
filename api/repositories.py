from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from models import Task, TaskSegment, RecognitionResult
from settings import settings

engine = create_async_engine(settings.database_url, echo=True)
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


class TaskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_task(self, task: Task) -> Task:
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def update_task_status(self, task_id: str, status: str):
        task = await self.session.get(Task, task_id)
        if task:
            task.status = status
            task.updated_at = datetime.now()
            await self.session.commit()

    async def get_task(self, task_id: str) -> Optional[Task]:
        result = await self.session.execute(select(Task).where(Task.id == task_id))
        return result.scalar_one_or_none()

    async def delete_task(self, task: Task):
        await self.session.delete(task)
        await self.session.commit()


class TaskSegmentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_segment(self, segment: TaskSegment):
        self.session.add(segment)
        await self.session.commit()
        await self.session.refresh(segment)
        return segment

    async def update_segment_status(
        self, segment_id: str, status: str, error_message: str = None
    ):
        segment = await self.session.get(TaskSegment, segment_id)
        if segment:
            segment.status = status
            segment.error_message = error_message
            segment.updated_at = datetime.utcnow()
            await self.session.commit()

    async def get_segments_by_task_id(self, task_id: str) -> List[TaskSegment]:
        result = await self.session.execute(
            select(TaskSegment).where(TaskSegment.task_id == task_id)
        )
        return result.scalars().all()

    async def get_segment(self, task_id: str, segment_id: str) -> Optional[TaskSegment]:
        result = await self.session.execute(
            select(TaskSegment).where(
                TaskSegment.id == segment_id, TaskSegment.task_id == task_id
            )
        )
        return result.scalar_one_or_none()


class RecognitionResultRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_results_by_segment_id(
        self, segment_id: str
    ) -> List[RecognitionResult]:
        result = await self.session.execute(
            select(RecognitionResult).where(RecognitionResult.segment_id == segment_id)
        )
        return result.scalars().all()
