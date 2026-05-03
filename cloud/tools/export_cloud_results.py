from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any


DEFAULT_TABLES = ("CloudTelemetry", "CloudAlerts", "CloudInvalid")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Phase 5 Azure Table results to JSONL and CSV.")
    parser.add_argument("--connection-string", default=os.getenv("CLOUD_RESULTS_STORAGE_CONNECTION_STRING"))
    parser.add_argument("--output-dir", type=Path, default=Path("cloud/results"))
    parser.add_argument("--tables", nargs="*", default=list(DEFAULT_TABLES))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.connection_string:
        print("CLOUD_RESULTS_STORAGE_CONNECTION_STRING or --connection-string is required.")
        return 2

    from azure.data.tables import TableServiceClient

    args.output_dir.mkdir(parents=True, exist_ok=True)
    service = TableServiceClient.from_connection_string(args.connection_string)
    for table_name in args.tables:
        rows = list(service.get_table_client(table_name).list_entities())
        _write_jsonl(args.output_dir / f"{table_name}.jsonl", rows)
        _write_csv(args.output_dir / f"{table_name}.csv", rows)
        print(f"Exported {len(rows)} rows from {table_name}.")
    return 0


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(dict(row), default=str, separators=(",", ":"), sort_keys=True) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in keys})


if __name__ == "__main__":
    raise SystemExit(main())
