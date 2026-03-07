"""
DATABASE
NarrativeIQ — SQLite database connection via SQLAlchemy
Zero config — creates narrativeiq.db in the project root automatically
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

# ─────────────────────────────────────────
# CONFIG
# SQLite by default — swap DATABASE_URL in .env for PostgreSQL
# PostgreSQL example: postgresql://user:password@localhost/narrativeiq
# ─────────────────────────────────────────

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///./narrativeiq.db"
)

# SQLite needs this extra arg; PostgreSQL doesn't
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False   # set True to log all SQL queries
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ─────────────────────────────────────────
# INIT DB
# Creates all tables if they don't exist
# Call this once at startup
# ─────────────────────────────────────────

def init_db():
    from models.auth_models import Base
    Base.metadata.create_all(bind=engine)
    print("[DB] Tables created / verified.")


# ─────────────────────────────────────────
# DEPENDENCY
# Use in FastAPI route functions:
#   db: Session = Depends(get_db)
# ─────────────────────────────────────────

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
