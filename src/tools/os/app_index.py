"""
Dynamic index of installed desktop applications.

Uses PowerShell's built-in Get-StartApps cmdlet as the primary source
-- it enumerates everything the Start Menu knows about, both classic
Win32 apps and UWP/Store-packaged apps, each with the correct
launchable identifier already resolved:

  - Classic apps  -> a full .exe path (launch via CreateProcess).
  - UWP/Store apps -> "PackageFamilyName!AppID" (must be activated via
    shell:AppsFolder, NOT executed directly -- see OSTool._launch).

Registry "App Paths" is kept as a secondary source for classic CLI
tools that may not have a Start Menu tile.

The index is cached to disk and rebuilt only when stale. Scanning on
every request would add unnecessary latency and work against the
project's lightweight-first hardware constraint (Ryzen 5 / 16 GB RAM).
"""

from __future__ import annotations

import difflib
import json
import shutil
import subprocess
import time
import winreg
from pathlib import Path

CACHE_PATH = Path(__file__).resolve().parent / "app_index_cache.json"
CACHE_TTL_SECONDS = 24 * 60 * 60  # rebuild once a day

# Bump this whenever the index's data format or discovery source
# changes, so stale caches from an older version self-invalidate
# instead of silently serving broken identifiers.
INDEX_VERSION = 3


class AppIndex:
    """
    Builds, caches, and searches an index of installed applications.

    Each entry maps a normalized app name to (identifier, is_path):
      - is_path=True  -> identifier is a real, existing .exe path.
                          Launch it directly.
      - is_path=False -> identifier is an opaque AppUserModelID (either
                          a UWP "PackageFamilyName!AppID", or a classic
                          app's custom AUMID -- Electron/Squirrel apps
                          like Brave/Discord/Slack commonly register
                          one of these too). MUST be activated via
                          Explorer's shell:AppsFolder, never exec'd
                          directly -- see OSTool._launch_via_shell_apps_folder.

        Whether an identifier is a real path is determined ONCE, here,
        at index-build time, by checking actual file existence on disk.
        This is the only reliable signal -- string shape (e.g. "does it
        contain '!'") is NOT reliable, since classic-app AUMIDs often
        don't contain '!' either.
    """

    def __init__(self) -> None:
        self._index: dict[str, tuple[str, bool]] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(self, query: str) -> list[tuple[str, str, bool]]:
        """
        Return a ranked list of (display_name, identifier, is_path)
        matches for query.

        Resolution order:
          1. Exact name match      -> single confident result.
          2. Substring match       -> all matches (either direction).
          3. Fuzzy match (difflib) -> top matches above a similarity cutoff.
        """

        query = query.strip().lower()

        if not query:
            return []

        if query in self._index:
            identifier, is_path = self._index[query]
            return [(self._display(query), identifier, is_path)]

        substring_matches = [
            name for name in self._index
            if query in name or name in query
        ]

        if substring_matches:
            return [
                (self._display(name), *self._index[name])
                for name in substring_matches[:5]
            ]

        close = difflib.get_close_matches(
            query, self._index.keys(), n=5, cutoff=0.6
        )

        return [(self._display(name), *self._index[name]) for name in close]

    def refresh(self) -> None:
        """
        Force a rebuild of the index and persist it to disk.
        """

        self._index = self._build_index()
        self._save()

    # ------------------------------------------------------------------
    # Internal: cache lifecycle
    # ------------------------------------------------------------------

    def _load(self) -> None:

        if CACHE_PATH.exists():
            try:
                cached = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
                age = time.time() - cached.get("built_at", 0)
                same_version = cached.get("version") == INDEX_VERSION

                if age < CACHE_TTL_SECONDS and same_version:
                    raw_index = cached.get("index", {})
                    self._index = {
                        name: (entry[0], entry[1])
                        for name, entry in raw_index.items()
                    }
                    return

            except (json.JSONDecodeError, OSError, IndexError, TypeError):
                pass

        self.refresh()

    def _save(self) -> None:

        payload = {
            "version": INDEX_VERSION,
            "built_at": time.time(),
            "index": {
                name: [identifier, is_path]
                for name, (identifier, is_path) in self._index.items()
            },
        }

        try:
            CACHE_PATH.write_text(json.dumps(payload), encoding="utf-8")
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Internal: index construction
    # ------------------------------------------------------------------

    def _build_index(self) -> dict[str, tuple[str, bool]]:

        index: dict[str, tuple[str, bool]] = {}

        # Registry first (classic CLI tools without a Start Menu tile),
        # Get-StartApps second -- it's the authoritative source and
        # should win on any name collisions.
        index.update(self._scan_app_paths_registry())
        index.update(self._scan_start_apps())

        return index

    def _scan_start_apps(self) -> dict[str, tuple[str, bool]]:

        found: dict[str, tuple[str, bool]] = {}

        powershell = shutil.which("powershell")

        if powershell is None:
            return found

        try:
            result = subprocess.run(
                [
                    powershell,
                    "-NoProfile",
                    "-Command",
                    "Get-StartApps | ConvertTo-Json -Compress",
                ],
                capture_output=True,
                text=True,
                timeout=15,
                shell=False,
            )

            if result.returncode != 0 or not result.stdout.strip():
                return found

            parsed = json.loads(result.stdout)

        except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
            return found

        # Get-StartApps returns a single dict (not a list) when there's
        # only one result.
        entries = parsed if isinstance(parsed, list) else [parsed]

        for entry in entries:

            if not isinstance(entry, dict):
                continue

            name = entry.get("Name")
            app_id = entry.get("AppID")

            if not (name and app_id):
                continue

            # The ONLY reliable way to know whether AppID is a real
            # executable path or an opaque AppUserModelID: check
            # whether it actually exists as a file. Many classic apps
            # (Brave, Discord, Slack, ...) get a synthetic AUMID here
            # too, not just UWP/Store apps -- string shape (e.g.
            # presence of "!") is not a safe signal.
            is_path = Path(app_id).is_absolute() and Path(app_id).exists()

            found[name.strip().lower()] = (app_id, is_path)

        return found

    def _scan_app_paths_registry(self) -> dict[str, tuple[str, bool]]:

        found: dict[str, tuple[str, bool]] = {}

        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"

        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):

            try:
                root_key = winreg.OpenKey(hive, key_path)
            except OSError:
                continue

            with root_key:

                index = 0

                while True:

                    try:
                        subkey_name = winreg.EnumKey(root_key, index)
                    except OSError:
                        break

                    index += 1

                    try:
                        with winreg.OpenKey(root_key, subkey_name) as subkey:
                            path, _ = winreg.QueryValueEx(subkey, "")

                            if (
                                path
                                and Path(path).suffix.lower() == ".exe"
                                and Path(path).exists()
                            ):
                                name = Path(subkey_name).stem.lower()
                                found[name] = (path, True)

                    except OSError:
                        continue

        return found

    def _display(self, normalized_name: str) -> str:
        return normalized_name.title()