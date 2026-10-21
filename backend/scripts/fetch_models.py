"""Build-time model fetch (D4): download pinned revisions and verify weight checksums.

Usage: python fetch_models.py models.lock.json /models
Runs only during `docker build`; the running containers set HF_HUB_OFFLINE=1.
"""

import hashlib
import json
import sys
from pathlib import Path

from huggingface_hub import snapshot_download


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(lock_path: str, out_dir: str) -> int:
    lock = json.loads(Path(lock_path).read_text())
    failed = False
    for name, spec in lock.items():
        target = Path(out_dir) / name
        snapshot_download(
            repo_id=spec["repo"],
            revision=spec["revision"],
            local_dir=target,
            allow_patterns=spec["allow_patterns"],
            ignore_patterns=spec["ignore_patterns"] or None,
        )
        for rel, expected in spec["sha256"].items():
            actual = sha256_of(target / rel)
            ok = actual == expected
            failed |= not ok
            print(f"{name}/{rel}: {'OK' if ok else 'MISMATCH ' + actual}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
