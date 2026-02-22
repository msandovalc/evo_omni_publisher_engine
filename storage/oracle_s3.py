# storage/oracle_s3.py
import oci
import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("Storage")

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
    """Uploads a video to Oracle Cloud."""
    logger.info(f"⬆️ Uploading '{local_file_path}'...")
    try:
        client = get_oci_client()
        namespace = os.getenv("ORACLE_NAMESPACE")
        bucket = os.getenv("ORACLE_BUCKET_NAME")

        with open(local_file_path, "rb") as f:
            client.put_object(namespace, bucket, object_name, f, content_type="video/mp4")

        logger.info(f"✅ Upload successful: {object_name}")
        return True
    except Exception as e:
        logger.error(f"❌ Upload error: {e}")
        return False

def download_video(object_name: str, local_destination: str) -> bool:
    """Downloads a video via OCI Native SDK."""
    logger.info(f"⬇️ Downloading '{object_name}'...")
    try:
        client = get_oci_client()
        namespace = os.getenv("ORACLE_NAMESPACE")
        bucket = os.getenv("ORACLE_BUCKET_NAME")

        get_obj = client.get_object(namespace, bucket, object_name)

        # 1MB buffer for performance
        with open(local_destination, 'wb') as f:
            for chunk in get_obj.data.raw.stream(1024 * 1024, decode_content=False):
                f.write(chunk)

        logger.info(f"✅ Download complete: {local_destination}")
        return True
    except Exception as e:
        logger.error(f"❌ Download error: {e}")
        return False