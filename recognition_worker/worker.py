import asyncio
import json
import logging
import sys
import uuid
from datetime import datetime

import aio_pika
import cv2
import numpy as np
import onnxruntime as ort
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from models import RecognitionResult
from rmq_utils import rmq
from repositories import TaskSegmentRepository, RecognitionResultRepository, LabelRepository
from s3_utils import download_file_from_s3_to_memory, save_bytes_to_s3
from settings import settings


logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format='{"time": "%(asctime)-s", "message": "%(message)s"}',
    datefmt="%d-%m-%Y %H:%M:%S",
)


class RecognitionWorker:
    def __init__(self):
        self.engine = None
        self.AsyncSessionLocal = None
        self.labels = None
        self.ort_session = None

    async def initialize(self):
        await self.initialize_database()
        await self.load_labels()
        await self.load_model()

    async def initialize_database(self):
        self.engine = create_async_engine(settings.database_url, echo=False)
        self.AsyncSessionLocal = sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def load_labels(self):
        with open("labels_map.txt", "r") as f:
            self.labels = json.load(f)

    async def load_model(self):
        gpu_available = await self.check_gpu_availability()
        providers = ['CUDAExecutionProvider'] if gpu_available else ['CPUExecutionProvider']

        model_path = 'model/efficientnet-lite4-11.onnx'
        self.ort_session = ort.InferenceSession(model_path, providers=providers)

    async def check_gpu_availability(self):
        providers = ort.get_available_providers()
        if 'CUDAExecutionProvider' in providers:
            return True
        return False

    async def process_message(self, message: aio_pika.IncomingMessage):
        async with message.process():
            task_data = json.loads(message.body.decode())
            await self.process_task(task_data)

    async def process_task(self, task_data):
        segment_id = task_data['segment_id']
        task_id = task_data['task_id']
        image_file_url = task_data.get('image_file_url')

        if not image_file_url:
            logging.error(f"No image_file_url provided for segment {segment_id}")
            return

        async with self.AsyncSessionLocal() as session:
            segment_repo = TaskSegmentRepository(session)
            result_repo = RecognitionResultRepository(session)

            await segment_repo.update_segment_status(segment_id, 'processing')

            try:
                image = await self.download_image(image_file_url)
                object_detected, confidence = await self.perform_inference(image)
                result_file_url = await self.save_result_image(image, object_detected, confidence, segment_id, task_id)
                await self.save_result(result_repo, segment_id, object_detected, confidence, result_file_url)
                await segment_repo.update_segment_status(segment_id, 'done')
            except Exception as e:
                await segment_repo.update_segment_status(segment_id, 'error', error_message=str(e))
                logging.error(f"Error processing segment {segment_id}: {e}")

    async def download_image(self, image_file_url):
        image_data = await download_file_from_s3_to_memory(image_file_url)
        image = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise Exception("Failed to read image")
        return image

    async def perform_inference(self, image):
        input_size = 224
        image_resized = cv2.resize(image, (input_size, input_size))
        image_data = np.expand_dims(image_resized.astype(np.float32), axis=0)

        mean = np.array([127.0, 127.0, 127.0])
        std = np.array([128.0, 128.0, 128.0])
        image_data = (image_data - mean) / std

        ort_inputs = {self.ort_session.get_inputs()[0].name: image_data.astype(np.float32)}
        ort_outs = self.ort_session.run(None, ort_inputs)
        predictions = ort_outs[0]

        top_class = np.argmax(predictions)
        confidence = predictions[0][top_class]
        object_detected = self.labels[str(top_class)] if confidence > 0.8 else 'unknown'
        return object_detected, confidence

    @staticmethod
    async def save_result_image(image, object_detected, confidence, segment_id, task_id):
        cv2.putText(image, f'{object_detected}: {confidence:.2f}', (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        _, buffer = cv2.imencode('.jpg', image)
        image_bytes = buffer.tobytes()

        result_file_url = f'recognition-results/{task_id}/{segment_id}_result.jpg'
        await save_bytes_to_s3(image_bytes, result_file_url)
        return result_file_url

    @staticmethod
    async def save_result(result_repo, segment_id, object_detected, confidence, result_file_url):
        result = RecognitionResult(
            id=str(uuid.uuid4()),
            segment_id=segment_id,
            object_detected=object_detected,
            confidence=float(confidence),
            result_file_url=result_file_url,
            created_at=datetime.now()
        )
        await result_repo.create_result(result)


async def main():
    worker = RecognitionWorker()
    await worker.initialize()
    await rmq.consume(settings.recognition_queue, worker.process_message)


if __name__ == "__main__":
    asyncio.run(main())
