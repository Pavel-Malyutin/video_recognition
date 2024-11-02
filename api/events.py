import asyncio

from sqlalchemy import event
from sqlalchemy.testing.plugin.plugin_base import logging

from models import Task, TaskSegment, RecognitionResult
from s3_utils import delete_file_from_s3, delete_folder_from_s3


def async_run(coro):
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.create_task(coro)
    else:
        loop.run_until_complete(coro)


@event.listens_for(Task, "after_delete")
def after_delete_task(mapper, connection, target):
    if target.input_file_url:
        async_run(delete_file_from_s3(target.input_file_url))
        async_run(delete_folder_from_s3(f"recognition-results/{target.id}"))
        async_run(delete_folder_from_s3(f"scene-images/{target.id}"))


@event.listens_for(TaskSegment, "after_delete")
def after_delete_task_segment(mapper, connection, target):
    if target.segment_file_url:
        async_run(delete_file_from_s3(target.segment_file_url))


@event.listens_for(RecognitionResult, "after_delete")
def after_delete_recognition_result(mapper, connection, target):
    if target.result_file_url:
        async_run(delete_file_from_s3(target.result_file_url))
