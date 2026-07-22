#!/usr/bin/env python3

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_CSV = ROOT / "2026-07-13_10_per_field.csv"
DEFAULT_JSON = ROOT / "participantCodes.json"
DEFAULT_OUT = ROOT / "participant_paper_contacts.csv"





def split_name(name):
    parts = str(name or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[-1]


def load_csv_by_arxiv_id(csv_path):
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as input_file:
        reader = csv.DictReader(input_file)
        if "arxiv_id" not in (reader.fieldnames or []):
            raise SystemExit(f"Missing arxiv_id column in {csv_path}")

        rows_by_id = {}
        for row in reader:
            paper_id = row.get("arxiv_id")
            if paper_id:
                rows_by_id[paper_id] = row

    return rows_by_id


def load_participant_codes(json_path):
    with Path(json_path).open("r", encoding="utf-8") as input_file:
        data = json.load(input_file)

    if not isinstance(data, dict):
        raise SystemExit(f"Expected {json_path} to contain a JSON object")
    return data


def build_rows(csv_path, json_path):
    csv_rows = load_csv_by_arxiv_id(csv_path)
    participant_codes = load_participant_codes(json_path)

    output_rows = []
    missing = []

    for participant_code, entry in participant_codes.items():
        if not isinstance(entry, dict):
            missing.append((participant_code, ""))
            continue

        paper_id = entry.get("paperId")
        csv_row = csv_rows.get(paper_id)
        if csv_row is None:
            missing.append((participant_code, paper_id))
            continue

        name = (csv_row.get("corresponding_author") or "").strip()
        first_name, last_name = split_name(name)

        output_rows.append(
            {
                "email": (csv_row.get("email") or "").strip(),
                "name": name,
                "first name": first_name,
                "last name": last_name,
                "paperId": entry.get("paperId", ""),
                "participantCode": participant_code,
                "paperTitle": entry.get("paperTitle", ""),
            }
        )

    return output_rows, missing


def write_output(rows, out_path):
    fieldnames = ["email", "name", "first name", "last name", "paperId", "participantCode", "paperTitle"]
    with Path(out_path).open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Join paper contact data from a CSV with participantCodes.json."
    )
    parser.add_argument("--csv", default=DEFAULT_CSV, help=f"Input CSV path. Defaults to {DEFAULT_CSV.name}.")
    parser.add_argument("--json", default=DEFAULT_JSON, help=f"Input JSON path. Defaults to {DEFAULT_JSON.name}.")
    parser.add_argument("--out", default=DEFAULT_OUT, help=f"Output CSV path. Defaults to {DEFAULT_OUT.name}.")
    return parser.parse_args()


def main():
    args = parse_args()
    rows, missing = build_rows(args.csv, args.json)
    write_output(rows, args.out)

    print(f"Wrote {len(rows)} rows to {args.out}")
    if missing:
        print(f"Skipped {len(missing)} JSON entries with no matching CSV arxiv_id:")
        for participant_code, paper_id in missing:
            print(f"  {participant_code}: {paper_id or '(missing paperId)'}")


if __name__ == "__main__":
    main()
