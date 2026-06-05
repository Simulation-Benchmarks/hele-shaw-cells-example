#!/usr/bin/env python3
"""upload_to_rohub.py — headless ROHub upload for the Hele-Shaw benchmark.

A non-notebook version of notebooks/RoCrate.ipynb's upload step, suitable
for CI / cron use. Discovers per-configuration ``solution_field_data.zip``
files, uploads each to the configured ROHub endpoint, and writes a
``{configuration: uuid}`` JSON mapping for downstream SPARQL extraction.

CLI:

  python openfoam/upload_to_rohub.py \\
      --results-dir results/ \\
      --endpoint dev|prod \\
      --output results/rohub_uuids.json \\
      [--configurations 1 2 3]

Behavior:

  * --endpoint selects between the dev and prod ROHub APIs. Endpoint
    URLs / Keycloak / SPARQL endpoint are set on ``rohub.settings`` before
    any login or upload, matching notebooks/RoCrate.ipynb Cell 2.
  * Credentials are read from ``ROHUB_USERNAME`` / ``ROHUB_PASSWORD`` env
    vars. If either is missing the script prints a notice to stderr and
    exits 0 (the "soft skip" for CI where uploads are opt-in).
  * Uploads that fail for a single configuration are logged and the
    batch continues; the exit code is 1 iff at least one upload failed.
  * Exit codes: 0 = all uploaded or soft-skipped, 1 = at least one
    upload failed, 2 = argument / results-dir error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results-dir", type=Path, required=True,
                    help="Directory containing <configuration>/solution_field_data.zip")
    ap.add_argument("--endpoint", choices=("dev", "prod"), default="dev",
                    help="ROHub endpoint: dev (default) or prod")
    ap.add_argument("--output", type=Path, required=True,
                    help="Path to write the {configuration: uuid} JSON mapping")
    ap.add_argument("--configurations", nargs="*", default=None,
                    help="Optional subset of configuration IDs to upload (default: all)")
    return ap.parse_args()


# Endpoint constants — mirrored from notebooks/RoCrate.ipynb Cell 2.
ENDPOINTS = {
    "dev": {
        "API_URL": "https://rohub2020-devel.apps.paas-dev.psnc.pl/api/",
        "KEYCLOAK_CLIENT_ID": "rohub2020-cli",
        "KEYCLOAK_CLIENT_SECRET": "714617a7-87bc-4a88-8682-5f9c2f60337d",
        "KEYCLOAK_URL": (
            "https://keycloak-dev.apps.paas-dev.psnc.pl/auth/realms/rohub/"
            "protocol/openid-connect/token"
        ),
        "SPARQL_ENDPOINT": "https://virtuoso-rohub2020-devel.apps.bst2.paas.psnc.pl/sparql",
    },
    "prod": {
        "API_URL": "https://api.rohub.org/api/",
        "KEYCLOAK_CLIENT_ID": "rohub2020-public-cli",
        "KEYCLOAK_URL": (
            "https://login.rohub.org/auth/realms/rohub/protocol/openid-connect/token"
        ),
        "SPARQL_ENDPOINT": "https://virtuoso-rohub2020-production.apps.bst2.paas.psnc.pl/sparql",
    },
}


def configure_endpoint(endpoint: str) -> dict:
    """Import rohub and set the endpoint URLs. Returns the chosen config."""
    if endpoint not in ENDPOINTS:
        raise SystemExit(f"ERROR: unknown endpoint {endpoint!r}; choose 'dev' or 'prod'")
    import rohub
    cfg = ENDPOINTS[endpoint]
    for key, value in cfg.items():
        setattr(rohub.settings, key, value)
    return cfg


def discover_zips(results_dir: Path, filter_ids: list[str] | None) -> dict[str, Path]:
    """Find <cfg>/solution_field_data.zip under results_dir."""
    if not results_dir.exists():
        print(f"ERROR: results-dir not found: {results_dir}", file=sys.stderr)
        raise SystemExit(2)
    zips: dict[str, Path] = {}
    for child in sorted(results_dir.iterdir()):
        if not child.is_dir():
            continue
        if not re.fullmatch(r"\d+", child.name):
            continue
        if filter_ids is not None and child.name not in filter_ids:
            continue
        candidate = child / "solution_field_data.zip"
        if not candidate.exists():
            print(f"WARNING: {candidate} not found; configuration "
                  f"{child.name} will be skipped", file=sys.stderr)
            continue
        zips[child.name] = candidate
    return zips


def upload_one(cfg: str, zip_path: Path, rohub) -> str | None:
    """Upload one zip; return the UUID, or None on failure."""
    import rohub as _rohub
    print(f"[upload_to_rohub] configuration {cfg}: uploading {zip_path.name}...")
    ro = _rohub.ros_upload(path_to_zip=str(zip_path))
    uuid = ro.identifier
    base = "ro-id-dev" if rohub.settings.API_URL.startswith("https://rohub2020") else "ro-id"
    print(f"[upload_to_rohub]   -> UUID {uuid}  (https://w3id.org/{base}/{uuid})")
    return uuid


def main() -> int:
    args = parse_args()

    username = os.environ.get("ROHUB_USERNAME")
    password = os.environ.get("ROHUB_PASSWORD")
    if not username or not password:
        print("ROHUB_USERNAME/ROHUB_PASSWORD not set; skipping upload",
              file=sys.stderr)
        return 0

    cfg = configure_endpoint(args.endpoint)
    print(f"[upload_to_rohub] endpoint  = {args.endpoint}")
    print(f"[upload_to_rohub] API URL   = {cfg['API_URL']}")
    print(f"[upload_to_rohub] SPARQL    = {cfg['SPARQL_ENDPOINT']}")

    import rohub
    rohub.login(username=username, password=password)
    print("[upload_to_rohub] logged in")

    zips = discover_zips(args.results_dir, args.configurations)
    if not zips:
        print(f"ERROR: no solution_field_data.zip found under {args.results_dir}",
              file=sys.stderr)
        return 2
    print(f"[upload_to_rohub] found {len(zips)} zip(s): {sorted(zips)}")

    uuids: dict[str, str] = {}
    failed: list[tuple[str, str]] = []
    for cfg_id, zip_path in zips.items():
        try:
            uuid = upload_one(cfg_id, zip_path, rohub)
        except Exception as exc:  # noqa: BLE001 — we want to log and continue
            print(f"[upload_to_rohub] configuration {cfg_id} FAILED: {exc}",
                  file=sys.stderr)
            failed.append((cfg_id, str(exc)))
            continue
        if uuid is not None:
            uuids[cfg_id] = uuid

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(uuids, indent=2, sort_keys=True) + "\n")
    n = len(uuids)
    m = len(zips)
    print(f"[upload_to_rohub] uploaded {n} of {m} configuration(s); "
          f"UUIDs in {args.output}")
    if failed:
        print(f"[upload_to_rohub] {len(failed)} configuration(s) failed: "
              f"{[c for c, _ in failed]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
