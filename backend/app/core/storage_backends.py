"""
Storage abstraction: disk and S3 backends for CSV uploads.
"""
import hashlib
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile


@dataclass
class StoredObject:
    storage: str  # "disk" | "s3"
    file_path: str | None  # for disk
    bucket: str | None  # for s3
    key: str | None  # for s3
    size_bytes: int
    sha256: str


UPLOAD_ROOT = Path(__file__).resolve().parent.parent.parent / "storage" / "uploads"


class DiskStorage:
    """Store uploads to local disk."""

    async def save_upload(
        self,
        file: UploadFile,
        org_id: UUID,
        dataset_id: UUID,
        run_id: UUID,
        max_size: int,
    ) -> StoredObject:
        dir_path = UPLOAD_ROOT / str(dataset_id)
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / f"{run_id}.csv"

        sha256_hash = hashlib.sha256()
        total_size = 0

        with open(file_path, "wb") as f:
            while chunk := await file.read(1024 * 64):
                total_size += len(chunk)
                if total_size > max_size:
                    if file_path.exists():
                        file_path.unlink()
                    raise ValueError(
                        f"File exceeds maximum size of {max_size} bytes ({total_size} bytes read)"
                    )
                sha256_hash.update(chunk)
                f.write(chunk)

        sha256_hex = sha256_hash.hexdigest()
        relative_path = f"storage/uploads/{dataset_id}/{run_id}.csv"
        return StoredObject(
            storage="disk",
            file_path=relative_path,
            bucket=None,
            key=None,
            size_bytes=total_size,
            sha256=sha256_hex,
        )


class S3Storage:
    """Store uploads to S3-compatible storage (MinIO, AWS S3)."""

    def __init__(self, endpoint_url: str, access_key: str, secret_key: str, bucket: str, region: str = "us-east-1", use_ssl: bool = False):
        import boto3
        from botocore.config import Config

        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            use_ssl=use_ssl,
            config=Config(signature_version="s3v4"),
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            self.client.create_bucket(Bucket=self.bucket)

    async def save_upload(
        self,
        file: UploadFile,
        org_id: UUID,
        dataset_id: UUID,
        run_id: UUID,
        max_size: int,
    ) -> StoredObject:
        import asyncio

        key = f"uploads/{org_id}/{dataset_id}/{run_id}.csv"
        sha256_hash = hashlib.sha256()
        total_size = 0
        chunks = []

        while chunk := await file.read(1024 * 64):
            total_size += len(chunk)
            if total_size > max_size:
                raise ValueError(
                    f"File exceeds maximum size of {max_size} bytes ({total_size} bytes read)"
                )
            sha256_hash.update(chunk)
            chunks.append(chunk)

        body = b"".join(chunks)
        sha256_hex = sha256_hash.hexdigest()

        def _upload():
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=body,
                ContentType="text/csv",
            )

        await asyncio.to_thread(_upload)

        return StoredObject(
            storage="s3",
            file_path=None,
            bucket=self.bucket,
            key=key,
            size_bytes=total_size,
            sha256=sha256_hex,
        )

    def presign_download(self, bucket: str, key: str, expires: int) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires,
        )
