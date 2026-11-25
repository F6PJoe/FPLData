#!/usr/bin/env python3
"""Check FPL Copilot for new numbers; rebuild + upload only when they changed.

Meant to run on a schedule (every ~2 hours) so nobody has to track FPL's
moving deadlines. One cheap /meta call per check. It rebuilds when:
  - FPL Copilot's numbers changed (/meta default_version differs), or
  - the next gameweek rolled over (a deadline passed), or
  - --force (use once a day after FPL's overnight price changes, since
    prices and Rost% come from FPL, not FPL Copilot)

Each run appends one line to refresh.log.

Usage:
    python refresh.py              check; rebuild + upload if changed
    python refresh.py --force      rebuild + upload regardless
    python refresh.py --no-upload  rebuild locally only (testing)
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import build_data

HERE = Path(__file__).resolve().parent
DATA_FILE = HERE / "data" / "fpl_projections.json"
LOG = HERE / "refresh.log"


LIVE_URL = "https://fantasysixpack.net/wp-content/uploads/f6p-data/fpl_projections.json"
# The site's bot protection blocks default script/curl user agents, so the
# check for "what is live right now" sends a browser-style one.
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


def previous_state():
    """(version, next_gw) of what readers are seeing right now.

    Reads the file live on the site, not the local copy: a GitHub runner has
    no local copy, and if both a runner and this PC publish, the live file is
    the only thing that is always current. Falls back to the local file, then
    to (None, None), which just means "rebuild" -- the safe direction.
    """
    try:
        m = build_data.get(LIVE_URL, {"User-Agent": BROWSER_UA})["meta"]
        return (m.get("version"), m.get("next_gw"))
    except Exception as exc:  # noqa: BLE001 - any failure means "can't tell"
        print(f"(could not read the live file: {exc}; using local copy)")
    if DATA_FILE.exists():
        m = json.loads(DATA_FILE.read_text(encoding="utf-8"))["meta"]
        return (m.get("version"), m.get("next_gw"))
    return (None, None)


def redact(text):
    """Run logs are public (public repo): blank out the SFTP host, username and
    server path if an error message happens to contain them."""
    import os
    import sftp_helpers
    sftp_helpers.load_env()
    for name in ("SFTP_HOST", "SFTP_USERNAME", "SFTP_REMOTE_ROOT"):
        val = os.environ.get(name)
        if val:
            text = text.replace(val, "***")
    return text


def log(msg):
    line = f"{datetime.now():%Y-%m-%d %H:%M}  {msg}"
    print(line)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-upload", action="store_true")
    args = ap.parse_args()

    meta = build_data.get(f"{build_data.BASE}/meta", {"X-Partner-Key": build_data.key()})["meta"]
    now = (meta.get("default_version"), meta["next_gw"])

    was = previous_state()

    if now == was and not args.force:
        log(f"no change (version {now[0]}, GW{now[1]})")
        return

    reason = "forced" if now == was else f"version {was[0]} -> {now[0]}, GW{was[1]} -> GW{now[1]}"
    build_data.main([], meta=meta)
    if args.no_upload:
        log(f"rebuilt ({reason}), upload skipped")
        return
    r = subprocess.run([sys.executable, str(HERE / "upload.py")], capture_output=True, text=True)
    if r.returncode:
        log(f"rebuilt ({reason}) but UPLOAD FAILED: {redact((r.stderr or r.stdout).strip()[-300:])}")
        sys.exit(1)
    log(f"rebuilt + uploaded ({reason})")


if __name__ == "__main__":
    main()
