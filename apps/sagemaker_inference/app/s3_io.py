"""S3 입출력 헬퍼.

테스트 편의를 위해 boto3 client 를 lazy 생성하고, endpoint_url 을 env 로 override
가능하게 (LocalStack / Minio 사용 시).
"""
from __future__ import annotations

import io
import json
import os
from typing import Any
from urllib.parse import urlparse

import numpy as np

from app.constants import EnvVar


_S3_CLIENT = None


def _get_client():
    global _S3_CLIENT
    if _S3_CLIENT is None:
        import boto3
        kwargs: dict[str, Any] = {}
        endpoint = os.getenv(EnvVar.AWS_S3_ENDPOINT_URL, "").strip()
        if endpoint:
            kwargs["endpoint_url"] = endpoint
        region = os.getenv(EnvVar.AWS_REGION, "").strip() or os.getenv(EnvVar.AWS_DEFAULT_REGION, "").strip()
        if region:
            kwargs["region_name"] = region
        _S3_CLIENT = boto3.client("s3", **kwargs)
    return _S3_CLIENT


def parse_s3_uri(uri: str) -> tuple[str, str]:
    """s3://bucket/key/path → (bucket, key)."""
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError(f"Not a valid S3 URI: {uri!r}")
    key = parsed.path.lstrip("/")
    if not key:
        raise ValueError(f"S3 URI must include a key: {uri!r}")
    return parsed.netloc, key


def parse_s3_prefix(prefix: str) -> tuple[str, str]:
    """s3://bucket/some/prefix/ → (bucket, 'some/prefix/')."""
    parsed = urlparse(prefix)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError(f"Not a valid S3 prefix: {prefix!r}")
    key_prefix = parsed.path.lstrip("/")
    return parsed.netloc, key_prefix


def download_bytes(s3_uri: str) -> bytes:
    bucket, key = parse_s3_uri(s3_uri)
    client = _get_client()
    response = client.get_object(Bucket=bucket, Key=key)
    body = response["Body"].read()
    return body


def upload_bytes(s3_uri: str, body: bytes, content_type: str | None = None) -> None:
    bucket, key = parse_s3_uri(s3_uri)
    client = _get_client()
    extra: dict[str, Any] = {}
    if content_type:
        extra["ContentType"] = content_type
    client.put_object(Bucket=bucket, Key=key, Body=body, **extra)


def upload_json(s3_uri: str, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    upload_bytes(s3_uri, body, content_type="application/json")


def upload_npy(s3_uri: str, array: np.ndarray) -> None:
    buf = io.BytesIO()
    np.save(buf, array, allow_pickle=False)
    upload_bytes(s3_uri, buf.getvalue(), content_type="application/octet-stream")


def upload_png(s3_uri: str, png_bytes: bytes) -> None:
    upload_bytes(s3_uri, png_bytes, content_type="image/png")
