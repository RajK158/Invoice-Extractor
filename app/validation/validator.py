"""
app/validation/validator.py - Rule-based consistency checks and field validation
"""

import re
from datetime import datetime
from typing import Dict, Any, List

from app.config import (
    TAX_TOTAL_TOLERANCE, MANDATORY_FIELDS,
    INVOICE_NUMBER_MIN_LEN, INVOICE_NUMBER_MAX_LEN,
)
from app.utils.helpers import parse_date
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ValidationResult:
    """Structured validation report for a single invoice."""

    def __init__(self):
        self.passed: List[str] = []
        self.warnings: List[str] = []
        self.errors: List[str] = []
        self.is_duplicate: bool = False

    @property
    def status(self) -> str:
        if self.errors:
            return "FAILED"
        if self.warnings:
            return "WARNING"
        return "PASSED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "passed": self.passed,
            "warnings": self.warnings,
            "errors": self.errors,
            "is_duplicate": self.is_duplicate,
        }


class InvoiceValidator:
    """
    Applies rule-based checks to extracted invoice fields.

    Checks:
    - Mandatory field presence
    - Invoice number format
    - Date validity and future-date detection
    - Arithmetic consistency: subtotal + tax ≈ total
    - Currency format
    - Duplicate detection
    """

    def __init__(self, db_session=None):
        """
        Args:
            db_session: Optional DB session for duplicate detection queries
        """
        self.db_session = db_session

    def validate(self, fields: Dict[str, Any], invoice_id: int = None) -> ValidationResult:
        """
        Run all validation rules against extracted fields.

        Args:
            fields:     Extracted invoice fields dict
            invoice_id: Current invoice DB ID (for duplicate detection)

        Returns:
            ValidationResult instance
        """
        result = ValidationResult()

        self._check_mandatory_fields(fields, result)
        self._check_invoice_number(fields, result)
        self._check_dates(fields, result)
        self._check_amounts(fields, result)
        self._check_currency(fields, result)
        if self.db_session and invoice_id:
            self._check_duplicates(fields, invoice_id, result)

        logger.debug(f"Validation: {result.status} | {len(result.errors)} errors, {len(result.warnings)} warnings")
        return result

    # ─── Individual Checks ───────────────────────────────────────────────────

    def _check_mandatory_fields(self, fields: dict, result: ValidationResult):
        """Flag missing mandatory fields."""
        for field in MANDATORY_FIELDS:
            val = fields.get(field)
            if val is None or str(val).strip() == "" or val == 0:
                result.errors.append(f"Missing mandatory field: '{field}'")
            else:
                result.passed.append(f"Mandatory field present: '{field}'")

    def _check_invoice_number(self, fields: dict, result: ValidationResult):
        """Validate invoice number length and format."""
        inv_num = str(fields.get("invoice_number", "") or "")
        if not inv_num:
            return  # Already caught by mandatory check

        if len(inv_num) < INVOICE_NUMBER_MIN_LEN:
            result.warnings.append(f"Invoice number '{inv_num}' is suspiciously short")
        elif len(inv_num) > INVOICE_NUMBER_MAX_LEN:
            result.warnings.append(f"Invoice number '{inv_num}' exceeds expected length")
        else:
            result.passed.append("Invoice number format valid")

        # Must contain at least one digit or letter
        if not re.search(r"[A-Za-z0-9]", inv_num):
            result.errors.append(f"Invoice number '{inv_num}' contains no alphanumeric characters")

    def _check_dates(self, fields: dict, result: ValidationResult):
        """Validate date fields for parseability and logical order."""
        inv_date_str = fields.get("invoice_date", "")
        due_date_str = fields.get("due_date", "")

        inv_date = parse_date(str(inv_date_str)) if inv_date_str else None
        due_date = parse_date(str(due_date_str)) if due_date_str else None

        if inv_date_str and not inv_date:
            result.warnings.append(f"Could not parse invoice date: '{inv_date_str}'")
        elif inv_date:
            # Future invoice date warning
            if inv_date > datetime.now():
                result.warnings.append(f"Invoice date {inv_date_str} is in the future")
            # Very old invoice warning
            elif inv_date.year < 2000:
                result.warnings.append(f"Invoice date {inv_date_str} may be incorrect (year < 2000)")
            else:
                result.passed.append("Invoice date is valid")

        if inv_date and due_date:
            if due_date < inv_date:
                result.errors.append("Due date is before invoice date — logically inconsistent")
            else:
                result.passed.append("Due date is after invoice date")

    def _check_amounts(self, fields: dict, result: ValidationResult):
        """Check arithmetic consistency: subtotal + tax ≈ total."""
        total = fields.get("total_amount")
        subtotal = fields.get("subtotal")
        tax = fields.get("tax_amount")

        if total is not None and total <= 0:
            result.errors.append(f"Total amount is non-positive: {total}")
        elif total is not None:
            result.passed.append(f"Total amount present: {total}")

        if subtotal is not None and tax is not None and total is not None:
            expected = subtotal + tax
            diff = abs(expected - total)
            tolerance = total * TAX_TOTAL_TOLERANCE
            if diff > tolerance:
                result.warnings.append(
                    f"Arithmetic inconsistency: subtotal ({subtotal}) + tax ({tax}) = "
                    f"{expected:.2f} but total is {total} (diff={diff:.2f})"
                )
            else:
                result.passed.append("Subtotal + tax ≈ total (arithmetic consistent)")

        # Sanity checks
        if subtotal is not None and total is not None and subtotal > total:
            result.warnings.append(f"Subtotal ({subtotal}) exceeds total ({total})")

        if tax is not None and tax < 0:
            result.warnings.append(f"Tax amount is negative: {tax}")

    def _check_currency(self, fields: dict, result: ValidationResult):
        """Validate currency code format."""
        currency = fields.get("currency", "")
        if currency:
            if not re.match(r"^[A-Z]{3}$", str(currency)):
                result.warnings.append(f"Non-standard currency format: '{currency}'")
            else:
                result.passed.append(f"Currency code valid: {currency}")

    def _check_duplicates(self, fields: dict, current_id: int, result: ValidationResult):
        """
        Check if an invoice with the same number/vendor/date already exists.
        Uses the DB session for a lightweight SQL query.
        """
        try:
            from app.db.database import InvoiceRecord
            inv_num = fields.get("invoice_number", "")
            vendor = fields.get("vendor_name", "")

            if inv_num and self.db_session:
                existing = (
                    self.db_session.query(InvoiceRecord)
                    .filter(
                        InvoiceRecord.invoice_number == inv_num,
                        InvoiceRecord.id != current_id,
                    )
                    .first()
                )
                if existing:
                    result.is_duplicate = True
                    result.warnings.append(
                        f"Duplicate invoice number '{inv_num}' found (ID: {existing.id})"
                    )
        except Exception as e:
            logger.debug(f"Duplicate check skipped: {e}")
