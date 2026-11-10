"""Combine the four explicitly published app-image release receipts."""

import argparse
import json
from pathlib import Path

from catalog import ROLES, validate_images


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipts", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("New image-lock output required")
    roles = {component: role for role, component in ROLES.items()}
    images = {}
    for file in args.receipts:
        report = json.loads(file.read_text())
        if report.get("format") != "qbitleap-image-release-v1":
            raise ValueError("Unexpected image release receipt")
        for item in report["images"]:
            role = roles[item["component"]]
            if item.get("published") is not True or role in images:
                raise ValueError("Exactly one published release per component required")
            images[role] = item["image"]
    validate_images(images)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(images, indent=2) + "\n")
