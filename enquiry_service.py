
"""
Akshita Melamine — Enquiry Service

Handles database operations for customer enquiries.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Enquiry
from schemas import EnquiryCreate, EnquiryUpdate


def create_enquiry(
    db: Session,
    enquiry_data: EnquiryCreate,
) -> Enquiry:
    """Save a new customer enquiry."""

    # The website field is a honeypot used to detect bot submissions.
    # Never store it as an Enquiry database field.
    data = enquiry_data.model_dump(exclude={"website"})

    enquiry = Enquiry(
        **data,
        status="new",
    )

    try:
        db.add(enquiry)
        db.commit()
        db.refresh(enquiry)
        return enquiry
    except Exception:
        db.rollback()
        raise


def get_enquiries(
    db: Session,
    offset: int = 0,
    limit: int = 50,
) -> list[Enquiry]:
    """Return enquiries with the newest submissions first."""

    statement = (
        select(Enquiry)
        .order_by(Enquiry.created_at.desc(), Enquiry.id.desc())
        .offset(offset)
        .limit(limit)
    )

    return list(db.scalars(statement).all())


def get_enquiry_by_id(
    db: Session,
    enquiry_id: int,
) -> Enquiry | None:
    """Find one enquiry by its database ID."""

    return db.get(Enquiry, enquiry_id)


def update_enquiry(
    db: Session,
    enquiry: Enquiry,
    update_data: EnquiryUpdate,
) -> Enquiry:
    """Update an enquiry's status."""

    enquiry.status = update_data.status

    try:
        db.commit()
        db.refresh(enquiry)
        return enquiry
    except Exception:
        db.rollback()
        raise
