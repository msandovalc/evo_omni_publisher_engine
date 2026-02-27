# storage/oracle_s3.py
import oci
import os
import logging
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()
logger = logging.getLogger("Storage")


def get_oci_client():
    """
    Initializes the OCI Object Storage client using RSA keys from .env.
    Includes validation for the key file path.
    """
    try:
        config = {
            "user": os.getenv("ORACLE_USER_OCID"),
            "key_file": os.getenv("ORACLE_KEY_FILE"),
            "fingerprint": os.getenv("ORACLE_FINGERPRINT"),
            "tenancy": os.getenv("ORACLE_TENANCY_OCID"),
            "region": os.getenv("ORACLE_REGION")
        }

        # Security check for the private key
        if not os.path.exists(config["key_file"]):
            logger.error(f"❌ OCI Config Error: Private key not found at {config['key_file']}")

        return oci.object_storage.ObjectStorageClient(config)
    except Exception as e:
        logger.error(f"❌ Failed to initialize OCI Client: {str(e)}")
        raise


def upload_video(local_file_path: str, object_name: str) -> bool:
    """
    Uploads a video to Oracle Cloud Object Storage with detailed logging.
    Used by the /web-direct endpoint.
    """
    logger.info(f"⬆️ [OCI] Initiating upload for '{local_file_path}' as '{object_name}'")
    try:
        client = get_oci_client()
        namespace = os.getenv("ORACLE_NAMESPACE")
        bucket = os.getenv("ORACLE_BUCKET_NAME")

        logger.info(f"📡 [OCI] Target - Namespace: {namespace}, Bucket: {bucket}")

        with open(local_file_path, "rb") as f:
            client.put_object(
                namespace_name=namespace,
                bucket_name=bucket,
                object_name=object_name,
                put_object_body=f,
                content_type="video/mp4"
            )

        logger.info(f"✅ [OCI] Upload successful: {object_name}")
        return True
    except Exception as e:
        logger.error(f"❌ [OCI] Upload failed for {object_name}: {str(e)}")
        return False


def download_video(object_name: str, local_destination: str) -> bool:
    """
    Downloads a video via OCI Native SDK.
    Used by the Scheduler and Publisher Manager.
    """
    logger.info(f"⬇️ [OCI] Downloading '{object_name}' to '{local_destination}'")
    try:
        client = get_oci_client()
        namespace = os.getenv("ORACLE_NAMESPACE")
        bucket = os.getenv("ORACLE_BUCKET_NAME")

        get_obj = client.get_object(namespace, bucket, object_name)

        # Use a 1MB buffer for optimal download performance
        with open(local_destination, 'wb') as f:
            for chunk in get_obj.data.raw.stream(1024 * 1024, decode_content=False):
                f.write(chunk)

        logger.info(f"✅ [OCI] Download successful: {object_name}")
        return True
    except Exception as e:
        logger.error(f"❌ [OCI] Download error for {object_name}: {str(e)}")
        return False