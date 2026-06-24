"""Sync the built Windows .exe to Aliyun OSS for fast in-China downloads.

Uploads three objects to a public-read OSS bucket:
  - PurrPause-{VERSION}-windows.exe   (versioned, immutable)
  - PurrPause-latest-windows.exe      (stable alias the landing-page button points at)
  - latest.json                       {version, size, sha256, date, url}

The landing page (site/) reads latest.json to show the current version/size and
defaults its download button to the "latest" alias, so a new release is picked up
with no page redeploy.

Run in CI after the release is published, or locally to seed the first upload:

    pip install oss2                      # dev-only dep, NOT in requirements.txt
    export ALIYUN_OSS_KEY_ID=...          # (Windows PowerShell: $env:ALIYUN_OSS_KEY_ID=...)
    export ALIYUN_OSS_KEY_SECRET=...
    export ALIYUN_OSS_BUCKET=purrpause
    export ALIYUN_OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
    python scripts/sync_oss.py            # uses dist/PurrPause-{VERSION}-windows.exe
    python scripts/sync_oss.py path/to/PurrPause-0.1.2-windows.exe   # explicit path

Note: configure the bucket as public-read and add a CORS rule allowing GET from the
site origin so the page can fetch latest.json cross-origin. That is bucket config,
done once in the OSS console — not by this script.
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import oss2
except ImportError:
    raise SystemExit(
        "oss2 not installed. Install with:\n"
        "    pip install oss2"
    )

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from version import VERSION  # noqa: E402

VERSIONED_NAME = f"PurrPause-{VERSION}-windows.exe"
LATEST_NAME = "PurrPause-latest-windows.exe"
LATEST_JSON = "latest.json"

ENV = ("ALIYUN_OSS_KEY_ID", "ALIYUN_OSS_KEY_SECRET", "ALIYUN_OSS_BUCKET", "ALIYUN_OSS_ENDPOINT")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_endpoint(endpoint: str) -> str:
    """Strip any scheme so we can build a clean public URL host."""
    return endpoint.replace("https://", "").replace("http://", "").strip("/")


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload the Windows .exe + latest.json to Aliyun OSS.")
    parser.add_argument(
        "exe", nargs="?", default=str(ROOT / "dist" / VERSIONED_NAME),
        help=f"path to the built .exe (default: dist/{VERSIONED_NAME})",
    )
    args = parser.parse_args()

    missing = [k for k in ENV if not os.environ.get(k)]
    if missing:
        raise SystemExit("missing required env var(s): " + ", ".join(missing))

    exe_path = Path(args.exe)
    if not exe_path.exists():
        raise SystemExit(f"built .exe not found: {exe_path}\n(run `python scripts/build_dist.py` first)")

    key_id = os.environ["ALIYUN_OSS_KEY_ID"]
    key_secret = os.environ["ALIYUN_OSS_KEY_SECRET"]
    bucket_name = os.environ["ALIYUN_OSS_BUCKET"]
    endpoint = normalize_endpoint(os.environ["ALIYUN_OSS_ENDPOINT"])

    size = exe_path.stat().st_size
    digest = sha256_of(exe_path)
    public_base = f"https://{bucket_name}.{endpoint}"
    latest_url = f"{public_base}/{LATEST_NAME}"

    manifest = {
        "version": VERSION,
        "size": size,
        "sha256": digest,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "url": latest_url,
    }

    bucket = oss2.Bucket(oss2.Auth(key_id, key_secret), f"https://{endpoint}", bucket_name)

    exe_headers = {"Content-Type": "application/octet-stream"}
    json_headers = {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-cache"}

    print(f"uploading {exe_path.name} ({size / 1024 / 1024:.1f} MB) to bucket '{bucket_name}' @ {endpoint}")

    print(f"  -> {VERSIONED_NAME}")
    bucket.put_object_from_file(VERSIONED_NAME, str(exe_path), headers=exe_headers)

    print(f"  -> {LATEST_NAME} (stable alias)")
    bucket.put_object_from_file(LATEST_NAME, str(exe_path), headers=exe_headers)

    print(f"  -> {LATEST_JSON}")
    bucket.put_object(LATEST_JSON, json.dumps(manifest, ensure_ascii=False).encode("utf-8"), headers=json_headers)

    print("\ndone. public URLs:")
    print(f"  versioned: {public_base}/{VERSIONED_NAME}")
    print(f"  latest:    {latest_url}")
    print(f"  manifest:  {public_base}/{LATEST_JSON}")
    print(f"  sha256:    {digest}")


if __name__ == "__main__":
    main()
