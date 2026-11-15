
"""
Initialize the Akshita Melamine database schema.

Run manually from the backend directory:
    python init_db.py
"""

from database import engine
from models import Base


def initialize_database() -> None:
    """Create missing tables defined in models.py."""
    Base.metadata.create_all(bind=engine)
    print("Database tables created or already exist.")


if __name__ == "__main__":
    initialize_database()
