# storage/local_temp.py
import os

def cleanup_temp_file(file_path: str):
    """Deletes the local video file after it has been published to save VPS disk space."""
    if os.path.exists(file_path):
        os.remove(file_path)
        print(f"[Cleanup] Deleted temporary file: {file_path}")