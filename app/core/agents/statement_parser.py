"""
app/core/agents/statement_parser.py
─────────────────────────────────────────────────────────
Phase 1 — Statement Parser

Extracts transaction data from:
  • MTN Mobile Money PDF statements
  • Airtel Money PDF statements
  • Stanbic Bank / Centenary Bank PDF statements
  • Any plain-text-readable PDF (best-effort)
  • PNG/JPG screenshots (requires pytesseract)

Returns a StatementResult dataclass with:
  - all transactions as a list
  - monthly income/expense totals
  - detected statement type
  - date range covered
  - raw text for debugging

Usage:
    result = StatementParser.parse("path/to/statement.pdf")
    print(result.avg_monthly_income)
    print(result.transactions)
"""

import re
import os
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional
from decimal import Decimal


@dataclass
class Transaction:
    """Single debit or credit transaction from a statement."""
    date:        date
    description: str
    amount:      Decimal
    tx_type:     str          # "credit" or "debit"
    balance:     Optional[Decimal] = None
    reference:   Optional[str]     = None


@dataclass
class StatementResult:
    """Full result from parsing a financial statement."""
    source_type:         str                    # "mtn", "airtel", "bank", "unknown"
    owner_name:          str                    = "Unknown"
    phone_or_account:    str                    = ""
    statement_from:      Optional[date]         = None
    statement_to:        Optional[date]         = None
    transactions:        list                   = field(default_factory=list)
    parse_errors:        list                   = field(default_factory=list)
    raw_text:            str                    = ""

    # Computed after parsing
    total_credits:       Decimal                = Decimal("0")
    total_debits:        Decimal                = Decimal("0")
    months_covered:      int                    = 1
    avg_monthly_income:  Decimal                = Decimal("0")
    avg_monthly_expense: Decimal                = Decimal("0")
    net_monthly_flow:    Decimal                = Decimal("0")
    income_consistency:  str                    = "UNKNOWN"   # HIGH / MEDIUM / LOW

    def compute_summary(self):
        """Calculate income/expense summaries from the transaction list."""
        if not self.transactions:
            return

        credits = [t.amount for t in self.transactions if t.tx_type == "credit"]
        debits  = [t.amount for t in self.transactions if t.tx_type == "debit"]

        self.total_credits = sum(credits, Decimal("0"))
        self.total_debits  = sum(debits,  Decimal("0"))

        # Determine months covered
        if self.statement_from and self.statement_to:
            delta = (self.statement_to - self.statement_from).days
            self.months_covered = max(1, round(delta / 30))
        else:
            # Guess from transaction dates
            dates = [t.date for t in self.transactions]
            if dates:
                delta = (max(dates) - min(dates)).days
                self.months_covered = max(1, round(delta / 30))

        self.avg_monthly_income  = self.total_credits / self.months_covered
        self.avg_monthly_expense = self.total_debits  / self.months_covered
        self.net_monthly_flow    = self.avg_monthly_income - self.avg_monthly_expense

        # Income consistency: look at spread of monthly credit totals
        self._compute_income_consistency(credits)

    def _compute_income_consistency(self, credit_amounts: list):
        """Rate how consistent the income stream is."""
        if not credit_amounts:
            self.income_consistency = "LOW"
            return
        if len(credit_amounts) < 3:
            self.income_consistency = "MEDIUM"
            return

        amounts = [float(a) for a in credit_amounts]
        mean    = sum(amounts) / len(amounts)
        if mean == 0:
            self.income_consistency = "LOW"
            return

        variance = sum((a - mean) ** 2 for a in amounts) / len(amounts)
        cv = (variance ** 0.5) / mean   # coefficient of variation

        if cv < 0.25:
            self.income_consistency = "HIGH"     # very regular — likely salary
        elif cv < 0.60:
            self.income_consistency = "MEDIUM"   # some variation — small business
        else:
            self.income_consistency = "LOW"      # very irregular — casual income


