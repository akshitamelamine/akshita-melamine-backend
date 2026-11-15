
"""
Akshita Melamine — Supabase Storage Service

Handles cloud storage for product images.
Only the Python backend should use the secret key.
"""

import os
from functools import lru_cache

from dotenv import load_dotenv
from supabase import Client, create_client


load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")
STORAGE_BUCKET = os.getenv(
    "SUPABASE_STORAGE_BUCKET",
    "product-images",
)


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """Create and reuse the Supabase client."""

    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        raise RuntimeError(
            "Supabase Storage configuration is missing. "
            "Check SUPABASE_URL and SUPABASE_SECRET_KEY in .env."
        )

    return create_client(
        SUPABASE_URL,
        SUPABASE_SECRET_KEY,
    )


def upload_file(
    storage_path: str,
    file_bytes: bytes,
    content_type: str,
) -> dict:
    """Upload a file to the configured Supabase Storage bucket."""

    if not storage_path or storage_path.startswith("/"):
        raise ValueError("A valid relative storage path is required.")

    if not file_bytes:
        raise ValueError("Cannot upload an empty file.")

    client = get_supabase_client()

    result = client.storage.from_(STORAGE_BUCKET).upload(
        path=storage_path,
        file=file_bytes,
        file_options={
            "content-type": content_type,
            "upsert": "true",
        },
    )

    return {
        "bucket": STORAGE_BUCKET,
        "path": storage_path,
        "result": result,
    }


def get_public_url(storage_path: str) -> str:
    """Return the public URL for an object in the configured bucket."""

    client = get_supabase_client()

    return client.storage.from_(STORAGE_BUCKET).get_public_url(
        storage_path
    )


def delete_files(
    storage_bucket: str,
    storage_paths: list[str],
) -> None:
    """
    Delete stored objects from Supabase.

    Raises an exception if storage deletion fails so callers can
    report a cleanup warning instead of silently ignoring it.
    """

    paths = list(dict.fromkeys(path for path in storage_paths if path))

    if not paths:
        return

    if not storage_bucket:
        raise ValueError("A storage bucket is required.")

    client = get_supabase_client()
    client.storage.from_(storage_bucket).remove(paths)
