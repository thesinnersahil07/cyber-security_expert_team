#!/usr/bin/env python3
"""UTC super-timeline merger for heterogeneous DFIR CSV and JSONL log exports.

Normalizes timestamps from mixed sources (ISO-8601, CloudTrail eventTime,
Windows/Linux exports) into a single sorted UTC CSV and flags source files
containing backwards timestamp jumps (possible clock skew or timestomping).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

TIME_KEYS = ("timestamp", "utc_time", "time", "eventTime", "@timestamp", "datetime", "date")
MSG_KEYS = ("event", "message", "eventName", "action", "summary", "command", "detail")


def parse_utc(raw: str) -> datetime | None:
    value = raw.strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%b %d %H:%M:%S %Y"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def pick_field(row: dict, keys: tuple[str, ...]) -> str:
    lower_map = {k.lower(): v for k, v in row.items()}
    for key in keys:
        if key.lower() in lower_map and lower_map[key.lower()] not in (None, ""):
            return str(lower_map[key.lower()])
    return ""


def load_records(path: Path) -> tuple[list[dict], int]:
    records: list[dict] = []
    out_of_order = 0
    prev_dt: datetime | None = None

    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
            rows = list(csv.DictReader(handle))
    else:
        raw_text = path.read_text(encoding="utf-8", errors="replace").strip()
        if raw_text.startswith("{") and '"Records"' in raw_text:
            rows = json.loads(raw_text).get("Records", [])
        elif raw_text.startswith("["):
            rows = json.loads(raw_text)
        else:
            rows = [json.loads(line) for line in raw_text.splitlines() if line.strip().startswith("{")]

    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_ts = pick_field(row, TIME_KEYS)
        dt = parse_utc(raw_ts)
        if dt is None:
            continue
        if prev_dt is not None and dt < prev_dt:
            out_of_order += 1
        prev_dt = dt
        msg = pick_field(row, MSG_KEYS) or json.dumps(row)[:160]
        records.append(
            {
                "utc_time": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source": path.name,
                "event": msg.replace("\n", " ")[:240],
                "status": "[CONFIRMED]",
            }
        )
    return records, out_of_order


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge CSV/JSONL/CloudTrail logs into a UTC super-timeline CSV.")
    parser.add_argument("inputs", nargs="+", type=Path, help="Input CSV, JSON, or JSONL log files.")
    parser.add_argument("-o", "--output", type=Path, default=Path("timeline.csv"), help="Output CSV file path.")
    args = parser.parse_args()

    all_rows: list[dict] = []
    anomalies: dict[str, int] = {}

    for path in args.inputs:
        if not path.is_file():
            print(f"Error: file not found: {path}", file=sys.stderr)
            return 1
        rows, jumps = load_records(path)
        all_rows.extend(rows)
        if jumps > 0:
            anomalies[path.name] = jumps

    all_rows.sort(key=lambda r: r["utc_time"])

    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["utc_time", "source", "event", "status"])
        writer.writeheader()
        writer.writerows(all_rows)

    print(
        json.dumps(
            {
                "output_csv": str(args.output),
                "total_events": len(all_rows),
                "backwards_timestamp_jumps": anomalies,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
