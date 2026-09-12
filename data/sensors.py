"""Sensor metadata parsing and categorization for HWiNFO64 CSV columns."""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Category constants
# ---------------------------------------------------------------------------

CATEGORY_CPU = "CPU"
CATEGORY_GPU = "GPU"
CATEGORY_MEMORY = "Memory"
CATEGORY_STORAGE = "Storage"
CATEGORY_MAINBOARD = "Mainboard"
CATEGORY_NETWORK = "Network"
CATEGORY_OTHER = "Other"

ALL_CATEGORIES: list[str] = [
    CATEGORY_CPU,
    CATEGORY_GPU,
    CATEGORY_MEMORY,
    CATEGORY_STORAGE,
    CATEGORY_MAINBOARD,
    CATEGORY_NETWORK,
    CATEGORY_OTHER,
]

# ---------------------------------------------------------------------------
# Measurement-type constants
# ---------------------------------------------------------------------------

MEAS_TEMPERATURE = "Temperature"
MEAS_CLOCK = "Clock"
MEAS_POWER = "Power"
MEAS_VOLTAGE = "Voltage"
MEAS_CURRENT = "Current"
MEAS_UTILIZATION = "Utilization"
MEAS_FAN = "Fan"
MEAS_MEMORY = "Memory"
MEAS_BANDWIDTH = "Bandwidth"
MEAS_FPS = "FPS"
MEAS_FRAMETIME = "Frametime"
MEAS_IO = "I/O"
MEAS_OTHER = "Other"

# ---------------------------------------------------------------------------
# Regex for unit extraction: matches "[unit]" at end, optional ".N" suffix
# ---------------------------------------------------------------------------

_UNIT_RE = re.compile(r"\[([^\]]*)\]\s*(?:\.\d+)?$")

# ---------------------------------------------------------------------------
# Category keyword rules — checked in order; first match wins.
# GPU before CPU so "GPU Core" → GPU, plain "Core 0" → CPU.
# ---------------------------------------------------------------------------

_GPU_KW: list[str] = [
    "gpu",
    "geforce",
    "radeon",
    "nvvdd",
    "vddcr_gfx",
    "bildrate",
    "framerate",
    "frame time",
    "frame rate",
    "gpu busy",
    "gpu wait",
    "cpu busy",
    "cpu wait",       # HWiNFO groups these under GPU / FrameView
    "d3d",
    "video decode",
    "video encode",
    "pcie-link",
    "pcie lane",
    "pci express",
    "drosselungsgrund",
    "throttle reason",
    "leistungsgrenzwert",
    "leistungsbegrenzer",
    "gesamte gpu",
    "total gpu",
    "bildrate presented",
    "bildrate displayed",
    "frame time presented",
]

_CPU_KW: list[str] = [
    "cpu",
    "core",
    "kern",
    "ccd",
    "iod",
    "package",
    "fclk",
    "uclk",
    "l3 ",
    "l3-",
    "l3 cache",
    "tdp",
    "tdc",
    "edc",
    "ppt",
    "prochot",
    "htc",
    "infinity fabric",
    "bustakt",
    "bus clock",
    "aktive kerne",
    "active cores",
    "vcore",
]

_MEMORY_KW: list[str] = [
    "speicher",       # German for "memory" — catches all memory-related columns
    "memory",
    "dram",
    "auslagerung",
    "page file",
    "spd hub",
    "pmic",
    "vdd (sw",
    "vddq (sw",
    "vpp (sw",
    "vout",
    "vin spannung",
    "vin voltage",
    "tcas",
    "trcd",
    "trp",
    "tras",
    "trc ",
    "trfc",
    "command rate",
]

_STORAGE_KW: list[str] = [
    "laufwerk",
    "festplatte",
    "drive",
    "disk",
    "nvme",
    "ssd",
    "hdd",
    "host-schreib",
    "host-lese",
    "host write",
    "host read",
    "lebensdauer",
    "lifetime",
    "remaining life",
    "reserveplatz",
    "reserve space",
    "leseaktivit",
    "schreibaktivit",
    "read activity",
    "write activity",
    "leserate",
    "schreibrate",
    "read rate",
    "write rate",
    "summe gelesen",
    "summe geschrieben",
    "total read",
    "total written",
    "festplattenfehler",
    "festplattenwarnung",
    "disk error",
    "disk warning",
]

_NETWORK_KW: list[str] = [
    "download",
    "upload",
    "netzwerk",
    "network",
]

_MAINBOARD_KW: list[str] = [
    "mos",
    "chipsatz",
    "chipset",
    "+12v",
    "+5v",
    "+3,3v",
    "+3.3v",
    "3vsb",
    "avsb",
    "vbat",
    "vtt",
    "vref",
    "pump",
    "t15",
]

