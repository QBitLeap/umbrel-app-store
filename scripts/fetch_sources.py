"""Check out the four exact public app sources named by the catalog source lock."""

import argparse
import json
from pathlib import Path

from source_fetch import fetch
from catalog import APPS


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--lock", type=Path, default=Path("sources.lock.json"))
    args = parser.parse_args()
    lock = json.loads(args.lock.read_text())
    if set(lock["apps"]) != set(APPS):
        raise ValueError("Exactly the four app sources are required")
    for role, item in lock["apps"].items():
        if item["repository"] != "https://github.com/QBitLeap/" + role + "-umbrel.git":
            raise ValueError("Unexpected app source repository")
        fetch(args.output / (role + "-umbrel"), item)
