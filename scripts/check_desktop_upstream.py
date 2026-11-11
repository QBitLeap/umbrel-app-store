"""Smoke-test official Qbit Core and qord release archives on each target OS."""

import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile

CORE = {
    "macos-arm64": ("arm64-apple-darwin-unsigned.tar.gz", "a98310136b57f49471bb19b7bbba1ccf3801da9a1d64202cf7dcf6756db0b3a1"),
    "macos-x64": ("x86_64-apple-darwin-unsigned.tar.gz", "e49b48469432e6f8bef26416b1660fc2a64809e0415f3b80cd6cb7b3f2109a2a"),
    "windows-x64": ("win64-unsigned.zip", "93ca27facf73f736c1e1b152ad19f11eba0f075b800053bd07de9068fbe885b4"),
    "linux-x64": ("x86_64-linux-gnu.tar.gz", "ae121af03263b55d530e3f3e8719a71362d0950cba82f54a2bc2d6c437a029b5"),
    "linux-arm64": ("aarch64-linux-gnu.tar.gz", "a0242e5941eec64070f386e80c848220e2ec2292984a9b2ab1fd93f57436b31d"),
}
QORD = {
    "macos-arm64": ("aarch64-apple-darwin.tar.gz", "9f415a414ccf9c660ad5471b77815a986fa0f0fb2a100562ab60dbb36494e57f"),
    "macos-x64": ("x86_64-apple-darwin.tar.gz", "625dc1b96dcf12f20f2107f82c3b223f842d7cb70fb90f5026a70f040d36109f"),
    "windows-x64": ("x86_64-pc-windows-msvc.zip", "3f3f553ca32e7a404d1f89e0ed06d74f245d09fd5439db14e9838c53d6ac4d4c"),
    "linux-x64": ("x86_64-unknown-linux-gnu.tar.gz", "0916fe6e535e1f972ce8a1e729e280efd3de9e6a8db22f834bbd20f679f5e8f8"),
}


def check(repository, tag, filename, expected, commands, executable_suffix):
    with tempfile.TemporaryDirectory(prefix="desktop-upstream-") as temporary:
        root = Path(temporary)
        subprocess.run(["gh", "release", "download", tag, "--repo", repository,
                        "--pattern", filename, "--dir", root], check=True)
        archive = root / filename
        with archive.open("rb") as stream:
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        if checksum != expected:
            raise ValueError(f"Digest differs for {filename}")
        extracted = root / "extracted"
        if filename.endswith(".tar.gz"):
            shutil.unpack_archive(archive, extracted, filter="data")
        else:
            shutil.unpack_archive(archive, extracted)
        for name, *arguments in commands:
            candidates = [p for p in extracted.rglob(name + executable_suffix) if p.is_file()]
            if len(candidates) != 1:
                raise ValueError(f"Expected one executable {name} in {filename}")
            subprocess.run([candidates[0], *arguments], cwd=root, check=True, timeout=30)
        print(f"Verified {filename}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=CORE)
    args = parser.parse_args()
    suffix = ".exe" if args.target.startswith("windows") else ""
    artifact, digest = CORE[args.target]
    check("Qbit-Org/qbit", "v1.0.0", "qbit-1.0.0-" + artifact, digest,
          [("qbitd", "--version"), ("qbit-cli", "--version")], suffix)
    if args.target in QORD:
        artifact, digest = QORD[args.target]
        check("djh58/qord", "qord/v0.1.0", "qord-0.1.0-" + artifact, digest,
              [("qord", "--version"), ("qord", "wallet", "inscribe", "--help")], suffix)
