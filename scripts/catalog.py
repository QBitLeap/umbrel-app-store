"""Assemble a community catalog only from pinned, accepted image references."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess

ROLES = {"core": "qbit-core", "services": "qbit-core-services", "leap": "leap-indexer",
         "pins": "pins-indexer", "qord": "qord-indexer"}
APPS = ("qbit-core", "leap", "pins", "qord")


def validate_images(images):
    if not isinstance(images, dict) or set(images) != set(ROLES):
        raise ValueError("Exactly five published component images are required")
    for role, repository in ROLES.items():
        value = images[role]
        if (not isinstance(value, str) or re.fullmatch(
                "ghcr.io/qbitleap/" + repository + r"@sha256:[0-9a-f]{64}", value) is None
                or value.endswith("0" * 64)):
            raise ValueError("Published GHCR manifest digest required for " + role)
    return images


def accepted(receipt, images):
    if receipt.get("passed") is not True or receipt.get("images") != images:
        raise ValueError("Passing acceptance for these exact image references required")
    networks = receipt.get("networks", {})
    if set(networks) != {"main", "testnet4"}:
        raise ValueError("Both supported networks must pass")
    for value in networks.values():
        if value.get("passed") is not True or value.get("fixtureCleanupComplete") is not True:
            raise ValueError("Fixture checks and owned cleanup must pass")
        if any(value.get("core", {}).get(k) is not True for k in
               ("restartAccepted", "unauthenticatedReadRejected", "publicationRpcRejected",
                "uiHasNoCoreCookie", "rawRpcNotReachableFromNeighbor", "tipErrorCodePreserved",
                "networkingControlAccepted", "networkingChoiceSurvivedRestart", "finalFixtureNetworkingDisabled")):
            raise ValueError("Core isolation and lifecycle acceptance missing")
        protocols = value.get("protocols", {})
        if set(protocols) != {"leap", "pins", "qord"}:
            raise ValueError("All three indexers must pass")
        for protocol in protocols.values():
            if any(protocol.get(k) is not True for k in ("apiAuthenticationAccepted", "restartAccepted",
                                                        "duplicateWriterRefused", "tipErrorCodePreserved")):
                raise ValueError("Indexer isolation and lifecycle acceptance missing")


def assemble(output, apps_root, sources, images, receipt, version="0.1.0-alpha.1"):
    validate_images(images)
    accepted(receipt, images)
    if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-.][a-z0-9][a-z0-9.-]*)?", version) is None:
        raise ValueError("Explicit catalog app version required")
    if output.exists() or output.is_symlink():
        raise ValueError("New catalog output required")
    if set(sources["apps"]) != set(APPS):
        raise ValueError("Four pinned app source repositories required")
    for role, item in sources["apps"].items():
        if (item["repository"] != "https://github.com/QBitLeap/" + role + "-umbrel.git"
                or re.fullmatch(r"[0-9a-f]{40}", item["commit"]) is None):
            raise ValueError("Unexpected app source identity")
        repo = apps_root / (role + "-umbrel")
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
        untracked = set(subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=repo).decode().rstrip("\0").split("\0")) - {""}
        if (head != item["commit"] or subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=repo).returncode
                or untracked - {".source-receipt.json"}):
            raise ValueError("App source differs from its pinned commit")
    output.mkdir(parents=True)
    for ordinal, chain in enumerate(("main", "testnet4")):
        core_id = "qbitleap-core-" + chain
        for offset, role in enumerate(APPS):
            repo = apps_root / (role + "-umbrel")
            spec = importlib.util.spec_from_file_location("package_" + role.replace("-", "_"), repo / "scripts/prepare_app_package.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            app_id = core_id if role == "qbit-core" else "qbitleap-" + role + "-" + chain
            icon = "https://raw.githubusercontent.com/QBitLeap/" + role + "-umbrel/" + sources["apps"][role]["commit"] + "/icon.svg"
            args = [output / app_id, app_id, chain, 5100 + ordinal * 10 + offset]
            if role == "qbit-core":
                module.prepare(*args, images["core"], images["services"], icon_url=icon, package_version=version)
            else:
                module.prepare(*args, images[role], core_id, icon_url=icon, package_version=version)
    (output / "images.lock.json").write_text(json.dumps(images, sort_keys=True, indent=2) + "\n")
    (output / "acceptance.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    manifest = {"format": "qbitleap-community-catalog-v1", "images": images, "sources": sources,
                "files": {p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(output.rglob("*")) if p.is_file()}}
    (output / "catalog-manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    return manifest


def promote(catalog, repository):
    manifest = json.loads((catalog / "catalog-manifest.json").read_text())
    previous = repository / "catalog-manifest.json"
    if previous.is_symlink():
        raise ValueError("Linked catalog ownership manifest refused")
    old = json.loads(previous.read_text())["files"] if previous.exists() else {}
    owned = set(manifest["files"]) | set(old)
    for rel in owned:
        path = Path(rel)
        if path.is_absolute() or ".." in path.parts or not (
                path.parts[0].startswith("qbitleap-") or rel in {"images.lock.json", "acceptance.json"}):
            raise ValueError("Unexpected managed catalog path")
        target = repository / rel
        if any(p.is_symlink() for p in [target, *list(target.parents)[:len(path.parts) - 1]]):
            raise ValueError("Linked catalog target refused")
        if target.is_symlink() or (target.exists() and (rel not in old or
                hashlib.sha256(target.read_bytes()).hexdigest() != old[rel])):
            raise ValueError("Existing catalog content differs; preserve it")
        if rel in manifest["files"]:
            source = catalog / rel
            if (source.is_symlink() or not source.resolve().is_relative_to(catalog.resolve())
                    or hashlib.sha256(source.read_bytes()).hexdigest() != manifest["files"][rel]):
                raise ValueError("Generated catalog changed")
    for rel in old.keys() - manifest["files"].keys():
        (repository / rel).unlink()
    for rel in manifest["files"]:
        target = repository / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(catalog / rel, target)
    shutil.copyfile(catalog / "catalog-manifest.json", previous)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--apps-root", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--promote-to", type=Path)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    report = assemble(args.output, args.apps_root, json.loads(args.sources.read_text()),
                      json.loads(args.images.read_text()), json.loads(args.acceptance.read_text()), args.version)
    if args.promote_to:
        promote(args.output, args.promote_to)
    print(json.dumps({"catalogFiles": len(report["files"]), "published": False}))
