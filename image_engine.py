"""
Akshita Melamine — Product Image Engine

Responsibilities:
1. Validate uploaded image data.
2. Preserve the exact original upload.
3. Generate smaller WebP images for cards and detail pages.
4. Upload all three versions to Supabase Storage.
5. Return storage paths and public URLs.

The original image bytes are preserved exactly.
Optimized variants are generated separately.
"""

from io import BytesIO
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

from storage_service import (
    STORAGE_BUCKET,
    get_public_url,
    upload_file,
)


# Upload and image-dimension safety limits.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_IMAGE_PIXELS = 30_000_000

# Only accept these image formats.
ALLOWED_FORMATS = {
    "JPEG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
}

# Maximum dimensions for generated image variants.
CARD_SIZE = (480, 480)
DETAIL_SIZE = (1600, 1600)


def prepare_image(image: Image.Image) -> Image.Image:
    """
    Correct image orientation and convert to a mode
    that WebP can display correctly.

    Transparency is retained when present.
    """
    image = ImageOps.exif_transpose(image)

    if "A" in image.getbands() or "transparency" in image.info:
        return image.convert("RGBA")

    return image.convert("RGB")


def create_webp_variant(
    image: Image.Image,
    max_size: tuple[int, int],
    quality: int,
) -> bytes:
    """
    Resize an image without cropping it and return
    optimized WebP bytes.
    """
    variant = image.copy()

    try:
        variant.thumbnail(
            max_size,
            Image.Resampling.LANCZOS,
        )

        output = BytesIO()

        variant.save(
            output,
            format="WEBP",
            quality=quality,
            method=6,
        )

        return output.getvalue()

    finally:
        variant.close()


def process_product_image(upload_bytes: bytes) -> dict:
    """
    Validate an uploaded image, preserve its original bytes,
    generate optimized variants, and upload everything to
    Supabase Storage.

    Returns image metadata, storage paths, and public URLs.
    """
    if not upload_bytes:
        raise ValueError("The uploaded file is empty.")

    if len(upload_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError("Image size must not exceed 10 MB.")

    prepared = None

    try:
        # Inspect the real image format instead of trusting
        # the filename or the supplied MIME type.
        with Image.open(BytesIO(upload_bytes)) as source:
            actual_format = source.format

            if actual_format not in ALLOWED_FORMATS:
                raise ValueError(
                    "Unsupported image format. "
                    "Upload a JPEG, PNG, or WebP image."
                )

            width, height = source.size

            if width <= 0 or height <= 0:
                raise ValueError(
                    "The image dimensions are invalid."
                )

            if width * height > MAX_IMAGE_PIXELS:
                raise ValueError(
                    "Image dimensions are too large."
                )

            # Animated files are not supported.
            if getattr(source, "is_animated", False):
                raise ValueError(
                    "Animated images are not supported. "
                    "Upload a static image instead."
                )

            # Decode the file so corrupted images are rejected.
            source.load()

            original_width, original_height = source.size

            # Make an independent image for processing.
            prepared = prepare_image(source.copy())

        # A unique ID prevents uploaded filenames from controlling
        # storage paths and reduces the chance of collisions.
        image_id = uuid4().hex
        storage_directory = f"products/{image_id}"

        original_extension = ALLOWED_FORMATS[actual_format]
        original_path = (
            f"{storage_directory}/original.{original_extension}"
        )
        card_path = f"{storage_directory}/card.webp"
        detail_path = f"{storage_directory}/detail.webp"

        # Create WebP variants in memory.
        card_bytes = create_webp_variant(
            prepared,
            CARD_SIZE,
            quality=82,
        )

        detail_bytes = create_webp_variant(
            prepared,
            DETAIL_SIZE,
            quality=88,
        )

        # Upload the original first, preserving its exact bytes.
        # WebP versions are separate, optimized files.
        upload_file(
            original_path,
            upload_bytes,
            f"image/{original_extension.replace('jpg', 'jpeg')}",
        )

        upload_file(
            card_path,
            card_bytes,
            "image/webp",
        )

        upload_file(
            detail_path,
            detail_bytes,
            "image/webp",
        )

        # Return public URLs for the configured public bucket.
        return {
            "image_id": image_id,
            "format": actual_format,
            "original_width": original_width,
            "original_height": original_height,
            "storage_bucket": STORAGE_BUCKET,
            "original_path": original_path,
            "card_path": card_path,
            "detail_path": detail_path,
            "original_url": get_public_url(original_path),
            "card_url": get_public_url(card_path),
            "detail_url": get_public_url(detail_path),
            "card_bytes": len(card_bytes),
            "detail_bytes": len(detail_bytes),
        }

    except ValueError:
        raise

    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
    ) as error:
        raise ValueError(
            "The uploaded file is not a valid, supported image."
        ) from error

    finally:
        if prepared is not None:
            prepared.close()