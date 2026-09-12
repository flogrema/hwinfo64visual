"""HWiNFO64 CSV loading and data normalisation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from data.sensors import Sensor, parse_sensors

logger = logging.getLogger(__name__)


@dataclass
class LoadResult:
    """Container for a successfully loaded HWiNFO64 log."""

    df: pd.DataFrame
    sensors: list[Sensor]
    file_path: str
    row_count: int = 0
    sensor_count: int = 0
    skipped_columns: list[str] = field(default_factory=list)


def load_hwinfo_csv(file_path: str) -> LoadResult:
    """Load and normalise a HWiNFO64 CSV log file.

    The function:

    1. Reads the CSV with ``latin1`` encoding.
    2. Merges the first two columns (Date + Time) into a ``Timestamp``.
    3. Converts every remaining column to numeric (``NaN`` for failures).
    4. Drops columns that are entirely non-numeric.
    5. Builds :class:`Sensor` metadata for surviving columns.

    Raises:
        FileNotFoundError: File does not exist.
        ValueError: CSV structure is invalid (too few columns / no valid
            timestamps).
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    logger.info("Loading CSV: %s", file_path)
    df_raw = pd.read_csv(
        file_path,
        header=0,
        encoding="latin1",
        on_bad_lines="skip",
        low_memory=False,
    )

    if len(df_raw.columns) < 2:
        raise ValueError(
            f"CSV must have at least Date and Time columns.  "
            f"Found {len(df_raw.columns)} column(s)."
        )

    # --- Timestamp from first two columns ----------------------------------
    date_col, time_col = df_raw.columns[0], df_raw.columns[1]
    logger.info("Parsing timestamps from '%s' + '%s'…", date_col, time_col)

    timestamps = pd.to_datetime(
        df_raw[date_col].astype(str) + " " + df_raw[time_col].astype(str),
        errors="coerce",
        dayfirst=True,
    )

    valid = timestamps.notna()
    n_valid = int(valid.sum())
    if n_valid == 0:
        raise ValueError("No valid timestamps found.  Check CSV Date/Time format.")

    dropped = len(df_raw) - n_valid
    if dropped:
        logger.warning("Dropped %d rows with invalid timestamps.", dropped)

    # --- Build clean DataFrame ---------------------------------------------
    data_cols = list(df_raw.columns[2:])

    # Convert all data columns to numeric in batch, then filter
    skipped: list[str] = []
    numeric_parts: dict[str, pd.Series] = {}
    for col in data_cols:
        series = df_raw.loc[valid, col].reset_index(drop=True)
        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.notna().any():
            numeric_parts[col] = numeric
        else:
            skipped.append(col)
            logger.debug("Skipping non-numeric column: %s", col)

    # Assemble in one shot to avoid DataFrame fragmentation
    ts_df = pd.DataFrame({"Timestamp": timestamps[valid].reset_index(drop=True)})
    if numeric_parts:
        data_df = pd.DataFrame(numeric_parts)
        df = pd.concat([ts_df, data_df], axis=1)
    else:
        df = ts_df

    # --- Sensor metadata ---------------------------------------------------
    sensor_cols = [c for c in df.columns if c != "Timestamp"]
    sensors = parse_sensors(sensor_cols)

    logger.info(
        "Loaded %d rows, %d sensors (%d non-numeric columns skipped).",
        len(df),
        len(sensors),
        len(skipped),
    )

    return LoadResult(
        df=df,
        sensors=sensors,
        file_path=file_path,
        row_count=len(df),
        sensor_count=len(sensors),
        skipped_columns=skipped,
    )
