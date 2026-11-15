
"""
Akshita Melamine — Product Routes

Provides public catalogue endpoints and product administration
endpoints for development. Protect admin endpoints with
authentication before production deployment.
"""

import logging
from collections.abc import Generator
from fastapi import Request  # Not required for this dependency approach.
from product_auth import require_product_admin
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import engine
from image_engine import MAX_UPLOAD_BYTES, process_product_image
from models import Product
from product_service import (
    create_product,
    delete_product,
    delete_product_image,
    get_all_products,
    get_featured_products,
    get_product_by_id,
    get_product_image,
    get_published_product,
    get_published_products,
    save_product_image,
    set_primary_product_image,
)
from schemas import (
    ProductCreate,
    ProductDetailResponse,
    ProductImageResponse,
    ProductResponse,
    ProductUpdate,
)
from storage_service import delete_files, get_public_url


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/products", tags=["Products"])


def get_db() -> Generator[Session, None, None]:
    """Provide a database session for one request."""
    with Session(engine) as db:
        yield db


def build_product_response(product: Product) -> ProductResponse:
    """Build a product response with its primary card image URL."""

    primary_image = next(
        (image for image in product.images if image.is_primary),
        None,
    )

    primary_image_url = (
        get_public_url(primary_image.card_path)
        if primary_image is not None
        else None
    )

    return ProductResponse(
        id=product.id,
        catalogue_number=product.catalogue_number,
        name=product.name,
        category=product.category,
        description=product.description,
        is_published=product.is_published,
        featured=product.featured,
        is_archived=product.is_archived,
        primary_image_url=primary_image_url,
    )


def build_image_response(image) -> ProductImageResponse:
    """Build an image response with its public URLs."""

    return ProductImageResponse(
        id=image.id,
        product_id=image.product_id,
        is_primary=image.is_primary,
        original_url=get_public_url(image.original_path),
        card_url=get_public_url(image.card_path),
        detail_url=get_public_url(image.detail_path),
    )


def build_product_detail_response(
    product: Product,
) -> ProductDetailResponse:
    """Build product details including all associated image records."""

    images = [
        build_image_response(image)
        for image in product.images
    ]

    primary_image = next(
        (image for image in product.images if image.is_primary),
        None,
    )

    return ProductDetailResponse(
        id=product.id,
        catalogue_number=product.catalogue_number,
        name=product.name,
        category=product.category,
        description=product.description,
        is_published=product.is_published,
        featured=product.featured,
        is_archived=product.is_archived,
        primary_image_url=(
            get_public_url(primary_image.card_path)
            if primary_image is not None
            else None
        ),
        images=images,
    )


def cleanup_storage_items(items: list[dict]) -> list[str]:
    """
    Attempt to remove stored image files.

    Returns cleanup errors instead of hiding them. Database changes
    may already be committed when storage cleanup is attempted.
    """

    errors: list[str] = []

    for item in items:
        try:
            delete_files(
                item["storage_bucket"],
                item["paths"],
            )
        except Exception:
            logger.exception(
                "Supabase image cleanup failed for bucket %s.",
                item.get("storage_bucket"),
            )
            errors.append(
                f"Could not clean up files in bucket "
                f"{item.get('storage_bucket', 'unknown')}."
            )

    return errors


def create_product_response(
    product_data: ProductCreate,
    db: Session,
) -> ProductResponse:
    """Create a product and return its serialized response."""

    try:
        product = create_product(db, product_data)
        return build_product_response(product)
    except SQLAlchemyError as error:
        db.rollback()
        logger.exception("Product creation failed.")

        raise HTTPException(
            status_code=409,
            detail=(
                "Could not create the product. "
                "Check whether its catalogue number already exists."
            ),
        ) from error


# ---------------------------------------------------------
# Public catalogue routes
# ---------------------------------------------------------

@router.get("", response_model=list[ProductResponse])
def list_products(db: Session = Depends(get_db)):
    """Return published, non-archived products."""

    return [
        build_product_response(product)
        for product in get_published_products(db)
    ]


@router.get("/featured", response_model=list[ProductResponse])
def list_featured_products(db: Session = Depends(get_db)):
    """Return published, featured, non-archived products."""

    return [
        build_product_response(product)
        for product in get_featured_products(db)
    ]


# ---------------------------------------------------------
# Admin product routes
# Keep these routes before /{product_id}.
# ---------------------------------------------------------

@router.get("/admin/all", response_model=list[ProductResponse], dependencies=[Depends(require_product_admin)],)
def list_all_products_for_admin(
    db: Session = Depends(get_db),
):
    """Return all products, including drafts and archived items."""

    return [
        build_product_response(product)
        for product in get_all_products(db)
    ]


@router.get(
    "/admin/{product_id}",
    response_model=ProductDetailResponse,
    dependencies=[Depends(require_product_admin)],
)
def admin_product_detail(
    product_id: int,
    db: Session = Depends(get_db),
):
    """Return a product and all its images, including drafts."""

    product = get_product_by_id(db, product_id)

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found.",
        )

    return build_product_detail_response(product)


# ---------------------------------------------------------
# Product creation
# ---------------------------------------------------------

@router.post("", response_model=ProductResponse, status_code=201,dependencies=[Depends(require_product_admin)],)
def create_product_endpoint(
    product_data: ProductCreate,
    db: Session = Depends(get_db),
):
    """
    Create a product for the admin workflow.

    New products are drafts by default unless publication is
    explicitly requested. Images can be uploaded afterwards.
    """

    return create_product_response(product_data, db)


# ---------------------------------------------------------
# Product updates
# ---------------------------------------------------------

