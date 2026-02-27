# storage/oracle_s3.py
import oci
import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("Storage")

# Version Marker for Debugging
VERSION = "3.0.1-FINAL"

def get_oci_client():
    """Initializes the OCI Object Storage client using RSA keys."""
    config = {
        "user": os.getenv("ORACLE_USER_OCID"),
        "key_file": os.getenv("ORACLE_KEY_FILE"),
        "fingerprint": os.getenv("ORACLE_FINGERPRINT"),
        "tenancy": os.getenv("ORACLE_TENANCY_OCID"),
        "region": os.getenv("ORACLE_REGION")
    }
    return oci.object_storage.ObjectStorageClient(config)

def upload_video(local_file_path: str, object_name: str) -> bool:
    """Uploads a video to Oracle Cloud with extreme logging [V3]."""
    logger.info(f"🚀 [OCI-V3] ATTEMPTING UPLOAD: {object_name} (from {local_file_path})")
    try:
        client = get_oci_client()
        namespace = os.getenv("ORACLE_NAMESPACE")
        bucket = os.getenv("ORACLE_BUCKET_NAME")

        logger.info(f"📡 [OCI-V3] Target Bucket: {bucket} | Namespace: {namespace}")

        with open(local_file_path, "rb") as f:
            client.put_object(
                namespace_name=namespace,
                bucket_name=bucket,
                object_name=object_name,
                put_object_body=f,
                content_type="video/mp4"
            )

        logger.info(f"✅ [OCI-V3] UPLOAD SUCCESSFUL: {object_name}")
        return True
    except Exception as e:
        logger.error(f"❌ [OCI-V3] UPLOAD CRITICAL ERROR: {str(e)}")
        return False

def download_video(object_name: str, local_destination: str) -> bool:
    """Downloads a video via OCI Native SDK [V3]."""
    logger.info(f"⬇️ [OCI-V3] DOWNLOADING: {object_name}")
    try:
        client = get_oci_client()
        namespace = os.getenv("ORACLE_NAMESPACE")
        bucket = os.getenv("ORACLE_BUCKET_NAME")

        get_obj = client.get_object(namespace, bucket, object_name)

        with open(local_destination, 'wb') as f:
            for chunk in get_obj.data.raw.stream(1024 * 1024, decode_content=False):
                f.write(chunk)

        logger.info(f"✅ [OCI-V3] DOWNLOAD COMPLETE: {object_name}")
        return True
    except Exception as e:
        logger.error(f"❌ [OCI-V3] DOWNLOAD ERROR: {str(e)}")
        return False