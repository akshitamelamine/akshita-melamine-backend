"""
Akshita Melamine — Product Admin Authentication

Protects product administration endpoints with a private
server-side token configured through PRODUCT_ADMIN_TOKEN.
"""

import hmac
import os

from fastapi import Header, HTTPException, status


def require_product_admin(
    supplied_token: str | None = Header(
        default=None,
        alias="X-Product-Admin-Token",
    ),
) -> None:
    """Reject product-admin requests without a valid token."""

    expected_token = os.getenv("PRODUCT_ADMIN_TOKEN", "")

    # Fail closed if the required server configuration is missing.
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Product administration is not configured.",
        )

    if not supplied_token or not hmac.compare_digest(
        supplied_token,
        expected_token,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing product admin token.",
        )