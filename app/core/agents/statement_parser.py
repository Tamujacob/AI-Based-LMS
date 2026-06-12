"""
app/core/agents/statement_parser.py
════════════════════════════════════════════════════════════════════════════════
Universal Financial Statement Parser — Uganda
AI-Based Loans Management System | Bingongold Credit

Supports: MTN MoMo · Airtel Money · Stanbic · Equity ·
          Centenary · DFCU · Generic bank PDFs · OCR images

NEW in this version:
  - result.client_name  — full name extracted from statement header
  - result.nin          — Uganda NIN (14 chars) extracted from PDF text

Uganda NIN format (14 chars, no spaces or punctuation):
  C[MF]  — Citizen + Male/Female
  \\d{2}  — last 2 digits of birth year
  \\d{6}  — unique security permutation
  [A-Z0-9]{4} — random suffix
  Examples: CM97027102X4CU  |  CF85123456ABCD

Usage:
    result = StatementParser.parse("/path/to/statement.pdf")
    print(result.client_name)        # "JACOB TAMUKEDDE"
    print(result.nin)                # "CM97027102X4CU" or "" if not found
    print(result.avg_monthly_income) # 100500.0
    print(result.as_text())          # full human-readable summary

Author : Tamukedde Jacob | Bugema University FYP | Bingongold Credit
"""

from __future__ import annotations

import os
import re
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Uganda NIN regex patterns
# ══════════════════════════════════════════════════════════════════════════════
#
# STRICT  — exact 14-char NIN starting with CM or CF (most common)
# LABELLED — any 14-char token that appears right after a NIN/ID label
# CONTEXT  — any 14-char alphanumeric near identity keywords in the header

_NIN_STRICT = re.compile(
    r'\bC[MF]\d{8}[A-Z0-9]{4}\b',
    re.IGNORECASE
)

_NIN_LABELLED = re.compile(
    r'(?:NIN|national\s+id(?:entification)?\s*(?:number|no|#)?'
    r'|id\s*(?:number|no|#))'
    r'[^\w]{0,20}([A-Z0-9]{14})',
    re.IGNORECASE
)


# ══════════════════════════════════════════════════════════════════════════════
# Data classes
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Transaction:
    date:        datetime
    description: str
    amount:      float          # positive = inflow, negative = outflow
    tx_type:     str            # "credit" | "debit"
    balance:     Optional[float] = None
    reference:   Optional[str]   = None


@dataclass
class MonthlySummary:
    month:     str              # e.g. "Apr 2026"
    total_in:  float
    total_out: float
    net:       float
    tx_count:  int


