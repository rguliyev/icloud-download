#!/usr/bin/env python3
"""Download all iCloud Drive files to a destination path (e.g., a USB mount).

Requires `pyicloud` (and its deps). Supports 2FA. Skips files whose size already
matches in the destination. Partial downloads should be removed before rerunning.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudFailedLoginException


def _write_stream(resp, dest_path: Path, mode: str, expected_size: Optional[int], start_size: int, show_progress: bool, label: str) -> None:
    """Write streamed response to disk with optional progress reporting."""
    bytes_written = start_size
    report_step = None
    next_report = None
    if show_progress and expected_size:
        report_step = max(expected_size // 20, 1_000_000)  # at most ~20 updates, min 1MB
        next_report = start_size + report_step

    with open(dest_path, mode) as out:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            out.write(chunk)
            bytes_written += len(chunk)
            if report_step and bytes_written >= next_report:
                pct = (bytes_written / expected_size) * 100
                print(f"  {label}: {bytes_written}/{expected_size} bytes ({pct:.1f}%)")
                next_report += report_step


def download_node(node, dest_path: Path, resume: bool = False, show_progress: bool = False) -> None:
    """Recursively download a node from iCloud Drive to dest_path."""
    if node.type == "FOLDER":
        dest_path.mkdir(parents=True, exist_ok=True)
        for child in node:
            download_node(child, dest_path / child.name, resume=resume, show_progress=show_progress)
        return

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    existing_size = dest_path.stat().st_size if dest_path.exists() else 0
    total_size = getattr(node, "size", None)
    if dest_path.exists() and total_size is not None and existing_size == total_size:
        print(f"[skip] {dest_path} (size matches)")
        return

    headers = {}
    mode = "wb"
    if resume and dest_path.exists() and total_size and existing_size < total_size:
        headers["Range"] = f"bytes={existing_size}-"
        mode = "ab"
        print(f"[resume] {dest_path} ({existing_size}/{total_size} bytes)")
    else:
        print(f"[get ] {dest_path} ({total_size} bytes)")

    with node.open(stream=True, headers=headers) as resp:
        label = dest_path.name
        _write_stream(resp, dest_path, mode, total_size, existing_size, show_progress, label)


def download_photo_asset(asset, dest_dir: Path, resume: bool = False, show_progress: bool = False) -> None:
    """Download a photo/video asset if not already present with matching size."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = getattr(asset, "filename", None) or f"{asset.id}.bin"
    dest_path = dest_dir / name

    versions = getattr(asset, "versions", {}) or {}
    original = versions.get("original", {})
    expected_size = original.get("size") or original.get("fileSize")
    existing_size = dest_path.stat().st_size if dest_path.exists() else 0

    if dest_path.exists() and expected_size and existing_size == expected_size:
        print(f"[skip] {dest_path} (size matches)")
        return

    headers = {}
    mode = "wb"
    if resume and dest_path.exists() and expected_size and existing_size < expected_size:
        headers["Range"] = f"bytes={existing_size}-"
        mode = "ab"
        print(f"[resume] {dest_path} ({existing_size}/{expected_size} bytes)")
    else:
        print(f"[get ] {dest_path}")

    resp = asset.download(headers=headers)
    label = dest_path.name
    _write_stream(resp, dest_path, mode, expected_size, existing_size, show_progress, label)


def asset_label(asset) -> str:
    name = getattr(asset, "filename", None) or ""
    return name if name else f"{asset.id}"


def format_album_name(key: str, album) -> str:
    """Return a human-friendly album name, including ID if the key is not the title."""
    title = getattr(album, "fullname", getattr(album, "name", key))
    if key != title:
        return f"{title} (id: {key})"
    return title


