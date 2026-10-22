import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

URL = os.getenv("DATABASE_URL", "sqlite:///./carewatch.db")
# Render/Heroku style URLs -> SQLAlchemy driver URL
if URL.startswith("postgres://"):
    URL = URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif URL.startswith("postgresql://"):
    URL = URL.replace("postgresql://", "postgresql+psycopg2://", 1)

engine = create_engine(
    URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
