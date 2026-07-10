#!/usr/bin/env python3
"""Measure ReccoBeats coverage for Spotify track IDs.

Examples:
  scripts/test_reccobeats_coverage.py --track-id 01K4zKU104LyJ8gMb7227B
  scripts/test_reccobeats_coverage.py --track-ids-file /tmp/track_ids.txt
  SPOTIBYE_AUTH_TOKEN=... scripts/test_reccobeats_coverage.py \
    --backend-url https://spotibye-backend-development.kevin-grizzard.workers.dev \
    --playlist-id 03YbVT4UhOxLrOAcpyCEqT
"""

from __future__ import annotations

import argparse
import concurrent.futures
import email.utils
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BATCH_SIZE = 30
CONCURRENCY = 3
RECCOBEATS_BASE_URL = "https://api.reccobeats.com/v1"
DEFAULT_BACKEND_URL = "http://localhost:8787"
REQUEST_TIMEOUT_SECONDS = 20
MAX_RETRIES = 3
DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "SpotiBye-ReccoBeats-Coverage/1.0",
}
ALLOWED_URL_SCHEMES = frozenset({"http", "https"})
ALLOWED_RECCOBEATS_HOST = "api.reccobeats.com"
ALLOWED_BACKEND_HOSTS = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "::1",
        "spotibye-backend-development.kevin-grizzard.workers.dev",
    }
)
ALLOWED_TRACK_IDS_FILE_EXTENSIONS = frozenset({".csv", ".list", ".txt"})
SPOTIFY_ID_PATTERN = re.compile(r"^[A-Za-z0-9]{22}$")


@dataclass(frozen=True)
class BatchResult:
    endpoint: str
    batch_index: int
    requested_ids: list[str]
    state: str
    status: int | None
    returned_ids: list[str]
    error: str | None = None


def parse_retry_after(value: str | None) -> int:
    if not value:
        return 1

    trimmed = value.strip()
    if not trimmed:
        return 1

    if trimmed.isdigit():
        return max(0, int(trimmed))

    try:
        parsed = email.utils.parsedate_to_datetime(trimmed)
    except (TypeError, ValueError):
        return 1

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    delta = parsed - datetime.now(timezone.utc)
    return max(0, int(delta.total_seconds() + 0.999))


