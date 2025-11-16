# iCloud Drive & Photos Downloader

This script signs in to iCloud (with 2FA), downloads iCloud Drive files and iCloud Photos/Videos to a folder (e.g., a USB drive), and can list albums/photos. It uses the unofficial `pyicloud` library, so it works on Linux and macOS without the Apple iCloud client.

## What you need
1) Your Apple ID email and password. You’ll be asked for a 2FA code on first use.
2) Python 3.8+ installed.
3) Space on your destination drive (USB or local folder).
4) An internet connection.

## One-time setup
1) Open a terminal and go to your home directory:
   ```bash
   cd ~
   ```
2) Clone this repo and enter the folder:
   ```bash
   git clone https://github.com/rguliyev/icloud-downloader.git
   cd icloud-downloader
   ```
3) Create/activate the virtual environment and install deps:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install pyicloud requests
   ```

## Common examples
Below commands assume the venv is active (`source .venv/bin/activate`).

### 1) Download everything (Drive + Photos) to a USB
```bash
./icloud-downloader.py --apple-id you@example.com \
  --dest /media/$USER/USB/icloud \
  --photos-all \
  --resume --progress
```
- `--resume` continues partial files instead of restarting.
- `--progress` shows per-file progress updates.

### 2) Download a specific iCloud Drive folder/file
```bash
./icloud-downloader.py --apple-id you@example.com \
  --dest /media/$USER/USB/icloud \
  --item "Documents/report.pdf" \
  --item "Projects/2024/"
```

### 3) Download a specific Photos album (e.g., “Cars”)
```bash
./icloud-downloader.py --apple-id you@example.com \
  --dest /media/$USER/USB/icloud \
  --photos-album "Cars" \
  --resume --progress
```

### 4) List albums or photos (no download, no dest needed)
- List album names:
  ```bash
  ./icloud-downloader.py --apple-id you@example.com --photos-list-albums
  ```
- List filenames in an album:
  ```bash
  ./icloud-downloader.py --apple-id you@example.com --photos-list-album "Cars"
  ```
- List all photo/video filenames:
  ```bash
  ./icloud-downloader.py --apple-id you@example.com --photos-list
  ```

## Tips
- If you see UUID-like album names, they’re real album IDs. You can pass either the friendly title or the ID to `--photos-album` / `--photos-list-album`.
- If the download was interrupted, rerun with `--resume` to continue. Files that already match size are skipped.
- Destination (`--dest`) is required for any download. Listing-only commands don’t need it.
- Warnings about LibreSSL vs OpenSSL come from `urllib3`; downloads still work.

## Security note
The script caches session cookies in `~/.pyicloud` to reduce repeated 2FA prompts. **If you’re on a shared machine, clear that folder when done.**
