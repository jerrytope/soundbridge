import hashlib
import json
import subprocess
import sys
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from accounts.models import User
from royalties.models import (
    ImportBatch,
    MappingRevision,
    Statement,
    RoyaltyTransaction,
    CURRENCIES,
    CATEGORIES,
)
from operations.services import audit

FIELDS = [
    "track",
    "platform",
    "amount",
    "currency",
    "work",
    "recording_id",
    "territory",
    "usage_type",
    "category",
    "units",
    "gross_amount",
    "deductions",
    "net_amount",
    "payee",
]
REQUIRED = ["track", "platform", "amount", "currency"]


def scan(raw):
    """Scanner errors, missing binaries and timeouts never count as a clean result."""
    if not settings.MALWARE_SCANNER:
        raise ValidationError(
            "Malware scanner is not configured. The upload remains quarantined."
        )
    with tempfile.TemporaryDirectory(prefix="soundbridge-scan-") as directory:
        path = Path(directory) / "upload.csv"
        path.write_bytes(raw)
        path.chmod(0o600)
        try:
            result = subprocess.run(
                [settings.MALWARE_SCANNER, "--no-summary", str(path)],
                capture_output=True,
                timeout=45,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise ValidationError("Malware scanning is unavailable. Try again later.")
        if result.returncode == 1:
            raise ValidationError("The scanner rejected this upload.", code="infected")
        if result.returncode != 0:
            raise ValidationError("Malware scanning is unavailable. Try again later.")


def extract(raw):
    try:
        result = subprocess.run(
            [sys.executable, "-I", str(Path(__file__).with_name("parse_worker.py"))],
            input=raw,
            capture_output=True,
            timeout=10,
            check=False,
        )
        payload = json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        raise ValidationError("The isolated parser could not process this CSV.")
    if result.returncode or payload.get("error"):
        raise ValidationError(payload.get("error", "CSV processing failed."))
    return payload


@transaction.atomic
def upload(user, file):
    if not file.name.lower().endswith(".csv") or file.size > 5 * 1024 * 1024:
        raise ValidationError("Choose a CSV file smaller than 5 MB.")
    User.objects.select_for_update().get(pk=user.pk)
    raw = file.read()
    digest = hashlib.sha256(raw).hexdigest()
    if user.import_batches.filter(digest=digest).exists():
        raise ValidationError(
            "This statement is already uploaded, even if its filename changed."
        )
    from billing.services import EntitlementRequired, check

    try:
        check(user, "statements", Statement.objects.filter(owner=user).count(), "Imported statements")
    except EntitlementRequired as limited:
        raise ValidationError(limited.message)
    batch = ImportBatch.objects.create(
        owner=user, name=Path(file.name).name[:300], raw=raw, digest=digest
    )
    audit(user, "statement.quarantined", batch)
    return batch


def process(batch_id):
    # Work is bounded and outside the request. A racing delete prevents persistence.
    batch = ImportBatch.objects.filter(pk=batch_id, state="quarantined").first()
    if batch is None:
        return
    try:
        scan(bytes(batch.raw))
    except ValidationError as error:
        ImportBatch.objects.filter(pk=batch_id, state="quarantined").update(
            error=error.messages[0][:500],
            state="failed" if error.code == "infected" else "quarantined",
        )
        return
    try:
        extracted = extract(bytes(batch.raw))
    except ValidationError as error:
        ImportBatch.objects.filter(pk=batch_id, state="quarantined").update(
            state="failed", error=error.messages[0][:500]
        )
        return
    suggested = {
        key: next(
            (
                column
                for column in extracted["columns"]
                if column.strip().lower().replace(" ", "_") == key
            ),
            "",
        )
        for key in FIELDS
    }
    ImportBatch.objects.filter(pk=batch_id, state="quarantined").update(
        state="review",
        error="",
        columns=extracted["columns"],
        extracted_rows=extracted["rows"],
        mapping=suggested,
    )


def normalize(batch, mapping):
    if any(mapping.get(field) not in batch.columns for field in REQUIRED):
        raise ValidationError(
            "Map track, platform, amount and currency before importing."
        )
    used = [value for value in mapping.values() if value]
    if len(used) != len(set(used)):
        raise ValidationError("Map each source column only once.")
    result = []
    for position, raw in enumerate(batch.extracted_rows):
        row = {key: raw.get(mapping.get(key, ""), "").strip() for key in FIELDS}
        if not row["track"] or not row["platform"]:
            raise ValidationError(
                f"Row {position + 2}: track and platform are required."
            )
        row["currency"] = row["currency"].upper()
        if row["currency"] not in dict(CURRENCIES):
            raise ValidationError(f"Row {position + 2}: unsupported currency.")
        if row["category"] and row["category"] not in dict(CATEGORIES):
            raise ValidationError(f"Row {position + 2}: unknown royalty category.")
        for field in ("amount", "gross_amount", "deductions", "net_amount"):
            try:
                value = Decimal(row[field]) if row[field] else None
                if value is not None and (
                    not value.is_finite() or abs(value) > Decimal("99999999999999.9999")
                ):
                    raise ValueError
                if field == "amount" and value is None:
                    raise ValueError
                row[field] = (
                    value.quantize(Decimal(".0001")) if value is not None else None
                )
            except (InvalidOperation, ValueError):
                raise ValidationError(
                    f"Row {position + 2}: {field} must be a finite amount within supported limits."
                )
        try:
            row["units"] = int(row["units"]) if row["units"] else None
            if row["units"] is not None and abs(row["units"]) > 9223372036854775807:
                raise ValueError
        except ValueError:
            raise ValidationError(
                f"Row {position + 2}: units must be a supported whole number."
            )
        for key in (
            "track",
            "platform",
            "work",
            "recording_id",
            "territory",
            "usage_type",
            "payee",
        ):
            max_length = RoyaltyTransaction._meta.get_field(key).max_length
            if len(row[key]) > max_length:
                raise ValidationError(f"Row {position + 2}: {key} is too long.")
        result.append(row)
    return result


@transaction.atomic
def confirm(user, batch_id, mapping, source, start, end):
    User.objects.select_for_update().get(pk=user.pk)
    batch = ImportBatch.objects.select_for_update().get(pk=batch_id, owner=user)
    if (
        batch.state == "imported"
        and batch.mapping == mapping
        and batch.statement.source == source
        and batch.statement.period_start == start
        and batch.statement.period_end == end
    ):
        return batch.statement
    if batch.state not in ("review", "imported"):
        raise ValidationError(
            "Wait for a successful scan and parsing before confirming."
        )
    rows = normalize(batch, mapping)
    canonical = json.dumps(
        sorted(json.dumps(row, sort_keys=True, default=str) for row in rows),
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    duplicate = Statement.objects.filter(owner=user, row_fingerprint=digest)
    if batch.statement_id:
        duplicate = duplicate.exclude(pk=batch.statement_id)
    if duplicate.exists():
        raise ValidationError(
            "Equivalent normalized statement data is already imported."
        )
    statement = batch.statement or Statement(owner=user, name=batch.name)
    statement.source = source
    statement.period_start = start
    statement.period_end = end
    statement.original_csv = batch.raw
    statement.row_fingerprint = digest
    statement.schema_version = "csv-2"
    statement.save()
    statement.transactions.all().delete()
    RoyaltyTransaction.objects.bulk_create(
        [
            RoyaltyTransaction(statement=statement, position=index, **row)
            for index, row in enumerate(rows)
        ]
    )
    MappingRevision.objects.create(batch=batch, mapping=mapping)
    batch.mapping = mapping
    batch.statement = statement
    batch.state = "imported"
    batch.save()
    audit(user, "statement.mapping.confirmed", statement)
    return statement
