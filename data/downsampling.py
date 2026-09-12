"""Peak-preserving downsampling for hardware telemetry data.

Uses a min/max bucket strategy so that short-lived spikes (thermal,
power, clock drops, etc.) are never silently removed.
"""

from __future__ import annotations

import numpy as np


def min_max_downsample(
    x: np.ndarray,
    y: np.ndarray,
    max_points: int = 2000,
) -> tuple[np.ndarray, np.ndarray]:
    """Downsample *x*/*y* arrays using min/max buckets.

    For each bucket the minimum **and** maximum *y*-values are kept (in
    chronological order), guaranteeing that important extrema survive
    the reduction.

    Args:
        x: X-axis values (e.g. matplotlib date-numbers).
        y: Y-axis values (sensor readings).  May contain ``NaN``.
        max_points: Upper bound on returned points.

    Returns:
        ``(x_out, y_out)`` — views into *x*/*y* (no copy of source data
        is made; the returned arrays share memory with the originals).
    """
    n = len(x)
    if n <= max_points or n == 0:
        return x, y

    # --- handle all-NaN edge case ---
    if np.issubdtype(y.dtype, np.floating):
        valid_mask = ~np.isnan(y)
    else:
        valid_mask = np.ones(n, dtype=bool)

    if not valid_mask.any():
        step = max(1, n // max(max_points, 1))
        idx = np.arange(0, n, step)
        return x[idx], y[idx]

    # --- bucket decomposition ---
    n_buckets = max(1, max_points // 2)
    bucket_size = n / n_buckets

    indices: list[int] = [0]  # always keep first point

    for b in range(n_buckets):
        start = int(b * bucket_size)
        end = min(int((b + 1) * bucket_size), n)
        if start >= end:
            continue

        bucket_valid = valid_mask[start:end]
        if not bucket_valid.any():
            # Entire bucket is NaN — include midpoint for continuity
            indices.append(start + (end - start) // 2)
            continue

        # Indices within the bucket where values are valid
        local_valid = np.where(bucket_valid)[0]
        local_vals = y[start:end][bucket_valid]

        local_min = local_valid[np.argmin(local_vals)]
        local_max = local_valid[np.argmax(local_vals)]

        abs_min = start + local_min
        abs_max = start + local_max

        # Emit in chronological order
        if abs_min <= abs_max:
            indices.append(abs_min)
            if abs_min != abs_max:
                indices.append(abs_max)
        else:
            indices.append(abs_max)
            indices.append(abs_min)

    indices.append(n - 1)  # always keep last point

    # Deduplicate, sort, and return indexed views
    idx_arr = np.array(sorted(set(indices)))
    return x[idx_arr], y[idx_arr]
