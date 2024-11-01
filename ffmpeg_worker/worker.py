import asyncio
import json
import os
import subprocess
import tempfile
import uuid
from datetime import datetime

import aio_pika
import ffmpeg
from scenedetect import ContentDetector, SceneManager, open_video
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from models import TaskSegment
from repositories import TaskRepository, TaskSegmentRepository
from rmq_utils import rmq
from s3_utils import upload_file_to_s3, download_file_from_s3
from settings import settings


class FFmpegWorker:
    def __init__(self):
        self.engine = None
        self.AsyncSessionLocal = None
        self.s3_client = None
        self.gpu_available = False

    async def initialize(self):
        await self.initialize_database()
        await self.check_gpu_availability()
        os.makedirs('tmp', exist_ok=True)

    async def initialize_database(self):
        self.engine = create_async_engine(settings.database_url, echo=False)
        self.AsyncSessionLocal = sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )

    async def check_gpu_availability(self):
        try:
            result = subprocess.run(
                ["nvidia-smi"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            if result.returncode == 0:
                self.gpu_available = True
        except FileNotFoundError:
            self.gpu_available = False

    async def process_message(self, message: aio_pika.IncomingMessage):
        async with message.process():
            message_raw = message.body.decode()
            task_data = json.loads(message_raw)
            await self.process_task(task_data)

    async def process_task(self, task_data):
        task_id = task_data["task_id"]
        input_file_url = task_data["input_file_url"]

        async with self.AsyncSessionLocal() as session:
            task_repo = TaskRepository(session)
            segment_repo = TaskSegmentRepository(session)

            await task_repo.update_task_status(task_id, "processing")

            input_file_path = os.path.join(tempfile.gettempdir(), f"{task_id}.mp4")
            await download_file_from_s3(input_file_url, input_file_path)

            scenes = await self.detect_scenes(input_file_path)
            segments_files_paths = {}
            recognition_tasks = []

            for idx, (start_time, end_time) in enumerate(scenes):
                segment_id = str(uuid.uuid4())
                segment_file_path = os.path.join(
                    tempfile.gettempdir(), f"{segment_id}.mp4"
                )
                segment_s3_key = f"video-segments/{task_id}/segment_{segment_id}.mp4"

                success = await self.extract_video_segment(
                    input_file_path, segment_file_path, start_time, end_time
                )
                if not success:
                    await segment_repo.create_segment(
                        TaskSegment(
                            id=segment_id,
                            task_id=task_id,
                            start_time=start_time,
                            end_time=end_time,
                            status="error",
                            segment_file_url=None,
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow(),
                            error_message="FFmpeg failed to extract segment",
                        )
                    )
                    continue

                segments_files_paths.update({segment_s3_key: segment_file_path})

                segment = TaskSegment(
                    id=segment_id,
                    task_id=task_id,
                    start_time=start_time,
                    end_time=end_time,
                    status="queued",
                    segment_file_url=segment_s3_key,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    error_message=None,
                )
                await segment_repo.create_segment(segment)

                recognition_tasks.append(
                    {
                        "segment_id": segment_id,
                        "task_id": task_id,
                        "segment_file_url": segment_s3_key,
                    }
                )

            async with asyncio.TaskGroup() as tg:
                for segment_s3_key, segment_file_path in segments_files_paths.items():
                    tg.create_task(
                        upload_file_to_s3(segment_file_path, segment_s3_key)
                    )
            async with asyncio.TaskGroup() as tg:
                for recognition_task in recognition_tasks:
                    tg.create_task(
                        rmq.post_message(recognition_task, settings.recognition_queue)
                    )
            for segment_file_path in segments_files_paths.values():
                os.remove(segment_file_path)

            await task_repo.update_task_status(task_id, "segmented")

            os.remove(input_file_path)

    @staticmethod
    async def detect_scenes(input_file_path: str):
        video = open_video(input_file_path)
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=10.0))
        scene_manager.detect_scenes(video)
        scene_list = scene_manager.get_scene_list()
        scenes = []
        for start, end in scene_list:
            scenes.append((start.get_seconds(), end.get_seconds()))

        if not scenes:
            duration = video.duration.get_seconds()
            scenes.append((0.0, duration))
        else:
            print(f"Detected {len(scenes)} scenes.")
        return scenes

    async def extract_video_segment(
        self,
        input_file_path: str,
        output_file_path: str,
        start_time: float,
        end_time: float
    ):
        try:
            stream = (
                ffmpeg
                .input(input_file_path, ss=start_time, to=end_time)
                .output(output_file_path, vcodec='copy', acodec='copy')
            )
            if self.gpu_available:
                stream = stream.global_args('-hwaccel', 'cuda')
            stream.run(overwrite_output=True)
            return True
        except ffmpeg.Error as e:
            print(f"Ошибка FFmpeg: {e}")
            return False


async def main():
    worker = FFmpegWorker()
    await worker.initialize()
    await rmq.consume(settings.video_processing_queue, worker.process_message)


if __name__ == "__main__":
    asyncio.run(main())
