
"""
Akshita Melamine — Database Connection

Loads the PostgreSQL connection URL from .env and creates
the SQLAlchemy engine and database session dependency.
"""

import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker


# Load environment variables from backend/.env.
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is missing. Check your backend/.env file."
    )


# Create the database engine.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
)

# Create a new SQLAlchemy session for each database operation.
SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Provide a database session and always close it afterward."""

    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def test_database_connection() -> dict:
    """Run a simple query to verify the database connection."""

    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version()"))
            database_version = result.scalar()

        return {
            "connected": True,
            "database": "Supabase PostgreSQL",
            "version": database_version,
        }

    except SQLAlchemyError as error:
        # Do not expose database credentials or connection details.
        raise RuntimeError(
            "Could not connect to Supabase PostgreSQL. "
            "Check the connection settings and network access."
        ) from error
