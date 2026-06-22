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
  - StatementParser.is_encrypted(path) — public helper used by the UI
    to decide whether to show the password field before parsing begins

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

    # ── Client identity ───────────────────────────────────────────────────
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
    avg_monthly_income:   float = 0.0   # 12-month average (no outlier stripping)
    avg_monthly_expense:  float = 0.0
    avg_monthly_net:      float = 0.0
    net_monthly_flow:     float = 0.0   # best income signal sent to ceiling engine
    recent_avg_income:    float = 0.0   # 3-month trailing average (recency-weighted)
    latest_balance:       float = 0.0   # last known account balance from transactions
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
            f"Recent 3-Month Income: UGX {self.recent_avg_income:,.0f}",
            f"Latest Balance:        UGX {self.latest_balance:,.0f}",
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

    # ── Public encryption check (used by the UI before parsing) ─────────────

    @staticmethod
    def is_encrypted(file_path: str) -> bool:
        """
        Returns True if *file_path* is a password-protected PDF.

        Called by the chatbot screen immediately after the user picks a file
        so the UI can decide whether to show the password field — without
        waiting until parse() is called.

        Returns False for:
          - Image files (never encrypted via PDF password)
          - Non-existent files
          - Unencrypted PDFs
          - Any file that is not a PDF
        """
        if not os.path.exists(file_path):
            return False
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in (".pdf",):
            return False

        # Try pdfplumber first — if it opens without exception, not encrypted
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                _ = pdf.pages   # force load; raises on encrypted PDF
            return False
        except Exception:
            pass

        # Fallback to pypdf for a definitive answer
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            return reader.is_encrypted
        except Exception:
            # If we can't open it at all, treat as encrypted so the user
            # is given the chance to provide a password.
            return True

    # ── Entry point ──────────────────────────────────────────────────────────

    @staticmethod
    def parse(file_path: str, password: str = None) -> StatementResult:
        """
        Parse any Uganda bank / mobile money statement PDF or image.
        Auto-detects institution and extracts client_name, nin, and
        full transaction + monthly summary data.

        Args:
            file_path: Path to the statement file (PDF, image, etc.)
            password: Password for encrypted PDFs.
                      For Ugandan bank statements this is typically the
                      last 4 digits of the account/loan number.
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
            if StatementParser.is_encrypted(file_path):
                if password:
                    # Had a password but still no text → wrong password
                    r.parse_warnings.append(
                        "No text extracted. The provided password is incorrect. "
                        "Please enter the last 4 digits of the loan number."
                    )
                else:
                    # Encrypted but no password given
                    r.parse_warnings.append(
                        "No text extracted. This PDF is password-protected. "
                        "Enter the last 4 digits of the loan number as the password."
                    )
            else:
                r.parse_warnings.append(
                    "No text extracted. Ensure pdfplumber is installed and "
                    "the PDF is not corrupted."
                )
            return r

        stmt_type = StatementParser._detect_type(raw_text)
        result    = StatementResult(source_file=file_path,
                                    statement_type=stmt_type)

        # ── Extract identity fields using INSTITUTION-SPECIFIC extractor ───
        # Each institution has its own header layout (label position, name
        # placement, period format) so a single generic regex set cannot
        # work for all of them. See IDENTITY_EXTRACTORS dispatch table.
        identity_fn = StatementParser._IDENTITY_EXTRACTORS.get(
            stmt_type, StatementParser._extract_identity_generic)
        identity_fn(raw_text, result)

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
    # Identity extraction — INSTITUTION-SPECIFIC dispatch
    # ══════════════════════════════════════════════════════════════════════════
    #
    # Each institution lays out client name / account number / NIN / period
    # differently. A single generic regex set cannot reliably parse all of
    # them — for example Equity Bank prints the client name as a bare,
    # label-less line under the statement title, while MTN MoMo always
    # labels it "Account holder:". Trying to force one regex set to handle
    # both causes false matches (e.g. capturing the literal word "Number"
    # from "Account Number" as if it were the account number value).
    #
    # Add a new institution by writing its own _extract_identity_<name>
    # method and registering it in _IDENTITY_EXTRACTORS below. This keeps
    # institutions fully isolated — fixing one institution's extractor can
    # never silently break another's.
    # ══════════════════════════════════════════════════════════════════════════

    # Common words that appear in PDF headers as 14-char strings — NOT NINs
    _NIN_FALSE_POSITIVES = {
        "ACCOUNTNUMBER", "AACCOUNTUMBER", "STATEMENTDATE",
        "AACCCCOOOUUNNTT", "CUSTOMERDETAIL", "BRANCHADDRESS",
        "CLOSINGBALANCE", "OPENINGBALANCE", "AVAILABLEBALANC",
    }

    # Words/phrases that are definitely not a person's name — used by every
    # institution-specific name extractor to reject false matches.
    _NOT_A_NAME = {
        "EQUITY BANK", "STANBIC BANK", "CENTENARY BANK", "DFCU BANK",
        "MTN MOBILE", "AIRTEL MONEY", "BANK OF UGANDA", "LIMITED",
        "STATEMENT", "ACCOUNT", "BRANCH", "DETAILS", "SUMMARY",
        "ACCOUNT STATEMENT", "TRANSACTION DETAILS", "PAYMENT REFERENCE",
        "VALUE DATE", "CREDIT MONEY", "DEBIT MONEY", "MONEY IN", "MONEY OUT",
    }

    @staticmethod
    def _is_valid_nin(token: str) -> bool:
        t = token.upper()
        if t in StatementParser._NIN_FALSE_POSITIVES:
            return False
        if len(set(t)) < 5:        # repeated-letter junk like AACCCC...
            return False
        return True

    @staticmethod
    def _is_valid_name(raw: str) -> bool:
        words = raw.split()
        if len(words) < 2 or len(words) > 5:
            return False
        if re.search(r'\d', raw):
            return False
        if len(raw) <= 4:
            return False
        upper = raw.upper()
        if upper in StatementParser._NOT_A_NAME:
            return False
        if any(n in upper for n in StatementParser._NOT_A_NAME):
            return False
        return True

    # ── Equity Bank ──────────────────────────────────────────────────────────
    #
    # Real layout observed (per Bingongold sample statements):
    #
    #   Account                                    Account Number  1004102795321
    #   Statement                                   Currency        UGX
    #                                                Account Branch 1004
    #   TAMUKEDDE JACOB                              Statement Date 10/06/2026
    #   256787022284                                 Statement      09/06/2025 - 09/06/2026
    #   JACOBTAMUKEDDE@GMAIL.COM                      Period
    #                                                 Account Created 30/01/2023
    #
    # Key facts about this layout:
    #   - Client name has NO LABEL — it is the first all-caps line that looks
    #     like a person's name, appearing after the "Account Statement" title
    #     and before the phone number line.
    #   - The phone number is the line directly below the name (digits only,
    #     9-12 digits, no other letters).
    #   - "Account Number" is a LABEL followed by digits — but because the
    #     PDF is a two-column key/value box, naive regex can capture the
    #     label text itself ("Number") if the digits are pushed to a
    #     different line by pdfplumber's text extraction. We anchor strictly
    #     on a label immediately followed by a long digit run.
    #   - "Statement Period" is printed as "START - END" with a literal
    #     hyphen, both in DD/MM/YYYY format, NOT separate "from"/"to" labels.
    #   - Equity Bank does NOT print the NIN anywhere on this statement type.
    @staticmethod
    def _extract_identity_equity(text: str, result: StatementResult):
        # ── Account number ────────────────────────────────────────────────
        # Anchor strictly: label "Account Number" followed by 6+ digits,
        # allowing for whitespace/newlines from table-cell extraction, but
        # requiring the captured group to be ALL DIGITS (rejects "Number").
        m = re.search(
            r'account\s*number\D{0,15}?(\d{6,20})',
            text, re.IGNORECASE | re.DOTALL
        )
        if m:
            result.account_number = m.group(1).strip()

        # ── Statement period — "09/06/2025 - 09/06/2026" ────────────────
        m = re.search(
            r'statement\s*period\D{0,15}?'
            r'(\d{1,2}/\d{1,2}/\d{2,4})\s*-\s*(\d{1,2}/\d{1,2}/\d{2,4})',
            text, re.IGNORECASE | re.DOTALL
        )
        if m:
            result.period_from = _parse_date(m.group(1))
            result.period_to   = _parse_date(m.group(2))

        # ── Client name — label-less, first valid name-looking ALL-CAPS line
        # appearing in the first 500 chars of the document (header area).
        header = text[:500]
        for line in header.splitlines():
            candidate = line.strip()
            if not candidate:
                continue
            # Must look like a name: 2-5 words, all letters/spaces, no digits
            if re.fullmatch(r"[A-Z][A-Z'\-]*(?:\s+[A-Z][A-Z'\-]*){1,4}", candidate):
                if StatementParser._is_valid_name(candidate):
                    result.client_name    = candidate.upper()
                    result.account_holder = candidate.upper()
                    break

        # NIN is not printed on Equity Bank statements — leave as "" and
        # let the UI show a clear "Not available on this statement type"
        # message rather than a generic "Not found" (handled in the card).
        result.nin = ""

    # ── MTN MoMo ─────────────────────────────────────────────────────────────
    #
    # Layout: "Account holder: NAME" / "Wallet Number: 256XXXXXXXXX"
    # "From Date: DD MMM YYYY" / "To Date: DD MMM YYYY"
    # MTN MoMo never prints a NIN.
    @staticmethod
    def _extract_identity_mtn_momo(text: str, result: StatementResult):
        m = re.search(r'account\s+holder[:\s]+([A-Z][A-Za-z\s\'\-\.]{2,50})',
                      text, re.IGNORECASE)
        if m:
            candidate = re.split(
                r'\s+(?:wallet|account|phone|from|to|date|number)',
                m.group(1).strip(), flags=re.IGNORECASE)[0].strip()
            if StatementParser._is_valid_name(candidate):
                result.client_name    = candidate.upper()
                result.account_holder = candidate.upper()

        m = re.search(r'wallet\s*number[:\s]+([\d\s+]{9,15})',
                      text, re.IGNORECASE)
        if m:
            result.account_number = m.group(1).replace(' ', '').strip()[:20]

        m = re.search(r'from\s+date[:\s]+(\d{1,2}\s+\w+\s+\d{4})',
                      text, re.IGNORECASE)
        if m:
            result.period_from = _parse_date(m.group(1))
        m = re.search(r'to\s+date[:\s]+(\d{1,2}\s+\w+\s+\d{4})',
                      text, re.IGNORECASE)
        if m:
            result.period_to = _parse_date(m.group(1))

        result.nin = ""   # MTN MoMo never prints NIN

    # ── Airtel Money ─────────────────────────────────────────────────────────
    #
    # Layout: "Account Name: NAME" / "Mobile Number: 256XXXXXXXXX"
    # Airtel Money never prints a NIN on the statement.
    @staticmethod
    def _extract_identity_airtel(text: str, result: StatementResult):
        m = re.search(r'account\s+name[:\s]+([A-Z][A-Za-z\s\'\-\.]{2,50})',
                      text, re.IGNORECASE)
        if m:
            candidate = re.split(
                r'\s+(?:wallet|account|phone|mobile|from|to|date|number)',
                m.group(1).strip(), flags=re.IGNORECASE)[0].strip()
            if StatementParser._is_valid_name(candidate):
                result.client_name    = candidate.upper()
                result.account_holder = candidate.upper()

        m = re.search(r'mobile\s*number[:\s]+([\d\s+]{9,15})',
                      text, re.IGNORECASE)
        if m:
            result.account_number = m.group(1).replace(' ', '').strip()[:20]

        m = re.search(r'from[:\s]+(\d{1,2}[/-]\w+[/-]\d{2,4})',
                      text, re.IGNORECASE)
        if m:
            result.period_from = _parse_date(m.group(1))
        m = re.search(r'\bto[:\s]+(\d{1,2}[/-]\w+[/-]\d{2,4})',
                      text, re.IGNORECASE)
        if m:
            result.period_to = _parse_date(m.group(1))

        result.nin = ""   # Airtel Money never prints NIN

    # ── Generic fallback — unknown / unrecognised institutions ──────────────
    #
    # Used only when _detect_type() couldn't identify the institution.
    # Best-effort: tries several common label patterns. Less reliable than
    # the institution-specific extractors above by design — if a statement
    # keeps landing here, it should get its own dedicated extractor once a
    # real sample is available.
    @staticmethod
    def _extract_identity_generic(text: str, result: StatementResult):
        name_patterns = [
            r'account\s+holder\s*[:\-]\s*([A-Z][A-Za-z\s\'\-\.]{2,50})',
            r'account\s+name\s*[:\-]\s*([A-Z][A-Za-z\s\'\-\.]{2,50})',
            r'customer\s+name\s*[:\-]\s*([A-Z][A-Za-z\s\'\-\.]{2,50})',
            r'name\s+of\s+account\s+holder\s*[:\-]\s*([A-Z][A-Za-z\s\'\-\.]{2,50})',
            r'account\s+owner\s*[:\-]\s*([A-Z][A-Za-z\s\'\-\.]{2,50})',
            r'client\s*[:\-]\s*([A-Z][A-Za-z\s\'\-\.]{2,50})',
            r'(?<!\w)name\s*[:\-]\s*([A-Z][A-Za-z\s\'\-\.]{2,50})',
        ]
        _STOP_WORDS = re.compile(
            r'\s+(?:wallet|account|phone|mobile|from|to|date|number|'
            r'period|statement|nin|national|balance|branch|printed|title)',
            re.IGNORECASE
        )
        for pat in name_patterns:
            m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
            if m:
                raw = m.group(1).strip()
                raw = _STOP_WORDS.split(raw)[0].strip()
                if StatementParser._is_valid_name(raw):
                    result.client_name    = raw.upper()
                    result.account_holder = raw.upper()
                    break

        # Account number — require the captured value to be digits only,
        # never the label text itself (fixes the "Number" false capture).
        m = re.search(r'account\s*(?:no)?\D{0,15}?(\d{6,20})',
                      text, re.IGNORECASE | re.DOTALL)
        if m:
            result.account_number = m.group(1).strip()

        # Period — try "from/to" labels first, then a dash-separated range
        m = re.search(r'from\s+date[:\s]+(\d{1,2}\s+\w+\s+\d{4})',
                      text, re.IGNORECASE)
        if m:
            result.period_from = _parse_date(m.group(1))
        m = re.search(r'to\s+date[:\s]+(\d{1,2}\s+\w+\s+\d{4})',
                      text, re.IGNORECASE)
        if m:
            result.period_to = _parse_date(m.group(1))

        if not result.period_from or not result.period_to:
            m = re.search(
                r'(\d{1,2}/\d{1,2}/\d{2,4})\s*-\s*(\d{1,2}/\d{1,2}/\d{2,4})',
                text)
            if m:
                result.period_from = result.period_from or _parse_date(m.group(1))
                result.period_to   = result.period_to   or _parse_date(m.group(2))

        # NIN — attempt strict + labelled tiers only (no blind scan)
        m = _NIN_STRICT.search(text)
        if m and StatementParser._is_valid_nin(m.group(0)):
            result.nin = m.group(0).upper()
            return
        m = _NIN_LABELLED.search(text)
        if m:
            candidate = m.group(1).strip().upper()
            if len(candidate) == 14 and StatementParser._is_valid_nin(candidate):
                result.nin = candidate

    # ── Dispatch table — institution type → identity extractor ──────────────
    _IDENTITY_EXTRACTORS = {
        "equity":    _extract_identity_equity.__func__,
        "mtn_momo":  _extract_identity_mtn_momo.__func__,
        "airtel":    _extract_identity_airtel.__func__,
        # stanbic / centenary / dfcu / bank fall through to generic until
        # real sample statements are available to build dedicated extractors
    }

    # ── PDF / image reading ──────────────────────────────────────────────────
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

    # ══════════════════════════════════════════════════════════════════════════
    # MTN MoMo parser
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

    _DATE_HDRS    = {"date", "txn date", "tran date", "trans date",
                     "value date", "posting date", "transaction date", "posting"}
    _DESC_HDRS    = {"narration", "description", "particulars", "details",
                     "transaction details", "remarks", "description of transaction"}
    _REF_HDRS     = {"reference", "ref", "cheque", "chq", "ref no", "cheque no",
                     "cheque number", "reference number", "transaction ref"}
    _DEBIT_HDRS   = {"debit", "withdrawal", "withdrawals", "dr",
                     "amount dr", "debit amount"}
    _CREDIT_HDRS  = {"credit", "deposit", "deposits", "cr",
                     "amount cr", "credit amount"}
    _BALANCE_HDRS = {"balance", "running balance", "closing balance",
                     "available balance", "account balance"}
    _AMOUNT_HDRS  = {"amount", "transaction amount", "amt"}

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
                    if any(h in cell for h in StatementParser._AMOUNT_HDRS) and "amount" not in tmp:
                        tmp["amount"] = ci
                    if any(h in cell for h in StatementParser._BALANCE_HDRS) and "balance" not in tmp:
                        tmp["balance"] = ci
                    if any(h in cell for h in StatementParser._REF_HDRS) and "ref" not in tmp:
                        tmp["ref"] = ci
                has_date = "date" in tmp
                has_amount_col = ("debit" in tmp and "credit" in tmp) or "amount" in tmp
                if has_date and (has_amount_col or "desc" in tmp):
                    header_idx = ri
                    col_map    = tmp
                    break

            if header_idx is None or "date" not in col_map:
                continue

            for row in table[header_idx + 1:]:
                if not row:
                    continue
                date_cell = (str(row[col_map["date"]]).strip()
                             if col_map["date"] < len(row) and row[col_map["date"]] else "")
                dt = _parse_date(date_cell)
                if dt is None:
                    continue

                desc = ""
                if "desc" in col_map and col_map["desc"] < len(row) and row[col_map["desc"]]:
                    desc = str(row[col_map["desc"]]).replace('\n', ' ').strip()
                ref = None
                if "ref" in col_map and col_map["ref"] < len(row) and row[col_map["ref"]]:
                    ref = str(row[col_map["ref"]]).strip()

                if "debit" in col_map and "credit" in col_map:
                    debit_amt  = (_parse_amount(str(row[col_map["debit"]]))
                                  if col_map["debit"] < len(row) and row[col_map["debit"]] else 0.0)
                    credit_amt = (_parse_amount(str(row[col_map["credit"]]))
                                  if col_map["credit"] < len(row) and row[col_map["credit"]] else 0.0)
                    amount = None
                elif "amount" in col_map:
                    amount = _parse_amount(str(row[col_map["amount"]]))
                    debit_amt = None
                    credit_amt = None
                else:
                    continue

                balance = None
                if ("balance" in col_map
                        and col_map["balance"] < len(row)
                        and row[col_map["balance"]]):
                    balance = _parse_amount(str(row[col_map["balance"]]))

                if debit_amt is not None and credit_amt is not None:
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
                elif amount is not None:
                    if amount == 0:
                        continue
                    transactions.append(Transaction(
                        date=dt, description=desc, amount=amount,
                        tx_type="credit" if amount > 0 else "debit",
                        balance=balance, reference=ref))

        if not transactions:
            logger.warning(
                f"_parse_bank_debit_credit: no transactions from "
                f"extract_tables() ({len(tables)} table(s) found in PDF) — "
                f"falling back to text-regex parsing. This usually means "
                f"pdfplumber could not detect a clean table grid for this "
                f"statement's layout.")
            transactions = StatementParser._parse_bank_text(raw_text)
        else:
            logger.info(
                f"_parse_bank_debit_credit: extracted {len(transactions)} "
                f"transaction(s) from {len(tables)} table(s).")

        transactions.sort(key=lambda t: t.date)
        return transactions

    @staticmethod
    def _parse_bank_text(text: str):
        """
        Text-regex fallback for bank statements with no table structure
        detected by pdfplumber.extract_tables().

        CRITICAL FIX: the old version classified credit/debit using
        keyword matching on the description (_classify_bank_text), which
        DEFAULTS TO "debit" when no keyword matches. Real Equity Bank
        transaction descriptions (e.g. "APP/MTN/256787022284/...",
        "GOU TREASURY SINGLE ACCOUNT") contain none of the credit/debit
        keywords, so every transaction silently defaulted to debit —
        this is what caused 12 straight months of negative net flow on
        a real statement that clearly had income.

        New approach: this fallback should rarely run for Equity Bank,
        since extract_tables() should detect the 6-column table directly
        (see _parse_bank_debit_credit). If it DOES run (table detection
        failed), we no longer guess direction from keywords. Instead we
        log a clear warning and skip ambiguous lines rather than silently
        mis-classifying them as debits — a wrong "no transactions found"
        is recoverable (user is told to check the file), but a wrong
        "all debits" silently corrupts the loan decision.
        """
        transactions = []
        date_re   = re.compile(
            r'\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}'
            r'|\d{1,2}[/\-][A-Za-z]{3}[/\-]\d{2,4}'
            r'|\d{4}[/\-]\d{2}[/\-]\d{2})\b'
        )
        amount_re = re.compile(r'([\d,]+(?:\.\d{2}))')
        skipped_ambiguous = 0

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
            desc = amount_re.sub('', line[dm.end():]).strip()[:80]

            # Only classify when a real keyword is present. If no keyword
            # matches, we cannot safely guess direction — skip the line
            # rather than silently defaulting to debit.
            tx_type = _classify_bank_text_strict(desc)
            if tx_type is None:
                skipped_ambiguous += 1
                continue

            amount = (amounts[0] if len(amounts) == 1
                      else amounts[-2] if len(amounts) >= 2 else amounts[0])
            if tx_type == "debit":
                amount = -amount
            transactions.append(Transaction(
                date=dt, description=desc, amount=amount, tx_type=tx_type,
                balance=amounts[-1] if len(amounts) >= 2 else None))

        if skipped_ambiguous > 0:
            logger.warning(
                f"_parse_bank_text: skipped {skipped_ambiguous} line(s) with "
                f"no credit/debit keyword match — table extraction likely "
                f"failed for this statement; transactions may be incomplete.")
        return transactions

    # ══════════════════════════════════════════════════════════════════════════
    # Summary builder — shared by all parsers
    # ══════════════════════════════════════════════════════════════════════════

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

        # Latest known balance — from the most recent transaction that has one
        bal_txns = [t for t in txns if t.balance is not None]
        if bal_txns:
            result.latest_balance = bal_txns[-1].balance

        monthly: dict = defaultdict(lambda: {"in": 0.0, "out": 0.0, "count": 0})
        for t in txns:
            key = t.date.strftime("%b %Y")
            if t.tx_type == "credit":
                monthly[key]["in"]  += t.amount
            else:
                monthly[key]["out"] += abs(t.amount)
            monthly[key]["count"] += 1

        start = result.period_from or (min((t.date for t in txns), default=None))
        end   = result.period_to   or (max((t.date for t in txns), default=None))

        months_ordered = []
        if start and end:
            cur  = datetime(start.year, start.month, 1)
            last = datetime(end.year,   end.month,   1)
            while cur <= last:
                months_ordered.append(cur.strftime("%b %Y"))
                if cur.month == 12:
                    cur = datetime(cur.year + 1, 1, 1)
                else:
                    cur = datetime(cur.year, cur.month + 1, 1)
        else:
            months_ordered = sorted(monthly.keys(),
                                    key=lambda kv: datetime.strptime(kv, "%b %Y"))

        for m in months_ordered:
            _ = monthly[m]

        result.monthly_summaries = [
            MonthlySummary(
                month=m, total_in=v["in"], total_out=v["out"],
                net=v["in"] - v["out"], tx_count=v["count"])
            for m, v in sorted(
                monthly.items(),
                key=lambda kv: datetime.strptime(kv[0], "%b %Y"))
        ]

        result.months_covered = max(len(result.monthly_summaries), 1)
        incomes = [m.total_in for m in result.monthly_summaries]

        def _median(xs):
            s = sorted(xs)
            n = len(s)
            if n == 0:
                return 0.0
            mid = n // 2
            return (s[mid] if n % 2 == 1 else (s[mid - 1] + s[mid]) / 2)

        # ── Avg monthly income: straight average, NO outlier stripping ────────
        # IQR stripping was incorrectly removing genuine large credits
        # (e.g. business income, large transfers) and zeroing out income entirely.
        result.avg_monthly_income = (result.total_credits / result.months_covered
                                     if result.months_covered else 0.0)
        result.avg_monthly_expense = (result.total_debits / result.months_covered
                                      if result.months_covered else 0.0)
        result.avg_monthly_net     = (result.avg_monthly_income
                                      - result.avg_monthly_expense)

        # ── Recent 3-month trailing average (recency-weighted income signal) ──
        # Uses only the last 3 months so a large recent credit (like the 16M)
        # is properly reflected without being diluted by older zero months.
        recent_summaries = result.monthly_summaries[-3:]
        if recent_summaries:
            result.recent_avg_income = (
                sum(m.total_in for m in recent_summaries) / len(recent_summaries))
        else:
            result.recent_avg_income = result.avg_monthly_income

        # ── net_monthly_flow: use the HIGHER of 12-month avg or 3-month recent ─
        # This ensures a borrower with recent strong income is not penalised
        # for an earlier gap period, while still protecting against one-month
        # spikes being the only signal.
        best_income  = max(result.avg_monthly_income, result.recent_avg_income)
        best_expense = result.avg_monthly_expense
        result.net_monthly_flow = best_income - best_expense

        # ── Income consistency: only count months that had ANY transactions ───
        # Zero-income months caused by a gap period (no transactions at all)
        # should not penalise the consistency score — the borrower simply
        # was not active in those months, not earning irregularly.
        active_incomes = [m.total_in for m in result.monthly_summaries
                          if m.tx_count > 0]
        if active_incomes and len(active_incomes) >= 2:
            med = _median(active_incomes)
            if med == 0:
                nonzero = sum(1 for i in active_incomes if i > 0)
                result.income_consistency = (0.0 if nonzero == 0
                                             else nonzero / len(active_incomes))
            else:
                # Band: within 30%-300% of median (wider than before to handle
                # irregular earners whose income genuinely varies month-to-month)
                in_band = sum(1 for i in active_incomes
                              if 0.30 * med <= i <= 3.0 * med)
                result.income_consistency = in_band / len(active_incomes)
        elif active_incomes:
            result.income_consistency = 1.0   # only 1 active month — no pattern yet
        else:
            result.income_consistency = 0.0

        credit_tx_by_month = defaultdict(list)
        for t in credits:
            credit_tx_by_month[t.date.strftime("%b %Y")].append(t)

        rep_days, rep_amounts = [], []
        for ms in result.monthly_summaries:
            txs = credit_tx_by_month.get(ms.month, [])
            if not txs:
                continue
            best = max(txs, key=lambda x: x.amount)
            rep_days.append(best.date.day)
            rep_amounts.append(best.amount)

        result.has_salary_pattern = False
        if len(rep_days) >= 3:
            median_day = int(_median(rep_days))
            day_match  = sum(1 for d in rep_days if abs(d - median_day) <= 3)
            med_amt    = _median(rep_amounts)
            amt_match  = sum(1 for a in rep_amounts
                             if med_amt * 0.7 <= a <= med_amt * 1.3)
            if (day_match  >= max(3, int(0.75 * len(rep_days)))
                    and amt_match >= max(3, int(0.75 * len(rep_amounts)))):
                result.has_salary_pattern = True

        sal_kw = ["salary", "payroll", "wage", "pay ", "employer", "net pay"]
        if any(k in raw_text.lower() for k in sal_kw):
            result.has_salary_pattern = True

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
    """
    Legacy keyword classifier — DEFAULTS TO DEBIT when no keyword matches.
    Kept only for backward compatibility with any external callers.
    Internal code should use _classify_bank_text_strict() instead, which
    returns None on ambiguous input rather than silently guessing.
    """
    d = desc.lower()
    for kw in _CREDIT_KW:
        if kw in d:
            return "credit"
    for kw in _DEBIT_KW:
        if kw in d:
            return "debit"
    return "debit"


def _classify_bank_text_strict(desc: str) -> Optional[str]:
    """
    Returns "credit", "debit", or None if no keyword matches.
    Used by _parse_bank_text() so ambiguous transactions are SKIPPED
    rather than silently assumed to be debits — this was the root cause
    of statements showing 100% negative cash flow when the real table
    extraction failed and descriptions contained no recognisable keyword
    (e.g. "APP/MTN/256787022284/...", "GOU TREASURY SINGLE ACCOUNT").
    """
    d = desc.lower()
    for kw in _CREDIT_KW:
        if kw in d:
            return "credit"
    for kw in _DEBIT_KW:
        if kw in d:
            return "debit"
    return None


# ══════════════════════════════════════════════════════════════════════════════
# CLI test  —  python statement_parser.py <statement.pdf>
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python statement_parser.py <statement.pdf> [password]")
        sys.exit(1)

    pw  = sys.argv[2] if len(sys.argv) > 2 else None
    enc = StatementParser.is_encrypted(sys.argv[1])
    if enc:
        print(f"[INFO] PDF is encrypted. Password provided: {'yes' if pw else 'no'}")

    r = StatementParser.parse(sys.argv[1], password=pw)

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