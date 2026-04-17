"""
app/nlp/extractor.py - AI-powered field extraction combining spaCy NER,
                       regex patterns, and rule-based heuristics.
"""

import re
from typing import Dict, Any, Optional

from app.config import SPACY_MODEL, NLP_CONFIDENCE_HIGH, NLP_CONFIDENCE_MEDIUM, NLP_CONFIDENCE_LOW
from app.nlp import patterns as P
from app.utils.helpers import safe_float, format_date_iso, normalize_whitespace
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Lazy spaCy load
_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load(SPACY_MODEL)
            logger.info(f"spaCy model loaded: {SPACY_MODEL}")
        except Exception as e:
            logger.warning(f"spaCy model not available ({e}). NER fallback disabled.")
            _nlp = False
    return _nlp if _nlp is not False else None


class InvoiceExtractor:
    """
    Multi-strategy field extractor for invoices.

    Priority chain per field:
    1. Regex patterns (fast, accurate for labeled fields)
    2. spaCy NER (catches unlabeled entities)
    3. Positional heuristics (last-resort keyword proximity)
    """

    def extract(self, text: str, lang_code: str = "en") -> Dict[str, Any]:
        """
        Extract all invoice fields from raw OCR text.

        Args:
            text:      Raw text from OCR engine
            lang_code: Detected language code

        Returns:
            Dictionary with extracted fields and confidence scores
        """
        text = normalize_whitespace(text)
        doc = _get_nlp()(text) if _get_nlp() else None

        fields = {}
        confidence = {}

        # ── Invoice Number ───────────────────────────────────────────────────
        inv_num, inv_conf = self._extract_invoice_number(text)
        fields["invoice_number"] = inv_num
        confidence["invoice_number"] = inv_conf

        # ── Invoice Date ─────────────────────────────────────────────────────
        inv_date, date_conf = self._extract_date(text, doc)
        fields["invoice_date"] = inv_date
        confidence["invoice_date"] = date_conf

        # ── Due Date ─────────────────────────────────────────────────────────
        due_date = P.extract_first_match(text, P.DUE_DATE_PATTERNS)
        fields["due_date"] = format_date_iso(due_date) if due_date else ""
        confidence["due_date"] = NLP_CONFIDENCE_MEDIUM if due_date else NLP_CONFIDENCE_LOW

        # ── Vendor / Seller ──────────────────────────────────────────────────
        vendor, v_conf = self._extract_vendor(text, doc)
        fields["vendor_name"] = vendor
        confidence["vendor_name"] = v_conf

        # ── Buyer / Customer ─────────────────────────────────────────────────
        buyer, b_conf = self._extract_buyer(text, doc)
        fields["buyer_name"] = buyer
        confidence["buyer_name"] = b_conf

        # ── Amounts ──────────────────────────────────────────────────────────
        total_raw = P.extract_first_match(text, P.TOTAL_PATTERNS)
        subtotal_raw = P.extract_first_match(text, P.SUBTOTAL_PATTERNS)
        tax_raw = P.extract_first_match(text, P.TAX_PATTERNS)
        discount_raw = P.extract_first_match(text, P.DISCOUNT_PATTERNS)

        fields["total_amount"] = safe_float(total_raw)
        fields["subtotal"] = safe_float(subtotal_raw)
        fields["tax_amount"] = safe_float(tax_raw) if "%" not in (tax_raw or "") else None
        fields["tax_rate"] = tax_raw if "%" in (tax_raw or "") else None
        fields["discount"] = safe_float(discount_raw)

        confidence["total_amount"] = NLP_CONFIDENCE_HIGH if total_raw else NLP_CONFIDENCE_LOW
        confidence["subtotal"] = NLP_CONFIDENCE_MEDIUM if subtotal_raw else NLP_CONFIDENCE_LOW
        confidence["tax_amount"] = NLP_CONFIDENCE_MEDIUM if tax_raw else NLP_CONFIDENCE_LOW

        # ── Currency ─────────────────────────────────────────────────────────
        fields["currency"] = self._extract_currency(text, total_raw)
        confidence["currency"] = NLP_CONFIDENCE_MEDIUM if fields["currency"] else NLP_CONFIDENCE_LOW

        # ── Tax ID ───────────────────────────────────────────────────────────
        tax_id = P.extract_first_match(text, P.TAX_ID_PATTERNS)
        fields["tax_id"] = tax_id
        confidence["tax_id"] = NLP_CONFIDENCE_HIGH if tax_id else NLP_CONFIDENCE_LOW

        # ── PO Number ────────────────────────────────────────────────────────
        po = P.extract_first_match(text, P.PO_NUMBER_PATTERNS)
        fields["po_number"] = po
        confidence["po_number"] = NLP_CONFIDENCE_HIGH if po else NLP_CONFIDENCE_LOW

        # ── Address ──────────────────────────────────────────────────────────
        addr = P.extract_first_match(text, P.ADDRESS_PATTERNS)
        fields["address"] = normalize_whitespace(addr)[:200] if addr else ""
        confidence["address"] = NLP_CONFIDENCE_MEDIUM if addr else NLP_CONFIDENCE_LOW

        # ── Payment Terms ─────────────────────────────────────────────────────
        terms = P.extract_first_match(text, P.PAYMENT_TERMS_PATTERNS)
        fields["payment_terms"] = terms
        confidence["payment_terms"] = NLP_CONFIDENCE_MEDIUM if terms else NLP_CONFIDENCE_LOW

        # ── Language ─────────────────────────────────────────────────────────
        fields["detected_language"] = lang_code

        return {"fields": fields, "confidence": confidence}

    # ─── Field-specific Extractors ───────────────────────────────────────────

    def _extract_invoice_number(self, text: str) -> tuple:
        val = P.extract_first_match(text, P.INVOICE_NUMBER_PATTERNS)
        if val:
            return val, NLP_CONFIDENCE_HIGH
        # Generic alphanumeric ID fallback
        m = re.search(r"\b([A-Z]{1,4}[-/]?\d{4,10})\b", text)
        if m:
            return m.group(1), NLP_CONFIDENCE_MEDIUM
        return "", NLP_CONFIDENCE_LOW

    def _extract_date(self, text: str, doc) -> tuple:
        val = P.extract_first_match(text, P.INVOICE_DATE_PATTERNS)
        if val:
            return format_date_iso(val), NLP_CONFIDENCE_HIGH

        # spaCy DATE entity fallback
        if doc:
            for ent in doc.ents:
                if ent.label_ == "DATE":
                    return format_date_iso(ent.text), NLP_CONFIDENCE_MEDIUM

        # Bare date fallback
        m = re.search(r"\b(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})\b", text)
        if m:
            return format_date_iso(m.group(1)), NLP_CONFIDENCE_LOW

        return "", NLP_CONFIDENCE_LOW

    def _extract_vendor(self, text: str, doc) -> tuple:
        val = P.extract_first_match(text, P.VENDOR_PATTERNS)
        if val:
            return val.strip()[:80], NLP_CONFIDENCE_HIGH

        # spaCy ORG entity at document beginning (first 500 chars)
        if doc:
            for ent in doc[:100]:  # First ~100 tokens
                if ent.ent_type_ == "ORG":
                    return ent.text.strip()[:80], NLP_CONFIDENCE_MEDIUM

        return "", NLP_CONFIDENCE_LOW

    def _extract_buyer(self, text: str, doc) -> tuple:
        val = P.extract_first_match(text, P.BUYER_PATTERNS)
        if val:
            return val.strip()[:80], NLP_CONFIDENCE_HIGH

        # Try second ORG entity in doc
        if doc:
            orgs = [ent.text for ent in doc.ents if ent.label_ == "ORG"]
            if len(orgs) >= 2:
                return orgs[1].strip()[:80], NLP_CONFIDENCE_MEDIUM

        return "", NLP_CONFIDENCE_LOW

    def _extract_currency(self, text: str, amount_str: Optional[str]) -> str:
        """Determine currency from symbol or ISO code."""
        from app.config import CURRENCY_SYMBOLS

        # From amount string
        if amount_str:
            for sym, code in CURRENCY_SYMBOLS.items():
                if sym in amount_str:
                    return code

        # From explicit currency mention in text
        val = P.extract_first_match(text, P.CURRENCY_PATTERNS)
        if val:
            for sym, code in CURRENCY_SYMBOLS.items():
                if val == sym:
                    return code
            if re.match(r"^[A-Z]{3}$", val):
                return val  # Already an ISO code

        return ""
