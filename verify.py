#!/usr/bin/env python3
"""
Verify pipeline data completeness.

Counts input JSON files vs output files and reports per-source match status.

Usage:
    python verify.py --input-dir ./input --output-dir ./output
"""
import argparse
import sys
from collections import defaultdict
from pathlib import Path


def count_files(directory: Path, extension: str) -> dict[str, int]:
    """Return per-source_id file counts from a flat directory.

    Skips hidden files and subdirectories.
    Source ID is the first underscore-delimited token in the filename stem.
    Files whose stems contain no underscore are skipped with a warning.
    """
    counts: dict[str, int] = defaultdict(int)
    for f in directory.glob(f"*{extension}"):
        if not f.is_file() or f.name.startswith("."):
            continue
        parts = f.stem.split("_")
        if len(parts) < 2:
            print(f"WARN: skipping unrecognised filename: {f.name}", file=sys.stderr)
            continue
        counts[parts[0]] += 1
    return dict(counts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify pipeline data completeness")
    parser.add_argument("--input-dir", required=True, type=Path, metavar="PATH")
    parser.add_argument("--output-dir", required=True, type=Path, metavar="PATH")
    args = parser.parse_args()

    if not args.input_dir.is_dir():
        print(f"ERROR: input-dir is not a directory: {args.input_dir}", file=sys.stderr)
        sys.exit(1)
    if not args.output_dir.is_dir():
        print(f"ERROR: output-dir is not a directory: {args.output_dir}", file=sys.stderr)
        sys.exit(1)

    input_counts = count_files(args.input_dir, ".json")
    output_counts = count_files(args.output_dir, "")  # any extension

    all_sources = sorted(set(input_counts) | set(output_counts))
    total_input = sum(input_counts.values())
    total_output = sum(output_counts.values())

    print(f"{'Source':<15} {'Input':>8} {'Output':>8} {'Status':>8}")
    print("-" * 45)
    for source in all_sources:
        inp = input_counts.get(source, 0)
        out = output_counts.get(source, 0)
        status = "OK" if inp == out else "MISMATCH"
        print(f"{source:<15} {inp:>8} {out:>8} {status:>8}")

    print("-" * 45)
    print(f"{'TOTAL':<15} {total_input:>8} {total_output:>8}")
    print()

    failed_sources = [s for s in all_sources if input_counts.get(s, 0) != output_counts.get(s, 0)]
    if not failed_sources:
        print("Status: PASS")
        sys.exit(0)
    else:
        print(f"Status: FAIL — {len(failed_sources)} source(s) have mismatched file counts")
        sys.exit(1)


if __name__ == "__main__":
    main()