@router.patch("/{product_id}", response_model=ProductResponse,dependencies=[Depends(require_product_admin)],)
def update_product(
    product_id: int,
    product_data: ProductUpdate,
    db: Session = Depends(get_db),
):
    """Update details, visibility, featured status, or archive status."""

    product = get_product_by_id(db, product_id)

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found.",
        )

    updates = product_data.model_dump(exclude_unset=True)

    for field in ("name", "catalogue_number", "category", "description"):
        if field in updates and updates[field] is None:
            raise HTTPException(
                status_code=422,
                detail=f"{field} cannot be null.",
            )

    if updates.get("is_archived") is True:
        updates["is_published"] = False
        updates["featured"] = False

    if (
        updates.get("is_published") is True
        and product.is_archived
        and updates.get("is_archived") is not False
    ):
        raise HTTPException(
            status_code=409,
            detail="Restore the product before publishing it.",
        )

    for field, value in updates.items():
        setattr(product, field, value)

    try:
        db.commit()
        db.refresh(product)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Could not update the product. "
                "Check whether its catalogue number is already in use."
            ),
        ) from error

    return build_product_response(product)


@router.get(
    "/{product_id}",
    response_model=ProductDetailResponse,
)
def product_detail(
    product_id: int,
    db: Session = Depends(get_db),
):
    """Return a published product and its image URLs publicly."""

    product = get_published_product(db, product_id)

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found.",
        )

    return build_product_detail_response(product)


# ---------------------------------------------------------
# Legacy development-only creation endpoint
# Retained to avoid breaking existing development workflows.
# ---------------------------------------------------------

@router.post("/dev", response_model=ProductResponse,dependencies=[Depends(require_product_admin)],)
def create_product_dev(
    product_data: ProductCreate,
    db: Session = Depends(get_db),
):
    """Development-only product creation endpoint."""

    return create_product_response(product_data, db)


# ---------------------------------------------------------
# Product image management
# ---------------------------------------------------------

@router.post("/{product_id}/images", dependencies=[Depends(require_product_admin)],)
async def upload_product_image_for_product(
    product_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload an image and make it the product's primary image."""

    try:
        product = get_product_by_id(db, product_id)

        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Product not found.",
            )

        upload_bytes = await file.read(MAX_UPLOAD_BYTES + 1)

        if not upload_bytes:
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is empty.",
            )

        if len(upload_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Image size must not exceed 10 MB.",
            )

        try:
            image_data = process_product_image(upload_bytes)
        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            ) from error
        except Exception as error:
            logger.exception("Product image processing/upload failed.")
            raise HTTPException(
                status_code=502,
                detail="Could not process or upload the image.",
            ) from error

        try:
            image = save_product_image(db, product, image_data)
        except SQLAlchemyError as error:
            db.rollback()

            cleanup_errors = cleanup_storage_items(
                [
                    {
                        "storage_bucket": image_data["storage_bucket"],
                        "paths": [
                            image_data["original_path"],
                            image_data["card_path"],
                            image_data["detail_path"],
                        ],
                    }
                ]
            )

            detail = "Image metadata could not be saved."

            if cleanup_errors:
                detail += " Uploaded storage files may need manual cleanup."

            raise HTTPException(
                status_code=500,
                detail=detail,
            ) from error

        return {
            "message": "Product image uploaded successfully.",
            "product_id": product.id,
            "image_record_id": image.id,
            "is_primary": image.is_primary,
            "storage_bucket": image_data["storage_bucket"],
            "original_url": image_data["original_url"],
            "card_url": image_data["card_url"],
            "detail_url": image_data["detail_url"],
        }

    finally:
        await file.close()


@router.patch("/{product_id}/images/{image_id}/primary", dependencies=[Depends(require_product_admin)],)
def make_product_image_primary(
    product_id: int,
    image_id: int,
    db: Session = Depends(get_db),
):
    """Select an existing image as the product's primary image."""

    product = get_product_by_id(db, product_id)

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found.",
        )

    image = get_product_image(db, product_id, image_id)

    if image is None:
        raise HTTPException(
            status_code=404,
            detail="Product image not found.",
        )

    try:
        set_primary_product_image(db, product, image)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not change the primary image.",
        ) from error

    return {
        "message": "Primary image updated.",
        "product_id": product_id,
        "image_record_id": image_id,
        "is_primary": True,
    }


@router.delete("/{product_id}/images/{image_id}", dependencies=[Depends(require_product_admin)],)
def remove_product_image(
    product_id: int,
    image_id: int,
    db: Session = Depends(get_db),
):
    """Remove image metadata and attempt to delete its storage files."""

    product = get_product_by_id(db, product_id)

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found.",
        )

    image = get_product_image(db, product_id, image_id)

    if image is None:
        raise HTTPException(
            status_code=404,
            detail="Product image not found.",
        )

    try:
        storage_data = delete_product_image(db, product, image)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not remove the product image.",
        ) from error

    cleanup_errors = cleanup_storage_items([storage_data])

    return {
        "message": "Image record removed.",
        "product_id": product_id,
        "image_record_id": image_id,
        "storage_cleanup_warning": cleanup_errors or None,
    }


@router.delete("/{product_id}", dependencies=[Depends(require_product_admin)],)
def permanently_delete_product(
    product_id: int,
    db: Session = Depends(get_db),
):
    """Permanently delete a product and attempt to remove its image files."""

    product = get_product_by_id(db, product_id)

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found.",
        )

    try:
        storage_items = delete_product(db, product)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not delete the product.",
        ) from error

    cleanup_errors = cleanup_storage_items(storage_items)

    return {
        "message": "Product permanently deleted.",
        "product_id": product_id,
        "storage_cleanup_warning": cleanup_errors or None,
    }
