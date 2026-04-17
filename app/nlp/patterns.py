"""
app/nlp/patterns.py - Comprehensive regex patterns for invoice field extraction
"""

import re
from typing import Dict, List, Pattern

# ─── Invoice Number ───────────────────────────────────────────────────────────
INVOICE_NUMBER_PATTERNS: List[Pattern] = [
    re.compile(r"(?:invoice\s*(?:no|number|num|#|id)[\s:.\-#]*)([\w\-/]{3,30})", re.IGNORECASE),
    re.compile(r"(?:inv\s*(?:no|#|id|num)[\s:.\-#]*)([\w\-/]{3,30})", re.IGNORECASE),
    re.compile(r"(?:bill\s*(?:no|number|num|#)[\s:.\-#]*)([\w\-/]{3,30})", re.IGNORECASE),
    re.compile(r"(?:factura\s*(?:no|n[°º]|num)[\s:.\-#]*)([\w\-/]{3,30})", re.IGNORECASE),  # Spanish
    re.compile(r"(?:rechnung\s*(?:nr|no|num)[\s:.\-#]*)([\w\-/]{3,30})", re.IGNORECASE),    # German
    re.compile(r"(?:فاتورة\s*رقم[\s:]*)([\w\-/]{3,20})", re.IGNORECASE),                   # Arabic
    re.compile(r"\b(INV[-/]?\d{4,10})\b"),
    re.compile(r"\b([A-Z]{2,4}[-/]?\d{4,10}[-/]?[A-Z0-9]{0,6})\b"),
]

# ─── Invoice Date ─────────────────────────────────────────────────────────────
INVOICE_DATE_PATTERNS: List[Pattern] = [
    re.compile(
        r"(?:invoice\s*date|date\s*of\s*invoice|bill\s*date|issued?|date)[\s:.\-]*"
        r"(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:invoice\s*date|date\s*of\s*invoice|bill\s*date|issued?|date)[\s:.\-]*"
        r"(\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
        r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?)\s+\d{2,4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:datum|fecha|date)[\s:.\-]*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
        re.IGNORECASE,
    ),
    re.compile(r"\b(\d{4}[-/]\d{2}[-/]\d{2})\b"),  # ISO date fallback
]

DUE_DATE_PATTERNS: List[Pattern] = [
    re.compile(
        r"(?:due\s*date|payment\s*due|pay\s*by|due\s*by)[\s:.\-]*"
        r"(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
        re.IGNORECASE,
    ),
]

# ─── Vendor / Seller ─────────────────────────────────────────────────────────
VENDOR_PATTERNS: List[Pattern] = [
    re.compile(
        r"(?:from|vendor|seller|biller|company|issued\s*by|bill\s*from|sold\s*by)"
        r"[\s:.\-]*([A-Z][A-Za-z0-9\s&.,'\-]{2,50})",
        re.IGNORECASE,
    ),
]

# ─── Buyer / Customer ────────────────────────────────────────────────────────
BUYER_PATTERNS: List[Pattern] = [
    re.compile(
        r"(?:to|bill\s*to|ship\s*to|buyer|customer|client|sold\s*to)"
        r"[\s:.\-]*([A-Z][A-Za-z0-9\s&.,'\-]{2,50})",
        re.IGNORECASE,
    ),
]

# ─── Amount Patterns ─────────────────────────────────────────────────────────
_AMT = r"([\$£€₹¥₩]?\s*[\d,]+(?:\.\d{1,3})?(?:\s*(?:USD|EUR|GBP|INR|JPY|AED|SAR))?)"

TOTAL_PATTERNS: List[Pattern] = [
    re.compile(rf"(?:total|grand\s*total|amount\s*due|total\s*due|amount\s*payable)[\s:.\-]*{_AMT}", re.IGNORECASE),
    re.compile(rf"(?:gesamt|montant\s*total|importe\s*total)[\s:.\-]*{_AMT}", re.IGNORECASE),
    re.compile(rf"(?:المجموع)[\s:.\-]*{_AMT}"),
]

SUBTOTAL_PATTERNS: List[Pattern] = [
    re.compile(rf"(?:subtotal|sub\s*total|net\s*amount|net\s*total|before\s*tax)[\s:.\-]*{_AMT}", re.IGNORECASE),
]

