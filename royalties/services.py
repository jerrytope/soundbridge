"""Royalty estimation and statement ingestion.

Ported from src/domain.js (`estimate`, `normalizeStatement`, `totals`) and the
CSV handling in the React Upload screen, with Papa Parse replaced by Python's
csv module. The validation rules and the user-facing error strings are
deliberately identical, so the same inputs produce the same messages.

Money is Decimal throughout (PRD 12.3): no float ever touches an amount.
"""

import csv
import hashlib
import io
from decimal import Decimal, InvalidOperation

CURRENCIES = ("USD", "NGN", "EUR", "GBP")
REQUIRED_COLUMNS = ("track", "platform", "amount", "currency")
MAX_CSV_BYTES = 5 * 1024 * 1024

SAMPLE_CSV = (
    "track,platform,amount,currency\n"
    "My track,Spotify,25.50,USD\n"
    "My track,Apple Music,12.25,USD\n"
)


class StatementError(ValueError):
    """Raised with the exact message the UI shows the creator."""


def estimate(streams, rate, share):
    """Port of estimate() in src/domain.js, using Decimal arithmetic.

    Returns the mid scenario. The rate is whatever the creator entered from
    their own statement or agreement, so this is a scenario and never a payout
    forecast (PRD 10.2); the screen says so above the form.
    """
    try:
        streams_value = int(str(streams).strip())
        rate_value = Decimal(str(rate).strip())
        share_value = Decimal(str(share).strip())
    except (InvalidOperation, TypeError, ValueError):
        raise StatementError("Enter valid streams, rate and ownership.")
    if (
        not rate_value.is_finite()
        or not share_value.is_finite()
        or streams_value < 0
        or rate_value < 0
        or share_value < 0
        or share_value > 100
    ):
        raise StatementError("Enter valid streams, rate and ownership.")
    result = streams_value * rate_value * share_value / Decimal(100)
    if result > Decimal("99999999999999"):
        raise StatementError("The estimate is too large.")
    return result.quantize(Decimal("0.0001"))


def parse_csv(text):
    """Read a statement CSV into dictionaries, rejecting malformed files."""
    try:
        sample = text[:4096]
        dialect = (
            csv.Sniffer().sniff(sample, delimiters=",;\t")
            if sample.strip()
            else csv.excel
        )
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if reader.fieldnames is None:
        raise StatementError("The CSV contains no data.")
    rows = []
    for row in reader:
        if None in row or any(key is None for key in row):
            raise StatementError(
                "Unable to read this CSV. Check column counts and quotation marks."
            )
        if not any((value or "").strip() for value in row.values()):
            continue  # skip empty lines, as Papa Parse's greedy mode did
        rows.append(row)
    return rows


def normalize_statement(rows):
    """Port of normalizeStatement() in src/domain.js.

    Required columns are track, platform, amount and currency; supported
    currencies are USD, NGN, EUR and GBP. Negative adjustments are allowed.
    Row numbers in errors count the header line, exactly as before.
    """
    if not rows:
        raise StatementError("The CSV contains no data.")
    result = []
    for index, raw in enumerate(rows):
        row = {
            (key or "").strip().lower(): str(value or "").strip()
            for key, value in raw.items()
        }
        amount = row.get("amount", "")
        currency = row.get("currency", "").upper()
        try:
            amount_value = Decimal(amount) if amount else None
        except InvalidOperation:
            amount_value = None
        if (
            not row.get("track")
            or not row.get("platform")
            or not currency
            or amount_value is None
            or not amount_value.is_finite()
            or currency not in CURRENCIES
        ):
            raise StatementError(
                f"Row {index + 2}: provide track, platform, numeric amount and currency (USD, NGN, EUR or GBP)."
            )
        result.append(
            {
                "track": row["track"],
                "platform": row["platform"],
                "amount": amount_value.quantize(Decimal("0.0001")),
                "currency": currency,
                "territory": row.get("territory", ""),
                "usage_type": row.get("usage type", "") or row.get("usage_type", ""),
                "work": row.get("work", ""),
                "recording_id": row.get("recording", "") or row.get("isrc", ""),
                "payee": row.get("payee", ""),
            }
        )
    return result


def fingerprint(rows):
    """Stable digest of normalised rows, used to detect a repeat import."""
    payload = "|".join(
        f"{row['track']}~{row['platform']}~{row['amount']}~{row['currency']}"
        for row in rows
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def totals(statements):
    """Per-currency totals across statements. Currencies are never converted."""
    result = {}
    for statement in statements:
        for row in statement.transactions.all():
            result[row.currency] = result.get(row.currency, Decimal(0)) + row.amount
    return result
