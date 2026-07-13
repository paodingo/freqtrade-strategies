#!/usr/bin/env python3
"""Build the immutable portable Runtime Asset Manifest from the approved Runtime."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from portable_runtime_assets import APPROVED_SOURCE_ROOT, MANIFEST_PATH, build_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=APPROVED_SOURCE_ROOT)
    parser.add_argument("--output", type=Path, default=MANIFEST_PATH)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    manifest = build_manifest(args.source)
    output = args.output if args.output.is_absolute() else repo / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({"output": output.as_posix(), "manifest_fingerprint": manifest["manifest_fingerprint"], "file_count": manifest["file_count"], "total_bytes": manifest["total_bytes"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
