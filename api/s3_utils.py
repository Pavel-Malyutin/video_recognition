import aioboto3
from settings import settings

s3_session = aioboto3.Session()


async def save_file_to_s3(file_content: bytes, key: str):
    async with s3_session.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    ) as s3_client:
        await s3_client.put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=file_content,
        )


async def delete_file_from_s3(bucket_key):
    async with s3_session.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
    ) as s3_client:
        await s3_client.delete_object(
            Bucket=settings.s3_bucket,
            Key=bucket_key
        )


async def create_buckets_if_not_exists():

    bucket_names = [
        'input-files',
        'video-segments',
        'recognition-results',
    ]

    try:
        async with s3_session.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
        ) as s3_client:
            response = await s3_client.list_buckets()
            existing_buckets = [bucket['Name'] for bucket in response.get('Buckets', [])]

            for bucket_name in bucket_names:
                if bucket_name not in existing_buckets:
                    await s3_client.create_bucket(Bucket=bucket_name)
                    print(f"Bucket '{bucket_name}' has been created.")
                else:
                    print(f"Bucket '{bucket_name}' already exists.")
    except Exception as e:
        print(f"An error occurred while creating buckets: {e}")