@dataclass
class StatementResult:
    source_file:          str
    statement_type:       str   # mtn_momo|airtel|stanbic|equity|
                                # centenary|dfcu|bank|unknown

    # ── Client identity (NEW) ─────────────────────────────────────────────
    client_name:          str   = ""   # Full name from header
    nin:                  str   = ""   # Uganda NIN, 14 chars, or ""
    # ─────────────────────────────────────────────────────────────────────

    account_holder:       str   = ""   # Raw account holder text
    account_number:       str   = ""
    period_from:          Optional[datetime] = None
    period_to:            Optional[datetime] = None

    transactions:         List[Transaction]    = field(default_factory=list)
    monthly_summaries:    List[MonthlySummary] = field(default_factory=list)

    total_credits:        float = 0.0
    total_debits:         float = 0.0
    net_cash_flow:        float = 0.0
    avg_monthly_income:   float = 0.0
    avg_monthly_expense:  float = 0.0
    avg_monthly_net:      float = 0.0
    months_covered:       int   = 0
    income_consistency:   float = 0.0
    largest_credit:       float = 0.0
    largest_debit:        float = 0.0
    has_salary_pattern:   bool  = False
    has_irregular_income: bool  = False
    parse_warnings:       List[str] = field(default_factory=list)

    def as_text(self) -> str:
        lines = [
            f"Statement Type:        {self.statement_type.replace('_', ' ').title()}",
            f"Client Name:           {self.client_name or 'Not found'}",
            f"NIN:                   {self.nin or 'Not found in PDF'}",
            f"Account Number:        {self.account_number or 'N/A'}",
        ]
        if self.period_from and self.period_to:
            lines.append(
                f"Period:                "
                f"{self.period_from.strftime('%d %b %Y')} – "
                f"{self.period_to.strftime('%d %b %Y')}"
            )
        lines += [
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


# ══════════════════════════════════════════════════════════════════════════════
# Main parser class
# ══════════════════════════════════════════════════════════════════════════════

class StatementParser:

    # ── Entry point ──────────────────────────────────────────────────────────

    @staticmethod
    def parse(file_path: str, password: str = None) -> StatementResult:
        """
        Parse any Uganda bank / mobile money statement PDF or image.
        Auto-detects institution and extracts client_name, nin, and
        full transaction + monthly summary data.
        
        Args:
            file_path: Path to the statement file (PDF, image, etc.)
            password: Password for encrypted PDFs (e.g., last 4 account digits)
        """
        if not os.path.exists(file_path):
            r = StatementResult(source_file=file_path, statement_type="unknown")
            r.parse_warnings.append(f"File not found: {file_path}")
            return r

        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            raw_text, tables = StatementParser._read_pdf(file_path, password=password)
        elif ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"):
            raw_text = StatementParser._ocr_image(file_path)
            tables   = []
        else:
            r = StatementResult(source_file=file_path, statement_type="unknown")
            r.parse_warnings.append(f"Unsupported file type: {ext}")
            return r

        if not raw_text.strip():
            r = StatementResult(source_file=file_path, statement_type="unknown")
            if password:
                r.parse_warnings.append(
                    "No text extracted. The provided password may be incorrect, "
                    "or the PDF uses unsupported encryption."
                )
            else:
                r.parse_warnings.append(
                    "No text extracted. Ensure pdfplumber is installed and "
                    "the PDF is not password-protected. If password-protected, "
                    "provide the password (last 4 account digits)."
                )
            return r

        stmt_type = StatementParser._detect_type(raw_text)
        result    = StatementResult(source_file=file_path,
                                    statement_type=stmt_type)

        # ── Extract identity fields first ─────────────────────────────────
        StatementParser._parse_header(raw_text, result)
        StatementParser._extract_nin(raw_text, result)
        StatementParser._extract_client_name(raw_text, result)

        # ── Route to institution-specific transaction parser ───────────────
        dispatch = {
            "mtn_momo":  StatementParser._parse_mtn_momo,
            "airtel":    StatementParser._parse_airtel,
            "stanbic":   StatementParser._parse_bank_debit_credit,
            "equity":    StatementParser._parse_bank_debit_credit,
            "centenary": StatementParser._parse_bank_debit_credit,
            "dfcu":      StatementParser._parse_bank_debit_credit,
            "bank":      StatementParser._parse_bank_debit_credit,
        }
        try:
            parser_fn    = dispatch.get(stmt_type,
                                        StatementParser._parse_bank_debit_credit)
            transactions = parser_fn(file_path, raw_text, tables)
        except Exception as exc:
            logger.exception("Transaction parsing failed")
            result.parse_warnings.append(f"Parsing error: {exc}")
            transactions = []

        if not transactions:
            result.parse_warnings.append(
                "No transactions extracted. "
                "The PDF may use an unsupported layout.")
            return result

        result.transactions = transactions
        StatementParser._build_summary(result, raw_text)
        return result

    # ══════════════════════════════════════════════════════════════════════════
    # NIN extraction  (NEW)
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _extract_nin(text: str, result: StatementResult):
        """
        Extract Uganda NIN from statement text using a 4-tier strategy:

        Tier 1 — STRICT regex: C[MF] + 8 digits + 4 alphanumeric (most reliable)
        Tier 2 — LABELLED: any 14-char token after a NIN/ID label keyword
        Tier 3 — CONTEXT: scan first 800 chars (account details section) for
                  any 14-char alphanumeric token near identity keywords
        Tier 4 — LAST RESORT: any standalone 14-char alphanumeric in header

        MTN MoMo statements do NOT contain NIN — result.nin stays "".
        Bank statements (Stanbic, Equity, Centenary, DFCU) include NIN in the
        account details header block per Bank of Uganda KYC requirements.
        """
        # Tier 1 — strict NIN pattern anywhere in document
        m = _NIN_STRICT.search(text)
        if m:
            result.nin = m.group(0).upper()
            return

        # Tier 2 — labelled: "NIN: AB12345678CDEF"
        m = _NIN_LABELLED.search(text)
        if m:
            candidate = m.group(1).strip().upper()
            if len(candidate) == 14:
                result.nin = candidate
                return

        # Tier 3 — context scan in header block (first 800 chars)
        header = text[:800]
        context_re = re.compile(
            r'(?:nin|national\s*id|identification|id\s*no|id\s*number)'
            r'.{0,30}?([A-Z0-9]{14})',
            re.IGNORECASE | re.DOTALL
        )
        m = context_re.search(header)
        if m:
            result.nin = m.group(1).upper()
            return

        # Tier 4 — any standalone 14-char alphanumeric token in header
        for token in re.findall(r'\b([A-Z]{1,2}[A-Z0-9]{12,13})\b',
                                header, re.IGNORECASE):
            if len(token) == 14:
                result.nin = token.upper()
                return
        # If nothing found, result.nin stays "" — this is expected for MoMo

    # ══════════════════════════════════════════════════════════════════════════
    # Client name extraction  (NEW)
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _extract_client_name(text: str, result: StatementResult):
        """
        Extract the borrower's full name from the statement header.

        Label patterns by institution:
          MTN MoMo   — "Account holder: JACOB TAMUKEDDE"
          Airtel     — "Account Name: JANE NAMUTEBI"
          Stanbic    — "Customer Name: JOHN MUKASA"
          Equity     — "Account Name: SARAH NAKATO"
          Centenary  — "Name: PETER SSEMAKULA"
          DFCU       — "Account Holder: ..."

        Sets result.client_name (uppercase).
        Falls back to result.account_holder if no label matches.
        """
        name_patterns = [
            r'account\s+holder\s*[:\-]\s*([A-Z][A-Za-z\s\'\-\.]{2,50})',
            r'account\s+name\s*[:\-]\s*([A-Z][A-Za-z\s\'\-\.]{2,50})',
            r'customer\s+name\s*[:\-]\s*([A-Z][A-Za-z\s\'\-\.]{2,50})',
            r'name\s+of\s+account\s+holder\s*[:\-]\s*([A-Z][A-Za-z\s\'\-\.]{2,50})',
            r'account\s+owner\s*[:\-]\s*([A-Z][A-Za-z\s\'\-\.]{2,50})',
            r'(?<!\w)name\s*[:\-]\s*([A-Z][A-Za-z\s\'\-\.]{2,50})',
        ]

        # Words that signal the name capture has gone too far
        _STOP_WORDS = re.compile(
            r'\s+(?:wallet|account|phone|mobile|from|to|date|number|'
            r'period|statement|nin|national|balance|branch)',
            re.IGNORECASE
        )

        for pat in name_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                raw   = m.group(1).strip()
                raw   = _STOP_WORDS.split(raw)[0].strip()
                words = raw.split()
                # Valid name: at least 2 words, no digits, reasonable length
                if len(words) >= 2 and not re.search(r'\d', raw) and len(raw) > 4:
                    result.client_name    = raw.upper()
                    result.account_holder = result.account_holder or raw.upper()
                    return

        # Fallback: use account_holder populated by _parse_header
        if result.account_holder and not result.client_name:
            result.client_name = result.account_holder

    # ── PDF / image reading ──────────────────────────────────────────────────

    @staticmethod
    def _read_pdf(path: str, password: str = None):
        """Returns (full_text, list_of_tables). Supports password-protected PDFs."""
        try:
            import pdfplumber
        except ImportError:
            return StatementParser._read_pdf_fallback(path, password=password), []

        try:
            all_text, all_tables = [], []
            open_kwargs = {}
            if password:
                open_kwargs["password"] = password

            with pdfplumber.open(path, **open_kwargs) as pdf:
                for page in pdf.pages:
                    all_text.append(page.extract_text() or "")
                    for tbl in page.extract_tables():
                        all_tables.append(tbl)

            text = "\n".join(all_text)
            if text.strip():
                return text, all_tables
            return "", []
        except Exception as e:
            logger.warning(f"pdfplumber read error for {path}: {e}")
            return StatementParser._read_pdf_fallback(path, password=password), []

    @staticmethod
    def _read_pdf_using_pypdf(path: str, password: str = None):
        try:
            from pypdf import PdfReader
            reader = PdfReader(path)

            if reader.is_encrypted:
                if not password:
                    logger.warning(f"Encrypted PDF requires a password: {path}")
                    return "", []
                result = reader.decrypt(password)
                if result == 0:
                    logger.warning(f"Password decryption failed for {path}")
                    return "", []

            all_text = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    all_text.append(page_text)
            return "\n".join(all_text), []
        except Exception as e:
            logger.warning(f"pypdf read error for {path}: {e}")
            return "", []

    @staticmethod
    def _read_pdf_fallback(path: str, password: str = None) -> str:
        try:
            from pypdf import PdfReader
            reader = PdfReader(path)

            if reader.is_encrypted:
                if not password:
                    logger.warning(f"Encrypted PDF requires a password: {path}")
                    return ""
                result = reader.decrypt(password)
                if result == 0:
                    logger.warning(f"Password decryption failed for {path}")
                    return ""

            return "\n".join(p.extract_text() or ""
                             for p in reader.pages)
        except Exception as e:
            logger.warning(f"PDF fallback read error: {e}")
            return ""

    @staticmethod
    def _ocr_image(path: str) -> str:
        try:
            import pytesseract
            from PIL import Image
            return pytesseract.image_to_string(Image.open(path), lang="eng")
        except Exception:
            return ""

    # ── Institution detection ────────────────────────────────────────────────

    @staticmethod
    def _detect_type(text: str) -> str:
        t = text.lower()
        if any(k in t for k in ["mtn mobile money", "mtn momo",
                                  "mtn uganda limited", "mtnu mobile money",
                                  "wallet number"]):
            return "mtn_momo"
        if any(k in t for k in ["airtel money", "airtel uganda",
                                  "airtel networks"]):
            return "airtel"
        if "stanbic" in t:
            return "stanbic"
        if "equity bank" in t or "equity b2c" in t:
            return "equity"
        if "centenary" in t:
            return "centenary"
        if "dfcu" in t:
            return "dfcu"
        if re.search(r'\b(debit|credit|balance|withdrawal|deposit|narration)\b', t):
            return "bank"
        return "unknown"

    # ── Generic header parsing ───────────────────────────────────────────────

    @staticmethod
    def _parse_header(text: str, result: StatementResult):
        # Account holder (raw — _extract_client_name refines this later)
        for pat in [
            r'account holder[:\s]+([A-Z][A-Z\s]{2,40})',
            r'account name[:\s]+([A-Z][A-Z\s]{2,40})',
            r'customer name[:\s]+([A-Z][A-Z\s]{2,40})',
        ]:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                candidate = re.split(
                    r'\s+(wallet|account|phone|from|to|date)',
                    m.group(1).strip(), flags=re.IGNORECASE
                )[0].strip()
                if len(candidate) > 3:
                    result.account_holder = candidate
                    break

        # Account / wallet number
        for pat in [
            r'wallet number[:\s]+([\d\s+]+)',
            r'account(?:\s+no)?[:\s#]+([\dA-Z\-]+)',
            r'mobile number[:\s]+([\d+\s]+)',
        ]:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                result.account_number = m.group(1).replace(' ', '').strip()[:20]
                break

        # Statement period
        for pat in [r'from\s+date[:\s]+(\d{1,2}\s+\w+\s+\d{4})',
                    r'from[:\s]+(\d{1,2}[/-]\w+[/-]\d{2,4})']:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                result.period_from = _parse_date(m.group(1))
                break

        for pat in [r'to\s+date[:\s]+(\d{1,2}\s+\w+\s+\d{4})',
                    r'\bto[:\s]+(\d{1,2}[/-]\w+[/-]\d{2,4})']:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                result.period_to = _parse_date(m.group(1))
                break

    # ══════════════════════════════════════════════════════════════════════════
    # MTN MoMo parser
    # ══════════════════════════════════════════════════════════════════════════
    # Root cause of original failure:
    #   pdfplumber collapses multi-line table cells → row[0] contains ALL data,
    #   row[1..N] = None.  Old parser only read row[4] → missed ~50% of rows.
    #
    # FORMAT A — clean row:  row[0]="26 Apr 2026 13:21", row[4]="-15000.00"
    # FORMAT B — collapsed:  row[0]="...26 Apr 2026 07:43 PAKAPAKA -400.00..."
    #                         row[1..] = all None
    # ══════════════════════════════════════════════════════════════════════════

    _MTN_DATE_RE   = re.compile(r'(\d{1,2}\s+\w{3}\s+\d{4}\s+\d{2}:\d{2})')
    _MTN_AMOUNT_RE = re.compile(r'([+\-][\d,]+(?:\.\d+)?)')
    _MTN_DEBIT_TYPES  = {"CASH OUT", "DEBIT", "PAYMENT", "PAKAPAKA",
                         "INTERNET BUNDLE", "INTERNET", "VOICE BUNDLE",
                         "SMS BUNDLE", "AIRTIME", "BUNDLE"}

    @staticmethod
    def _parse_mtn_momo(file_path, raw_text, tables):
        transactions, seen = [], set()

        for table in tables:
            for row in table:
                if not row or not row[0]:
                    continue
                cell0 = str(row[0])
                if "Date" in cell0 and ("Time" in cell0 or "Payment" in cell0):
                    continue

                # FORMAT A — signed amount in col 4 (fallback to 3 or 5)
                amt_col = None
                for ci in [4, 3, 5]:
                    if (len(row) > ci and row[ci] is not None
                            and StatementParser._MTN_AMOUNT_RE.match(
                                str(row[ci]).strip())):
                        amt_col = ci
                        break

                if amt_col is not None:
                    dm = StatementParser._MTN_DATE_RE.search(cell0)
                    if not dm:
                        continue
                    dt = _parse_datetime(dm.group(1))
                    if dt is None:
                        continue
                    try:
                        amount = float(str(row[amt_col]).replace(',', '').strip())
                    except ValueError:
                        continue
                    if abs(amount) < 100:
                        continue
                    ref   = str(row[5]).strip() if len(row) > 5 and row[5] else ''
                    ptype = (str(row[1]).replace('\n', ' ').strip()
                             if row[1] else '')
                    if ref and ref in seen:
                        continue
                    if ref:
                        seen.add(ref)
                    transactions.append(Transaction(
                        date=dt, description=ptype, amount=amount,
                        tx_type="credit" if amount > 0 else "debit",
                        reference=ref or None))
                    continue

                # FORMAT B — all columns after cell0 are None
                if all(c is None for c in (row[1:] if len(row) > 1 else [])):
                    dm = StatementParser._MTN_DATE_RE.search(cell0)
                    if not dm:
                        continue
                    dt = _parse_datetime(dm.group(1))
                    if dt is None:
                        continue
                    post = cell0[dm.end():]
                    am   = StatementParser._MTN_AMOUNT_RE.search(post)
                    if not am:
                        continue
                    try:
                        amount = float(am.group(1).replace(',', ''))
                    except ValueError:
                        continue
                    if abs(amount) < 100:
                        continue
                    tokens = post[:am.start()].strip().split()
                    ptype  = ' '.join(tokens[:2]).upper() if tokens else 'UNKNOWN'
                    if not am.group(1).startswith(('+', '-')):
                        amount = (-abs(amount)
                                  if any(k in ptype
                                         for k in StatementParser._MTN_DEBIT_TYPES)
                                  else abs(amount))
                    transactions.append(Transaction(
                        date=dt, description=ptype, amount=amount,
                        tx_type="credit" if amount > 0 else "debit"))

        transactions.sort(key=lambda t: t.date)
        return transactions

    # ══════════════════════════════════════════════════════════════════════════
    # Airtel Money parser
    # ══════════════════════════════════════════════════════════════════════════
    # New format (2022+): table
    #   Date|Trans ID|Tx Type|Description|From|To|Status|Amount|Fee|Balance
    #   Amount uses +/- prefix. Date: YYYY-MM-DD.
    #
    # Old format: text lines
    #   "16:23 PM (CO240409.1623.H54784) 10/04/24 Money Sent to X -- 2.63"
    # ══════════════════════════════════════════════════════════════════════════

    _AIRTEL_CREDIT = {"withdraw money", "money received", "receive money",
                      "c2c", "cashin", "cash in", "incoming", "reversal",
                      "top up", "topup"}
    _AIRTEL_DEBIT  = {"deposit money", "money sent", "send money", "payment",
                      "bill payment", "cashout", "cash out", "outgoing",
                      "transfer out", "airtime", "data bundle"}

    @staticmethod
    def _parse_airtel(file_path, raw_text, tables):
        transactions = []

        for table in tables:
            for row in table:
                if not row or not row[0]:
                    continue
                cell0 = str(row[0]).strip()
                if re.match(r'date|time|trans', cell0, re.IGNORECASE):
                    continue
                if len(row) < 8:
                    continue
                dt = _parse_date(cell0)
                if dt is None:
                    continue
                tx_raw = str(row[2]).strip().lower() if row[2] else ""
                desc   = str(row[3]).strip()         if row[3] else tx_raw
                amt_s  = str(row[7]).replace(',', '').strip() if row[7] else ""
                signed = re.match(r'([+\-])([\d.]+)', amt_s)
                if signed:
                    amount = float(signed.group(2)) * (
                        1 if signed.group(1) == '+' else -1)
                else:
                    plain = re.match(r'([\d.,]+)', amt_s)
                    if not plain:
                        continue
                    v    = float(plain.group(1).replace(',', ''))
                    sign = (1 if any(k in tx_raw
                                     for k in StatementParser._AIRTEL_CREDIT)
                            else -1)
                    amount = sign * v
                if abs(amount) < 1:
                    continue
                bal = (_parse_amount(str(row[9]))
                       if len(row) > 9 and row[9] else None)
                transactions.append(Transaction(
                    date=dt, description=desc or tx_raw, amount=amount,
                    tx_type="credit" if amount > 0 else "debit",
                    balance=bal,
                    reference=str(row[1]).strip() if row[1] else None))

        # Old text-format fallback
        if not transactions:
            line_re = re.compile(
                r'(?:[\d:]+\s*(?:AM|PM)\s*)?(?:\(([A-Z0-9.]+)\)\s*)?'
                r'(\d{2}/\d{2}/\d{2,4})\s+(.{4,60}?)\s+'
                r'(?:--\s*)?([+\-]?[\d,]+\.\d{2})',
                re.IGNORECASE
            )
            for m in line_re.finditer(raw_text):
                dt = _parse_date(m.group(2))
                if dt is None:
                    continue
                desc   = m.group(3).strip()
                amount = _parse_amount(m.group(4))
                if amount == 0:
                    continue
                if any(k in desc.lower()
                       for k in ["sent", "payment", "deposit", "purchase"]):
                    amount = -abs(amount)
                transactions.append(Transaction(
                    date=dt, description=desc, amount=amount,
                    tx_type="credit" if amount > 0 else "debit",
                    reference=m.group(1) or None))

        transactions.sort(key=lambda t: t.date)
        return transactions

    # ══════════════════════════════════════════════════════════════════════════
    # Bank parser — Stanbic, Equity, Centenary, DFCU, generic
    # ══════════════════════════════════════════════════════════════════════════
    # All Ugandan banks use separate Debit + Credit columns.
    # Column positions are auto-detected from header row keywords.
    # Falls back to text-regex if no table structure is found.
    # ══════════════════════════════════════════════════════════════════════════

    _DATE_HDRS    = {"date", "txn date", "tran date", "trans date",
                     "value date", "posting date", "transaction date"}
    _DESC_HDRS    = {"narration", "description", "particulars", "details",
                     "transaction details", "remarks"}
    _REF_HDRS     = {"reference", "ref", "cheque", "chq", "ref no", "cheque no"}
    _DEBIT_HDRS   = {"debit", "withdrawal", "withdrawals", "dr",
                     "amount dr", "debit amount"}
    _CREDIT_HDRS  = {"credit", "deposit", "deposits", "cr",
                     "amount cr", "credit amount"}
    _BALANCE_HDRS = {"balance", "running balance", "closing balance",
                     "available balance"}

    @staticmethod
    def _parse_bank_debit_credit(file_path, raw_text, tables):
        transactions = []

        for table in tables:
            if len(table) < 2:
                continue
            header_idx, col_map = None, {}

            for ri, row in enumerate(table[:6]):
                if not row:
                    continue
                low = [str(c).lower().strip() if c else "" for c in row]
                matches, tmp = 0, {}
                for ci, cell in enumerate(low):
                    if any(h in cell for h in StatementParser._DATE_HDRS) and "date" not in tmp:
                        tmp["date"] = ci;    matches += 1
                    if any(h in cell for h in StatementParser._DESC_HDRS) and "desc" not in tmp:
                        tmp["desc"] = ci;    matches += 1
                    if any(h in cell for h in StatementParser._DEBIT_HDRS) and "debit" not in tmp:
                        tmp["debit"] = ci;   matches += 1
                    if any(h in cell for h in StatementParser._CREDIT_HDRS) and "credit" not in tmp:
                        tmp["credit"] = ci;  matches += 1
                    if any(h in cell for h in StatementParser._BALANCE_HDRS) and "balance" not in tmp:
                        tmp["balance"] = ci
                    if any(h in cell for h in StatementParser._REF_HDRS) and "ref" not in tmp:
                        tmp["ref"] = ci
                if matches >= 2:
                    header_idx = ri
                    col_map    = tmp
                    break

            if header_idx is None or "date" not in col_map:
                continue

            for row in table[header_idx + 1:]:
                if not row:
                    continue
                date_cell = (str(row[col_map["date"]]).strip()
                             if row[col_map["date"]] else "")
                dt = _parse_date(date_cell)
                if dt is None:
                    continue

                desc = ""
                if "desc" in col_map and row[col_map["desc"]]:
                    desc = str(row[col_map["desc"]]).replace('\n', ' ').strip()
                ref = None
                if "ref" in col_map and row[col_map["ref"]]:
                    ref = str(row[col_map["ref"]]).strip()

                debit_amt  = (_parse_amount(str(row[col_map["debit"]]))
                              if "debit" in col_map
                              and col_map["debit"] < len(row)
                              and row[col_map["debit"]] else 0.0)
                credit_amt = (_parse_amount(str(row[col_map["credit"]]))
                              if "credit" in col_map
                              and col_map["credit"] < len(row)
                              and row[col_map["credit"]] else 0.0)
                balance    = None
                if ("balance" in col_map
                        and col_map["balance"] < len(row)
                        and row[col_map["balance"]]):
                    balance = _parse_amount(str(row[col_map["balance"]]))

                if debit_amt == 0 and credit_amt == 0:
                    continue
                if credit_amt > 0:
                    transactions.append(Transaction(
                        date=dt, description=desc, amount=credit_amt,
                        tx_type="credit", balance=balance, reference=ref))
                if debit_amt > 0:
                    transactions.append(Transaction(
                        date=dt, description=desc, amount=-debit_amt,
                        tx_type="debit", balance=balance, reference=ref))

        if not transactions:
            transactions = StatementParser._parse_bank_text(raw_text)

        transactions.sort(key=lambda t: t.date)
        return transactions

    @staticmethod
    def _parse_bank_text(text: str):
        """Text-regex fallback for bank statements with no table structure."""
        transactions = []
        date_re   = re.compile(
            r'\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}'
            r'|\d{1,2}[/\-][A-Za-z]{3}[/\-]\d{2,4}'
            r'|\d{4}[/\-]\d{2}[/\-]\d{2})\b'
        )
        amount_re = re.compile(r'([\d,]+(?:\.\d{2}))')
        for line in text.splitlines():
            line = line.strip()
            if len(line) < 12:
                continue
            dm = date_re.search(line)
            if not dm:
                continue
            amounts = [_parse_amount(a) for a in amount_re.findall(line)
                       if _parse_amount(a) > 10]
            if not amounts:
                continue
            dt = _parse_date(dm.group(1))
            if dt is None:
                continue
            desc    = amount_re.sub('', line[dm.end():]).strip()[:80]
            tx_type = _classify_bank_text(desc)
            amount  = (amounts[0] if len(amounts) == 1
                       else amounts[-2] if len(amounts) >= 2 else amounts[0])
            if tx_type == "debit":
                amount = -amount
            transactions.append(Transaction(
                date=dt, description=desc, amount=amount, tx_type=tx_type,
                balance=amounts[-1] if len(amounts) >= 2 else None))
        return transactions

    # ══════════════════════════════════════════════════════════════════════════
    # Summary builder — shared by all parsers
    # ══════════════════════════════════════════════════════════════════════════

    _ONE_OFF_THRESHOLD = 500_000  # UGX — bank-to-wallet top-ups excluded

    @staticmethod
    def _build_summary(result: StatementResult, raw_text: str):
        txns    = result.transactions
        credits = [t for t in txns if t.tx_type == "credit"]
        debits  = [t for t in txns if t.tx_type == "debit"]

        result.total_credits  = sum(t.amount for t in credits)
        result.total_debits   = sum(abs(t.amount) for t in debits)
        result.net_cash_flow  = result.total_credits - result.total_debits
        result.largest_credit = max((t.amount for t in credits), default=0)
        result.largest_debit  = max((abs(t.amount) for t in debits), default=0)

        # Exclude one-off large transfers from monthly income average
        one_off  = sum(t.amount for t in credits
                       if t.amount >= StatementParser._ONE_OFF_THRESHOLD)
        adjusted = result.total_credits - one_off

        monthly: dict = defaultdict(lambda: {"in": 0.0, "out": 0.0, "count": 0})
        for t in txns:
            key = t.date.strftime("%b %Y")
            if t.tx_type == "credit":
                monthly[key]["in"]  += t.amount
            else:
                monthly[key]["out"] += abs(t.amount)
            monthly[key]["count"] += 1

        result.monthly_summaries = [
            MonthlySummary(
                month=m, total_in=v["in"], total_out=v["out"],
                net=v["in"] - v["out"], tx_count=v["count"])
            for m, v in sorted(
                monthly.items(),
                key=lambda kv: datetime.strptime(kv[0], "%b %Y"))
        ]
        result.months_covered     = max(len(result.monthly_summaries), 1)
        result.avg_monthly_income  = adjusted / result.months_covered
        result.avg_monthly_expense = result.total_debits / result.months_covered
        result.avg_monthly_net     = (result.avg_monthly_income
                                      - result.avg_monthly_expense)

        incomes = [m.total_in for m in result.monthly_summaries]
        if len(incomes) >= 2:
            avg = sum(incomes) / len(incomes)
            if avg > 0:
                devs = [abs(i - avg) / avg for i in incomes]
                result.income_consistency = max(
                    0.0, 1.0 - sum(devs) / len(devs))
        else:
            result.income_consistency = 0.5

        sal_kw = ["salary", "payroll", "wage", "pay ", "employer", "net pay"]
        result.has_salary_pattern   = any(k in raw_text.lower() for k in sal_kw)
        result.has_irregular_income = result.income_consistency < 0.5


# ══════════════════════════════════════════════════════════════════════════════
# Shared utility functions
# ══════════════════════════════════════════════════════════════════════════════

_DATE_FMTS = [
    "%d %b %Y", "%d %B %Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d",
    "%d/%m/%y", "%d-%m-%y", "%d-%b-%Y", "%d-%b-%y", "%d/%b/%Y",
    "%m/%d/%Y", "%d %b %y",
]
_DATETIME_FMTS = [
    "%d %b %Y %H:%M", "%d %B %Y %H:%M", "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M", "%d-%m-%Y %H:%M",
]


def _parse_date(s: str) -> Optional[datetime]:
    s = s.strip()
    for fmt in _DATE_FMTS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    m = re.search(r'(\d{4})[/\-](\d{2})[/\-](\d{2})', s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


def _parse_datetime(s: str) -> Optional[datetime]:
    s = s.strip()
    for fmt in _DATETIME_FMTS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return _parse_date(s)


def _parse_amount(s: str) -> float:
    if not s:
        return 0.0
    s = re.sub(r'[^\d.\+\-]', '', str(s).replace(',', ''))
    try:
        return float(s)
    except ValueError:
        return 0.0


_CREDIT_KW = {"salary", "credit", "deposit", "received", "transfer in",
              "inward", "refund", "interest", "topup", "income", "wage",
              "payroll", "cash in", "cashin", "payment received"}
_DEBIT_KW  = {"debit", "withdrawal", "withdraw", "transfer out", "payment",
              "charge", "fee", "outward", "purchase", "sent", "send",
              "cash out", "cashout", "bill", "airtime"}


def _classify_bank_text(desc: str) -> str:
    d = desc.lower()
    for kw in _CREDIT_KW:
        if kw in d:
            return "credit"
    for kw in _DEBIT_KW:
        if kw in d:
            return "debit"
    return "debit"


# ══════════════════════════════════════════════════════════════════════════════
# CLI test  —  python statement_parser.py <statement.pdf>
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python statement_parser.py <statement.pdf>")
        sys.exit(1)

    r = StatementParser.parse(sys.argv[1])

    print("\n" + "=" * 60)
    print("  STATEMENT ANALYSIS")
    print("=" * 60)
    print(r.as_text())

    if r.monthly_summaries:
        print("\nMonthly breakdown:")
        print(f"  {'Month':<12} {'In':>12} {'Out':>12} {'Net':>12}")
        print(f"  {'-'*12} {'-'*12} {'-'*12} {'-'*12}")
        for ms in r.monthly_summaries:
            print(f"  {ms.month:<12} {ms.total_in:>12,.0f} "
                  f"{ms.total_out:>12,.0f} {ms.net:>12,.0f}")

    print(f"\n{'✅' if r.transactions else '⚠️ '} "
          f"{len(r.transactions)} transactions extracted.")
    sys.exit(0 if r.transactions else 1)