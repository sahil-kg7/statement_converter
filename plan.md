## Plan: Add HDFC Savings V2 Parser for Revised PDF Format

### TL;DR

The existing HDFC savings parser (`hdfc_savings.py`) matches a format with `"Txn Date"` / `"Withdrawals"` / `"Deposits"` column headers and 4-digit year dates. HDFC has issued statements with a different column layout (`"Date"` / `"Narration"` / `"Withdrawal Amt."` / `"Deposit Amt."`) and 2-digit year dates — currently undetectable and unparseable. This plan adds a **second parser** (`hdfc_savings_v2.py`) alongside the existing one, fixes the **detector** to recognize the new format, and **registers** v2 before v1 in the orchestrator (same pattern as the Kotak savings v1/v2 setup).

---

### Architecture Overview

**Root cause**: The new PDF has:
1. A **different column header**: `"Date / Narration / Chq./Ref.No. / Value Dt / Withdrawal Amt. / Deposit Amt. / Closing Balance"` instead of `"Txn Date / Description / Withdrawals / Deposits / Balance"`
2. **2-digit years** (`DD/MM/YY`) instead of 4-digit (`DD/MM/YYYY`)
3. An **extra ref-number + value-date** column pair between narration and amounts
4. **Multi-page structure** with repeating account-info headers per page
5. The existing detection keyword `"savings account details"` is **missing** from the new format

**Detection fix**: Change the HDFC Savings detection heuristic to use `"savings a/c - resident"` alone (present in both old and new formats). The current `and` with `"savings account details"` makes the new format undetectable.

**Parser approach** (matching `kotak_savings_v2.py` patterns):
- Column-position-based extraction for amounts using `pdftotext -layout` fixed positions (Withdrawal=137, Deposit=169)
- Date extracted via `DD/MM/YY` → converted to `DD/MM/YYYY` by prefixing `20` (these are all 2026 statements)
- Narration extracted by splitting the text between date-end and withdrawal-column on 2+ spaces; first chunk is the narration, second is the ref number, third is the value date
- Continuation lines (indented, no date prefix) appended to current transaction's description
- Multi-page: filter known page-header/footer lines, stop at `"STATEMENT SUMMARY"`

---

### Design Decisions

- **Detection**: Use `"savings a/c - resident"` as the sole HDFC savings signal — both old and new formats contain this, and it's unique to HDFC savings accounts (no other bank in the system uses this phrasing). Remove the `"savings account details"` requirement.
- **2-digit year handling**: Convert `DD/MM/YY` → `DD/MM/YYYY` (prefix `20`) in the parser before calling `normalize_transaction_date`. This avoids modifying the shared date normalizer and is safe for 2026-era statements.
- **Column positions**: Hardcode the fixed positions derived from the `pdftotext -layout` output: Withdrawal starts at col 137, Deposit at col 169, Balance at col 195. These are guaranteed by `pdftotext -layout` columnar preservation.
- **Narration extraction**: Split the region between date-end and withdrawal-column on `\s{2,}` (2+ spaces). The first segment is the narration. This works because `pdftotext -layout` preserves column spacing and the ref number + value date are separated by large gaps.
- **Multi-page detection**: Check for known page-header text patterns (customer name, address, account details) that repeat on each page. These lines are skipped entirely. The column header also repeats — skip it on subsequent pages.
- **Parser registration**: Add `HdfcSavingsPdfParserV2` **before** `HdfcSavingsPdfParser` in the orchestrator's parser list for HDFC Savings. If v2 fails (unlikely for matching format), v1 is tried as fallback.

---

### Files to Create

| File | Purpose | Priority |
|------|---------|----------|
| `backend/app/parsers/banks/hdfc_savings_v2.py` | New parser for the revised HDFC savings PDF column layout | HIGH |

### Files to Modify

