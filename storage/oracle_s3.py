# storage/oracle_s3.py
import oci
import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("Storage")


def get_oci_client():
    """Initializes the OCI Object Storage client using RSA keys."""
    try:
        config = {
            "user": os.getenv("ORACLE_USER_OCID"),
            "key_file": os.getenv("ORACLE_KEY_FILE"),
            "fingerprint": os.getenv("ORACLE_FINGERPRINT"),
            "tenancy": os.getenv("ORACLE_TENANCY_OCID"),
            "region": os.getenv("ORACLE_REGION")
        }
        # Extra check: Ensure the key file exists
        if not os.path.exists(config["key_file"]):
            logger.error(f"❌ OCI Config Error: Key file not found at {config['key_file']}")

        return oci.object_storage.ObjectStorageClient(config)
    except Exception as e:
        logger.error(f"❌ Failed to initialize OCI Client: {str(e)}")
        raise


def upload_video(local_file_path: str, object_name: str) -> bool:
    """Uploads a video to Oracle Cloud with detailed logging."""
    logger.info(f"⬆️ [OCI] Starting upload: '{local_file_path}' as '{object_name}'")
    try:
        client = get_oci_client()
        namespace = os.getenv("ORACLE_NAMESPACE")
        bucket = os.getenv("ORACLE_BUCKET_NAME")

        logger.info(f"📡 [OCI] Targeting Namespace: {namespace}, Bucket: {bucket}")

        with open(local_file_path, "rb") as f:
            client.put_object(
                namespace_name=namespace,
                bucket_name=bucket,
                object_name=object_name,
                put_object_body=f,
                content_type="video/mp4"
            )

        logger.info(f"✅ [OCI] Upload successful: {object_name} is now in the cloud.")
        return True
    except Exception as e:
        logger.error(f"❌ [OCI] Upload failed for {object_name}: {str(e)}")
        return False