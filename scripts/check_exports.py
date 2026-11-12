"""Check dependency credentials under Umbrel's caller-scoped app context."""

import argparse
import json
from pathlib import Path
import subprocess

SHELL = """
set -eu
derive_entropy() { printf '%s' "$1"; }
app_entropy_identifier="app-$2-seed"
. "$1"
shift 2
for variable do printenv "$variable"; done
"""


def check(catalog):
    manifests = [json.loads(path.read_text()) for path in catalog.glob("qbitleap-*/umbrel-app.yml")]
    if len(manifests) not in (8,9) or (len(manifests)==9 and not any(app["id"]=="qbitleap-q20-main" for app in manifests)):
        raise ValueError("Expected the eight existing app variants and optional Mainnet q20")
    app_ids = [app["id"] for app in manifests]
    for app_id in app_ids:
        prefix = "APP_" + app_id.upper().replace("-", "_")
        if app_id.startswith("qbitleap-core-"):
            purposes = {"READ_TOKEN": "read-rpc", "UI_TOKEN": "status-ui", "CONTROL_TOKEN": "network-control"}
        elif app_id=="qbitleap-q20-main":
            purposes = {"API_TOKEN": "read-api"}
        else:
            purposes = {"API_TOKEN": "read-api", "LOCAL_TOKEN": "local-rpc"}
        variables = [f"{prefix}_{purpose}" for purpose in purposes]
        expected = [f"app-{app_id}-seed-{purpose}" for purpose in purposes.values()]
        exports = catalog / app_id / "exports.sh"
        for caller in app_ids:
            actual = subprocess.check_output(
                ["sh", "-c", SHELL, "check-exports", exports, caller, *variables], text=True
            ).splitlines()
            if actual != expected:
                raise ValueError(f"{app_id} exports vary when sourced by {caller}")
    print(f"All {len(manifests)} app exports retain their own credential context under every caller")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    args = parser.parse_args()
    check(args.catalog)
