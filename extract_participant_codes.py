#!/usr/bin/env python3

import argparse
import json
import random
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SKIPPED_DIRS = {".git", "node_modules", "dist", "build"}


def collect_json_files(input_path):
    input_path = Path(input_path)
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() == ".json" else []

    if not input_path.is_dir():
        return []

    files = []
    for child in input_path.iterdir():
        if child.is_dir() and child.name in SKIPPED_DIRS:
            continue
        if child.is_dir():
            files.extend(collect_json_files(child))
        elif child.is_file() and child.suffix.lower() == ".json":
            files.append(child)

    return files


def make_code_base(primary_author):
    return re.sub(r"\s+", "", primary_author)


def make_participant_code(primary_author, used_codes, digits):
    base = make_code_base(primary_author)
    if not base:
        raise ValueError("primary_author becomes empty after removing whitespace")

    lower = 10 ** (digits - 1)
    upper = (10 ** digits) - 1

    for _ in range(10000):
        code = f"{base}{random.SystemRandom().randint(lower, upper)}"
        if code not in used_codes:
            used_codes.add(code)
            return code

    raise RuntimeError(f"Could not create a unique participant code for {primary_author}")


def load_existing_participant_codes(out_path):
    out_path = Path(out_path)
    if not out_path.exists():
        return {}

    with out_path.open("r", encoding="utf-8") as input_file:
        data = json.load(input_file)

    if not isinstance(data, dict):
        raise SystemExit(f"Expected {out_path} to contain a JSON object.")
    return data


def extract_participant_codes(inputs, out_path, digits):
    files = sorted({file.resolve() for input_path in inputs for file in collect_json_files(input_path)})
    if not files:
        raise SystemExit("No JSON files found.")

    out_path = Path(out_path)
    participant_codes = load_existing_participant_codes(out_path)
    used_codes = set(participant_codes)
    existing_paper_ids = {
        entry.get("paperId")
        for entry in participant_codes.values()
        if isinstance(entry, dict) and entry.get("paperId")
    }
    added_count = 0

    for file_path in files:
        with file_path.open("r", encoding="utf-8") as input_file:
            data = json.load(input_file)

        primary_author = data.get("primary_author")
        title = data.get("title")
        if not isinstance(primary_author, str) or not primary_author.strip():
            raise SystemExit(f"Missing string primary_author value in {file_path}")
        if not isinstance(title, str) or not title.strip():
            raise SystemExit(f"Missing string title value in {file_path}")

        if file_path.stem in existing_paper_ids:
            continue

        participant_code = make_participant_code(primary_author, used_codes, digits)
        participant_codes[participant_code] = {
            "paperId": file_path.stem,
            "paperTitle": title,
        }
        existing_paper_ids.add(file_path.stem)
        added_count += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(participant_codes, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Added {added_count} participant codes; wrote {len(participant_codes)} total to {out_path}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract participant-code mappings from json_raw paper metadata."
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        default=[str(ROOT / "json_raw")],
        help="JSON file or directory. Defaults to json_raw.",
    )
    parser.add_argument(
        "--out",
        default=str(ROOT / "participantCodes.json"),
        help="Output JSON path. Defaults to participantCodes.json.",
    )
    parser.add_argument(
        "--digits",
        type=int,
        default=4,
        help="Number of random digits appended to primary_author. Defaults to 4.",
    )

    args = parser.parse_args()
    if args.digits < 1:
        parser.error("--digits must be at least 1")
    return args


def main():
    args = parse_args()
    extract_participant_codes(args.inputs, args.out, args.digits)


if __name__ == "__main__":
    main()
