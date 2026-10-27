"""Aliyun OSS staging for ASR audio uploads.

The transcribe flow uploads audio.m4a to OSS, hands a signed URL to the ASR
engine, and deletes the object when done (including failure paths).
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Protocol

import oss2

SIGNED_URL_TTL_SECONDS = 3600


class ObjectStorage(Protocol):
    """Minimal object storage seam: upload, sign, delete."""

    def upload(self, local_path: Path) -> str:
        """Upload a local file and return its object key."""
        ...

    def signed_url(self, key: str) -> str:
        """Return a signed, time-limited download URL for the object."""
        ...

    def delete(self, key: str) -> None:
        """Delete the object. Missing objects are not an error."""
        ...


class OssStorage:
    """ObjectStorage backed by Aliyun OSS via the oss2 SDK."""

    def __init__(
        self,
        bucket_name: str,
        endpoint: str,
        access_key_id: str,
        access_key_secret: str,
        prefix: str = "video-cut",
    ) -> None:
        auth = oss2.Auth(access_key_id, access_key_secret)
        self._bucket = oss2.Bucket(auth, endpoint, bucket_name)
        self._prefix = prefix

    def upload(self, local_path: Path) -> str:
        key = f"{self._prefix}/{uuid.uuid4().hex}-{local_path.name}"
        self._bucket.put_object_from_file(key, str(local_path))
        return key

    def signed_url(self, key: str) -> str:
        return self._bucket.sign_url("GET", key, SIGNED_URL_TTL_SECONDS, slash_safe=True)

    def delete(self, key: str) -> None:
        self._bucket.delete_object(key)
