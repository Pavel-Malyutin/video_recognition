from pydantic import Field, ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = Field(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/recognition",
        validation_alias="DATABASE_URL"
    )
    s3_endpoint: str = Field(
        "http://localhost:9000",
        validation_alias="S3_ENDPOINT"
    )
    s3_access_key: str = Field(
        "minioadmin",
        validation_alias="S3_ACCESS_KEY"
    )
    s3_secret_key: str = Field(
        "minioadmin",
        validation_alias="S3_SECRET_KEY"
    )
    s3_bucket: str = Field(
        default="input-files",
        validation_alias="S3_BUCKET"
    )
    rmq_url: str = Field(
        "amqp://guest:guest@localhost:5672/",
        validation_alias="RABBITMQ_URL"
    )
    video_processing_queue: str = Field(
        default='video_processing_queue',
        validation_alias='VIDEO_PROCESSING_QUEUE'
    )
    photo_processing_queue: str = Field(
        default='photo_processing_queue',
        validation_alias='PHOTO_PROCESSING_QUEUE'
    )
    recognition_queue: str = Field(
        default='recognition_queue',
        validation_alias='RECOGNITION_QUEUE'
    )

    model_config = ConfigDict(extra="ignore")


settings = Settings()
