
"""
Akshita Melamine — Enquiry Routes

Provides public enquiry submission and protected
administrative enquiry management.
"""

import os
import secrets

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    status,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import get_db
from enquiry_service import (
    create_enquiry,
    get_enquiries,
    get_enquiry_by_id,
    update_enquiry,
)
from rate_limit import limiter
from schemas import EnquiryCreate, EnquiryResponse, EnquiryUpdate


router = APIRouter(
    prefix="/enquiries",
    tags=["Enquiries"],
)


def require_enquiry_admin(
    x_admin_token: str | None = Header(default=None),
) -> None:
    """Require the configured admin token for private endpoints."""

    expected_token = os.getenv("ENQUIRY_ADMIN_TOKEN")

    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Enquiry admin access is not configured.",
        )

    if not x_admin_token or not secrets.compare_digest(
        x_admin_token,
        expected_token,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token.",
        )


@router.post(
    "",
    response_model=EnquiryResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/minute")
def submit_enquiry(
    request: Request,
    enquiry_data: EnquiryCreate,
    db: Session = Depends(get_db),
):
    """Accept and store a customer enquiry."""

    try:
        return create_enquiry(db, enquiry_data)
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save your enquiry. Please try again later.",
        ) from error


@router.get(
    "/admin/all",
    response_model=list[EnquiryResponse],
    dependencies=[Depends(require_enquiry_admin)],
)
def list_admin_enquiries(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List enquiries for authorized administrators."""

    try:
        return get_enquiries(db, offset=offset, limit=limit)
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve enquiries.",
        ) from error


@router.patch(
    "/admin/{enquiry_id}",
    response_model=EnquiryResponse,
    dependencies=[Depends(require_enquiry_admin)],
)
def update_admin_enquiry(
    enquiry_id: int,
    update_data: EnquiryUpdate,
    db: Session = Depends(get_db),
):
    """Update an enquiry's status."""

    enquiry = get_enquiry_by_id(db, enquiry_id)

    if enquiry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enquiry not found.",
        )

    try:
        return update_enquiry(db, enquiry, update_data)
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update the enquiry.",
        ) from error
