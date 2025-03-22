import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException
from app.core.config import settings

class S3Service:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.bucket = settings.S3_BUCKET

    async def upload_file(self, file_obj, key: str) -> str:
        try:
            self.s3_client.upload_fileobj(file_obj, self.bucket, key)
            return f"https://{self.bucket}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
        except ClientError as e:
            raise HTTPException(status_code=500, detail=f"Failed to upload file to S3: {str(e)}")

    async def delete_file(self, key: str) -> bool:
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete file from S3: {str(e)}")

    async def get_file_url(self, key: str) -> str:
        try:
            return self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': key},
                ExpiresIn=3600
            )
        except ClientError as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate presigned URL: {str(e)}")

s3_service = S3Service() 