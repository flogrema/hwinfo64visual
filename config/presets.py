"""Versioned preset persistence with %APPDATA% storage and legacy migration."""

from __future__ import annotations

import json
import logging
import os
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CURRENT_VERSION = 1
APP_NAME = "HWInfo64Visualizer"


# ---------------------------------------------------------------------------
# Application data directory
# ---------------------------------------------------------------------------

def get_app_data_dir() -> Path:
    """Return the platform-appropriate application data directory.

    * Windows  → ``%APPDATA%/HWInfo64Visualizer``
    * macOS    → ``~/Library/Application Support/HWInfo64Visualizer``
    * Linux    → ``$XDG_CONFIG_HOME/HWInfo64Visualizer`` or ``~/.config/…``
    """
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_NAME
    elif system == "Darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        if xdg:
            return Path(xdg) / APP_NAME
        return Path.home() / ".config" / APP_NAME

    # Ultimate fallback
    return Path.home() / f".{APP_NAME.lower()}"


# ---------------------------------------------------------------------------
# Preset model
# ---------------------------------------------------------------------------

@dataclass
class Preset:
    """A named sensor-selection preset."""

    columns: list[str] = field(default_factory=list)
    plot_mode: str = "auto"
    time_range: int = 100


# ---------------------------------------------------------------------------
# Preset manager
# ---------------------------------------------------------------------------

class PresetManager:
    """Read, write, migrate, and validate presets on disk.

    Storage location is determined by :func:`get_app_data_dir`.  On first
    launch the manager checks for a legacy ``presets.json`` in the working
    directory and migrates it automatically.
    """

    def __init__(self) -> None:
        self._dir = get_app_data_dir()
        self._file = self._dir / "presets.json"
        self._presets: dict[str, Preset] = {}
        self._load()

    # --- public API --------------------------------------------------------

    def list_presets(self) -> list[str]:
        """Return sorted list of preset names."""
        return sorted(self._presets.keys())

    def get_preset(self, name: str) -> Preset | None:
        """Return the preset with *name*, or ``None``."""
        return self._presets.get(name)

    def save_preset(
        self,
        name: str,
        columns: list[str],
        plot_mode: str = "auto",
        time_range: int = 100,
    ) -> bool:
        """Create or overwrite a preset.  Returns ``True`` on success."""
        self._presets[name] = Preset(
            columns=list(columns),
            plot_mode=plot_mode,
            time_range=time_range,
        )
        return self._save()

    def delete_preset(self, name: str) -> bool:
        """Delete a preset.  Returns ``True`` on success."""
        if name not in self._presets:
            return False
        del self._presets[name]
        return self._save()

    @property
    def storage_path(self) -> Path:
        """Path to the on-disk preset file."""
        return self._file

    # --- persistence -------------------------------------------------------

    def _ensure_dir(self) -> bool:
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            return True
        except OSError as exc:
            logger.error("Cannot create data directory %s: %s", self._dir, exc)
            return False

    def _load(self) -> None:
        """Load presets — try new location, then legacy, then start fresh."""
        if self._file.exists():
            self._load_from(self._file)
            return

        legacy = Path("presets.json")
        if legacy.exists() and legacy.is_file():
            logger.info("Migrating legacy presets from %s", legacy.resolve())
            self._load_from(legacy)
            self._save()
            return

        logger.info("No preset file found — starting with empty presets.")

    def _load_from(self, path: Path) -> None:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to read presets from %s: %s", path, exc)
            return

        if not isinstance(raw, dict):
            logger.warning("Preset file is not a JSON object — ignored.")
            return

        if "version" in raw and "presets" in raw:
            self._parse_versioned(raw)
        else:
            self._parse_legacy(raw)

    def _parse_versioned(self, raw: dict[str, Any]) -> None:
        version = raw.get("version", 0)
        if version > CURRENT_VERSION:
            logger.warning(
                "Preset file version %d is newer than supported (%d). "
                "Some fields may be lost.",
                version,
                CURRENT_VERSION,
            )

        presets_data = raw.get("presets", {})
        if not isinstance(presets_data, dict):
            return

        for name, data in presets_data.items():
            if not isinstance(data, dict):
                logger.warning("Skipping malformed preset '%s'.", name)
                continue
            cols = data.get("columns", [])
            if not isinstance(cols, list):
                continue
            self._presets[name] = Preset(
                columns=[c for c in cols if isinstance(c, str)],
                plot_mode=str(data.get("plot_mode", "auto")),
                time_range=int(data.get("time_range", 100)),
            )

    def _parse_legacy(self, raw: dict[str, Any]) -> None:
        """Migrate ``{"name": ["col1", "col2"]}`` format."""
        for name, columns in raw.items():
            if isinstance(columns, list):
                self._presets[name] = Preset(
                    columns=[c for c in columns if isinstance(c, str)],
                )

    def _save(self) -> bool:
        if not self._ensure_dir():
            return False

        data = {
            "version": CURRENT_VERSION,
            "presets": {
                name: {
                    "columns": p.columns,
                    "plot_mode": p.plot_mode,
                    "time_range": p.time_range,
                }
                for name, p in self._presets.items()
            },
        }

        try:
            with open(self._file, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
            return True
        except OSError as exc:
            logger.error("Failed to write presets to %s: %s", self._file, exc)
            return False
