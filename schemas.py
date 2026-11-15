
"""
Akshita Melamine — API Schemas

Defines validation rules for products, product images,
and customer enquiries.
"""

import re
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


# ---------------------------------------------------------
# Shared validation helpers
# ---------------------------------------------------------

def normalize_required_text(value: str) -> str:
    """Trim text and reject values containing only whitespace."""

    normalized = value.strip()

    if not normalized:
        raise ValueError("This field cannot be blank.")

    return normalized


def normalize_optional_text(value: str | None) -> str | None:
    """Trim optional text and convert empty values to None."""

    if value is None:
        return None

    normalized = value.strip()
    return normalized or None


# ---------------------------------------------------------
# Product schemas
# ---------------------------------------------------------

class ProductCreate(BaseModel):
    """Fields accepted when creating a product."""

    catalogue_number: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=10000)

    is_published: bool = False
    featured: bool = False


class ProductImageResponse(BaseModel):
    """Image metadata returned by the API."""

    id: int
    product_id: int
    is_primary: bool
    original_url: str
    card_url: str
    detail_url: str


class ProductResponse(BaseModel):
    """Product information returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    catalogue_number: str
    name: str
    category: str
    description: str
    is_published: bool
    featured: bool = False
    is_archived: bool = False
    primary_image_url: str | None = None


class ProductDetailResponse(ProductResponse):
    """Product details, including associated images."""

    images: list[ProductImageResponse] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    """Fields that an admin can update on a product."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    catalogue_number: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    category: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(
        default=None,
        min_length=1,
        max_length=10000,
    )
    is_published: bool | None = None
    featured: bool | None = None
    is_archived: bool | None = None


# ---------------------------------------------------------
# Enquiry schemas
# ---------------------------------------------------------

class EnquiryCreate(BaseModel):
    """Customer details accepted when submitting an enquiry."""

    customer_name: str = Field(min_length=1, max_length=150)
    company_name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=1, max_length=30)
    email: EmailStr
    city: str = Field(min_length=1, max_length=100)
    # Anti-spam field; legitimate customers should leave this empty.
    website: str = Field(default="", max_length=200)

    requested_product: str | None = Field(default=None, max_length=200)
    quantity: str | None = Field(default=None, max_length=100)
    variant: str | None = Field(default=None, max_length=150)
    message: str | None = Field(default=None, max_length=10000)

    @field_validator("website")
    @classmethod
    def reject_honeypot(cls, value: str) -> str:
        """Reject submissions where the hidden honeypot was filled."""

        if value.strip():
            raise ValueError("Invalid enquiry submission.")

        return ""

    @field_validator(
        "customer_name",
        "company_name",
        "phone",
        "city",
        mode="before",
    )
    @classmethod
    def validate_required_text(cls, value: object) -> object:
        """Normalize required text before standard validation."""

        if not isinstance(value, str):
            return value

        return normalize_required_text(value)

    @field_validator(
        "requested_product",
        "quantity",
        "variant",
        "message",
        mode="before",
    )
    @classmethod
    def validate_optional_text(cls, value: object) -> object:
        """Normalize optional text and empty strings."""

        if value is None:
            return None

        if not isinstance(value, str):
            return value

        return normalize_optional_text(value)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        """Trim surrounding whitespace from email addresses."""

        if isinstance(value, str):
            return value.strip()

        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        """Reject phone values without a plausible digit sequence."""

        digits = re.sub(r"\D", "", value)

        if not 7 <= len(digits) <= 15:
            raise ValueError(
                "Enter a phone number containing 7 to 15 digits."
            )

        return value


class EnquiryUpdate(BaseModel):
    """Fields an administrator can change on an enquiry."""

    status: str = Field(
        min_length=1,
        max_length=30,
        pattern=r"^(new|in_progress|contacted|resolved|closed)$",
    )


class EnquiryResponse(BaseModel):
    """Enquiry details returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_name: str
    company_name: str
    phone: str
    email: str
    city: str
    requested_product: str | None = None
    quantity: str | None = None
    variant: str | None = None
    message: str | None = None
    status: str
    created_at: datetime
