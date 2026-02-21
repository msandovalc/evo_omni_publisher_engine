# storage/oracle_s3.py
import boto3
from botocore.exceptions import ClientError
import os

def get_s3_client():
    """Initializes the boto3 client for Oracle Object Storage."""
    return boto3.client(
        's3',
        region_name=os.getenv("ORACLE_REGION"),
        endpoint_url=os.getenv("ORACLE_ENDPOINT"),
        aws_access_key_id=os.getenv("ORACLE_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("ORACLE_SECRET_KEY")
    )

def download_video(object_name: str, local_destination: str) -> bool:
    """Downloads the video file from Oracle Cloud to the local VPS."""
    print(f"[Storage] Downloading '{object_name}' from Oracle Cloud...")
    try:
        s3 = get_s3_client()
        bucket = os.getenv("ORACLE_BUCKET_NAME")
        s3.download_file(bucket, object_name, local_destination)
        print(f"[Storage] Download complete: {local_destination}")
        return True
    except ClientError as e:
        print(f"[Storage Error] Failed to download video: {e}")
        return False