"""
app/api.py - Optional FastAPI REST layer for headless / programmatic access.

Run with:  uvicorn app.api:app --reload --port 8001
"""

from pathlib import Path
from typing import Optional, List
import json

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.db.database import get_db, get_all_invoices, get_analytics, get_invoice_by_id
from app.processing.pipeline import process_bytes
from app.retrieval.search import search_invoices
from app.exports.exporter import to_csv_bytes, to_json_bytes
from app.utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="Multi-Language Invoice Extractor API",
    description="AI-powered structured extraction from multilingual invoice images and PDFs.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Upload & Process ─────────────────────────────────────────────────────────

@app.post("/invoices/upload", summary="Upload and process a single invoice")
async def upload_invoice(file: UploadFile = File(...)):
    """
    Upload an invoice file (image or PDF), run the full extraction pipeline,
    and return structured results.
    """
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".pdf"}:
        raise HTTPException(400, f"Unsupported file type: {suffix}")

    content = await file.read()
    result = process_bytes(content, file.filename, suffix)

    if not result.success:
        raise HTTPException(500, f"Processing failed: {result.error}")

    return JSONResponse(content=result.to_dict())


# ─── List & Get ───────────────────────────────────────────────────────────────

@app.get("/invoices", summary="List all processed invoices")
def list_invoices(limit: int = Query(100, le=1000), db: Session = Depends(get_db)):
    records = get_all_invoices(db, limit=limit)
    return [r.to_dict() for r in records]


@app.get("/invoices/{invoice_id}", summary="Get invoice by ID")
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    record = get_invoice_by_id(invoice_id, db)
    if not record:
        raise HTTPException(404, f"Invoice {invoice_id} not found")
    return record.to_dict()


# ─── Search ──────────────────────────────────────────────────────────────────

@app.get("/invoices/search/query", summary="Full-text search over invoices")
def search(
    q: str = Query(""),
    vendor: str = Query(""),
    currency: str = Query(""),
    language: str = Query(""),
    validation_status: str = Query(""),
    min_amount: Optional[float] = Query(None),
    max_amount: Optional[float] = Query(None),
    limit: int = Query(50, le=500),
):
    results = search_invoices(
        query_str=q, vendor=vendor, currency=currency,
        language=language, validation_status=validation_status,
        min_amount=min_amount, max_amount=max_amount, limit=limit,
    )
    return results


# ─── Analytics ───────────────────────────────────────────────────────────────

@app.get("/analytics", summary="Aggregate statistics across all invoices")
def analytics(db: Session = Depends(get_db)):
    return get_analytics(db)


# ─── Exports ─────────────────────────────────────────────────────────────────

@app.get("/export/csv", summary="Download all invoices as CSV")
def export_csv(db: Session = Depends(get_db)):
    records = [r.to_dict() for r in get_all_invoices(db, limit=10000)]
    csv_bytes = to_csv_bytes(records)
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=invoices.csv"},
    )


@app.get("/export/json", summary="Download all invoices as JSON")
def export_json(db: Session = Depends(get_db)):
    records = [r.to_dict() for r in get_all_invoices(db, limit=10000)]
    json_bytes = to_json_bytes(records)
    return StreamingResponse(
        iter([json_bytes]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=invoices.json"},
    )


# ─── Health ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "invoice-extractor"}
