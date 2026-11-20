"""Build and verify the source and evidence archive for the Suhail submission."""

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist" / "suhail-health-submission.zip"
SCRATCH = ROOT / ".runtime" / "tmp"
ROOT_FILES = {
    ".dockerignore", ".env.example", ".gitignore", "Makefile", "README.md",
    "SUBMISSION.md", "SUBMISSION_TODO_FOR_HUMAN.md", "compose.yaml",
    "requirements.lock", "suhail-health-logo.png",
}
SOURCE_TREES = (
    "apps/web", "services", "integrations", "pathways", "contracts", "evals",
    "infra", "scripts", "tests", "docs", "bundle", "Suhail_Codex_Build_Pack",
    "reports/impact", "reports/verification", "reports/submission-screenshots",
    "reports/runs/software-delivery-final", "reports/runs/20261120T123924Z-offline",
    "reports/runs/20261120T135507Z-offline", "reports/runs/groq-smoke-holdout-v1",
)
SKIP_DIRECTORIES = {
    ".agents", ".aws", ".codex", ".git", ".next", ".pytest_cache", ".runtime",
    ".venv", "__pycache__", "cache", "node_modules", "playwright-report",
    "runtime", "test-results",
}
SKIP_SUFFIXES = {
    ".db", ".db-shm", ".db-wal", ".log", ".mp3", ".mp4", ".pyc",
    ".sqlite", ".sqlite-shm", ".sqlite-wal", ".sqlite3", ".sqlite3-shm",
    ".sqlite3-wal", ".tsbuildinfo", ".webm", ".zip",
}
VIDEO_SIDECARS = {".jpg", ".srt", ".txt", ".vtt"}
VIDEO_PROOFS = {
    "authored-sync-verification.json", "delivery-qc.json",
    "final-encoded-editorial-review.json", "five-minute-verification.json",
    "packaging-verification.json",
    "verification.json", "visual-sync-verification.json",
}
TOKEN_PATTERNS = (
    ("provider token", re.compile(rb"(?<![\w-])(?:gsk_|sk-)[A-Za-z0-9_-]{16,}")),
    ("ElevenLabs key", re.compile(rb"""\b(?:xi-api-key["']?\s*[:=]|elevenlabs_api\s*=)\s*["']?[A-Za-z0-9_+./=-]{16,}""", re.I)),
    ("database password", re.compile(rb"""\bPOSTGRES_PASSWORD\s*=\s*["']?[A-Za-z0-9!@%_+./=-]+""", re.I)),
    ("PEM block", re.compile(rb"-----BEGIN [A-Z0-9][A-Z0-9 -]{2,80}-----")),
)
PUBLIC_SETTINGS = {
    "AGENT_MODE", "ALLOW_REAL_NOTIFICATIONS", "APP_BASE_URL", "APP_ENV_FILE",
    "APP_MODE", "GROQ_BASE_URL", "NOTIFICATION_MODE",
}


def is_allowed_file(path):
    name = path.name
    return (
        path.is_file() and not path.is_symlink()
        and path.resolve().is_relative_to(ROOT)
        and path.suffix.lower() not in SKIP_SUFFIXES
        and (not name.lower().startswith(".env") or name == ".env.example")
        and name.lower() not in {"app.env", "demo-credentials.json", "settings.json"}
    )


def video_sidecars():
    for path in (ROOT / "reports" / "video-final").glob("*"):
        if not is_allowed_file(path):
            continue
        if path.suffix.lower() in VIDEO_SIDECARS:
            yield path
        elif path.name in VIDEO_PROOFS:
            try:
                report = json.loads(path.read_text())
            except (OSError, ValueError):
                continue
            if isinstance(report, dict) and (report.get("status") == "passed" or report.get("passed") is True):
                yield path


def sources():
    candidates = {ROOT / name for name in ROOT_FILES}
    candidates.update(ROOT.glob("requirements*.txt"))
    candidates.update(video_sidecars())
    for tree in SOURCE_TREES:
        folder = ROOT / tree
        if folder.is_symlink() or not folder.resolve().is_relative_to(ROOT):
            continue
        for directory, children, files in os.walk(folder, followlinks=False):
            parent = Path(directory)
            children[:] = [name for name in children
                           if name not in SKIP_DIRECTORIES and not (parent / name).is_symlink()]
            candidates.update(parent / name for name in files)
    return sorted(path for path in candidates if is_allowed_file(path))


def local_secrets():
    example = dotenv_values(ROOT / ".env.example", interpolate=False)
    secrets = set()
    for filename in (".env", ".env_elevenlabs"):
        for name, value in dotenv_values(ROOT / filename, interpolate=False).items():
            if not value or value == example.get(name):
                continue
            # These documented settings are public unless a URL embeds credentials.
            if name in PUBLIC_SETTINGS and "@" not in value:
                continue
            secrets.add(value.encode())
    return sorted(secrets, key=len, reverse=True)


def scan_archive(path, secrets):
    with ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise SystemExit("Submission archive failed its ZIP integrity check.")
        for index, member in enumerate(archive.infolist(), 1):
            data = archive.read(member)
            name = member.filename.encode()
            if any(secret in data or secret in name for secret in secrets):
                raise SystemExit(f"Private environment value detected in archive member {index}.")
            for kind, pattern in TOKEN_PATTERNS:
                if pattern.search(data) or pattern.search(name):
                    raise SystemExit(f"Possible {kind} detected in archive member {index}.")


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    files = sources()
    with tempfile.TemporaryDirectory(prefix="submission-zip-", dir=SCRATCH) as temporary:
        staged = Path(temporary) / OUTPUT.name
        with ZipFile(staged, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
            for path in files:
                archive.write(path, path.relative_to(ROOT).as_posix())
        scan_archive(staged, local_secrets())
        with staged.open("rb") as file:
            digest = hashlib.file_digest(file, "sha256").hexdigest()
        staged.replace(OUTPUT)
    print(f"{OUTPUT.relative_to(ROOT)} · {len(files)} files · {OUTPUT.stat().st_size:,} bytes")
    print(f"SHA-256 {digest}")


if __name__ == "__main__":
    main()
