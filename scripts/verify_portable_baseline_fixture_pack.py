#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from portable_baseline_fixtures import HYDRATED_PACK, verify

parser = argparse.ArgumentParser()
parser.add_argument("--pack", default=str(HYDRATED_PACK))
args = parser.parse_args()
print(json.dumps(verify(Path(args.pack)), indent=2))
