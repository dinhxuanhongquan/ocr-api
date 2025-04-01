from sqlalchemy.orm import Session
from app.models.video import Video, SRT, VIDEO_TTS
from app.core.config import get_settings
import boto3
import os

s3 = boto3.client(
    's3', 
    aws_access_key_id=get_settings().AWS_ACCESS_KEY_ID, 
    aws_secret_access_key=get_settings().AWS_SECRET_ACCESS_KEY
    )

def upload_file_to_s3(file_path, bucket_name):
    # file name
    filename = os.path.basename(file_path)

    basename, ext = os.path.splitext(filename)
    new_filename = filename

    # Kiem tra file co ton tai tren S3 hay chua
    count = 0
    while True:
        try:
            s3.head_object(Bucket=bucket_name, Key=new_filename)
            count += 1
            new_filename = f"{count}_{filename}"
        except s3.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '404':
                break
            else:
                return None
    # Upload file len S3
    s3.upload_file(file_path, bucket_name, new_filename)
    url_file = f"https://{bucket_name}.s3-{get_settings().AWS_REGION}.amazonaws.com/{new_filename}"
    return url_file

def delete_file_from_s3(file_url, bucket_name):
    filename = file_url.split("/")[-1]
    s3.delete_object(Bucket=bucket_name, Key=filename)
    return True


def download_file_from_s3(file_url, bucket_name, download_path):
    filename = file_url.split("/")[-1]
    try:
        s3.download_file(bucket_name, filename, download_path)
        return True
    except Exception:
        return False
    

def replace_file_on_s3(file_url, bucket_name, file_path):    # delete old file and upload new
    if not delete_file_from_s3( file_url=file_url, bucket_name=bucket_name):
        raise Exception("Can't delete old file")
    return upload_file_to_s3(file_path=file_path, bucket_name=bucket_name)


