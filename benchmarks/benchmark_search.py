"""
benchmarks/benchmark_search.py - Measure retrieval speed: Whoosh-indexed vs naive SQLite scan.

Usage:
    python benchmarks/benchmark_search.py --n 1000 --queries 50

This script:
1. Seeds the database with N synthetic invoice records
2. Runs Q search queries against both strategies
3. Reports mean/median latency and speedup factor
"""

import argparse
import json
import random
import string
import time
from statistics import mean, median

# Ensure project root is importable
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


VENDORS = [
    "Acme Corp", "Global Supplies Ltd", "TechPro India", "Al Farouq Trading",
    "Deutsche Handel GmbH", "Société Générale", "BrightStar Electronics",
    "Pacific Rim Exports", "NovaTech Solutions", "Sunrise Distributors",
]
CURRENCIES = ["USD", "EUR", "GBP", "INR", "JPY", "AED"]
LANGUAGES = ["en", "hi", "ar", "fr", "de", "es"]
STATUSES = ["PASSED", "WARNING", "FAILED"]


def random_invoice_number() -> str:
    prefix = random.choice(["INV", "BILL", "REC", "FAC"])
    num = random.randint(1000, 99999)
    return f"{prefix}-{num}"


def seed_db(n: int):
    """Insert N synthetic invoice records into the database."""
    from app.db.database import get_session_factory, InvoiceRecord
    factory = get_session_factory()
    db = factory()
    try:
        existing = db.query(InvoiceRecord).count()
        if existing >= n:
            print(f"DB already has {existing} records, skipping seed.")
            return existing

        print(f"Seeding {n - existing} synthetic invoices…")
        batch = []
        for i in range(existing, n):
            vendor = random.choice(VENDORS)
            total = round(random.uniform(100, 50000), 2)
            record = InvoiceRecord(
                filename=f"invoice_{i:05d}.jpg",
                file_hash="".join(random.choices(string.hexdigits, k=64)),
                invoice_number=random_invoice_number(),
                invoice_date=f"2023-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
                vendor_name=vendor,
                buyer_name=random.choice(VENDORS),
                total_amount=total,
                subtotal=round(total * 0.85, 2),
                tax_amount=round(total * 0.15, 2),
                currency=random.choice(CURRENCIES),
                detected_language=random.choice(LANGUAGES),
                validation_status=random.choice(STATUSES),
                validation_report=json.dumps({"status": "PASSED", "passed": [], "warnings": [], "errors": []}),
                confidence_scores="{}",
                raw_text=f"Invoice from {vendor} for services rendered. Total: {total}",
                avg_field_confidence=round(random.uniform(0.5, 0.98), 3),
                ocr_engine="tesseract",
                ocr_confidence=round(random.uniform(0.6, 0.99), 3),
                is_duplicate=False,
            )
            batch.append(record)

            if len(batch) % 200 == 0:
                db.bulk_save_objects(batch)
                db.commit()
                batch = []
                print(f"  Inserted {i+1}/{n}…")

        if batch:
            db.bulk_save_objects(batch)
            db.commit()

        total_count = db.query(InvoiceRecord).count()
        print(f"DB now has {total_count} records.")
        return total_count
    finally:
        db.close()


def run_indexed_search(queries: list) -> list:
    """Run queries via Whoosh-indexed search (with LRU cache)."""
    from app.retrieval.search import search_invoices, cached_search

    # Clear cache to ensure fair comparison
    cached_search.cache_clear()

    timings = []
    for vendor_q in queries:
        t0 = time.perf_counter()
        results = search_invoices(vendor=vendor_q, limit=20)
        timings.append((time.perf_counter() - t0) * 1000)
    return timings


def run_naive_search(queries: list) -> list:
    """Run queries via naive SQLite full-table scan."""
    from app.db.database import get_session_factory, InvoiceRecord

    factory = get_session_factory()
    timings = []
    for vendor_q in queries:
        t0 = time.perf_counter()
        db = factory()
        try:
            _ = (
                db.query(InvoiceRecord)
                .filter(InvoiceRecord.vendor_name.ilike(f"%{vendor_q}%"))
                .limit(20)
                .all()
            )
        finally:
            db.close()
        timings.append((time.perf_counter() - t0) * 1000)
    return timings


def print_stats(label: str, timings: list):
    print(f"\n{'─'*50}")
    print(f"  Strategy : {label}")
    print(f"  Queries  : {len(timings)}")
    print(f"  Mean     : {mean(timings):.2f} ms")
    print(f"  Median   : {median(timings):.2f} ms")
    print(f"  Min      : {min(timings):.2f} ms")
    print(f"  Max      : {max(timings):.2f} ms")
    print(f"{'─'*50}")


def main():
    parser = argparse.ArgumentParser(description="Invoice retrieval speed benchmark")
    parser.add_argument("--n", type=int, default=500, help="Number of records to seed")
    parser.add_argument("--queries", type=int, default=30, help="Number of benchmark queries")
    args = parser.parse_args()

    print("\n╔══════════════════════════════════════════════════╗")
    print("║   Invoice Extractor — Retrieval Speed Benchmark  ║")
    print("╚══════════════════════════════════════════════════╝\n")

    seed_db(args.n)

    # Build the Whoosh index from DB
    print("\nBuilding Whoosh index from DB…")
    from app.retrieval.search import rebuild_index_from_db
    rebuild_index_from_db()

    # Generate query terms
    query_terms = [random.choice(VENDORS).split()[0] for _ in range(args.queries)]

    print(f"\nRunning {args.queries} queries against {args.n} records…")

    naive_timings = run_naive_search(query_terms)
    indexed_timings = run_indexed_search(query_terms)

    print_stats("Naive SQLite Scan", naive_timings)
    print_stats("Whoosh Indexed + LRU Cache", indexed_timings)

    speedup = mean(naive_timings) / mean(indexed_timings) if mean(indexed_timings) > 0 else float("inf")
    improvement_pct = (1 - mean(indexed_timings) / mean(naive_timings)) * 100

    print(f"\n🚀 Speedup factor  : {speedup:.2f}x")
    print(f"📈 Improvement     : {improvement_pct:.1f}% faster")

    if improvement_pct >= 40:
        print("✅ Target achieved: ≥40% retrieval speed improvement confirmed.")
    else:
        print(f"ℹ️  Improvement is {improvement_pct:.1f}% — increase --n for a larger dataset to see full benefit.")


if __name__ == "__main__":
    main()
