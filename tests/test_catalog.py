import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from catalog import ROLES, accepted, promote, validate_images

spec = importlib.util.spec_from_file_location("app_integration", ROOT / "checks/integration.py")
integration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(integration)


def images():
    return {role: "ghcr.io/qbitleap/" + name + "@sha256:" + hashlib.sha256(role.encode()).hexdigest()
            for role, name in ROLES.items()}


def receipt():
    value = {"passed": True, "images": images(), "networks": {}}
    for chain in ("main", "testnet4"):
        value["networks"][chain] = {"passed": True, "fixtureCleanupComplete": True,
            "core": {k: True for k in ("restartAccepted", "unauthenticatedReadRejected", "publicationRpcRejected",
                                       "uiHasNoCoreCookie", "rawRpcNotReachableFromNeighbor", "tipErrorCodePreserved",
                                       "networkingControlAccepted", "networkingChoiceSurvivedRestart", "finalFixtureNetworkingDisabled")},
            "protocols": {role: {k: True for k in ("apiAuthenticationAccepted", "restartAccepted",
                                                  "duplicateWriterRefused", "tipErrorCodePreserved")}
                          for role in ("leap", "pins", "qord")}}
    return value


class CatalogTests(unittest.TestCase):
    def test_catalog_refuses_tags_config_ids_wrong_components_and_incomplete_sets(self):
        validate_images(images())
        for invalid in ("sha256:" + "a" * 64, "ghcr.io/qbitleap/qbit-core:latest",
                        "ghcr.io/unrelated/qbit-core@sha256:" + "a" * 64,
                        "ghcr.io/qbitleap/qord-indexer@sha256:" + "a" * 64):
            with self.subTest(reference=invalid), self.assertRaises(ValueError):
                validate_images({**images(), "core": invalid})
        with self.assertRaises(ValueError):
            validate_images({"core": images()["core"]})

    def test_acceptance_cannot_be_reused_for_different_images_or_partial_checks(self):
        accepted(receipt(), images())
        changed = images()
        changed["core"] = "ghcr.io/qbitleap/qbit-core@sha256:" + "a" * 64
        with self.assertRaises(ValueError):
            accepted(receipt(), changed)
        for key in ("fixtureCleanupComplete", "passed"):
            value = receipt()
            value["networks"]["testnet4"][key] = False
            with self.assertRaises(ValueError):
                accepted(value, images())
        value = receipt()
        value["networks"]["main"]["core"]["networkingChoiceSurvivedRestart"] = False
        with self.assertRaises(ValueError):
            accepted(value, images())
        value = receipt()
        value["networks"]["main"]["protocols"]["qord"]["tipErrorCodePreserved"] = False
        with self.assertRaises(ValueError):
            accepted(value, images())

    def test_catalog_promotion_refuses_existing_changes_and_linked_targets(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            catalog, repo = root / "catalog", root / "repository"
            catalog.mkdir()
            repo.mkdir()
            file = "qbitleap-core-main/umbrel-app.yml"
            (catalog / file).parent.mkdir()
            (catalog / file).write_text("new")
            digest = hashlib.sha256(b"new").hexdigest()
            (catalog / "catalog-manifest.json").write_text(json.dumps({"files": {file: digest}}))
            promote(catalog, repo)
            (repo / file).write_text("owner change")
            with self.assertRaises(ValueError):
                promote(catalog, repo)
            self.assertEqual((repo / file).read_text(), "owner change")
            (repo / file).unlink()
            (repo / file).parent.rmdir()
            outside = root / "outside"
            outside.mkdir()
            (outside / "umbrel-app.yml").write_text("new")
            (repo / "qbitleap-core-main").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                promote(catalog, repo)

    def test_fixture_cleanup_never_removes_foreign_resources(self):
        class Docker:
            def __init__(self):
                self.commands = []
            def inspect(self, kind, name):
                return {"Config": {"Labels": {"qbitleap.run": "someone-else"}}}
            def call(self, args, **kwargs):
                self.commands.append(args)
        docker = Docker()
        fixture = integration.Fixture(docker, {}, "main")
        fixture.containers = ["foreign"]
        self.assertTrue(fixture.cleanup())
        self.assertEqual(docker.commands, [])


if __name__ == "__main__":
    unittest.main()
