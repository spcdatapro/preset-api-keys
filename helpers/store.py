"""Where the per-preset API keys live: usr/preset_api_keys/keys.json.

Outside the plugin folder, folder 0700 and file 0600, written atomically. Entries are indexed by
the preset name in casefold (preset names are unique case-insensitively in Agent Zero):

    {"version": 1, "keys": {"<casefold name>": {"preset", "provider", "key", "updated_at"}}}

The file is plain text on the volume. Nothing in this module logs or raises a key value.
"""

from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from datetime import datetime, timezone

from helpers import files

from usr.plugins.preset_api_keys.helpers.errors import KeyStoreError

STORE_DIR_PARTS = ("usr", "preset_api_keys")
STORE_FILE = "keys.json"
VERSION = 1
MAX_KEY_LENGTH = 500

LOCK = threading.RLock()
_cache: tuple[tuple, dict] | None = None


def norm(name: object) -> str:
    return str(name or "").strip().casefold()


def store_dir() -> str:
    return files.get_abs_path(*STORE_DIR_PARTS)


def store_path() -> str:
    return os.path.join(store_dir(), STORE_FILE)


def _signature() -> tuple:
    path = store_path()
    try:
        stat = os.stat(path)
    except OSError:
        return (path, None, None)
    return (path, stat.st_mtime_ns, stat.st_size)


def _valid_entry(entry: object) -> bool:
    return isinstance(entry, dict) and all(
        isinstance(entry.get(field), str) and entry.get(field) for field in ("preset", "provider", "key")
    )


def _read() -> dict[str, dict]:
    try:
        with open(store_path(), encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        raise KeyStoreError("The key store could not be read") from None
    keys = data.get("keys") if isinstance(data, dict) else None
    if not isinstance(keys, dict) or not all(_valid_entry(entry) for entry in keys.values()):
        raise KeyStoreError("The key store is corrupted")
    return {norm(entry["preset"]): entry for entry in keys.values()}


def _entries() -> dict[str, dict]:
    """Cached by file signature: the model hook calls this on every model build."""
    global _cache
    with LOCK:
        signature = _signature()
        if _cache is None or _cache[0] != signature:
            _cache = (signature, _read())
        return _cache[1]


def _write(entries: dict[str, dict]) -> None:
    global _cache
    folder = store_dir()
    os.makedirs(folder, exist_ok=True)
    try:
        os.chmod(folder, 0o700)
    except OSError:
        pass  # some bind mounts ignore chmod
    path = store_path()
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump({"version": VERSION, "keys": entries}, handle, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    _cache = None


def has_keys() -> bool:
    return bool(_entries())


def entries() -> dict[str, dict]:
    """All entries by casefold preset name. Holds key values: never send this to the browser."""
    return deepcopy(_entries())


def get(preset: object) -> dict | None:
    entry = _entries().get(norm(preset))
    return dict(entry) if entry else None


def put(preset: str, provider: str, key: str) -> None:
    with LOCK:
        current = dict(_entries())  # raises if the file is unreadable: never overwrite it blindly
        current[norm(preset)] = {
            "preset": preset,
            "provider": provider,
            "key": key,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        _write(current)


def remove(preset: object) -> bool:
    with LOCK:
        current = dict(_entries())
        if current.pop(norm(preset), None) is None:
            return False
        _write(current)
        return True


def move(source: object, target: str) -> None:
    """Hand the entry of `source` to `target` unchanged (same key, provider and date)."""
    with LOCK:
        current = dict(_entries())
        if norm(source) not in current:
            raise KeyStoreError("No key is stored under that name")
        if norm(target) in current:
            raise KeyStoreError("The target preset already has a key")
        current[norm(target)] = {**current.pop(norm(source)), "preset": target}
        _write(current)


def delete_store() -> None:
    """Remove the key file (and a leftover temp file). Used on uninstall."""
    global _cache
    with LOCK:
        for path in (store_path(), store_path() + ".tmp"):
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
        _cache = None
