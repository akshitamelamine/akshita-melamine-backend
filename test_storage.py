"""
Test the connection to Supabase Storage.

Run:
    python test_storage.py
"""

from storage_service import (
    STORAGE_BUCKET,
    get_supabase_client,
)


def main() -> None:
    """Confirm that the configured bucket exists."""

    client = get_supabase_client()

    buckets = client.storage.list_buckets()

    bucket_names = [
        bucket.name for bucket in buckets
    ]

    print("Supabase Storage connection successful.")
    print("Available buckets:", bucket_names)

    if STORAGE_BUCKET not in bucket_names:
        raise RuntimeError(
            f"The '{STORAGE_BUCKET}' bucket was not found. "
            "Check its name in Supabase Storage and your .env file."
        )

    print(f"Bucket '{STORAGE_BUCKET}' verified successfully.")


if __name__ == "__main__":
    main()