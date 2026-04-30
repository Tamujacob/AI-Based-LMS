"""
app/core/agents/statement_parser.py
─────────────────────────────────────────────────────────────
Extracts financial transactions from:
  - MTN Mobile Money PDF statements
  - Airtel Money PDF statements
  - Stanbic / Centenary / other bank PDF statements
  - Image files (JPG/PNG) via pytesseract OCR

Returns a StatementResult with:
  - raw transactions list
  - monthly summary (income, expenditure, net)
  - income consistency score
  - detected statement type
"""

import re
import os
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from decimal import Decimal


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class Transaction:
    date:        str
    description: str
    amount:      float
    tx_type:     str   # "credit" or "debit"
    balance:     Optional[float] = None
    reference:   Optional[str]   = None


@dataclass
class MonthlySummary:
    month:       str
    total_in:    float
    total_out:   float
    net:         float
    tx_count:    int


@dataclass
class StatementResult:
    source_file:         str
    statement_type:      str          # "mtn_momo" | "airtel" | "bank" | "unknown"
    transactions:        List[Transaction] = field(default_factory=list)
    monthly_summaries:   List[MonthlySummary] = field(default_factory=list)

    # Aggregated
    total_credits:       float = 0.0
    total_debits:        float = 0.0
    net_cash_flow:       float = 0.0
    avg_monthly_income:  float = 0.0
    avg_monthly_expense: float = 0.0
    avg_monthly_net:     float = 0.0
    months_covered:      int   = 0
    income_consistency:  float = 0.0   # 0.0 – 1.0
    largest_credit:      float = 0.0
    largest_debit:       float = 0.0

    # Flags
    has_salary_pattern:  bool  = False
    has_irregular_income:bool  = False
    parse_warnings:      List[str] = field(default_factory=list)

    def as_text(self) -> str:
        lines = [
            f"Statement Type:        {self.statement_type.replace('_',' ').title()}",
            f"Months Covered:        {self.months_covered}",
            f"Total Transactions:    {len(self.transactions)}",
            f"Total Credits (In):    UGX {self.total_credits:,.0f}",
            f"Total Debits (Out):    UGX {self.total_debits:,.0f}",
            f"Net Cash Flow:         UGX {self.net_cash_flow:,.0f}",
            f"Avg Monthly Income:    UGX {self.avg_monthly_income:,.0f}",
            f"Avg Monthly Expense:   UGX {self.avg_monthly_expense:,.0f}",
            f"Avg Monthly Net:       UGX {self.avg_monthly_net:,.0f}",
            f"Income Consistency:    {self.income_consistency:.0%}",
            f"Salary Pattern:        {'Yes' if self.has_salary_pattern else 'No'}",
            f"Largest Credit:        UGX {self.largest_credit:,.0f}",
            f"Largest Debit:         UGX {self.largest_debit:,.0f}",
        ]
        if self.parse_warnings:
            lines.append(f"Warnings:              {'; '.join(self.parse_warnings)}")
        return "\n".join(lines)


# ── Main parser ───────────────────────────────────────────────────────────────

