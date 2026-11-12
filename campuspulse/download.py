"""Download Scorecard bulk data, its dictionary and IPEDS files into data/raw/ (resumable, checksummed)."""
import hashlib
import json
import re
import sys
import requests
from . import config as C

MANIFEST = C.RAW / "MANIFEST.json"
RAW_ZIP_RE = re.compile(r"https?://[^\"' <>]+College_Scorecard_Raw_Data_\d{8}\.zip")


def scrape_raw_zip_url(html: str) -> str:
    m = RAW_ZIP_RE.search(html)
    if not m:
        raise RuntimeError("no College_Scorecard_Raw_Data_<date>.zip link found on the Scorecard data page")
    return m.group(0)


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, dest, session: requests.Session) -> str:
    """Resumable download. Returns 'downloaded', 'cached' or 'missing' (HTTP 404)."""
    head = session.head(url, allow_redirects=True, timeout=60)
    if head.status_code == 404:
        return "missing"
    head.raise_for_status()
    total = int(head.headers["Content-Length"])
    have = dest.stat().st_size if dest.exists() else 0
    if have == total:
        return "cached"
    if have > total:
        dest.unlink()
        have = 0
    headers = {"Range": f"bytes={have}-"} if have else {}
    with session.get(url, headers=headers, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, "ab" if have else "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    return "downloaded"


def run() -> dict:
    C.RAW.mkdir(parents=True, exist_ok=True)
    (C.RAW / "ipeds").mkdir(exist_ok=True)
    s = requests.Session()
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    html = s.get(C.SCORECARD_PAGE, timeout=60).text
    jobs = [(scrape_raw_zip_url(html), C.RAW / "College_Scorecard_Raw_Data.zip", "scorecard_raw"),
            (C.DICT_URL, C.RAW / "dict.xlsx", "scorecard_dictionary")]
    for year in sorted(set(C.IPEDS_YEARS.values())):
        for kind, stem in C.ipeds_files(year).items():
            for suffix in ("", "_Dict"):
                jobs.append((f"{C.IPEDS_BASE}{stem}{suffix}.zip", C.RAW / "ipeds" / f"{stem}{suffix}.zip", f"ipeds_{kind}{suffix}"))
    for url, dest, tag in jobs:
        key = dest.relative_to(C.RAW).as_posix()
        status = fetch(url, dest, s)
        if status == "missing":
            print(f"MISSING (404, continuing): {url}", file=sys.stderr)
            manifest[key] = {"url": url, "status": "missing", "tag": tag}
        elif status == "downloaded" or key not in manifest or manifest[key].get("status") == "missing":
            manifest[key] = {"url": url, "status": "ok", "tag": tag, "bytes": dest.stat().st_size, "sha256": sha256(dest)}
        print(f"{status:10s} {key}")
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


if __name__ == "__main__":
    run()