| File | What Changes | Priority |
|------|-------------|----------|
| `backend/app/parsers/detector.py` | Fix HDFC Savings detection to work with new format | HIGH |
| `backend/app/pipeline/orchestrator.py` | Register `HdfcSavingsPdfParserV2` before `HdfcSavingsPdfParser` | HIGH |
| `backend/tests/test_pdf_parsers.py` | Add test for the new PDF format | HIGH |
| `backend/tests/test_pdf_detector.py` | Add detection test for the new PDF format | MEDIUM |

---

### Implementation Steps

#### Phase A — Fix Detection (`detector.py`)

**Current code** (line 22):
```python
if "savings account details" in lower_text and "savings a/c - resident" in lower_text:
    return PdfDetectionResult(BankName.HDFC, StatementKind.SAVINGS)
```

**Problem**: New format does not contain `"savings account details"` — it only has `"savings a/c - resident"` (inside `"Account Type : SAVINGS A/C - RESIDENT (100)"`). Neither format can be uniquely fingerprinted by `"savings a/c - resident"` alone? **Check**: No other bank in the system uses `"savings a/c"` phrasing; Kotak uses `"account type savings"` without the `/c - resident` suffix. So `"savings a/c - resident"` is specific enough.

**Change to**: Detect on `"savings a/c - resident"` alone. Both old and new formats contain it.

```python
if "savings a/c - resident" in lower_text:
    return PdfDetectionResult(BankName.HDFC, StatementKind.SAVINGS)
```

Move this line **above** the existing check (or replace the existing check entirely). Keep `"savings account details"` as an optional additional path for robustness (or remove it since the new single check covers both).

**Recommendation**: Replace entirely. `"savings a/c - resident"` is present in both formats and is HDFC-specific. Removing the `"savings account details"` requirement eliminates the detection gap.

**Files**: `backend/app/parsers/detector.py` — line 22-23

---

#### Phase B — Create `hdfc_savings_v2.py`

New file at `backend/app/parsers/banks/hdfc_savings_v2.py`. Follow the structural pattern of `kotak_savings_v2.py`.

**Class**: `HdfcSavingsPdfParserV2(PdfBankParser)` — `bank = BankName.HDFC`, `statement_kind = StatementKind.SAVINGS`

**Constants**:

```python
ROW_RE = re.compile(r"^\s*(\d{2}/\d{2}/\d{2})\s+(.*)$")
# Column positions from pdftotext -layout analysis:
# Header: "Date / Narration / Chq./Ref.No. / Value Dt / Withdrawal Amt. / Deposit Amt. / Closing Balance"
#   'Withdrawal Amt.' starts at position 137
#   'Deposit Amt.' starts at position 169
#   'Closing Balance' starts at position 195
WITHDRAWAL_COL = 137
DEPOSIT_COL = 169
BALANCE_COL = 195  # captured but not used
```

**Page header/footer tokens** — lines to skip between pages:
- `_PAGE_HEADER_TOKENS`: `"Page No"`, `"MR     SAHIL"`, `"E-16 INDRAPRASTHA"`, `"RATANLAL NAGAR"`, `"KANPUR NAGAR"`, `"UTTAR PRADESH"`, `"JOINT HOLDERS"`, `"Nomination"`, `"Statement From"`, `"Account Branch"`, `"Address"`, `"Phone no."`, `"Email"`, `"Cust ID"`, `"Account No"`, `"A/C Open"`, `"Account Status"`, `"RTGS/NEFT"`, `"Branch Code"`, `"Account Type"`, `"OD Limit"`, lines starting with `"PLOT"`, `"NEAR"`, `"UDYOG"`, `"City"`, `"State"`
- `_PAGE_FOOTER_TOKENS`: `"HDFC BANK LIMITED"`, `"*Closing balance includes"`, `"Contents of this statement"`, `"GSTIN"`, `"Registered Office Address"`, `"computer generated statement"`, `"not require signature"`
- `_STOP_TOKENS`: `"STATEMENT SUMMARY"`, `"Opening Balance"`, `"Generated On"`, `"Generated By"`

