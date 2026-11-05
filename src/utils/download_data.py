"""Download the raw datasets used by the project into ``data/raw/``.

Only HTTPS links are accepted. Each download is written to a temporary file
first and moved into place only after its checksum matches, so a failed or
partial download never leaves a broken file behind.

Run from the project root::

    python -m src.utils.download_data            # download everything missing
    python -m src.utils.download_data --force    # re-download everything

The NSL-KDD *test* file is deliberately not downloaded: it was rejected in
Phase 1 (see docs/data_sources.md).
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
USER_AGENT = "SentinelEdge-data-download/0.1 (academic research)"
CHUNK_SIZE = 1024 * 1024


class DownloadError(RuntimeError):
    """Raised when a dataset cannot be downloaded or fails its checksum."""


@dataclass(frozen=True)
class DatasetSource:
    """Where one dataset comes from and how to verify it."""

    name: str
    url: str
    dest: Path
    sha256: str | None = None  # None = no published checksum; recorded on first run
    unzip_member: str | None = None  # If set, the file is extracted from a zip


SOURCES: tuple[DatasetSource, ...] = (
    DatasetSource(
        name="UCI SMS Spam Collection",
        url="https://archive.ics.uci.edu/static/public/228/sms+spam+collection.zip",
        dest=RAW_DIR / "sms_uci" / "SMSSpamCollection",
        unzip_member="SMSSpamCollection",
    ),
    DatasetSource(
        name="Phishing Websites Dataset (Mendeley, small variant)",
        url=(
            "https://data.mendeley.com/public-files/datasets/72ptz43s9v/files/"
            "154607af-0e5d-487d-87e4-c5070b2eb544/file_downloaded"
        ),
        dest=RAW_DIR / "phishing_mendeley" / "dataset_small.csv",
        sha256="2252b0d69252301880b1c87fe34b4f7fa646edaab67e3fc16f7779245085a492",
    ),
    DatasetSource(
        name="NSL-KDD training file (Zenodo copy, team-approved)",
        url="https://zenodo.org/records/17424143/files/KDDTrain+.txt?download=1",
        dest=RAW_DIR / "nsl_kdd" / "KDDTrain+.txt",
        sha256=None,  # Zenodo publishes MD5 only; checked in _verify_md5 below
    ),
)

NSL_KDD_TRAIN_MD5 = "120b13c9092ab72d4902f2079143cc2c"


def _require_https(url: str) -> None:
    if urlparse(url).scheme != "https":
        raise DownloadError(f"Refusing non-HTTPS URL: {url}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fetch(url: str, target: Path, timeout: float) -> None:
    """Stream ``url`` into ``target``. Raises DownloadError on any failure."""
    _require_https(url)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            with target.open("wb") as handle:
                shutil.copyfileobj(response, handle, CHUNK_SIZE)
    except urllib.error.HTTPError as exc:
        raise DownloadError(f"HTTP {exc.code} while fetching {url}") from exc
    except urllib.error.URLError as exc:
        raise DownloadError(
            f"Network error while fetching {url}: {exc.reason}"
        ) from exc
    except TimeoutError as exc:
        raise DownloadError(f"Timed out after {timeout} s: {url}") from exc


def download_source(
    source: DatasetSource, force: bool = False, timeout: float = 60.0
) -> Path:
    """Download one dataset into ``source.dest`` and verify it.

    Returns the final path. Skips the download when the file already exists
    and ``force`` is False.
    """
    if source.dest.exists() and not force:
        print(f"[skip] {source.name}: already present at {source.dest}")
        return source.dest

    source.dest.parent.mkdir(parents=True, exist_ok=True)
    temp = source.dest.parent / (source.dest.name + ".part")
    archive = source.dest.parent / (source.dest.name + ".zip.part")
    print(f"[get ] {source.name} from {source.url}")
    try:
        if source.unzip_member is None:
            _fetch(source.url, temp, timeout)
        else:
            _fetch(source.url, archive, timeout)
            _extract_member(archive, source.unzip_member, temp)
        _verify(source, temp)
        temp.replace(source.dest)
    except (DownloadError, zipfile.BadZipFile, KeyError, OSError) as exc:
        temp.unlink(missing_ok=True)
        raise DownloadError(f"{source.name}: {exc}") from exc
    finally:
        archive.unlink(missing_ok=True)
    print(f"[ok  ] {source.name} -> {source.dest}")
    return source.dest


def _extract_member(archive: Path, member: str, out: Path) -> None:
    """Copy one member of a zip archive to ``out``."""
    with zipfile.ZipFile(archive) as zf, zf.open(member) as src:
        out.write_bytes(src.read())


def _verify(source: DatasetSource, path: Path) -> None:
    if source.sha256 is not None and _sha256(path) != source.sha256:
        raise DownloadError("SHA-256 mismatch; file is corrupt or has changed")
    if source.dest.name == "KDDTrain+.txt" and _md5(path) != NSL_KDD_TRAIN_MD5:
        raise DownloadError("MD5 mismatch against the Zenodo listing")
    if path.stat().st_size == 0:
        raise DownloadError("Downloaded file is empty")


def download_all(force: bool = False) -> list[Path]:
    """Download every source. Stops at the first failure with a clear message."""
    return [download_source(source, force=force) for source in SOURCES]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="re-download files")
    args = parser.parse_args(argv)
    try:
        download_all(force=args.force)
    except DownloadError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
