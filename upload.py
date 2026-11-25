#!/usr/bin/env python3
"""Upload data/fpl_projections.json to the site over SFTP.

    data/fpl_projections.json -> wp-content/uploads/f6p-data/fpl_projections.json

Public path on purpose -- the page is free, so the data isn't gated.
Credentials: SFTP_* in .env (local) or the environment (GitHub Actions).

Usage:
    python upload.py --dry-run
    python upload.py
"""
import argparse
import os
import sys
from pathlib import Path

import sftp_helpers

HERE = Path(__file__).resolve().parent
LOCAL = HERE / "data" / "fpl_projections.json"
REMOTE_REL = "wp-content/uploads/f6p-data/fpl_projections.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="connect and check the path, upload nothing")
    args = ap.parse_args()

    if not LOCAL.exists():
        sys.exit(f"{LOCAL} not found -- run build_data.py first.")
    sftp_helpers.load_env()
    root = os.environ.get("SFTP_REMOTE_ROOT")
    if not root:
        sys.exit("Missing SFTP_REMOTE_ROOT (set it in .env or the environment).")

    remote = sftp_helpers.remote_join(root, REMOTE_REL)
    size = LOCAL.stat().st_size
    client = sftp_helpers.connect()
    try:
        sftp = client.open_sftp()
        try:
            now = f"{sftp.stat(remote).st_size/1024:.1f} KB currently there"
        except FileNotFoundError:
            now = "does not exist yet on the server"
        # Only the site-relative path -- run logs are public, and the full
        # remote path is the server's filesystem layout.
        print(f"{LOCAL.name} ({size/1024:.1f} KB) -> {REMOTE_REL}  [{now}]")
        if args.dry_run:
            print("Dry run -- nothing uploaded.")
            return
        sftp.put(str(LOCAL), remote)
        if sftp.stat(remote).st_size != size:
            sys.exit("UPLOAD MISMATCH -- re-run.")
        print("uploaded (size verified)")
    finally:
        client.close()


if __name__ == "__main__":
    main()