class StatementParser:
    """
    Main parser class. Detects statement format and routes to the
    correct extraction method.
    """

    # ── Amount patterns ──────────────────────────────────────────────────────
    # Matches: 1,234,567  or  1234567  or  1,234,567.50
    _AMOUNT_RE = re.compile(r"[\d]{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?")

    # ── Date patterns ────────────────────────────────────────────────────────
    _DATE_PATTERNS = [
        (re.compile(r"\b(\d{2})[/-](\d{2})[/-](\d{4})\b"), "%d/%m/%Y"),
        (re.compile(r"\b(\d{4})[/-](\d{2})[/-](\d{2})\b"), "%Y/%m/%d"),
        (re.compile(r"\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(\d{4})\b", re.I), "dmy_month"),
    ]

    @classmethod
    def parse(cls, file_path: str) -> StatementResult:
        """
        Parse a statement file and return a StatementResult.

        Supports: .pdf, .png, .jpg, .jpeg
        """
        if not os.path.exists(file_path):
            result = StatementResult(source_type="error")
            result.parse_errors.append(f"File not found: {file_path}")
            return result

        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".pdf":
            return cls._parse_pdf(file_path)
        elif ext in (".png", ".jpg", ".jpeg", ".bmp", ".tiff"):
            return cls._parse_image(file_path)
        else:
            result = StatementResult(source_type="unknown")
            result.parse_errors.append(f"Unsupported file type: {ext}")
            return result

    # ── PDF parsing ───────────────────────────────────────────────────────────

    @classmethod
    def _parse_pdf(cls, path: str) -> StatementResult:
        try:
            import pdfplumber
        except ImportError:
            r = StatementResult(source_type="error")
            r.parse_errors.append("pdfplumber not installed. Run: pip install pdfplumber")
            return r

        try:
            with pdfplumber.open(path) as pdf:
                full_text = "\n".join(
                    page.extract_text() or "" for page in pdf.pages
                )
        except Exception as e:
            r = StatementResult(source_type="error")
            r.parse_errors.append(f"PDF read error: {e}")
            return r

        source_type = cls._detect_source(full_text)
        result      = StatementResult(source_type=source_type, raw_text=full_text)

        cls._extract_owner(result, full_text)
        cls._extract_date_range(result, full_text)
        cls._extract_transactions(result, full_text)
        result.compute_summary()
        return result

    # ── Image parsing (OCR) ───────────────────────────────────────────────────

    @classmethod
    def _parse_image(cls, path: str) -> StatementResult:
        try:
            import pytesseract
            from PIL import Image
            img  = Image.open(path)
            text = pytesseract.image_to_string(img)
        except ImportError:
            r = StatementResult(source_type="error")
            r.parse_errors.append(
                "pytesseract not installed. Run: pip install pytesseract\n"
                "Also install Tesseract OCR: sudo apt-get install tesseract-ocr")
            return r
        except Exception as e:
            r = StatementResult(source_type="error")
            r.parse_errors.append(f"Image read error: {e}")
            return r

        source_type = cls._detect_source(text)
        result      = StatementResult(source_type=source_type, raw_text=text)
        cls._extract_owner(result, text)
        cls._extract_date_range(result, text)
        cls._extract_transactions(result, text)
        result.compute_summary()
        return result

    # ── Detection and extraction ──────────────────────────────────────────────

    @classmethod
    def _detect_source(cls, text: str) -> str:
        t = text.lower()
        if "mtn"    in t and ("mobile money" in t or "momo" in t):
            return "mtn"
        if "airtel" in t and ("money" in t or "airtel money" in t):
            return "airtel"
        if "stanbic" in t:
            return "stanbic"
        if "centenary" in t:
            return "centenary"
        if "bank statement" in t or "account statement" in t:
            return "bank"
        return "unknown"

    @classmethod
    def _extract_owner(cls, result: StatementResult, text: str):
        # Look for "Name:" or "Account Name:" or "Customer:" patterns
        patterns = [
            r"(?:name|account\s+name|customer\s+name|subscriber)[:\s]+([A-Z][A-Z\s]{3,40})",
            r"(?:dear|hello)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.I)
            if m:
                result.owner_name = m.group(1).strip().title()
                break

        # Phone number
        phone = re.search(r"(?:07|2567|256\s*7)\d{8}", text)
        if phone:
            result.phone_or_account = phone.group(0).strip()

    @classmethod
    def _extract_date_range(cls, result: StatementResult, text: str):
        # Look for "From: ... To: ..." or "Period: ... to ..."
        period_pat = re.search(
            r"(?:from|period|statement\s+date)[:\s]+(\d{1,2}[/-]\d{2}[/-]\d{4})"
            r".*?(?:to|through)[:\s]+(\d{1,2}[/-]\d{2}[/-]\d{4})",
            text, re.I | re.S)
        if period_pat:
            result.statement_from = cls._parse_date(period_pat.group(1))
            result.statement_to   = cls._parse_date(period_pat.group(2))

    @classmethod
    def _extract_transactions(cls, result: StatementResult, text: str):
        """
        Extract transactions from statement text.
        Handles two common formats:
        Format A (MoMo): date | description | amount | balance
        Format B (Bank): date | description | debit | credit | balance
        """
        lines = text.split("\n")

        for line in lines:
            line = line.strip()
            if not line or len(line) < 10:
                continue

            # Skip header/footer lines
            skip_words = ["transaction", "date", "description", "balance",
                          "debit", "credit", "total", "opening", "closing",
                          "statement", "page", "continued"]
            if any(line.lower().startswith(w) for w in skip_words):
                continue

            # Try to detect a date at the start of the line
            tx_date = cls._extract_leading_date(line)
            if not tx_date:
                continue

            amounts = cls._AMOUNT_RE.findall(line)
            if not amounts:
                continue

            # Determine credit vs debit from keywords
            line_lower = line.lower()
            is_credit = any(w in line_lower for w in [
                "received", "deposit", "credit", "payment in",
                "transferred in", "cash in", "salary", "airtime purchase reversal",
                "incoming", "reversal"
            ])
            is_debit = any(w in line_lower for w in [
                "sent", "paid", "withdrawal", "debit", "transferred out",
                "cash out", "charge", "fee", "tax", "payment out", "outgoing"
            ])

            if not is_credit and not is_debit:
                # Guess from position — last amount is usually balance
                # second-to-last is the transaction amount
                is_debit = True  # safe default

            # Parse the primary amount (largest non-balance number)
            try:
                parsed_amounts = [
                    Decimal(str(a).replace(",", ""))
                    for a in amounts
                    if a and str(a).replace(",", "").replace(".", "").isdigit()
                ]
                if not parsed_amounts:
                    continue
                amount = max(parsed_amounts)   # largest is usually the tx amount
            except Exception:
                continue

            if amount <= 0:
                continue

            # Build description from the non-numeric parts
            desc = re.sub(r"[\d,./]+", " ", line).strip()
            desc = re.sub(r"\s{2,}", " ", desc)[:100]

            tx = Transaction(
                date        = tx_date,
                description = desc,
                amount      = amount,
                tx_type     = "credit" if is_credit else "debit",
            )
            result.transactions.append(tx)

    @classmethod
    def _extract_leading_date(cls, line: str) -> Optional[date]:
        """Try to parse a date from the beginning of a text line."""
        # Try DD/MM/YYYY or DD-MM-YYYY at start
        m = re.match(r"^(\d{2})[/-](\d{2})[/-](\d{4})", line)
        if m:
            try:
                return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                pass

        # Try YYYY-MM-DD
        m = re.match(r"^(\d{4})[/-](\d{2})[/-](\d{2})", line)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass

        # Try DD Mon YYYY
        m = re.match(r"^(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(\d{4})", line, re.I)
        if m:
            try:
                return datetime.strptime(f"{m.group(1)} {m.group(2)[:3]} {m.group(3)}", "%d %b %Y").date()
            except ValueError:
                pass
        return None

    @classmethod
    def _parse_date(cls, s: str) -> Optional[date]:
        for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d"]:
            try:
                return datetime.strptime(s.strip(), fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def format_result_summary(result: StatementResult) -> str:
        """Return a human-readable summary string for display in the UI."""
        if result.source_type == "error":
            return "Error: " + "; ".join(result.parse_errors)

        months = result.months_covered
        lines = [
            f"Statement Type:        {result.source_type.upper()}",
            f"Account Holder:        {result.owner_name}",
            f"Period:                {result.statement_from} → {result.statement_to}",
            f"Months Covered:        {months}",
            f"Transactions Found:    {len(result.transactions)}",
            f"",
            f"Total Credits (In):    UGX {float(result.total_credits):,.0f}",
            f"Total Debits (Out):    UGX {float(result.total_debits):,.0f}",
            f"",
            f"Avg Monthly Income:    UGX {float(result.avg_monthly_income):,.0f}",
            f"Avg Monthly Expense:   UGX {float(result.avg_monthly_expense):,.0f}",
            f"Net Monthly Flow:      UGX {float(result.net_monthly_flow):,.0f}",
            f"Income Consistency:    {result.income_consistency}",
        ]
        if result.parse_errors:
            lines += ["", "Warnings:"] + [f"  • {e}" for e in result.parse_errors]
        return "\n".join(lines)