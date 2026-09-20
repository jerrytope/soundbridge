"""Standalone CSV parser, run with -I and OS resource limits outside the web request."""

import csv
import io
import json
import sys

try:
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
except ImportError:
    pass
try:
    raw = sys.stdin.buffer.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise ValueError("File exceeds 5 MB.")
    text = raw.decode("utf-8-sig")
    if "\x00" in text:
        raise ValueError("Binary content is not supported.")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    csv.field_size_limit(16000)
    reader = csv.DictReader(io.StringIO(text), dialect=dialect, strict=True)
    headers = reader.fieldnames
    if (
        not headers
        or len(headers) > 60
        or len(set(headers)) != len(headers)
        or any(not h.strip() or len(h) > 200 for h in headers)
    ):
        raise ValueError("Supply unique nonempty headers (at most 60 columns).")
    rows = []
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("Column counts differ from the header.")
        if any(value.strip() for value in row.values()):
            rows.append(row)
        if len(rows) > 20000:
            raise ValueError("At most 20,000 rows are supported.")
    if not rows:
        raise ValueError("The CSV contains no data.")
    json.dump({"columns": headers, "rows": rows}, sys.stdout)
except (ValueError, UnicodeError, csv.Error) as error:
    json.dump({"error": str(error)}, sys.stdout)
    sys.exit(1)