**`parse()` method**:

```
lines = extracted_text.splitlines()
self._find_header_line(lines)
current = None
transactions = []

for line in self._iter_table_lines(lines):
    date_match = ROW_RE.match(line)
    if date_match is not None:
        # Verify this is truly a data row by checking for amounts in column zone
        withdrawal_raw = line[WITHDRAWAL_COL:DEPOSIT_COL].strip()
        deposit_raw = line[DEPOSIT_COL:BALANCE_COL].strip()
        if withdrawal_raw or deposit_raw:
            current = self._append_completed(transactions, current)
            current = self._start_transaction(line, date_match)
            continue
    
    # Continuation line — append to current description
    self._append_continuation(current, line)

if current is not None:
    transactions.append(self._build_transaction(current))

return transactions
```

**`_find_header_line()`**: Search for a line containing `"Date"` AND `"Narration"` AND `"Withdrawal Amt."` AND `"Deposit Amt."`. Raise `ValueError("Could not locate the HDFC savings v2 transaction table")` if not found.

**`_iter_table_lines()`**: After the first column header, yield lines that:
- Are not empty / form-feed only
- Don't match any `_PAGE_HEADER_TOKENS` or `_PAGE_FOOTER_TOKENS`
- Don't match `_STOP_TOKENS` (which also terminates iteration)
- Skip repeated column headers on subsequent pages (detect by `"Date"` + `"Narration"` + `"Withdrawal Amt."`)

**`_start_transaction()`**:

```
Extract date from date_match.group(1)  # "DD/MM/YY"
Convert to 4-digit: "DD/MM/YYYY" using _normalize_date()

# Extract narration from the region between date-end and withdrawal column
# Split on 2+ spaces — first segment is the narration, second is ref no, third is value date
middle = line[date_match.end():WITHDRAWAL_COL].strip()
parts = re.split(r"\s{2,}", middle)
narration = parts[0].strip() if parts else ""

withdrawal_raw = line[WITHDRAWAL_COL:DEPOSIT_COL].strip()
deposit_raw = line[DEPOSIT_COL:BALANCE_COL].strip()

return {
    "date": normalized_date,
    "description_parts": [narration],
    "withdrawal": withdrawal_raw,
    "deposit": deposit_raw,
}
```

**`_append_continuation()`**: Strip the indented continuation text and append to `current["description_parts"]`.

**`_build_transaction()`**: Same logic as v1 — use `signed_amount()` (or equivalent logic: `deposit if deposit > 0 else -withdrawal`). Run dates and descriptions through the normalizers.

**`_normalize_date()`**: Static helper:
```python
@staticmethod
def _normalize_date(dd_mm_yy: str) -> str:
    parts = dd_mm_yy.split("/")
    return f"{parts[0]}/{parts[1]}/20{parts[2]}"
```

**Files**: `backend/app/parsers/banks/hdfc_savings_v2.py`

---

#### Phase C — Register V2 in Orchestrator

**Current code** (`orchestrator.py:26`):
```python
(BankName.HDFC, StatementKind.SAVINGS): [HdfcSavingsPdfParser()],
```

**Change to**:
```python
(BankName.HDFC, StatementKind.SAVINGS): [HdfcSavingsPdfParserV2(), HdfcSavingsPdfParser()],
```

Also add the import:
```python
from app.parsers.banks.hdfc_savings_v2 import HdfcSavingsPdfParserV2
```

This ensures v2 is tried first (for the new format), and v1 is the fallback (for the old format).

**Files**: `backend/app/pipeline/orchestrator.py` — line 26, plus import at top

---

#### Phase D — Add Tests

**`test_pdf_parsers.py`** — Add a new test function:

