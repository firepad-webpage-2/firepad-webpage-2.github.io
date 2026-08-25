#!/usr/bin/env python3

import argparse
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_MARKDOWN_DIR = ROOT / "markdown_norm"
DEFAULT_BUILDER = ROOT / "build_r2_figure_manifest.py"
PUBLIC_FIGURE_URL_RE = re.compile(
    r"https://paper-assets\.alphaxiv\.org/((?:figures-normalized/)?figures/[^)\s]+/)[^)\s]+"
)


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

    if not builder.exists():
        raise SystemExit(f"Manifest builder not found: {builder}")

    paper_ids = get_paper_ids(markdown_dir)
    prefixes = get_existing_figure_prefixes(markdown_dir)
    cmd = [
        sys.executable,
        str(builder),
        "--out",
        args.out,
        "--public-base-url",
        args.public_base_url,
    ]

    for paper_id in paper_ids:
        cmd.extend(["--paper-id", paper_id])

    for prefix in prefixes:
        cmd.extend(["--prefix", prefix])

    print(f"Building figure manifest for {len(paper_ids)} papers:")
    # for paper_id in paper_ids:
        # print(f"  {paper_id}")
    # if prefixes:
    #     print(f"Using {len(prefixes)} existing figure prefixes from markdown:")
    #     for prefix in prefixes:
    #         print(f"  {prefix}")

    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
