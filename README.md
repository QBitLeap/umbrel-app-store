# QBitLeap community app store

Community distribution for the independent Qbit Core, LEAP, PINS and qord
Umbrel apps. Each app keeps its source and image release workflow in its own
QBitLeap repository. Initial packages target Linux amd64 and umbrelOS 2.0+.
The initial `0.1.0-alpha.1` catalog is published. Its pinned images passed
isolated Mainnet/Testnet4 integration; managed installation and real-chain
operation acceptance remain pending.

App sources: [Qbit Core](https://github.com/QBitLeap/qbit-core-umbrel),
[LEAP](https://github.com/QBitLeap/leap-umbrel),
[PINS](https://github.com/QBitLeap/pins-umbrel) and
[qord](https://github.com/QBitLeap/qord-umbrel).

## Release flow

1. Review and publish the pinned app/protocol source repositories.
2. Run each app's manual Image release workflow with an explicit version.
   Publication defaults off. Retain its published-images.json artifact.
3. Make all five GHCR packages public. GitHub package visibility is separate
   from source repository visibility. Community users must be able to pull
   images without a GitHub account or registry login.
4. Combine the four image receipts with scripts/merge_image_receipts.py.
5. Run Validate and publish catalog with that five-component image JSON and
   a new package version. The workflow verifies anonymous manifest access,
   source labels, both networks, auth/isolation, tip behavior, restart and
   single-writer protection before generating a catalog.
6. Set publish_catalog only when ready to commit the accepted catalog. The
   generated apps use immutable registry digests and source-pinned icons.

The store intentionally has no placeholder app directories. Adding a source
repository or a locally built image ID is not a completed app release.
Catalog changes are scoped to generated files and refuse unexpected edits.
Upstream app locks are reviewed separately; running apps never auto-adopt
upstream source changes.

## Install a published catalog

After the first accepted catalog is on main, add this community-store URL in
Umbrel's App Store:

https://github.com/QBitLeap/umbrel-app-store

Install a Core instance before its dependent indexers. Peer networking and
indexing start off/paused; enable them in app settings after selecting the
intended network and checking storage and power readiness. Each instance owns
separate data. Never share a writable chain or index folder.

The status UI and authenticated read APIs are independent services. They do
not contain wallets, signing, transaction submission or private deployment
configuration. The LEAP protocol's native macOS/Windows/Linux releases remain
separate from these Umbrel packages.

## Checks

python3 -m unittest discover -s tests -v

The full integration runner needs a Linux amd64 Docker host and five published,
digest-pinned images. It creates labelled empty-chain resources, keeps peers
off, and cleans up only its own containers, volumes and private network.
Managed dashboard installation and real-chain operation require their own
acceptance after catalog publication.
