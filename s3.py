import boto3

# Initialize AWS session with proper region
session = boto3.Session(
    aws_access_key_id='AKIAW5WU5HNSQ4BPJH6H',
    aws_secret_access_key='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',
    region_name='ap-southeast-2'  # Sydney region
)

# Create S3 client
s3_client = session.client('s3')

# Bucket configuration
bucket_name = "video-translation-storage-bucket"