def login(apple_id: str, password: Optional[str], cookie_dir: Path) -> PyiCloudService:
    if not password:
        import getpass

        password = getpass.getpass("Apple ID password: ")

    try:
        api = PyiCloudService(apple_id, password, cookie_directory=str(cookie_dir))
    except PyiCloudFailedLoginException as exc:
        print(f"Login failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if api.requires_2fa:
        print("Two-factor authentication required.")
        code = input("Enter the 2FA code sent to your device: ")
        if not api.validate_2fa_code(code):
            print("Invalid 2FA code.", file=sys.stderr)
            sys.exit(1)
        if not api.is_trusted_session:
            print("Session not trusted; attempting to trust this session...")
            if not api.trust_session():
                print(
                    "Failed to trust session; you may be prompted for 2FA again next run.",
                    file=sys.stderr,
                )
    return api


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download all iCloud Drive files to a destination folder (e.g., USB)."
    )
    parser.add_argument("--apple-id", required=True, help="Apple ID email")
    parser.add_argument(
        "--password",
        help="Password (omit to prompt or set ICLOUD_PWD env var)",
    )
    parser.add_argument(
        "--dest",
        required=False,
        help="Destination path (required for any download operations)",
    )
    parser.add_argument(
        "--item",
        action="append",
        default=[],
        help=(
            "Specific file/folder path relative to iCloud Drive root to download "
            "(e.g., 'Documents/report.pdf' or 'Photos/Trip'). Repeat for multiple."
        ),
    )
    parser.add_argument(
        "--cookie-dir",
        default=str(Path.home() / ".pyicloud"),
        help="Directory to cache session cookies",
    )
    parser.add_argument(
        "--photos-all",
        action="store_true",
        help="Download all iCloud Photos (photos and videos) to DEST/Photos",
    )
    parser.add_argument(
        "--photos-album",
        action="append",
        default=[],
        help="Specific album name to download to DEST/Photos/<Album>. Repeatable.",
    )
    parser.add_argument(
        "--photos-list",
        action="store_true",
        help="List all iCloud Photos filenames (no download).",
    )
    parser.add_argument(
        "--photos-list-album",
        action="append",
        default=[],
        help="List filenames in a specific album (repeatable).",
    )
    parser.add_argument(
        "--photos-list-albums",
        action="store_true",
        help="List all album names in iCloud Photos.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume partial downloads using HTTP Range (append to existing files).",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Show per-file download progress (periodic byte/percentage updates).",
    )
    args = parser.parse_args()

    password = args.password or os.environ.get("ICLOUD_PWD")
    dest_root = Path(args.dest).expanduser() if args.dest else None
    cookie_dir = Path(args.cookie_dir).expanduser()

    requires_dest = bool(
        args.item or args.photos_all or args.photos_album or not args.photos_list_albums and not args.photos_list and not args.photos_list_album
    )

    if requires_dest and not dest_root:
        print("Error: --dest is required for download operations.", file=sys.stderr)
        sys.exit(1)

    cookie_dir.mkdir(parents=True, exist_ok=True)
    if dest_root:
        dest_root.mkdir(parents=True, exist_ok=True)

    api = login(args.apple_id, password, cookie_dir)

    has_drive_download = args.item or (
        dest_root
        and not (
            args.photos_all
            or args.photos_album
            or args.photos_list
            or args.photos_list_album
            or args.photos_list_albums
        )
    )
    if has_drive_download:
        targets = args.item
        if targets:
            print("Downloading specified items…")
            for target in targets:
                try:
                    node = api.drive[target]
                except KeyError:
                    print(f"Not found in iCloud Drive: {target}", file=sys.stderr)
                    continue
                download_node(node, dest_root / target, resume=args.resume, show_progress=args.progress)
        else:
            print("Listing iCloud Drive root…")
            for item in api.drive:
                download_node(item, dest_root / item.name, resume=args.resume, show_progress=args.progress)

    if args.photos_list or args.photos_list_album or args.photos_list_albums:
        if args.photos_list:
            print("Listing all iCloud Photos:")
            for asset in api.photos.all:
                print(asset_label(asset))
        if args.photos_list_album:
            albums = api.photos.albums
            for album_name in args.photos_list_album:
                try:
                    album = albums[album_name]
                except KeyError:
                    print(f"Album not found: {album_name}", file=sys.stderr)
                    continue
                print(f"Listing album: {album_name}")
                for asset in album:
                    print(asset_label(asset))
        if args.photos_list_albums:
            print("Listing all iCloud Photos albums:")
            for key, album in api.photos.albums._albums.items():
                print(format_album_name(key, album))

    if args.photos_all or args.photos_album:
        photos_root = dest_root / "Photos"
        if args.photos_all:
            print("Downloading all iCloud Photos (this may take a while)…")
            for asset in api.photos.all:
                download_photo_asset(asset, photos_root, resume=args.resume, show_progress=args.progress)
        if args.photos_album:
            albums = api.photos.albums
            for album_name in args.photos_album:
                try:
                    album = albums[album_name]
                except KeyError:
                    print(f"Album not found: {album_name}", file=sys.stderr)
                    continue
                album_dir = photos_root / album_name
                print(f"Downloading album: {album_name}")
                for asset in album:
                    download_photo_asset(asset, album_dir, resume=args.resume, show_progress=args.progress)

    print("Done.")


if __name__ == "__main__":
    main()
