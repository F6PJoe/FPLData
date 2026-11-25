"""SFTP login helpers for the SiteGround host.

Copied from the usage tool's sftp_upload.py (NFLData/ff_utilization) so this
repo stands alone. Reads SFTP_* settings from .env (local) or the environment
(GitHub Actions); real environment variables always win.
"""
import os
import sys
from pathlib import Path

import paramiko

HERE = Path(__file__).resolve().parent


def load_env():
    """Read .env next to this file if present. Real env vars always win."""
    path = HERE / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())


def load_private_key(key_path, passphrase):
    """Try every key type paramiko supports rather than assuming RSA --
    SiteGround's SSH Keys Manager can hand out RSA or Ed25519. A PuTTY .ppk
    can't be read directly: export it as an OpenSSH key in PuTTYgen first."""
    errors = []
    for cls in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
        try:
            return cls.from_private_key_file(key_path, password=passphrase)
        except paramiko.SSHException as exc:
            errors.append(f"{cls.__name__}: {exc}")
    detail = "\n  ".join(errors)
    sys.exit(f"Could not load {key_path} as any known key type:\n  {detail}")


def connect():
    host = os.environ.get("SFTP_HOST")
    username = os.environ.get("SFTP_USERNAME")
    if not host or not username:
        sys.exit("Missing SFTP_HOST or SFTP_USERNAME (set them in .env or the environment).")
    port = int(os.environ.get("SFTP_PORT", "22"))
    key_path = os.environ.get("SFTP_KEY_PATH")
    password = os.environ.get("SFTP_PASSWORD")
    key_passphrase = os.environ.get("SFTP_KEY_PASSPHRASE") or None

    # AutoAddPolicy trusts an unknown host key on first connect -- a reasonable
    # tradeoff for one personal host on a stable hostname.
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    if key_path:
        pkey = load_private_key(key_path, key_passphrase)
        client.connect(host, port=port, username=username, pkey=pkey, timeout=30)
    elif password:
        client.connect(host, port=port, username=username, password=password, timeout=30)
    else:
        sys.exit("Set either SFTP_PASSWORD or SFTP_KEY_PATH.")
    return client


def remote_join(root, rel):
    return root.rstrip("/") + "/" + rel
