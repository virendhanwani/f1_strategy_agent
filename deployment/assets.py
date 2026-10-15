"""Restore a versioned private R2 bundle once per server process."""
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from threading import Lock
import zipfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
_lock = Lock()
_ready = False


def data_root():
    return PROJECT_ROOT / (".deployment_data" if os.getenv("R2_BUNDLE_KEY") else "data")


def r2_client():
    import boto3
    from botocore.config import Config
    return boto3.client(
        "s3", endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto", config=Config(connect_timeout=15, read_timeout=90,
                                         retries={"max_attempts": 2}),
    )


def extract_bundle(archive, destination):
    """Extract only expected data paths with a bounded uncompressed size."""
    with zipfile.ZipFile(archive) as bundle:
        if sum(item.file_size for item in bundle.infolist()) > 512 * 1024 * 1024:
            raise ValueError("Asset bundle exceeds the 512 MB extraction limit.")
        for item in bundle.infolist():
            path = Path(item.filename)
            if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] not in {"chroma", "processed"}:
                raise ValueError("Unexpected path in asset bundle.")
        bundle.extractall(destination)
    if not (destination / "chroma" / "chroma.sqlite3").is_file():
        raise ValueError("Asset bundle is missing the regulation index.")
    if not (destination / "processed").is_dir():
        raise ValueError("Asset bundle is missing processed race data.")


def ensure_assets():
    global _ready
    if not os.getenv("R2_BUNDLE_KEY"):
        return
    with _lock:
        if _ready:
            return
        expected = os.environ["R2_BUNDLE_SHA256"].lower()
        if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
            raise ValueError("Invalid bundle checksum configuration.")
        root = data_root()
        marker = root / ".sha256"
        if marker.is_file() and marker.read_text() == expected:
            _ready = True
            return
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temporary:
            temporary = Path(temporary)
            archive = temporary / "assets.zip"
            r2_client().download_file(os.environ["R2_BUCKET"], os.environ["R2_BUNDLE_KEY"], str(archive))
            with archive.open("rb") as stream:
                checksum = hashlib.file_digest(stream, "sha256").hexdigest()
            if checksum != expected:
                raise ValueError("Downloaded assets failed checksum verification.")
            staging = temporary / "data"
            extract_bundle(archive, staging)
            (staging / ".sha256").write_text(expected)
            if root.exists():
                shutil.rmtree(root)
            staging.replace(root)
        _ready = True
