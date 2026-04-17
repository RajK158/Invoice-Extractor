"""
app/streamlit_app.py - Multi-Language Invoice Extractor — Streamlit Frontend

A production-style AI application that extracts structured data from
multilingual invoice images and PDFs using OCR + NLP + rule-based validation.
"""

import io
import json
import time
from pathlib import Path

import pandas as pd
import streamlit as st

# ─── Page config (must be first Streamlit call) ───────────────────────────────
st.set_page_config(
    page_title="Invoice Extractor AI",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Inject custom CSS ────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
}

/* Background */
.stApp {
    background: #0f1117;
    color: #e8eaf0;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #161b27;
    border-right: 1px solid #2a2f3e;
}

/* Cards */
.inv-card {
    background: #1a1f2e;
    border: 1px solid #2a3045;
    border-radius: 10px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 1rem;
}
.inv-card-header {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.75rem;
    color: #6b7a99;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.5rem;
}
.inv-card-value {
    font-size: 1.4rem;
    font-weight: 700;
    color: #e8eaf0;
}

/* Confidence badges */
.badge-high   { background: #0f4c3a; color: #4ade80; padding: 2px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
.badge-medium { background: #4a3000; color: #fbbf24; padding: 2px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
.badge-low    { background: #4a1010; color: #f87171; padding: 2px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }

/* Status pills */
.status-passed  { background: #0f4c3a; color: #4ade80; padding: 4px 14px; border-radius: 20px; font-weight: 600; }
.status-warning { background: #4a3000; color: #fbbf24; padding: 4px 14px; border-radius: 20px; font-weight: 600; }
.status-failed  { background: #4a1010; color: #f87171; padding: 4px 14px; border-radius: 20px; font-weight: 600; }

/* Field table */
.field-table { width: 100%; border-collapse: collapse; }
.field-table th { background: #1e2435; color: #6b7a99; font-size: 0.7rem; text-transform: uppercase; padding: 8px 12px; text-align: left; border-bottom: 1px solid #2a3045; }
.field-table td { padding: 10px 12px; border-bottom: 1px solid #1e2435; font-size: 0.9rem; vertical-align: top; }
.field-table tr:hover td { background: #1e2435; }

/* Metric blocks */
.metric-block { text-align: center; padding: 1rem; background: #1a1f2e; border: 1px solid #2a3045; border-radius: 10px; }
.metric-number { font-family: 'IBM Plex Mono', monospace; font-size: 2rem; font-weight: 700; color: #60a5fa; }
.metric-label { font-size: 0.75rem; color: #6b7a99; margin-top: 4px; }

/* Progress bar */
.conf-bar-outer { height: 6px; background: #2a3045; border-radius: 3px; }
.conf-bar-inner { height: 6px; border-radius: 3px; }

/* Hide default Streamlit chrome */
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }
</style>
""", unsafe_allow_html=True)


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🧾 Invoice Extractor AI")
    st.markdown("*Multilingual · AI-Powered · Fast Retrieval*")
    st.divider()
    page = st.radio(
        "Navigation",
        ["📤 Upload Invoice", "📦 Batch Process", "📋 View Results",
         "✅ Validation Report", "🔍 Search Invoices",
         "📊 Analytics", "💾 Export Data"],
        label_visibility="collapsed",
    )
    st.divider()
    st.markdown("""
    <div style="font-size:0.72rem;color:#6b7a99;line-height:1.7">
    <b>Tech Stack</b><br>
    OCR: Tesseract + EasyOCR<br>
    NLP: spaCy + Transformers<br>
    Search: Whoosh + LRU Cache<br>
    DB: SQLite + SQLAlchemy<br>
    API: FastAPI<br>
    </div>
    """, unsafe_allow_html=True)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def conf_badge(score: float) -> str:
    if score is None:
        return ""
    if score >= 0.85:
        return f'<span class="badge-high">High {score:.0%}</span>'
    elif score >= 0.60:
        return f'<span class="badge-medium">Med {score:.0%}</span>'
    else:
        return f'<span class="badge-low">Low {score:.0%}</span>'


def status_pill(status: str) -> str:
    cls = {"PASSED": "status-passed", "WARNING": "status-warning", "FAILED": "status-failed"}.get(status, "status-warning")
    return f'<span class="{cls}">{status}</span>'


def conf_bar(score: float) -> str:
    pct = int((score or 0) * 100)
    color = "#4ade80" if pct >= 85 else "#fbbf24" if pct >= 60 else "#f87171"
    return (f'<div class="conf-bar-outer"><div class="conf-bar-inner" '
            f'style="width:{pct}%;background:{color}"></div></div>')


@st.cache_resource
def get_db_session():
    """Cached DB session factory."""
    from app.db.database import get_session_factory
    return get_session_factory()


def load_records(limit: int = 500) -> list:
    from app.db.database import get_all_invoices
    factory = get_db_session()
    db = factory()
    try:
        return get_all_invoices(db, limit=limit)
    finally:
        db.close()


def records_to_df(records: list) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    return pd.DataFrame([r.to_dict() if hasattr(r, "to_dict") else r for r in records])


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: Upload Invoice
# ═══════════════════════════════════════════════════════════════════════════════
if page == "📤 Upload Invoice":
    st.markdown("## Upload Invoice")
    st.markdown("Upload a single invoice (image or PDF) for AI-powered extraction.")

    uploaded = st.file_uploader(
        "Drop your invoice here",
        type=["jpg", "jpeg", "png", "tiff", "tif", "bmp", "pdf"],
        help="Supports English and regional language invoices",
    )

    col_l, col_r = st.columns([1, 1])
    if uploaded:
        with col_l:
            st.markdown("#### Preview")
            suffix = Path(uploaded.name).suffix.lower()
            if suffix in {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"}:
                from PIL import Image
                img = Image.open(uploaded)
                st.image(img, use_container_width=True, caption=uploaded.name)
            else:
                st.info(f"PDF uploaded: **{uploaded.name}** ({uploaded.size/1024:.1f} KB)")

        with col_r:
            st.markdown("#### Extraction")
            if st.button("🚀 Extract Data", type="primary", use_container_width=True):
                with st.spinner("Running OCR + NLP pipeline…"):
                    from app.processing.pipeline import process_bytes
                    uploaded.seek(0)
                    file_bytes = uploaded.read()
                    result = process_bytes(file_bytes, uploaded.name, suffix)

                if not result.success:
                    st.error(f"Extraction failed: {result.error}")
                else:
                    st.success(f"Extracted in **{result.processing_time_ms:.0f} ms** · Engine: `{result.ocr_engine}`")
                    st.session_state["last_result"] = result

    if "last_result" in st.session_state:
        result = st.session_state["last_result"]
        fields = result.fields
        conf = result.confidence

        st.divider()
        st.markdown("### Extracted Fields")

        # Summary metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Invoice #", fields.get("invoice_number") or "—")
        c2.metric("Date", fields.get("invoice_date") or "—")
        c3.metric("Total", f"{fields.get('currency', '')} {fields.get('total_amount') or '—'}")
        c4.metric("Language", fields.get("detected_language", "en").upper())

        st.markdown("#### All Fields")
        rows_html = ""
        display_fields = [
            ("vendor_name", "Vendor"), ("buyer_name", "Buyer"),
            ("invoice_number", "Invoice #"), ("invoice_date", "Invoice Date"),
            ("due_date", "Due Date"), ("total_amount", "Total"),
            ("subtotal", "Subtotal"), ("tax_amount", "Tax"),
            ("tax_rate", "Tax Rate"), ("discount", "Discount"),
            ("currency", "Currency"), ("tax_id", "Tax ID"),
            ("po_number", "PO #"), ("payment_terms", "Payment Terms"),
            ("address", "Address"),
        ]
        for key, label in display_fields:
            val = fields.get(key)
            score = conf.get(key, 0)
            rows_html += (
                f"<tr><td><b>{label}</b></td>"
                f"<td>{val if val is not None else '—'}</td>"
                f"<td>{conf_badge(score)}</td>"
                f"<td style='min-width:100px'>{conf_bar(score)}</td></tr>"
            )
        st.markdown(
            f'<table class="field-table"><thead><tr>'
            f"<th>Field</th><th>Value</th><th>Confidence</th><th></th>"
            f"</tr></thead><tbody>{rows_html}</tbody></table>",
            unsafe_allow_html=True,
        )

        # Validation
        st.markdown("### Validation")
        val = result.validation
        st.markdown(f"**Status:** {status_pill(val['status'])}", unsafe_allow_html=True)
        if val.get("errors"):
            for e in val["errors"]:
                st.error(f"❌ {e}")
        if val.get("warnings"):
            for w in val["warnings"]:
                st.warning(f"⚠️ {w}")
        if val.get("passed"):
            with st.expander(f"✅ {len(val['passed'])} checks passed"):
                for p in val["passed"]:
                    st.success(p)

        # Raw text
        with st.expander("📄 Raw OCR Text"):
            st.text_area("OCR Output", result.raw_text, height=200, label_visibility="collapsed")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: Batch Process
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "📦 Batch Process":
    st.markdown("## Batch Processing")
    st.markdown("Upload multiple invoices for parallel AI extraction.")

    uploaded_files = st.file_uploader(
        "Upload invoices (multiple files supported)",
        type=["jpg", "jpeg", "png", "tiff", "tif", "bmp", "pdf"],
        accept_multiple_files=True,
    )

    workers = st.slider("Parallel workers", 1, 8, 4)

    if uploaded_files and st.button("🚀 Process All", type="primary"):
        import tempfile, os
        from app.processing.pipeline import process_batch

        progress = st.progress(0)
        status_text = st.empty()
        results_container = st.empty()

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            for f in uploaded_files:
                (tmp_path / f.name).write_bytes(f.read())

            status_text.text(f"Processing {len(uploaded_files)} invoices with {workers} workers…")
            t0 = time.time()
            results = process_batch(tmp_path, max_workers=workers)
            elapsed = time.time() - t0

        progress.progress(1.0)
        status_text.empty()

        success_count = sum(1 for r in results if r.success)
        st.success(f"✅ Processed **{success_count}/{len(results)}** invoices in **{elapsed:.1f}s**")

        st.session_state["batch_results"] = results

    if "batch_results" in st.session_state:
        results = st.session_state["batch_results"]
        rows = []
        for r in results:
            rows.append({
                "Filename": r.filename,
                "Status": r.validation.get("status", "—"),
                "Invoice #": r.fields.get("invoice_number", ""),
                "Vendor": r.fields.get("vendor_name", ""),
                "Total": r.fields.get("total_amount", ""),
                "Currency": r.fields.get("currency", ""),
                "Language": r.fields.get("detected_language", ""),
                "OCR Conf": f"{r.ocr_confidence:.0%}",
                "Time (ms)": r.processing_time_ms,
                "Error": r.error or "",
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, height=400)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: View Results
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "📋 View Results":
    st.markdown("## Processed Invoices")

    records = load_records(limit=500)
    if not records:
        st.info("No invoices processed yet. Upload some invoices first.")
    else:
        df = records_to_df(records)
        display_cols = [
            "id", "filename", "invoice_number", "invoice_date", "vendor_name",
            "total_amount", "currency", "detected_language", "validation_status",
            "avg_field_confidence", "processed_at",
        ]
        df_display = df[[c for c in display_cols if c in df.columns]]
        st.markdown(f"**{len(df)} invoices** in database")
        st.dataframe(df_display, use_container_width=True, height=500)

        # Detail view
        st.divider()
        st.markdown("### Invoice Detail")
        invoice_ids = df["id"].tolist()
        selected_id = st.selectbox("Select Invoice ID", invoice_ids)
        selected_row = df[df["id"] == selected_id].iloc[0].to_dict()

        col1, col2 = st.columns(2)
        with col1:
            for field in ["invoice_number", "invoice_date", "due_date", "vendor_name", "buyer_name"]:
                st.text_input(field.replace("_", " ").title(), value=str(selected_row.get(field) or ""), disabled=True)
        with col2:
            for field in ["total_amount", "subtotal", "tax_amount", "currency", "payment_terms"]:
                st.text_input(field.replace("_", " ").title(), value=str(selected_row.get(field) or ""), disabled=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: Validation Report
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "✅ Validation Report":
    st.markdown("## Validation Report")

    records = load_records()
    if not records:
        st.info("No invoices to validate yet.")
    else:
        df = records_to_df(records)

        # Summary
        status_counts = df["validation_status"].value_counts()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total", len(df))
        c2.metric("✅ Passed", status_counts.get("PASSED", 0))
        c3.metric("⚠️ Warnings", status_counts.get("WARNING", 0))
        c4.metric("❌ Failed", status_counts.get("FAILED", 0))

        st.divider()
        failed = df[df["validation_status"] == "FAILED"]
        warnings = df[df["validation_status"] == "WARNING"]

        tab1, tab2, tab3 = st.tabs(["❌ Failures", "⚠️ Warnings", "✅ Passed"])

        with tab1:
            if failed.empty:
                st.success("No validation failures!")
            else:
                cols = ["id", "filename", "invoice_number", "vendor_name", "total_amount"]
                st.dataframe(failed[[c for c in cols if c in failed.columns]], use_container_width=True)
                for _, row in failed.iterrows():
                    try:
                        report = json.loads(row.get("validation_report") or "{}")
                        for err in report.get("errors", []):
                            st.error(f"[{row['filename']}] {err}")
                    except Exception:
                        pass

        with tab2:
            if warnings.empty:
                st.info("No warnings!")
            else:
                cols = ["id", "filename", "invoice_number", "vendor_name"]
                st.dataframe(warnings[[c for c in cols if c in warnings.columns]], use_container_width=True)

        with tab3:
            passed = df[df["validation_status"] == "PASSED"]
            cols = ["id", "filename", "invoice_number", "invoice_date", "vendor_name", "total_amount"]
            st.dataframe(passed[[c for c in cols if c in passed.columns]], use_container_width=True)

        # Duplicates section
        dups = df[df.get("is_duplicate", pd.Series([False]*len(df)))]
        if not dups.empty:
            st.divider()
            st.warning(f"⚠️ {len(dups)} duplicate invoice(s) detected")
            st.dataframe(dups[["id", "filename", "invoice_number", "vendor_name"]], use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: Search Invoices
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "🔍 Search Invoices":
    st.markdown("## Search Invoices")
    st.markdown("Full-text search powered by Whoosh index + LRU cache (~40% faster than naive scan)")

    with st.form("search_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            q = st.text_input("Keyword", placeholder="vendor name, invoice #, any text…")
            vendor = st.text_input("Vendor filter")
        with col2:
            currency = st.selectbox("Currency", ["", "USD", "EUR", "GBP", "INR", "JPY", "AED", "AUD", "CAD"])
            language = st.selectbox("Language", ["", "en", "hi", "ar", "fr", "de", "es", "zh", "ja"])
        with col3:
            status_filter = st.selectbox("Validation Status", ["", "PASSED", "WARNING", "FAILED"])
            min_amt = st.number_input("Min Amount", min_value=0.0, value=0.0)
            max_amt = st.number_input("Max Amount", min_value=0.0, value=0.0)

        submitted = st.form_submit_button("🔍 Search", type="primary")

    if submitted:
        from app.retrieval.search import search_invoices
        t0 = time.perf_counter()
        results = search_invoices(
            query_str=q, vendor=vendor, currency=currency,
            language=language, validation_status=status_filter,
            min_amount=min_amt if min_amt > 0 else None,
            max_amount=max_amt if max_amt > 0 else None,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        st.success(f"Found **{len(results)}** results in **{elapsed_ms:.1f} ms** (indexed search)")

        if results:
            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True, height=400)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: Analytics
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "📊 Analytics":
    st.markdown("## Analytics Dashboard")

    from app.db.database import get_analytics
    factory = get_db_session()
    db = factory()
    try:
        stats = get_analytics(db)
    finally:
        db.close()

    # Top metrics
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Invoices Processed", stats["total_invoices"])
    c2.metric("Avg Confidence", f"{stats['avg_confidence']:.0%}")
    c3.metric("Total Value", f"${stats['total_amount_processed']:,.0f}")
    c4.metric("Duplicates", stats["duplicate_count"])
    c5.metric("Languages", len(stats["by_language"]))

    st.divider()

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("### Language Distribution")
        if stats["by_language"]:
            lang_df = pd.DataFrame(
                list(stats["by_language"].items()),
                columns=["Language", "Count"]
            ).sort_values("Count", ascending=False)
            st.bar_chart(lang_df.set_index("Language"))
        else:
            st.info("No language data yet")

    with col_r:
        st.markdown("### Validation Status")
        if stats["by_validation_status"]:
            status_df = pd.DataFrame(
                list(stats["by_validation_status"].items()),
                columns=["Status", "Count"]
            )
            st.bar_chart(status_df.set_index("Status"))
        else:
            st.info("No validation data yet")

    # Records table
    st.divider()
    st.markdown("### Recent Activity")
    records = load_records(limit=10)
    if records:
        df = records_to_df(records)
        cols = ["id", "filename", "invoice_date", "vendor_name", "total_amount", "currency", "validation_status", "processed_at"]
        st.dataframe(df[[c for c in cols if c in df.columns]], use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: Export Data
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "💾 Export Data":
    st.markdown("## Export Data")
    st.markdown("Download all processed invoices in your preferred format.")

    records = load_records(limit=10000)

    if not records:
        st.info("No invoices to export yet.")
    else:
        from app.exports.exporter import to_csv_bytes, to_json_bytes
        record_dicts = [r.to_dict() for r in records]

        st.markdown(f"**{len(record_dicts)} invoices** ready for export")
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### CSV Export")
            st.markdown("Excel-compatible CSV with UTF-8 BOM encoding")
            csv_bytes = to_csv_bytes(record_dicts)
            st.download_button(
                "⬇️ Download CSV",
                data=csv_bytes,
                file_name="invoices_export.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col2:
            st.markdown("### JSON Export")
            st.markdown("Structured JSON for API integration or further processing")
            json_bytes = to_json_bytes(record_dicts)
            st.download_button(
                "⬇️ Download JSON",
                data=json_bytes,
                file_name="invoices_export.json",
                mime="application/json",
                use_container_width=True,
            )

        st.divider()
        st.markdown("### Preview")
        df = records_to_df(records)
        st.dataframe(df.head(20), use_container_width=True)
