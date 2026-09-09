"""S3-compatible storage using the upstream MinIO SDK; no vendor business API."""

import hashlib
import io

from app.adapters.storage_local import validate_key
from app.domain.errors import CapabilityUnavailable, DomainError, NotFound, ProviderError


class S3CompatibleFileStore:
    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        secure: bool = True,
        max_bytes: int = 25 * 1024 * 1024,
        *,
        client=None,
    ):
        if not bucket or "/" in bucket:
            raise DomainError("Invalid S3 bucket name")
        self.bucket, self.max_bytes = bucket, max_bytes
        self._client = client
        self._configuration = (endpoint, access_key, secret_key, secure)

    @property
    def client(self):
        if self._client is not None:
            return self._client
        endpoint, access_key, secret_key, secure = self._configuration
        if not access_key or not secret_key:
            raise CapabilityUnavailable("S3 credentials are missing")
        try:
            from minio import Minio
            from urllib3 import PoolManager, Retry, Timeout
        except ImportError as exc:
            raise CapabilityUnavailable("Install the storage extra for S3") from exc
        http = PoolManager(
            timeout=Timeout(connect=2, read=5), retries=Retry(total=1, backoff_factor=0.2)
        )
        self._client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            http_client=http,
        )
        return self._client

    def put(self, key: str, content: bytes) -> str:
        validate_key(key)
        if len(content) > self.max_bytes:
            raise DomainError("File exceeds configured size limit")
        digest = hashlib.sha256(content).hexdigest()
        try:
            self.client.put_object(
                bucket_name=self.bucket,
                object_name=key,
                data=io.BytesIO(content),
                length=len(content),
                content_type="application/octet-stream",
                metadata={"sha256": digest},
            )
        except DomainError:
            raise
        except Exception as exc:
            raise ProviderError("S3 upload failed; no application metadata was committed") from exc
        return digest

    def read(self, key: str) -> bytes:
        validate_key(key)
        response = None
        try:
            info = self.client.stat_object(bucket_name=self.bucket, object_name=key)
            if info.size is None or info.size > self.max_bytes:
                raise DomainError("Stored object exceeds configured size limit")
            response = self.client.get_object(bucket_name=self.bucket, object_name=key)
            content = response.read(self.max_bytes + 1)
            if len(content) > self.max_bytes:
                raise DomainError("Stored object exceeds configured size limit")
            metadata = {str(k).lower(): v for k, v in (info.metadata or {}).items()}
            expected = metadata.get("x-amz-meta-sha256") or metadata.get("sha256")
            if not expected or expected != hashlib.sha256(content).hexdigest():
                raise ProviderError("S3 object content hash is absent or does not match")
            return content
        except (DomainError, ProviderError):
            raise
        except Exception as exc:
            if getattr(exc, "code", None) in {"NoSuchKey", "NoSuchObject"}:
                raise NotFound("Stored S3 object not found") from exc
            raise ProviderError("S3 read failed") from exc
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    def delete(self, key: str) -> None:
        validate_key(key)
        try:
            self.client.remove_object(bucket_name=self.bucket, object_name=key)
        except DomainError:
            raise
        except Exception as exc:
            raise ProviderError("S3 delete failed") from exc

    def health(self) -> tuple[bool, str]:
        try:
            exists = self.client.bucket_exists(bucket_name=self.bucket)
            return exists, "Bucket reachable" if exists else "Configured bucket does not exist"
        except Exception:
            return False, "Bucket reachability check failed (bounded SDK timeout)"