def chunk(items: list[str], size: int) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def is_within_path(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def allowed_file_roots() -> tuple[Path, Path]:
    return (Path.cwd().resolve(), Path(tempfile.gettempdir()).resolve())


def validate_track_ids_file_path(file_path: str) -> Path:
    path = Path(file_path).expanduser().resolve(strict=True)
    if not any(is_within_path(path, root) for root in allowed_file_roots()):
        raise ValueError("Track IDs file must be under this repo or the system temp dir")
    if not path.is_file():
        raise ValueError("Track IDs path must point to a regular file")
    if path.suffix.lower() not in ALLOWED_TRACK_IDS_FILE_EXTENSIONS:
        raise ValueError("Track IDs file must use .txt, .list, or .csv")
    return path


def validate_spotify_id(value: str, label: str) -> str:
    if not SPOTIFY_ID_PATTERN.fullmatch(value):
        raise ValueError(f"{label} must be a 22-character Spotify ID")
    return value


def validate_endpoint(endpoint: str) -> str:
    if endpoint not in {"audio-features", "track"}:
        raise ValueError("Unexpected ReccoBeats endpoint")
    return endpoint


def validate_request_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname.lower() if parsed.hostname else ""
    if (
        parsed.scheme not in ALLOWED_URL_SCHEMES
        or not hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ValueError("Request URL must be an absolute HTTP or HTTPS URL")

    if (
        parsed.scheme == "https"
        and hostname == ALLOWED_RECCOBEATS_HOST
        and parsed.path.startswith("/v1/")
    ):
        return

    if hostname not in ALLOWED_BACKEND_HOSTS:
        raise ValueError("Backend URL host is not allowlisted")
    if hostname in {"localhost", "127.0.0.1", "::1"}:
        return
    if parsed.scheme != "https":
        raise ValueError("Remote backend URLs must use HTTPS")
    if parsed.port not in {None, 443}:
        raise ValueError("Remote backend URLs must use the default HTTPS port")


def validate_backend_base_url(backend_url: str) -> str:
    normalized = backend_url.rstrip("/")
    validate_request_url(f"{normalized}/health")
    return normalized


def request_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = REQUEST_TIMEOUT_SECONDS,
) -> tuple[int, Any]:
    validate_request_url(url)
    request_headers = {**DEFAULT_HEADERS, **(headers or {})}
    request = urllib.request.Request(url, headers=request_headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
        body = response.read().decode("utf-8")
        return response.status, json.loads(body)


def request_json_with_retry(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = REQUEST_TIMEOUT_SECONDS,
) -> tuple[int, Any]:
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            return request_json(url, headers=headers, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == MAX_RETRIES:
                raise
            retry_after = parse_retry_after(exc.headers.get("Retry-After"))
            time.sleep(retry_after)
            last_error = exc
        except (TimeoutError, urllib.error.URLError) as exc:
            if attempt == MAX_RETRIES:
                raise
            time.sleep(2**attempt)
            last_error = exc

    raise RuntimeError(f"Retries exhausted: {last_error}")


def extract_spotify_id_from_href(href: Any) -> str | None:
    if not isinstance(href, str):
        return None
    marker = "/track/"
    if marker not in href:
        return None
    track_id = href.rsplit(marker, 1)[-1].split("?", 1)[0].split("#", 1)[0]
    return track_id or None


def extract_track_ids_from_backend_items(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []

    track_ids: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        track = item.get("track") or item.get("item") or item
        if isinstance(track, dict) and isinstance(track.get("id"), str):
            track_ids.append(track["id"])
    return track_ids


def unwrap_backend_data(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def fetch_playlist_track_ids(
    backend_url: str,
    playlist_id: str,
    token: str,
    *,
    page_size: int = 50,
) -> list[str]:
    safe_backend_url = validate_backend_base_url(backend_url)
    safe_playlist_id = validate_spotify_id(playlist_id, "playlist ID")
    headers = {"Authorization": f"Bearer {token}"}
    all_ids: list[str] = []
    offset = 0

    while True:
        query = urllib.parse.urlencode({"limit": page_size, "offset": offset})
        url = (
            f"{safe_backend_url}/spotify/playlists/"
            f"{urllib.parse.quote(safe_playlist_id)}/items?{query}"
        )
        _, payload = request_json_with_retry(url, headers=headers)
        data = unwrap_backend_data(payload)

        if isinstance(data, dict):
            items = data.get("items") or data.get("tracks") or []
        else:
            items = data

        ids = extract_track_ids_from_backend_items(items)
        all_ids.extend(ids)

        raw_count = len(items) if isinstance(items, list) else 0
        if raw_count < page_size:
            break
        offset += page_size

    return all_ids


def reccobeats_url(endpoint: str, ids: list[str]) -> str:
    safe_endpoint = validate_endpoint(endpoint)
    for track_id in ids:
        validate_spotify_id(track_id, "track ID")
    query = urllib.parse.urlencode([("ids", track_id) for track_id in ids])
    return f"{RECCOBEATS_BASE_URL}/{safe_endpoint}?{query}"


def fetch_reccobeats_batch(
    endpoint: str,
    batch_index: int,
    requested_ids: list[str],
) -> BatchResult:
    url = reccobeats_url(endpoint, requested_ids)
    try:
        status, payload = request_json_with_retry(url)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        return BatchResult(
            endpoint=endpoint,
            batch_index=batch_index,
            requested_ids=requested_ids,
            state="throw",
            status=exc.code,
            returned_ids=[],
            error=f"HTTP {exc.code}: {body}",
        )
    except (TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return BatchResult(
            endpoint=endpoint,
            batch_index=batch_index,
            requested_ids=requested_ids,
            state="throw",
            status=None,
            returned_ids=[],
            error=str(exc),
        )

    content = payload.get("content") if isinstance(payload, dict) else None
    if not isinstance(content, list):
        return BatchResult(
            endpoint=endpoint,
            batch_index=batch_index,
            requested_ids=requested_ids,
            state="throw",
            status=status,
            returned_ids=[],
            error="Invalid ReccoBeats response shape",
        )

    returned_ids = [
        track_id
        for entry in content
        if isinstance(entry, dict)
        for track_id in [extract_spotify_id_from_href(entry.get("href"))]
        if track_id
    ]
    state = "200 []" if status == 200 and not returned_ids else "200 [data]"
    return BatchResult(
        endpoint=endpoint,
        batch_index=batch_index,
        requested_ids=requested_ids,
        state=state,
        status=status,
        returned_ids=returned_ids,
    )


def run_coverage(track_ids: list[str], batch_size: int) -> list[BatchResult]:
    batches = chunk(track_ids, batch_size)
    jobs = [
        (endpoint, index, batch)
        for endpoint in ("audio-features", "track")
        for index, batch in enumerate(batches, start=1)
    ]

    results: list[BatchResult] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = [
            executor.submit(fetch_reccobeats_batch, endpoint, index, batch)
            for endpoint, index, batch in jobs
        ]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    return sorted(results, key=lambda result: (result.endpoint, result.batch_index))


def load_track_ids(args: argparse.Namespace) -> list[str]:
    track_ids: list[str] = []
    track_ids.extend(
        validate_spotify_id(track_id, "track ID") for track_id in args.track_id or []
    )

    if args.track_ids_file:
        track_ids_path = validate_track_ids_file_path(args.track_ids_file)
        with track_ids_path.open(encoding="utf-8") as file:
            track_ids.extend(
                validate_spotify_id(line.strip(), "track ID")
                for line in file
                if line.strip() and not line.strip().startswith("#")
            )

    if args.playlist_id:
        token = args.auth_token or os.environ.get("SPOTIBYE_AUTH_TOKEN")
        if not token:
            raise SystemExit(
                "--playlist-id requires --auth-token or SPOTIBYE_AUTH_TOKEN"
            )
        track_ids.extend(
            fetch_playlist_track_ids(args.backend_url, args.playlist_id, token)
        )

    deduped: list[str] = []
    seen: set[str] = set()
    for track_id in track_ids:
        if track_id not in seen:
            seen.add(track_id)
            deduped.append(track_id)
    return deduped


def summarize(
    results: list[BatchResult], track_ids: list[str], batch_size: int
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "requested_track_count": len(track_ids),
        "batch_size": batch_size,
        "concurrency": CONCURRENCY,
        "endpoints": {},
    }
    for endpoint in ("audio-features", "track"):
        endpoint_results = [result for result in results if result.endpoint == endpoint]
        returned = {
            track_id
            for result in endpoint_results
            for track_id in result.returned_ids
        }
        throw_batches = [result for result in endpoint_results if result.state == "throw"]
        empty_batches = [result for result in endpoint_results if result.state == "200 []"]
        data_batches = [
            result for result in endpoint_results if result.state == "200 [data]"
        ]
        summary["endpoints"][endpoint] = {
            "covered_tracks": len(returned),
            "coverage_percent": round((len(returned) / len(track_ids)) * 100, 2)
            if track_ids
            else 0,
            "throw_batches": len(throw_batches),
            "empty_200_batches": len(empty_batches),
            "data_200_batches": len(data_batches),
        }
    return summary


def print_report(
    results: list[BatchResult], track_ids: list[str], batch_size: int
) -> None:
    print(json.dumps(summarize(results, track_ids, batch_size), indent=2))
    print("\nBatch detail:")
    for result in results:
        print(
            f"- {result.endpoint} batch {result.batch_index}: "
            f"{result.state}; requested={len(result.requested_ids)}; "
            f"returned={len(result.returned_ids)}; status={result.status}"
        )
        if result.error:
            print(f"  error={result.error}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure ReccoBeats coverage for Spotify track IDs."
    )
    parser.add_argument("--playlist-id", help="Spotify playlist ID to fetch via backend")
    parser.add_argument(
        "--backend-url",
        default=os.environ.get("SPOTIBYE_BACKEND_URL", DEFAULT_BACKEND_URL),
        help="SpotiBye backend URL for playlist track lookup",
    )
    parser.add_argument(
        "--auth-token",
        default=os.environ.get("SPOTIBYE_AUTH_TOKEN"),
        help="SpotiBye backend JWT; can also use SPOTIBYE_AUTH_TOKEN",
    )
    parser.add_argument(
        "--track-id",
        action="append",
        help="Spotify track ID to test; repeatable",
    )
    parser.add_argument("--track-ids-file", help="Newline-delimited Spotify track IDs")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help="ReccoBeats IDs per request; default matches current Worker batch size",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    track_ids = load_track_ids(args)
    if not track_ids:
        print(
            "No track IDs supplied. Use --playlist-id, --track-id, or --track-ids-file.",
            file=sys.stderr,
        )
        return 2

    print(f"Testing {len(track_ids)} unique track IDs")
    results = run_coverage(track_ids, args.batch_size)
    print_report(results, track_ids, args.batch_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
