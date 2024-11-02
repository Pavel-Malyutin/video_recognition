import asyncio
import json
import logging
import os
import subprocess
import sys
import tempfile
import traceback
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


logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format='{"time": "%(asctime)-s", "message": "%(message)s"}',
    datefmt="%d-%m-%Y %H:%M:%S",
)


class FFmpegWorker:
    def __init__(self):
        self.engine = None
        self.AsyncSessionLocal = None
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

    async def process_scenes(
            self,
            scenes: list,
            task_id: str,
            input_file_path: str,
            image_files_paths: dict,
            recognition_tasks: list,
            segment_repo
    ):
        for idx, (start_time, end_time) in enumerate(scenes):
            segment_id = str(uuid.uuid4())
            image_file_path = os.path.join(
                tempfile.gettempdir(), f"{segment_id}.jpg"
            )
            image_s3_key = f"scene-images/{task_id}/scene_{segment_id}.jpg"

            middle_time = (start_time + end_time) / 2

            success = self.extract_frame_from_video(
                input_file_path, image_file_path, middle_time
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
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                        error_message="Failed to extract frame",
                    )
                )
                continue

            image_files_paths.update({image_s3_key: image_file_path})

            segment = TaskSegment(
                id=segment_id,
                task_id=task_id,
                start_time=start_time,
                end_time=end_time,
                status="queued",
                segment_file_url=image_s3_key,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                error_message=None,
            )
            await segment_repo.create_segment(segment)

            recognition_tasks.append(
                {
                    "segment_id": segment_id,
                    "task_id": task_id,
                    "image_file_url": image_s3_key,
                }
            )

    async def finish_task_processing(
            self,
            image_files_paths: dict,
            recognition_tasks: list,
            task_id: str,
            task_repo
    ):

        async with asyncio.TaskGroup() as tg:
            for image_s3_key, image_file_path in image_files_paths.items():
                tg.create_task(
                    upload_file_to_s3(image_file_path, image_s3_key)
                )

        async with asyncio.TaskGroup() as tg:
            for recognition_task in recognition_tasks:
                tg.create_task(
                    rmq.post_message(recognition_task, settings.recognition_queue)
                )

        await task_repo.update_task_status(task_id, "segmented")

    async def process_task(self, task_data):
        task_id = task_data["task_id"]
        input_file_url = task_data["input_file_url"]
        image_files_paths = {}
        recognition_tasks = []
        input_file_path = None

        async with self.AsyncSessionLocal() as session:
            task_repo = TaskRepository(session)
            segment_repo = TaskSegmentRepository(session)

            try:
                await task_repo.update_task_status(task_id, "processing")
                input_file_path = os.path.join(tempfile.gettempdir(), f"{task_id}.mp4")
                await download_file_from_s3(input_file_url, input_file_path)
                scenes = await self.detect_scenes(input_file_path)
                await self.process_scenes(
                    scenes=scenes,
                    recognition_tasks=recognition_tasks,
                    input_file_path=input_file_path,
                    image_files_paths=image_files_paths,
                    segment_repo=segment_repo,
                    task_id=task_id
                )
                await self.finish_task_processing(
                    task_id=task_id,
                    image_files_paths=image_files_paths,
                    recognition_tasks=recognition_tasks,
                    task_repo=task_repo
                )
            except Exception as e:
                logging.error(f"process_task exception {traceback.format_exc()}")
                await task_repo.update_task_status(task_id, "segmentation error")
            finally:
                if input_file_path:
                    image_files_paths.update({"input_file_path": input_file_path})
                for image_file_path in image_files_paths.values():
                    try:
                        os.remove(image_file_path)
                    except OSError:
                        pass

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
            logging.info(f"Detected {len(scenes)} scenes.")
        return scenes

    def extract_frame_from_video(
            self,
            input_file_path: str,
            output_image_path: str,
            timestamp: float
    ):
        try:
            stream = (
                ffmpeg
                .input(input_file_path, ss=timestamp)
                .output(output_image_path, vframes=1)
            )

            if self.gpu_available:
                stream = stream.global_args('-hwaccel', 'cuda')

            stream.run(
                overwrite_output=True,
                capture_stdout=True,
                capture_stderr=True
            )
            return True
        except ffmpeg.Error as e:
            logging.error(f"Ошибка FFmpeg: {e}")
            return False

async def main():
    worker = FFmpegWorker()
    await worker.initialize()
    await rmq.consume(settings.video_processing_queue, worker.process_message)


if __name__ == "__main__":
    asyncio.run(main())
