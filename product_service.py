
"""
Akshita Melamine — Product Service

Contains database operations for creating, retrieving,
archiving, and managing products and their images.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Product, ProductImage
from schemas import ProductCreate


def get_published_products(db: Session) -> list[Product]:
    """Return published, non-archived products, newest first."""

    statement = (
        select(Product)
        .where(
            Product.is_published.is_(True),
            Product.is_archived.is_(False),
        )
        .order_by(Product.id.desc())
    )

    return list(db.scalars(statement).all())


def get_featured_products(db: Session) -> list[Product]:
    """Return published, featured, non-archived products."""

    statement = (
        select(Product)
        .where(
            Product.is_published.is_(True),
            Product.featured.is_(True),
            Product.is_archived.is_(False),
        )
        .order_by(Product.id.desc())
    )

    return list(db.scalars(statement).all())


def get_published_product(
    db: Session,
    product_id: int,
) -> Product | None:
    """Return one published, non-archived product."""

    statement = select(Product).where(
        Product.id == product_id,
        Product.is_published.is_(True),
        Product.is_archived.is_(False),
    )

    return db.scalar(statement)


def get_all_products(db: Session) -> list[Product]:
    """Return all products, including drafts and archived items."""

    statement = select(Product).order_by(Product.id.desc())
    return list(db.scalars(statement).all())


def get_product_by_id(
    db: Session,
    product_id: int,
) -> Product | None:
    """Return a product by ID, including drafts and archived items."""

    statement = select(Product).where(Product.id == product_id)
    return db.scalar(statement)


def create_product(
    db: Session,
    product_data: ProductCreate,
) -> Product:
    """Create a product using validated request data."""

    product = Product(
        **product_data.model_dump(),
        is_archived=False,
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    return product


def save_product_image(
    db: Session,
    product: Product,
    image_data: dict,
) -> ProductImage:
    """Save image metadata and make the newly uploaded image primary."""

    # Only one image should be primary for a product.
    for existing_image in product.images:
        existing_image.is_primary = False

    image = ProductImage(
        product_id=product.id,
        storage_bucket=image_data["storage_bucket"],
        original_path=image_data["original_path"],
        card_path=image_data["card_path"],
        detail_path=image_data["detail_path"],
        original_format=image_data["format"],
        original_width=image_data["original_width"],
        original_height=image_data["original_height"],
        is_primary=True,
    )

    db.add(image)
    db.commit()
    db.refresh(image)

    return image


def set_primary_product_image(
    db: Session,
    product: Product,
    image: ProductImage,
) -> ProductImage:
    """Make an existing product image the primary image."""

    if image.product_id != product.id:
        raise ValueError("The image does not belong to this product.")

    for existing_image in product.images:
        existing_image.is_primary = existing_image.id == image.id

    db.commit()
    db.refresh(image)

    return image


def get_product_image(
    db: Session,
    product_id: int,
    image_id: int,
) -> ProductImage | None:
    """Find an image belonging to the specified product."""

    statement = select(ProductImage).where(
        ProductImage.id == image_id,
        ProductImage.product_id == product_id,
    )

    return db.scalar(statement)


def image_storage_data(image: ProductImage) -> dict:
    """Return the storage bucket and object paths for an image."""

    return {
        "storage_bucket": image.storage_bucket,
        "paths": [
            image.original_path,
            image.card_path,
            image.detail_path,
        ],
    }


def delete_product_image(
    db: Session,
    product: Product,
    image: ProductImage,
) -> dict:
    """
    Delete image metadata and promote a remaining image if needed.

    Returns the removed image's storage locations for later cleanup.
    """

    storage_data = image_storage_data(image)
    was_primary = image.is_primary

    remaining_images = sorted(
        (
            item
            for item in product.images
            if item.id != image.id
        ),
        key=lambda item: item.id,
    )

    db.delete(image)

    if was_primary and remaining_images:
        remaining_images[0].is_primary = True

    db.commit()

    return storage_data


def delete_product(
    db: Session,
    product: Product,
) -> list[dict]:
    """
    Permanently delete a product and its image metadata.

    Returns storage locations so the route can remove the actual files.
    """

    storage_data = [
        image_storage_data(image)
        for image in product.images
    ]

    db.delete(product)
    db.commit()

    return storage_data
