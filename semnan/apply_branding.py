#!/usr/bin/env python3
"""Apply SemnanDesk branding to the RustDesk source tree. Idempotent.

Run from the repository root (after `git submodule update --init`):
    python semnan/apply_branding.py
"""
import os
import re
import shutil
import sys
from pathlib import Path

APP_NAME = "SemnanDesk"
ORG = "ir.ac.semnan"
COMPANY = "Semnan University"
SERVER = "r.semnan.ac.ir"
API = "http://r.semnan.ac.ir:8000"
KEY = "2NoJhtty9L0ImqzzQDGaw+GTyH5t7CoWZrxc5tVXEtA="

ROOT = Path(__file__).resolve().parent.parent
A = ROOT / "semnan" / "assets"


def sub(path, pattern, repl, count=1):
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    new, n = re.subn(pattern, repl, text, count=count)
    if n == 0 and repl not in text:
        sys.exit(f"pattern not found in {path}: {pattern}")
    p.write_text(new, encoding="utf-8", newline="")


# --- server / name (hbb_common submodule) ---
cfg = "libs/hbb_common/src/config.rs"
sub(cfg, r'pub const RENDEZVOUS_SERVERS: &\[&str\] = &\[[^\]]*\];',
    f'pub const RENDEZVOUS_SERVERS: &[&str] = &["{SERVER}"];')
sub(cfg, r'pub const RS_PUB_KEY: &str = "[^"]*";', f'pub const RS_PUB_KEY: &str = "{KEY}";')
sub(cfg, r'APP_NAME: RwLock<String> = RwLock::new\("[^"]*"', f'APP_NAME: RwLock<String> = RwLock::new("{APP_NAME}"')
sub(cfg, r'ORG: RwLock<String> = RwLock::new\("[^"]*"', f'ORG: RwLock<String> = RwLock::new("{ORG}"')

# --- default API server ---
sub("src/common.rs", r'"https://admin\.rustdesk\.com"\.to_owned\(\)\n\}', f'"{API}".to_owned()\n}}')

# --- Windows exe metadata ---
rc = "flutter/windows/runner/Runner.rc"
sub(rc, r'VALUE "CompanyName", "[^"]*"', f'VALUE "CompanyName", "{COMPANY}"')
sub(rc, r'VALUE "FileDescription", "[^"]*"', f'VALUE "FileDescription", "{APP_NAME} Remote Desktop"')
sub(rc, r'VALUE "LegalCopyright", "[^"]*"', f'VALUE "LegalCopyright", "{COMPANY}. Based on RustDesk (AGPL-3.0)."')
sub(rc, r'VALUE "ProductName", "[^"]*"', f'VALUE "ProductName", "{APP_NAME}"')

# --- exe metadata (main exe and portable packer) ---
for toml in ("Cargo.toml", "libs/portable/Cargo.toml"):
    sub(toml, r'LegalCopyright = "[^"]*"', f'LegalCopyright = "{COMPANY}. Based on RustDesk (AGPL-3.0)."')
    sub(toml, r'ProductName = "[^"]*"', f'ProductName = "{APP_NAME}"')
    sub(toml, r'FileDescription = "[^"]*"', f'FileDescription = "{APP_NAME} Remote Desktop"')
    sub(toml, r'OriginalFilename = "[^"]*"', f'OriginalFilename = "{APP_NAME}.exe"')

# --- version (SEMNAN_VERSION env, e.g. 1.5.3-2); auto update compares this ---
VERSION = os.environ.get("SEMNAN_VERSION", "").strip()
if VERSION:
    if not re.fullmatch(r"\d+\.\d+\.\d+(-\d+)?", VERSION):
        sys.exit(f"bad SEMNAN_VERSION: {VERSION}")
    sub("Cargo.toml", r'(\[package\]\s*\nname = "rustdesk"\s*\nversion = )"[^"]*"', rf'\g<1>"{VERSION}"')
    sub("Cargo.lock", r'(name = "rustdesk"\r?\nversion = )"[^"]*"', rf'\g<1>"{VERSION}"')

# --- icons ---
copies = {
    "icon.ico": ["res/icon.ico", "res/tray-icon.ico", "flutter/windows/runner/resources/app_icon.ico"],
    "icon-1024.png": ["res/icon.png", "res/mac-icon.png"],
    "icon-32.png": ["res/32x32.png"],
    "icon-64.png": ["res/64x64.png"],
    "icon-128.png": ["res/128x128.png"],
    "icon-256.png": ["res/128x128@2x.png"],
    "logo.svg": ["res/logo.svg", "res/scalable.svg", "flutter/assets/icon.svg"],
}
for src, dsts in copies.items():
    for d in dsts:
        shutil.copyfile(A / src, ROOT / d)

print("SemnanDesk branding applied.")