_CATEGORY_RULES: list[tuple[str, list[str]]] = [
    (CATEGORY_GPU, _GPU_KW),
    (CATEGORY_CPU, _CPU_KW),
    (CATEGORY_MEMORY, _MEMORY_KW),
    (CATEGORY_STORAGE, _STORAGE_KW),
    (CATEGORY_NETWORK, _NETWORK_KW),
    (CATEGORY_MAINBOARD, _MAINBOARD_KW),
]

# ---------------------------------------------------------------------------
# Unit → measurement-type mapping
# ---------------------------------------------------------------------------

_UNIT_TO_MEASUREMENT: dict[str, str] = {
    "°C": MEAS_TEMPERATURE,
    "°c": MEAS_TEMPERATURE,
    "MHz": MEAS_CLOCK,
    "W": MEAS_POWER,
    "V": MEAS_VOLTAGE,
    "A": MEAS_CURRENT,
    "%": MEAS_UTILIZATION,
    "RPM": MEAS_FAN,
    "MB": MEAS_MEMORY,
    "GB": MEAS_MEMORY,
    "MB/s": MEAS_BANDWIDTH,
    "GB/s": MEAS_BANDWIDTH,
    "KB/s": MEAS_BANDWIDTH,
    "GT/s": MEAS_BANDWIDTH,
    "FPS": MEAS_FPS,
    "ms": MEAS_FRAMETIME,
    "% von TDP": MEAS_POWER,
    "% of TDP": MEAS_POWER,
    "Yes/No": MEAS_OTHER,
    "Ja/Nein": MEAS_OTHER,
}


# ---------------------------------------------------------------------------
# Sensor dataclass
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Sensor:
    """Represents a single sensor column from an HWiNFO64 CSV log."""

    column: str                 # Original column header (used for DataFrame access)
    name: str                   # Cleaned display name
    unit: str | None            # Extracted unit string, e.g. "°C", "MHz"
    category: str               # One of ALL_CATEGORIES
    measurement: str            # One of MEAS_* constants
    device: str | None = None   # Reserved for future device identification


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def extract_unit(column_name: str) -> str | None:
    """Extract the unit from a HWiNFO64 column header.

    Examples::

        "CPU Temperature [°C]"      → "°C"
        "+12V [V]"                   → "V"
        "Core 0 VID [V].1"          → "V"
        "Gesamtfehler []"           → ""
        "Some Column"               → None
    """
    match = _UNIT_RE.search(column_name)
    return match.group(1) if match else None


def parse_sensor(column_name: str) -> Sensor:
    """Parse a single HWiNFO64 column name into a *Sensor* object."""
    unit = extract_unit(column_name)
    name = _clean_name(column_name)
    category = _classify_category(column_name)
    measurement = _classify_measurement(column_name, unit)

    return Sensor(
        column=column_name,
        name=name,
        unit=unit,
        category=category,
        measurement=measurement,
    )


def parse_sensors(columns: list[str]) -> list[Sensor]:
    """Parse a list of HWiNFO64 column names into *Sensor* objects.

    Args:
        columns: Column headers *excluding* Date/Time/Timestamp.

    Returns:
        Ordered list of ``Sensor`` objects with metadata populated.
    """
    return [parse_sensor(col) for col in columns]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clean_name(column_name: str) -> str:
    """Build a human-readable display name from a raw column header."""
    # Strip trailing duplicate marker (.1, .2, …)
    name = re.sub(r"\.\d+$", "", column_name)
    # Strip unit suffix
    name = _UNIT_RE.sub("", name).strip()
    return name


def _classify_category(column_name: str) -> str:
    """Classify a column into a hardware category by keyword matching."""
    lower = column_name.lower()

    for category, keywords in _CATEGORY_RULES:
        for kw in keywords:
            if kw in lower:
                return category

    # Fallback heuristics for remaining board-level sensors
    unit = extract_unit(column_name)
    if unit == "RPM":
        return CATEGORY_MAINBOARD
    if unit == "V" and not any(k in lower for k in ("gpu", "cpu", "core")):
        return CATEGORY_MAINBOARD

    return CATEGORY_OTHER


def _classify_measurement(column_name: str, unit: str | None) -> str:
    """Classify measurement type from the unit and column context."""
    if unit is None or unit == "":
        return MEAS_OTHER

    meas = _UNIT_TO_MEASUREMENT.get(unit)
    if meas is None:
        return MEAS_OTHER

    # Context-based refinement
    lower = column_name.lower()
    if meas == MEAS_MEMORY:
        # Check I/O (totals) BEFORE bandwidth (rates) — "insgesamt" must win
        # over "schreib" when both appear in the same column name.
        if any(k in lower for k in ("summe", "total", "insgesamt", "host")):
            return MEAS_IO
        if any(k in lower for k in ("rate", "lese", "schreib", "read", "write",
                                     "bandwidth", "bandbreite")):
            return MEAS_BANDWIDTH
    if meas == MEAS_UTILIZATION:
        if any(k in lower for k in ("tdp", "grenzwert", "limit")):
            return MEAS_POWER

    return meas
