"""Small publication guard, not a comprehensive secret scanner. Scans tracked files only."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DENIED_PARTS = {"private", "exports", "downloads", ".venv", "node_modules", "__pycache__"}
DENIED_SUFFIXES = {".har", ".pdf", ".png", ".jpg", ".jpeg", ".log", ".pem", ".key"}
PATTERNS = [
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(rb"sk-[A-Za-z0-9]{32,}"),
    re.compile(rb"(?<!\d)\d{6}-\d{4}(?!\d)"),
]


def main() -> None:
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0")
    failures = []
    for name in filter(None, names):
        path = ROOT / name.decode()
        relative = path.relative_to(ROOT)
        if (
            set(relative.parts) & DENIED_PARTS
            or path.suffix in DENIED_SUFFIXES
            or (path.name.startswith(".env") and path.name != ".env.example")
        ):
            failures.append(str(relative))
        data = path.read_bytes()
        if any(pattern.search(data) for pattern in PATTERNS):
            failures.append(str(relative))
    if failures:
        raise SystemExit("Publication guard failed in: " + ", ".join(sorted(set(failures))))
    print("PASS: tracked-file publication guard (manual review still required)")


if __name__ == "__main__":
    main()
