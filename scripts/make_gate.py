#!/usr/bin/env python3
"""Create docs/gate.json — the passcode-encrypted shared config for the UI.

Run locally whenever you want to set/change the passcode or rotate the token:

    pip3 install cryptography   (once)
    python3 scripts/make_gate.py
    git add docs/gate.json && git commit -m "update access gate" && git push

What it stores (AES-256-GCM, key derived from your passcode via PBKDF2):
owner, repo, branch, and a shared GitHub PAT. Recommended token: fine-grained,
this repo only, Contents RW + Actions RW, 90-day expiry, named "shared-ui".

HONEST SECURITY NOTE: the encrypted blob is public. A short numeric passcode
(e.g. 5 digits = 100,000 possibilities) can be brute-forced offline by a
determined attacker, exposing the token. A passphrase of 3-4 random words is
strongly recommended instead. Either way: scope the token minimally, give it
an expiry, and remember that revoking it at github.com instantly locks
everyone out (your admin lever). The repo data itself remains public.
"""
import base64
import getpass
import json
import os
from pathlib import Path

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    raise SystemExit("Run first:  pip3 install cryptography")
import hashlib

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "gate.json"
ITERATIONS = 600_000

owner = input("GitHub owner [yudanin]: ").strip() or "yudanin"
repo = input("Repository [decolonialist-monitor]: ").strip() or "decolonialist-monitor"
branch = input("Branch [main]: ").strip() or "main"
pat = getpass.getpass("Shared PAT (input hidden): ").strip()
code = getpass.getpass("Passcode to require (input hidden): ").strip()
code2 = getpass.getpass("Repeat passcode: ").strip()
assert pat.startswith(("github_pat_", "ghp_")), "that doesn't look like a GitHub token"
assert code and code == code2, "passcodes empty or mismatched"
if code.isdigit() and len(code) <= 6:
    print("\n⚠  Short numeric codes are offline-brute-forceable — see the note "
          "at the top of this script. Proceeding as instructed.\n")

salt, iv = os.urandom(16), os.urandom(12)
key = hashlib.pbkdf2_hmac("sha256", code.encode(), salt, ITERATIONS, dklen=32)
payload = json.dumps({"owner": owner, "repo": repo,
                      "branch": branch, "pat": pat}).encode()
ct = AESGCM(key).encrypt(iv, payload, None)

OUT.write_text(json.dumps({
    "v": 1, "kdf": "PBKDF2-SHA256", "iter": ITERATIONS,
    "salt": base64.b64encode(salt).decode(),
    "iv": base64.b64encode(iv).decode(),
    "ct": base64.b64encode(ct).decode()}, indent=2))
print(f"Wrote {OUT.relative_to(ROOT)} — commit and push it.")