class StatementParser:

    @staticmethod
    def parse(file_path: str) -> StatementResult:
        """
        Parse a bank or mobile money statement file.
        Automatically detects format and routes to the correct extractor.

        Args:
            file_path: Path to PDF or image file.

        Returns:
            StatementResult with all extracted data.
        """
        if not os.path.exists(file_path):
            result = StatementResult(source_file=file_path,
                                     statement_type="unknown")
            result.parse_warnings.append(f"File not found: {file_path}")
            return result

        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".pdf":
            text = StatementParser._extract_pdf_text(file_path)
        elif ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff"):
            text = StatementParser._extract_image_text(file_path)
        else:
            result = StatementResult(source_file=file_path,
                                     statement_type="unknown")
            result.parse_warnings.append(f"Unsupported file type: {ext}")
            return result

        if not text.strip():
            result = StatementResult(source_file=file_path,
                                     statement_type="unknown")
            result.parse_warnings.append(
                "No text could be extracted from the file. "
                "If this is a scanned image, ensure pytesseract is installed.")
            return result

        # Detect statement type
        stmt_type = StatementParser._detect_type(text)

        # Extract transactions
        if stmt_type == "mtn_momo":
            transactions = StatementParser._parse_mtn(text)
        elif stmt_type == "airtel":
            transactions = StatementParser._parse_airtel(text)
        else:
            transactions = StatementParser._parse_generic_bank(text)

        # Build result
        result = StatementParser._build_result(
            file_path, stmt_type, transactions, text)
        return result

    # ── Text extraction ────────────────────────────────────────────────────────

    @staticmethod
    def _extract_pdf_text(path: str) -> str:
        """Extract all text from PDF using pdfplumber."""
        try:
            import pdfplumber
            pages = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
            return "\n".join(pages)
        except ImportError:
            return StatementParser._extract_pdf_fallback(path)
        except Exception as e:
            return ""

    @staticmethod
    def _extract_pdf_fallback(path: str) -> str:
        """Fallback PDF reader using pypdf."""
        try:
            from pypdf import PdfReader
            reader = PdfReader(path)
            return "\n".join(
                page.extract_text() or "" for page in reader.pages)
        except Exception:
            return ""

    @staticmethod
    def _extract_image_text(path: str) -> str:
        """OCR text extraction from image using pytesseract."""
        try:
            import pytesseract
            from PIL import Image
            img  = Image.open(path)
            text = pytesseract.image_to_string(img, lang="eng")
            return text
        except ImportError:
            return ""
        except Exception:
            return ""

    # ── Statement type detection ───────────────────────────────────────────────

    @staticmethod
    def _detect_type(text: str) -> str:
        t = text.lower()
        if any(k in t for k in ["mtn mobile money", "mtn momo", "mtn uganda"]):
            return "mtn_momo"
        if any(k in t for k in ["airtel money", "airtel uganda"]):
            return "airtel"
        if any(k in t for k in ["stanbic", "centenary", "dfcu", "equity bank",
                                  "absa", "bank statement"]):
            return "bank"
        # Generic detection — look for common financial patterns
        if re.search(r"(debit|credit|balance|transaction)", t):
            return "bank"
        return "unknown"

    # ── MTN MoMo parser ────────────────────────────────────────────────────────

    @staticmethod
    def _parse_mtn(text: str) -> List[Transaction]:
        """
        Parse MTN Mobile Money statement.
        Typical format:
          DATE        DESCRIPTION              AMOUNT      BALANCE
          2025-01-03  Payment from John        50,000      130,000
        """
        transactions = []

        # Pattern: date, description, amount, optional balance
        # MTN uses formats like: 03/01/2025 or 2025-01-03
        pattern = re.compile(
            r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4}[/\-]\d{2}[/\-]\d{2})"
            r"\s+(.{5,60}?)\s+"
            r"([\d,]+(?:\.\d{2})?)"
            r"(?:\s+([\d,]+(?:\.\d{2})?))?",
            re.IGNORECASE
        )

        for m in pattern.finditer(text):
            date_str  = m.group(1)
            desc      = m.group(2).strip()
            amount    = StatementParser._parse_amount(m.group(3))
            balance   = StatementParser._parse_amount(m.group(4)) if m.group(4) else None

            if amount <= 0:
                continue

            # Classify credit vs debit by keywords in description
            tx_type = StatementParser._classify_mtn(desc)

            transactions.append(Transaction(
                date=date_str, description=desc,
                amount=amount, tx_type=tx_type, balance=balance))

        return transactions

    @staticmethod
    def _classify_mtn(desc: str) -> str:
        d = desc.lower()
        credit_keywords = [
            "received", "deposit", "payment from", "transfer from",
            "incoming", "credit", "refund", "reversal in", "topup",
        ]
        debit_keywords = [
            "sent", "withdraw", "payment to", "transfer to",
            "outgoing", "debit", "charge", "fee", "bill", "purchase",
            "airtime", "data bundle",
        ]
        for kw in credit_keywords:
            if kw in d:
                return "credit"
        for kw in debit_keywords:
            if kw in d:
                return "debit"
        return "credit"   # default to credit if ambiguous

    # ── Airtel Money parser ────────────────────────────────────────────────────

    @staticmethod
    def _parse_airtel(text: str) -> List[Transaction]:
        """Airtel Money statement — similar format to MTN."""
        # Reuse MTN parser logic with Airtel-specific classification
        transactions = StatementParser._parse_mtn(text)
        # Re-classify using Airtel-specific keywords
        for tx in transactions:
            tx.tx_type = StatementParser._classify_airtel(tx.description)
        return transactions

    @staticmethod
    def _classify_airtel(desc: str) -> str:
        d = desc.lower()
        if any(k in d for k in ["receive", "credit", "deposit", "from"]):
            return "credit"
        if any(k in d for k in ["send", "debit", "withdrawal", "payment", "to"]):
            return "debit"
        return "credit"

    # ── Generic bank parser ────────────────────────────────────────────────────

    @staticmethod
    def _parse_generic_bank(text: str) -> List[Transaction]:
        """
        Parse generic bank statement.
        Handles common formats:
          DATE | DESCRIPTION | DEBIT | CREDIT | BALANCE
        """
        transactions = []
        lines = text.split("\n")

        # Amount pattern — matches numbers like 1,500,000 or 1500000.00
        amount_pat = re.compile(r"([\d,]+(?:\.\d{2})?)")
        date_pat   = re.compile(
            r"\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4}[/\-]\d{2}[/\-]\d{2})\b")

        for line in lines:
            line = line.strip()
            if len(line) < 10:
                continue

            date_m = date_pat.search(line)
            if not date_m:
                continue

            amounts = amount_pat.findall(line)
            if len(amounts) < 1:
                continue

            # Remove date from description
            desc = line[date_m.end():].strip()

            # Try to identify debit/credit columns
            # Banks often show: description | debit_amount | credit_amount | balance
            parsed_amounts = [StatementParser._parse_amount(a)
                               for a in amounts if StatementParser._parse_amount(a) > 0]

            if not parsed_amounts:
                continue

            # Classify by description keywords
            tx_type = StatementParser._classify_bank(desc)
            amount  = max(parsed_amounts[:-1]) if len(parsed_amounts) > 1 else parsed_amounts[0]
            balance = parsed_amounts[-1] if len(parsed_amounts) > 1 else None

            if amount <= 0:
                continue

            transactions.append(Transaction(
                date=date_m.group(1),
                description=desc[:80],
                amount=amount,
                tx_type=tx_type,
                balance=balance,
            ))

        return transactions

    @staticmethod
    def _classify_bank(desc: str) -> str:
        d = desc.lower()
        credit_kw = ["salary", "credit", "deposit", "transfer in", "received",
                     "inward", "refund", "interest earned", "payment received"]
        debit_kw  = ["debit", "withdrawal", "transfer out", "payment",
                     "charge", "fee", "outward", "purchase"]
        for kw in credit_kw:
            if kw in d:
                return "credit"
        for kw in debit_kw:
            if kw in d:
                return "debit"
        return "debit"

    # ── Result builder ─────────────────────────────────────────────────────────

    @staticmethod
    def _build_result(file_path: str, stmt_type: str,
                      transactions: List[Transaction],
                      raw_text: str) -> StatementResult:
        result = StatementResult(
            source_file=file_path,
            statement_type=stmt_type,
            transactions=transactions,
        )

        if not transactions:
            result.parse_warnings.append(
                "No transactions could be extracted. "
                "The file may be a scanned image or use an unsupported format.")
            return result

        credits = [t for t in transactions if t.tx_type == "credit"]
        debits  = [t for t in transactions if t.tx_type == "debit"]

        result.total_credits  = sum(t.amount for t in credits)
        result.total_debits   = sum(t.amount for t in debits)
        result.net_cash_flow  = result.total_credits - result.total_debits
        result.largest_credit = max((t.amount for t in credits), default=0)
        result.largest_debit  = max((t.amount for t in debits),  default=0)

        # Monthly breakdown
        monthly = {}
        for tx in transactions:
            # Extract YYYY-MM from date string
            month_key = StatementParser._extract_month(tx.date)
            if not month_key:
                continue
            if month_key not in monthly:
                monthly[month_key] = {"in": 0.0, "out": 0.0, "count": 0}
            if tx.tx_type == "credit":
                monthly[month_key]["in"] += tx.amount
            else:
                monthly[month_key]["out"] += tx.amount
            monthly[month_key]["count"] += 1

        for month_key, m in sorted(monthly.items()):
            result.monthly_summaries.append(MonthlySummary(
                month     = month_key,
                total_in  = m["in"],
                total_out = m["out"],
                net       = m["in"] - m["out"],
                tx_count  = m["count"],
            ))

        result.months_covered = len(result.monthly_summaries)
        if result.months_covered > 0:
            result.avg_monthly_income  = (
                result.total_credits / result.months_covered)
            result.avg_monthly_expense = (
                result.total_debits / result.months_covered)
            result.avg_monthly_net     = (
                result.net_cash_flow / result.months_covered)

        # Income consistency — how similar are monthly incomes?
        if len(result.monthly_summaries) >= 2:
            incomes = [m.total_in for m in result.monthly_summaries]
            avg     = sum(incomes) / len(incomes)
            if avg > 0:
                deviations = [abs(i - avg) / avg for i in incomes]
                result.income_consistency = max(0.0, 1.0 - (
                    sum(deviations) / len(deviations)))
            else:
                result.income_consistency = 0.0
        else:
            result.income_consistency = 0.5   # not enough data

        # Salary pattern detection
        salary_keywords = ["salary", "payroll", "wage", "pay ", "employer"]
        text_lower = raw_text.lower()
        result.has_salary_pattern = any(k in text_lower for k in salary_keywords)
        result.has_irregular_income = result.income_consistency < 0.5

        return result

    # ── Utilities ──────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_amount(s: str) -> float:
        if not s:
            return 0.0
        try:
            return float(str(s).replace(",", "").replace(" ", ""))
        except ValueError:
            return 0.0

    @staticmethod
    def _extract_month(date_str: str) -> Optional[str]:
        """Extract YYYY-MM from various date formats."""
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d",
                    "%d/%m/%y", "%d-%m-%y", "%m/%d/%Y"):
            try:
                d = datetime.strptime(date_str.strip(), fmt)
                return d.strftime("%Y-%m")
            except ValueError:
                continue
        # Last resort — regex
        m = re.search(r"(\d{4})[/\-](\d{2})", date_str)
        if m:
            return f"{m.group(1)}-{m.group(2)}"
        m = re.search(r"(\d{2})[/\-](\d{2})[/\-](\d{4})", date_str)
        if m:
            return f"{m.group(3)}-{m.group(2)}"
        return None