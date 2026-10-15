#!/usr/bin/env python3
"""manifest.json (файлы + SHA-256 + размер) и manifest.sig (Ed25519, base64). Ключ — секрет LUMO_SIGNING_KEY
(32 байта raw, base64). Публичный ключ кладётся в FilterUpdater.publicKeyBase64.
    python3 make_manifest.py public            — подписать
    python3 make_manifest.py --new-key         — создать пару ключей (один раз, на своём маке)"""
import base64
import hashlib
import json
import os
import sys
import time
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

if "--new-key" in sys.argv:
    k = Ed25519PrivateKey.generate()
    raw = k.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    pub = k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    print("PRIVATE (в секрет GitHub LUMO_SIGNING_KEY, никому не показывать):", base64.b64encode(raw).decode())
    print("PUBLIC  (в FilterUpdater.publicKeyBase64):", base64.b64encode(pub).decode())
    sys.exit(0)

out = Path(sys.argv[1])
files = []
for f in sorted(out.glob("*.json")):
    if f.name in ("manifest.json", "lists.json"):
        continue
    data = f.read_bytes()
    files.append({"file": f.name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
manifest = json.dumps({"version": time.strftime("%Y%m%d%H%M", time.gmtime()),
                       "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "files": files},
                      separators=(",", ":")).encode()
(out / "manifest.json").write_bytes(manifest)
key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(os.environ["LUMO_SIGNING_KEY"]))
(out / "manifest.sig").write_text(base64.b64encode(key.sign(manifest)).decode())
print(f"manifest: {len(files)} files, signed")
