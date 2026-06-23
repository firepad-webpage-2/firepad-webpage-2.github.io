#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path

from figure_markdown_normalizer import normalize_initial_markdown


ROOT = Path(__file__).resolve().parent
SKIPPED_DIRS = {".git", "node_modules", "dist", "build"}


def collect_files(input_path, suffix):
    input_path = Path(input_path)
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() == suffix else []

    if not input_path.is_dir():
        return []

    files = []
    for child in input_path.iterdir():
        if child.is_dir() and child.name in SKIPPED_DIRS:
            continue
        if child.is_dir():
            files.extend(collect_files(child, suffix))
        elif child.is_file() and child.suffix.lower() == suffix:
            files.append(child)

    return files


def get_relative_output_path(file_path, input_roots, out_dir, suffix=None):
    file_path = Path(file_path).resolve()
    out_dir = Path(out_dir).resolve()

    relative_path = None
    for root in input_roots:
        root = Path(root).resolve()
        if root.is_dir():
            try:
                relative_path = file_path.relative_to(root)
                break
            except ValueError:
                pass

    if relative_path is None:
        relative_path = Path(file_path.name)

    if suffix:
        relative_path = relative_path.with_suffix(suffix)

    return out_dir / relative_path


def extract_overview(inputs, out_dir):
    input_roots = [Path(input_path).resolve() for input_path in inputs]
    files = sorted({file.resolve() for input_path in inputs for file in collect_files(input_path, ".json")})

    if not files:
        raise SystemExit("No JSON files found.")

    for file_path in files:
        output_path = get_relative_output_path(file_path, input_roots, out_dir, ".md")
        with file_path.open("r", encoding="utf-8") as input_file:
            data = json.load(input_file)

        overview = data.get("overview")
        if not isinstance(overview, str):
            raise SystemExit(f"Missing string overview value in {file_path}")

        markdown = overview if overview.endswith("\n") else f"{overview}\n"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        print(f"{file_path} -> {output_path}")


def normalize_markdown(inputs, out_dir):
    input_roots = [Path(input_path).resolve() for input_path in inputs]
    files = sorted({file.resolve() for input_path in inputs for file in collect_files(input_path, ".md")})

    if not files:
        raise SystemExit("No markdown files found.")

    for file_path in files:
        output_path = get_relative_output_path(file_path, input_roots, out_dir)
        markdown = file_path.read_text(encoding="utf-8")
        normalized = normalize_initial_markdown(markdown)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(normalized, encoding="utf-8")
        print(f"{file_path} -> {output_path}")


def build_markdown(args):
    extract_overview(args.json_inputs, args.raw_out)
    normalize_markdown([args.raw_out], args.norm_out)


def add_io_args(parser, default_input, default_out, input_help):
    parser.add_argument("inputs", nargs="*", default=[default_input], help=input_help)
    parser.add_argument("--out", default=default_out, help="Output directory")


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Build markdown_raw and markdown_norm from AlphaXiv overview JSON."
    )
    subparsers = parser.add_subparsers(dest="command")

    extract_parser = subparsers.add_parser("extract", help="Extract JSON overview fields to markdown_raw")
    add_io_args(
        extract_parser,
        str(ROOT / "json_raw"),
        str(ROOT / "markdown_raw"),
        "JSON file or directory. Defaults to json_raw.",
    )

    normalize_parser = subparsers.add_parser("normalize", help="Normalize markdown_raw into markdown_norm")
    add_io_args(
        normalize_parser,
        str(ROOT / "markdown_raw"),
        str(ROOT / "markdown_norm"),
        "Markdown file or directory. Defaults to markdown_raw.",
    )

    build_parser = subparsers.add_parser("build", help="Extract overview JSON, then normalize markdown")
    build_parser.add_argument("--json-in", dest="json_inputs", action="append", default=None)
    build_parser.add_argument("--raw-out", default=str(ROOT / "markdown_raw"))
    build_parser.add_argument("--norm-out", default=str(ROOT / "markdown_norm"))

    args = parser.parse_args(argv)
    if args.command is None:
        args.command = "build"

    if args.command == "build" and args.json_inputs is None:
        args.json_inputs = [str(ROOT / "json_raw")]

    return args


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])

    if args.command == "extract":
        extract_overview(args.inputs, args.out)
    elif args.command == "normalize":
        normalize_markdown(args.inputs, args.out)
    elif args.command == "build":
        build_markdown(args)
    else:
        raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
