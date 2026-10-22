from datetime import datetime, timezone
from sqlalchemy import JSON, BigInteger, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


def utcnow() -> datetime:
    """Naive UTC timestamp (same behaviour on SQLite and PostgreSQL)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() + "Z" if dt else None


BigId = BigInteger().with_variant(Integer, "sqlite")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(120))
    full_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))  # physician | nurse | admin
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Patient(Base):
    __tablename__ = "patients"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    age: Mapped[int] = mapped_column(Integer)
    sex: Mapped[str] = mapped_column(String(1))
    condition: Mapped[str] = mapped_column(String(80))
    thresholds: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # per-patient overrides
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    risk_level: Mapped[str] = mapped_column(String(10), default="stable")
    factors: Mapped[list | None] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Vital(Base):
    __tablename__ = "vitals"
    __table_args__ = (Index("ix_vitals_patient_ts", "patient_id", "ts"),)
    id: Mapped[int] = mapped_column(BigId, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    hr: Mapped[float] = mapped_column(Float)
    sys: Mapped[float] = mapped_column(Float)
    dia: Mapped[float] = mapped_column(Float)
    spo2: Mapped[float] = mapped_column(Float)
    temp: Mapped[float] = mapped_column(Float)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(BigId, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    layer: Mapped[str] = mapped_column(String(12))      # threshold | anomaly | trend | ml
    severity: Mapped[str] = mapped_column(String(8))    # watch | high
    message: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(15), default="active", index=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RiskSnapshot(Base):
    __tablename__ = "risk_snapshots"
    id: Mapped[int] = mapped_column(BigId, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    score: Mapped[int] = mapped_column(Integer)
    level: Mapped[str] = mapped_column(String(10))
    factors: Mapped[list | None] = mapped_column(JSON, default=list)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(BigId, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    username: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    patient_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
