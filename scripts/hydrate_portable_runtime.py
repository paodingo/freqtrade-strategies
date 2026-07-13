#!/usr/bin/env python3
"""Hydrate only files declared by the approved portable Runtime Asset Manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from portable_runtime_assets import APPROVED_SOURCE_ROOT, PortableRuntimeError, hydrate_runtime


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=APPROVED_SOURCE_ROOT)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    try:
        result = hydrate_runtime(repo, args.source)
    except PortableRuntimeError as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}, indent=2))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
