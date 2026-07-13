#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from portable_baseline_fixtures import COMMITTED_PACK, build

parser = argparse.ArgumentParser()
parser.add_argument("--authoritative-root", required=True)
parser.add_argument("--output", default=str(COMMITTED_PACK))
args = parser.parse_args()
print(json.dumps(build(Path.cwd(), Path(args.authoritative_root).resolve(), Path(args.output)), indent=2))
