"""
app/db/database.py - SQLAlchemy ORM models and session factory for SQLite
"""

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean,
    DateTime, Text, Index, func
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from typing import Optional, Generator

from app.config import DB_PATH
from app.utils.logger import get_logger

logger = get_logger(__name__)

Base = declarative_base()
_engine = None
_SessionLocal = None


# ─── ORM Models ──────────────────────────────────────────────────────────────

class InvoiceRecord(Base):
    """Persisted invoice with all extracted fields."""

    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    file_hash = Column(String(64), unique=True, nullable=False, index=True)

    # Extracted fields
    invoice_number = Column(String(50), index=True)
    invoice_date = Column(String(20), index=True)
    due_date = Column(String(20))
    vendor_name = Column(String(200), index=True)
    buyer_name = Column(String(200))
    total_amount = Column(Float)
    subtotal = Column(Float)
    tax_amount = Column(Float)
    tax_rate = Column(String(20))
    discount = Column(Float)
    currency = Column(String(10), index=True)
    tax_id = Column(String(30))
    po_number = Column(String(30))
    address = Column(Text)
    payment_terms = Column(String(100))
    detected_language = Column(String(10), index=True)

    # Metadata
    ocr_engine = Column(String(20))
    ocr_confidence = Column(Float)
    avg_field_confidence = Column(Float)
    validation_status = Column(String(20), index=True)
    validation_report = Column(Text)    # JSON
    confidence_scores = Column(Text)    # JSON
    raw_text = Column(Text)
    is_duplicate = Column(Boolean, default=False)
    processed_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_vendor_date", "vendor_name", "invoice_date"),
        Index("ix_currency_total", "currency", "total_amount"),
    )

    def to_dict(self) -> dict:
        """Serialize record to a flat dictionary."""
        return {
            "id": self.id,
            "filename": self.filename,
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date,
            "due_date": self.due_date,
            "vendor_name": self.vendor_name,
            "buyer_name": self.buyer_name,
            "total_amount": self.total_amount,
            "subtotal": self.subtotal,
            "tax_amount": self.tax_amount,
            "tax_rate": self.tax_rate,
            "discount": self.discount,
            "currency": self.currency,
            "tax_id": self.tax_id,
            "po_number": self.po_number,
            "address": self.address,
            "payment_terms": self.payment_terms,
            "detected_language": self.detected_language,
            "ocr_engine": self.ocr_engine,
            "ocr_confidence": self.ocr_confidence,
            "avg_field_confidence": self.avg_field_confidence,
            "validation_status": self.validation_status,
            "is_duplicate": self.is_duplicate,
            "processed_at": str(self.processed_at),
        }


# ─── Engine & Session ─────────────────────────────────────────────────────────

def get_engine():
    global _engine
    if _engine is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            f"sqlite:///{DB_PATH}",
            connect_args={"check_same_thread": False},
            echo=False,
        )
        Base.metadata.create_all(_engine)
        logger.info(f"Database initialized at {DB_PATH}")
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=True, autocommit=False)
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI-style dependency; also usable as context manager."""
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()


# ─── CRUD Helpers ─────────────────────────────────────────────────────────────

def save_invoice(record_data: dict, db: Session) -> InvoiceRecord:
    """
    Upsert an invoice record (by file_hash).

    Args:
        record_data: Dict with all invoice fields
        db:          SQLAlchemy session

    Returns:
        Saved InvoiceRecord instance
    """
    existing = db.query(InvoiceRecord).filter_by(
        file_hash=record_data["file_hash"]
    ).first()

    if existing:
        for k, v in record_data.items():
            setattr(existing, k, v)
        record = existing
        logger.debug(f"Updated invoice record hash={record_data['file_hash'][:8]}")
    else:
        record = InvoiceRecord(**record_data)
        db.add(record)
        logger.debug(f"Inserted new invoice record: {record_data.get('filename')}")

    db.commit()
    db.refresh(record)
    return record


def get_all_invoices(db: Session, limit: int = 1000) -> list:
    return db.query(InvoiceRecord).order_by(InvoiceRecord.processed_at.desc()).limit(limit).all()


def get_invoice_by_id(invoice_id: int, db: Session) -> Optional[InvoiceRecord]:
    return db.query(InvoiceRecord).filter_by(id=invoice_id).first()


def get_analytics(db: Session) -> dict:
    """Return aggregate statistics for the analytics dashboard."""
    total = db.query(func.count(InvoiceRecord.id)).scalar() or 0
    by_lang = dict(
        db.query(InvoiceRecord.detected_language, func.count(InvoiceRecord.id))
        .group_by(InvoiceRecord.detected_language).all()
    )
    by_status = dict(
        db.query(InvoiceRecord.validation_status, func.count(InvoiceRecord.id))
        .group_by(InvoiceRecord.validation_status).all()
    )
    avg_conf = db.query(func.avg(InvoiceRecord.avg_field_confidence)).scalar() or 0
    total_amount_sum = db.query(func.sum(InvoiceRecord.total_amount)).scalar() or 0
    duplicates = db.query(func.count(InvoiceRecord.id)).filter_by(is_duplicate=True).scalar() or 0

    return {
        "total_invoices": total,
        "by_language": by_lang,
        "by_validation_status": by_status,
        "avg_confidence": round(float(avg_conf), 3),
        "total_amount_processed": round(float(total_amount_sum), 2),
        "duplicate_count": duplicates,
    }
