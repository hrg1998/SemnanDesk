#!/usr/bin/env python3
"""Create the signed latest.json for SemnanDesk auto update.

Usage:
  python semnan/make_update_json.py --version 1.5.3-2 \
      --x64 out/SemnanDesk-1.5.3-2-x86_64.exe --x86 out/SemnanDesk-1.5.3-2-x86-sciter.exe \
      -o out/latest.json

The ed25519 private key (base64 of the 32-byte seed) is read from the
SEMNAN_UPDATE_SIGNING_KEY environment variable, or from --key-file.

Put latest.json and both executables on the server at the URLs below.
Generate a new key pair:  python semnan/make_update_json.py --gen-key
"""
import argparse
import base64
import hashlib
import json
import os
import sys

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

BASE_URL = "https://it.semnan.ac.ir/uploads/6/helpdesk/"
X64_NAME = "rustdesk86.exe"
X86_NAME = "rustdesk32.exe"


def describe(path, url):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return {"url": url, "sha256": h.hexdigest(), "size": os.path.getsize(path)}


def raw_public(key):
    return key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen-key", action="store_true")
    ap.add_argument("--version")
    ap.add_argument("--x64")
    ap.add_argument("--x86")
    ap.add_argument("--key-file")
    ap.add_argument("-o", "--output", default="latest.json")
    a = ap.parse_args()

    if a.gen_key:
        k = Ed25519PrivateKey.generate()
        seed = k.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                               serialization.NoEncryption())
        print("PRIVATE (keep secret):", base64.b64encode(seed).decode())
        print("PUBLIC:", base64.b64encode(raw_public(k)).decode())
        return

    if not a.version or not (a.x64 or a.x86):
        sys.exit("--version and at least one of --x64/--x86 are required")
    seed_b64 = os.environ.get("SEMNAN_UPDATE_SIGNING_KEY", "")
    if a.key_file:
        seed_b64 = open(a.key_file, encoding="utf-8").read()
    if not seed_b64.strip():
        sys.exit("signing key missing (SEMNAN_UPDATE_SIGNING_KEY or --key-file)")
    key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(seed_b64.strip()))

    payload = {"version": a.version}
    if a.x64:
        payload["x64"] = describe(a.x64, BASE_URL + X64_NAME)
    if a.x86:
        payload["x86"] = describe(a.x86, BASE_URL + X86_NAME)
    payload_str = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    sig = key.sign(payload_str.encode("utf-8"))
    env = {"payload": payload_str, "signature": base64.b64encode(sig).decode()}
    with open(a.output, "w", encoding="utf-8") as f:
        json.dump(env, f, indent=2)
    print("wrote", a.output, "public key:", base64.b64encode(raw_public(key)).decode())


if __name__ == "__main__":
    main()
