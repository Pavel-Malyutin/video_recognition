import asyncio
import json
import logging

import aio_pika
from aio_pika import Message
from aio_pika.abc import AbstractRobustConnection
from aio_pika.pool import Pool

from settings import settings


class RMQ:
    def __init__(self):
        self.connection_pool: Pool = Pool(self.get_connection, max_size=5)
        self.channel_pool: Pool = Pool(self.get_channel, max_size=5)

    @staticmethod
    async def get_connection() -> AbstractRobustConnection:
        return await aio_pika.connect_robust(settings.rmq_url)

    async def get_channel(self) -> aio_pika.Channel:
        async with self.connection_pool.acquire() as connection:
            return await connection.channel()

    async def create_queue(self, name: str, max_priority: int = 10):
        connection = await self.get_connection()
        channel = await connection.channel()
        await channel.declare_queue(
            name,
            durable=True,
            arguments={"x-max-priority": max_priority}
        )
        await connection.close()
        logging.info(f"queue {name} created")

    async def post_message(self, msg: dict, query:str, priority: int = 0):
        body = json.dumps(msg).encode()
        async with self.channel_pool.acquire() as channel:
            await channel.default_exchange.publish(
                message=Message(body=body, priority=priority),
                routing_key=query,
            )

    async def consume(self, queue_name: str, func):
        connection = await self.get_connection()
        async with connection:
            channel = await connection.channel()
            queue = await channel.declare_queue(queue_name, durable=True, arguments={"x-max-priority": 10})
            await queue.consume(func)
            logging.info(f" [*] Waiting for messages in {queue_name}. To exit press CTRL+C")
            await asyncio.Future()


rmq = RMQ()