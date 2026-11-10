"""Verify every pinned manifest is anonymously readable from GHCR."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, ProxyHandler, HTTPRedirectHandler, build_opener

from catalog import validate_images


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("Unexpected registry redirect")


def verify(images):
    validate_images(images)
    opener = build_opener(ProxyHandler({}), NoRedirect())
    for role, image in images.items():
        repository, digest = image.removeprefix("ghcr.io/").split("@", 1)
        query = urlencode({"service": "ghcr.io", "scope": "repository:" + repository + ":pull"})
        # Deliberately no GitHub credentials: community installs must work anonymously.
        with opener.open("https://ghcr.io/token?" + query, timeout=20) as response:
            token = json.loads(response.read(64 * 1024))["token"]
        request = Request("https://ghcr.io/v2/" + repository + "/manifests/" + digest,
            headers={"Authorization": "Bearer " + token, "Accept":
                     "application/vnd.oci.image.index.v1+json, application/vnd.oci.image.manifest.v1+json, "
                     "application/vnd.docker.distribution.manifest.v2+json"})
        with opener.open(request, timeout=20) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024 or "sha256:" + hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("Public image manifest digest differs")
        json.loads(raw)
        print(role + " manifest is anonymously readable and matches its digest")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", type=Path)
    args = parser.parse_args()
    verify(json.loads(args.images.read_text()))
