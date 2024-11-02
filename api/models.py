import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Float,
    ForeignKey,
    Text, Integer,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import relationship


class Base(DeclarativeBase):
    pass


class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    file_type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now())
    input_file_url = Column(String, nullable=False)
    error_message = Column(Text, nullable=True)

    segments = relationship(
        "TaskSegment",
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class TaskSegment(Base):
    __tablename__ = "task_segments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    start_time = Column(Float, nullable=True)
    end_time = Column(Float, nullable=True)
    status = Column(String, nullable=False)
    segment_file_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now())
    error_message = Column(Text, nullable=True)

    task = relationship("Task", back_populates="segments")
    recognition_results = relationship(
        "RecognitionResult",
        back_populates="segment",
        cascade="all, delete-orphan",
        passive_deletes=True
    )


class RecognitionResult(Base):
    __tablename__ = "recognition_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    segment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("task_segments.id", ondelete="CASCADE"),
        nullable=False,
    )
    object_detected = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    result_file_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now())

    segment = relationship("TaskSegment", back_populates="recognition_results")


class Label(Base):
    __tablename__ = 'labels_map'

    id = Column(Integer, primary_key=True)
    label = Column(String, nullable=False)
