#!/usr/bin/env python3

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_MARKDOWN_DIR = ROOT / "markdown_norm"
DEFAULT_BUILDER = ROOT / "build_r2_figure_manifest.py"
PUBLIC_FIGURE_URL_RE = re.compile(
    r"https://paper-assets\.alphaxiv\.org/((?:figures-normalized/)?figures/[^)\s]+/)[^)\s]+"
)
PAPER_ID_RE = re.compile(r"(\d{4}\.\d{4,5})(?:v\d+)?")


def get_paper_ids(markdown_dir):
    if not markdown_dir.exists():
        raise SystemExit(f"Markdown directory not found: {markdown_dir}")

    paper_ids = []
    for path in sorted(markdown_dir.glob("*.md")):
        paper_id = path.stem.strip()
        if paper_id:
            paper_ids.append(paper_id)

    if not paper_ids:
        raise SystemExit(f"No markdown files found in: {markdown_dir}")

    return paper_ids


def get_existing_figure_prefixes(markdown_dir):
    prefixes = []
    for path in sorted(markdown_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        prefixes.extend(match.group(1) for match in PUBLIC_FIGURE_URL_RE.finditer(text))

    return list(dict.fromkeys(prefixes))


def base_paper_id(paper_id):
    return re.sub(r"v\d+$", "", paper_id)


def get_prefix_paper_id(prefix):
    match = PAPER_ID_RE.search(prefix)
    return match.group(0) if match else ""


def load_existing_manifest(out_path):
    out_path = Path(out_path)
    if not out_path.exists():
        return {}

    with out_path.open("r", encoding="utf-8") as input_file:
        data = json.load(input_file)

    if not isinstance(data, dict):
        raise SystemExit(f"Expected {out_path} to contain a JSON object.")
    return data


def get_existing_paper_ids(manifest):
    ids = set()
    for paper_id, images in manifest.items():
        if images:
            ids.add(paper_id)
            ids.add(base_paper_id(paper_id))
    return ids


def merge_manifest(existing_manifest, new_manifest):
    merged = dict(existing_manifest)

    for paper_id, new_images in new_manifest.items():
        existing_images = merged.get(paper_id, [])
        seen = {
            image.get("key") or image.get("url")
            for image in existing_images
            if isinstance(image, dict)
        }
        combined = list(existing_images)

        for image in new_images:
            if not isinstance(image, dict):
                continue
            image_id = image.get("key") or image.get("url")
            if image_id in seen:
                continue
            seen.add(image_id)
            combined.append(image)

        merged[paper_id] = combined

    return merged


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build figure_manifest.json for every paper represented in markdown_norm/*.md."
    )
    parser.add_argument("--markdown-dir", default=str(DEFAULT_MARKDOWN_DIR))
    parser.add_argument("--builder", default=str(DEFAULT_BUILDER))
    parser.add_argument("--out", default=str(ROOT / "figure_manifest.json"))
    parser.add_argument("--public-base-url", default="https://paper-assets.alphaxiv.org")
    return parser.parse_args()


def main():
    args = parse_args()
    markdown_dir = Path(args.markdown_dir)
    builder = Path(args.builder)
    out_path = Path(args.out)

    if not builder.exists():
        raise SystemExit(f"Manifest builder not found: {builder}")

    existing_manifest = load_existing_manifest(out_path)
    existing_paper_ids = get_existing_paper_ids(existing_manifest)
    paper_ids = get_paper_ids(markdown_dir)
    prefixes = get_existing_figure_prefixes(markdown_dir)
    missing_paper_ids = [
        paper_id for paper_id in paper_ids
        if paper_id not in existing_paper_ids and base_paper_id(paper_id) not in existing_paper_ids
    ]
    missing_prefixes = []
    for prefix in prefixes:
        prefix_paper_id = get_prefix_paper_id(prefix)
        if (
            prefix_paper_id
            and (
                prefix_paper_id in existing_paper_ids
                or base_paper_id(prefix_paper_id) in existing_paper_ids
            )
        ):
            continue
        missing_prefixes.append(prefix)

    if not missing_paper_ids and not missing_prefixes:
        print(f"No new papers or figure prefixes to add; kept {len(existing_manifest)} existing manifest entries in {out_path}")
        return

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as output_file:
        temp_out_path = Path(output_file.name)

    cmd = [
        sys.executable,
        str(builder),
        "--out",
        str(temp_out_path),
        "--public-base-url",
        args.public_base_url,
    ]

    for paper_id in missing_paper_ids:
        cmd.extend(["--paper-id", paper_id])

    for prefix in missing_prefixes:
        cmd.extend(["--prefix", prefix])

    print(f"Building figure manifest for {len(missing_paper_ids)} new papers; skipping {len(paper_ids) - len(missing_paper_ids)} already present papers.")
    if missing_prefixes:
        print(f"Using {len(missing_prefixes)} new figure prefixes from markdown.")

    try:
        subprocess.run(cmd, check=True)
        new_manifest = load_existing_manifest(temp_out_path)
        merged_manifest = merge_manifest(existing_manifest, new_manifest)
        out_path.write_text(json.dumps(merged_manifest, indent=2) + "\n", encoding="utf-8")
        print(f"Merged {len(new_manifest)} new manifest entries into {out_path}")
    finally:
        temp_out_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
