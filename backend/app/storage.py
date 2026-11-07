"""Image storage backends.

* ``local`` writes files to UPLOAD_DIR. Fine for development or a single
  instance with an attached volume (EBS/EFS), but not shared between
  instances in an Auto Scaling Group.
* ``s3`` stores objects in a private S3 bucket. The app tier authenticates
  with its IAM role (no access keys in code or env), and the browser gets
  either a CloudFront URL (S3_PUBLIC_BASE_URL) or a short-lived pre-signed URL.
"""
import os
import uuid

ALLOWED_IMAGE_TYPES = {
    "jpg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}


def detect_image_type(data):
    """Identify the image by its magic bytes rather than trusting the filename."""
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def new_key(property_id, ext):
    return f"properties/{property_id}/{uuid.uuid4().hex}.{ext}"


class LocalStorage:
    def __init__(self, cfg):
        self.root = cfg.UPLOAD_DIR
        os.makedirs(self.root, exist_ok=True)

    def _path(self, key):
        path = os.path.abspath(os.path.join(self.root, key))
        if not path.startswith(self.root + os.sep):
            raise ValueError("Invalid storage key")
        return path

    def save(self, key, data, content_type):
        path = self._path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)

    def delete(self, key):
        try:
            os.remove(self._path(key))
        except FileNotFoundError:
            pass

    def url(self, key):
        return f"/api/uploads/{key}"

    def check(self):
        return os.access(self.root, os.W_OK)


class S3Storage:
    def __init__(self, cfg):
        import boto3

        self.bucket = cfg.S3_BUCKET
        self.prefix = cfg.S3_PREFIX or ""
        self.public_base = (cfg.S3_PUBLIC_BASE_URL or "").rstrip("/")
        self.expires = cfg.S3_URL_EXPIRES
        self.client = boto3.client("s3", region_name=cfg.AWS_REGION)

    def _object_key(self, key):
        return f"{self.prefix}{key}"

    def save(self, key, data, content_type):
        self.client.put_object(
            Bucket=self.bucket,
            Key=self._object_key(key),
            Body=data,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
            ServerSideEncryption="AES256",
        )

    def delete(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=self._object_key(key))

    def url(self, key):
        if self.public_base:
            return f"{self.public_base}/{self._object_key(key)}"
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": self._object_key(key)},
            ExpiresIn=self.expires,
        )

    def check(self):
        self.client.head_bucket(Bucket=self.bucket)
        return True


def create_storage(cfg):
    if cfg.STORAGE_BACKEND == "s3":
        return S3Storage(cfg)
    return LocalStorage(cfg)
