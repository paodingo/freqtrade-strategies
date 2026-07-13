#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from portable_baseline_fixtures import HYDRATED_PACK, hydrate

parser = argparse.ArgumentParser()
parser.add_argument("--target", default=str(HYDRATED_PACK))
args = parser.parse_args()
print(json.dumps(hydrate(Path.cwd(), Path(args.target)), indent=2))
