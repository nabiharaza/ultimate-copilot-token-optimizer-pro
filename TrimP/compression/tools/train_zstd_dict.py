#!/usr/bin/env python3
"""
Train a Zstandard dictionary from a directory of sample text files.

Usage:
  python -m TrimP.compression.tools.train_zstd_dict --input-dir samples/ --out ~/.trimp/trimp.zstd.dict

This script is intentionally simple: it reads up to --max-samples files from
--input-dir, trains a dictionary (size --dict-size), and writes the dict file.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

try:
    import zstandard as zstd
except Exception as e:
    print("zstandard is required to train dictionary: pip install zstandard", file=sys.stderr)
    raise


def gather_samples(input_dir: Path, max_samples: int = 1000):
    samples = []
    for p in input_dir.rglob("*"):
        if p.is_file():
            try:
                data = p.read_bytes()
                if data:
                    samples.append(data)
                if len(samples) >= max_samples:
                    break
            except Exception:
                continue
    return samples


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input-dir", type=Path, required=True, help="Directory with sample text files")
    p.add_argument("--out", type=Path, default=Path.home() / ".trimp" / "trimp.zstd.dict", help="Output dictionary file")
    p.add_argument("--dict-size", type=int, default=112640, help="Dictionary size in bytes (recommended ~100KB)")
    p.add_argument("--max-samples", type=int, default=2000, help="Max number of sample files to read")
    args = p.parse_args()

    if not args.input_dir.exists():
        print(f"Input directory {args.input_dir} doesn't exist", file=sys.stderr)
        sys.exit(2)

    samples = gather_samples(args.input_dir, args.max_samples)
    if not samples:
        print("No samples found to train dictionary", file=sys.stderr)
        sys.exit(2)

    print(f"Training dictionary from {len(samples)} samples (dict_size={args.dict_size})...")
    dict_buf = zstd.train_dictionary(args.dict_size, samples)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "wb") as fh:
        fh.write(dict_buf.as_bytes())
    print(f"Wrote dictionary to {args.out}")


if __name__ == "__main__":
    main()