```python
def test_hdfc_savings_v2_pdf_parses_new_format() -> None:
    transactions = _convert("hdfc 1 march to 19 june.pdf")
    
    assert len(transactions) == 30  # exact count from the PDF
    
    # Transaction 1: IMPS deposit
    assert transactions[0].transaction_date == "01-03-2026"
    assert transactions[0].amount == Decimal("60000.00")
    assert "IMPS" in transactions[0].description
    
    # Transaction 3: POS debit
    assert transactions[2].amount == Decimal("-3550.52")
    assert "POS" in transactions[2].description
    assert "NIVA" in transactions[2].description
    
    # Transaction 5: Bill pay debit
    assert transactions[4].amount == Decimal("-75991.44")
    assert "BILLPAY" in transactions[4].description
    
    # Transaction: Interest credit
    interest_tx = [tx for tx in transactions if "INTEREST" in tx.description]
    assert len(interest_tx) == 1
    assert interest_tx[0].amount == Decimal("462.00")
    assert interest_tx[0].transaction_date == "01-04-2026"
    
    # Last transaction: RD installment debit
    assert transactions[-1].amount == Decimal("-5000.00")
    assert "RD INSTALLMENT" in transactions[-1].description
```

**`test_pdf_detector.py`** — Add:

```python
def test_hdfc_savings_v2_detection() -> None:
    detection = detect_pdf_statement(_extract("hdfc 1 march to 19 june.pdf"))
    assert detection is not None
    assert detection.bank is BankName.HDFC
    assert detection.statement_kind is StatementKind.SAVINGS
```

**Note**: The exact count (30) and specific assertion values need to be verified by running the parser against the actual PDF and inspecting the output. The values above are estimates based on visual inspection of the extracted text (26 visible `DD/MM/YY` dated rows, but some may be multi-line transactions).

**Files**: `backend/tests/test_pdf_parsers.py`, `backend/tests/test_pdf_detector.py`

---

#### Phase E (Optional) — Copy PDF to Workspace Root

The test helpers read from the workspace root. Copy `"/home/abcd/Downloads/hdfc 1 march to 19 june.pdf"` to `"/home/abcd/projects/statement_converter/hdfc 1 march to 19 june.pdf"` so tests can find it.

---

### Implementation Order

```
Phase A (detector fix) ──────┐
                              ├──> Phase C (orchestrator)
Phase B (v2 parser file) ────┘         │
                                        └──> Phase D (tests)
                                               │
                                               └──> Phase E (copy PDF)
```

**Phase A** and **Phase B** are independent and can run in parallel. **Phase C** depends on both being complete. **Phase D** depends on Phase C.

---

### Verification

1. `pytest backend/tests/test_pdf_detector.py::test_hdfc_savings_v2_detection -v` — detection works for the new format
2. `pytest backend/tests/test_pdf_parsers.py::test_hdfc_savings_v2_pdf_parses_new_format -v` — parser produces correct count and amounts
3. `pytest backend/tests/test_pdf_parsers.py::test_hdfc_savings_pdf_parses_expected_rows -v` — existing v1 format still works
4. `pytest backend/tests/ -v` — full test suite passes (all existing tests remain green)

---

### Decisions & Scope

- **In scope**: New HDFC savings PDF format with `"Date / Narration / Withdrawal Amt. / Deposit Amt."` columns
- **In scope**: Detection fix to recognize the new format
- **In scope**: Parser registration in orchestrator (v2 first, v1 fallback)
- **In scope**: Multi-page statements with repeating headers
- **Not in scope**: HDFC credit card (different format, different detection path)
- **Not in scope**: Changes to `normalize/date.py` or `normalize/amount.py`
- **Not in scope**: LLM fallback or generic PDF fallback changes
- **Not in scope**: The existing `hdfc_savings.py` parser — it remains unchanged for the old format

### Open Questions

1. **Transaction count**: The exact number of transactions in `"hdfc 1 march to 19 june.pdf"` needs to be verified by running the parser. Estimated: ~26-30 based on visual inspection of the extracted text.
