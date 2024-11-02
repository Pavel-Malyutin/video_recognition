from datetime import datetime
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from models import TaskSegment, RecognitionResult, Label


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

    async def create_result(self, result: RecognitionResult):
        self.session.add(result)
        await self.session.commit()
        await self.session.refresh(result)
        return result


class LabelRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_labels(self):
        result = await self.session.execute(select(Label).order_by(Label.id))
        return [row.label for row in result.scalars().all()]
