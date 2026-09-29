"""Shared helpers for the data pipeline: paths, polite HTTP fetching, JSON I/O."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MANUAL_DIR = DATA_DIR / "manual"
PERSONAS_DIR = DATA_DIR / "personas"

USER_AGENT = "ShortcutDataPipeline/0.1 (portfolio project; polite, cached, low-rate)"
PRD_APPENDIX_SOURCE = "PRD appendix (transcribed)"


class OfflineMissingError(RuntimeError):
    """Raised in offline mode when a raw file has not been committed."""


@dataclass
class FetchLog:
    """Records every fetch attempt so REPORT.md can show what was reachable."""

    entries: list[dict[str, Any]] = field(default_factory=list)

    def add(self, url: str, status: str, path: Path | None = None, detail: str = "") -> None:
        self.entries.append(
            {
                "url": url,
                "status": status,
                "path": str(path.relative_to(REPO_ROOT)) if path else None,
                "detail": detail,
            }
        )


class Fetcher:
    """Downloads into data/raw (online) or reads committed raw files (offline).

    Online mode reuses a raw file that already exists unless ``refresh`` is set, so
    re-running the pipeline is cheap and polite.
    """

    def __init__(self, online: bool, refresh: bool = False, delay_s: float = 0.25) -> None:
        self.online = online
        self.refresh = refresh
        self.delay_s = delay_s
        self.log = FetchLog()
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=45.0,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def get(self, url: str, dest: Path) -> bytes:
        if dest.exists() and (not self.online or not self.refresh):
            self.log.add(url, "cached", dest)
            return dest.read_bytes()
        if not self.online:
            self.log.add(url, "missing-offline", dest)
            raise OfflineMissingError(f"{dest} not found and pipeline is offline")
        body = self._download(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
        self.log.add(url, "downloaded", dest)
        return body

    def _download(self, url: str) -> bytes:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                time.sleep(self.delay_s)
                response = self.client.get(url)
                if response.status_code == 202 and not response.content:
                    raise WafChallengeError(url)
                response.raise_for_status()
                return response.content
            except WafChallengeError:
                raise
            except httpx.HTTPError as exc:
                last_error = exc
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"failed to fetch {url}: {last_error}")


class WafChallengeError(RuntimeError):
    """catalog.atu.edu answers with an AWS WAF JavaScript challenge (HTTP 202, empty body)."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False)
    path.write_text(text + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def course_code(subject: str, number: str) -> str:
    return f"{subject.strip().upper()} {number.strip().upper()}"


def course_level(number: str) -> int:
    """Level bucket from the catalog number: 1003 -> 1000, 3213 -> 3000."""
    digits = "".join(ch for ch in number if ch.isdigit())
    return int(digits[0]) * 1000 if digits else 0