TAX_PATTERNS: List[Pattern] = [
    re.compile(rf"(?:tax|vat|gst|igst|cgst|sgst|hst|sales\s*tax|tax\s*amount)[\s:.\-]*{_AMT}", re.IGNORECASE),
    re.compile(rf"(?:tax)[\s:.\-]*(\d+(?:\.\d+)?%)", re.IGNORECASE),
]

DISCOUNT_PATTERNS: List[Pattern] = [
    re.compile(rf"(?:discount|deduction|rebate)[\s:.\-]*{_AMT}", re.IGNORECASE),
]

# ─── Currency ─────────────────────────────────────────────────────────────────
CURRENCY_PATTERNS: List[Pattern] = [
    re.compile(r"\b(USD|EUR|GBP|INR|JPY|AED|SAR|AUD|CAD|CHF|CNY|KRW|SGD|ZAR|BRL|MXN|TRY)\b"),
    re.compile(r"([\$£€₹¥₩₺﷼])"),
    re.compile(r"(?:currency|curr)[\s:.\-]*([A-Z]{3})", re.IGNORECASE),
]

# ─── Tax ID / GST / VAT ──────────────────────────────────────────────────────
TAX_ID_PATTERNS: List[Pattern] = [
    re.compile(r"(?:gstin|gst\s*(?:no|number|id|#))[\s:.\-]*([A-Z0-9]{15})", re.IGNORECASE),
    re.compile(r"(?:vat\s*(?:no|number|reg|#))[\s:.\-]*([\w\-]{5,20})", re.IGNORECASE),
    re.compile(r"(?:tax\s*(?:id|no|number))[\s:.\-]*([\w\-]{5,20})", re.IGNORECASE),
    re.compile(r"(?:ein|tin|pan)[\s:.\-]*:?\s*([A-Z0-9\-]{9,15})", re.IGNORECASE),
    re.compile(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})\b"),  # GSTIN format
]

# ─── Address ─────────────────────────────────────────────────────────────────
ADDRESS_PATTERNS: List[Pattern] = [
    re.compile(
        r"(?:address|addr|ship\s*to|bill\s*to|location)[\s:.\-]*"
        r"((?:[A-Za-z0-9\s,.\-#/]+\n?){1,4})",
        re.IGNORECASE,
    ),
    re.compile(r"\b(\d+\s+[A-Za-z0-9\s]+(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr|Blvd|Way)\.?[,\s]*[A-Za-z\s,\d]+)", re.IGNORECASE),
]

# ─── Payment Terms ────────────────────────────────────────────────────────────
PAYMENT_TERMS_PATTERNS: List[Pattern] = [
    re.compile(r"(?:payment\s*terms?|terms?)[\s:.\-]*((?:net|due|within|on\s*receipt)[^.\n]{0,40})", re.IGNORECASE),
    re.compile(r"\b(net\s*\d+|net30|net60|net90|due\s*on\s*receipt|immediate(?:ly)?|prepaid)\b", re.IGNORECASE),
    re.compile(r"\b(\d+\s*days?\s*(?:from|after|net)?)\b", re.IGNORECASE),
]

# ─── PO Number ────────────────────────────────────────────────────────────────
PO_NUMBER_PATTERNS: List[Pattern] = [
    re.compile(r"(?:p\.?o\.?\s*(?:no|number|#)|purchase\s*order\s*(?:no|#|number))[\s:.\-]*([\w\-]{3,20})", re.IGNORECASE),
]


def extract_first_match(text: str, patterns: List[Pattern]) -> str:
    """
    Return the first capture group match from a list of patterns.

    Args:
        text:     Raw text to search
        patterns: Ordered list of compiled regex patterns

    Returns:
        Matched string or empty string
    """
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return ""


def extract_all_matches(text: str, patterns: List[Pattern]) -> List[str]:
    """Return all non-overlapping matches from a list of patterns."""
    results = []
    for pattern in patterns:
        results.extend(m.group(1).strip() for m in pattern.finditer(text))
    return list(dict.fromkeys(results))  # Deduplicate while preserving order
