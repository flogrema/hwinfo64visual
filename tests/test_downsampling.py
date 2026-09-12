"""Tests for data.downsampling — spike preservation and edge cases."""

import numpy as np
import pytest
from data.downsampling import min_max_downsample


class TestMinMaxDownsample:
    """Core downsampling behaviour."""

    def test_small_input_unchanged(self) -> None:
        """Input smaller than max_points is returned as-is."""
        x = np.arange(10, dtype=float)
        y = np.arange(10, dtype=float)
        xo, yo = min_max_downsample(x, y, max_points=20)
        np.testing.assert_array_equal(xo, x)
        np.testing.assert_array_equal(yo, y)

    def test_preserves_high_spike(self) -> None:
        """A single high spike must survive downsampling."""
        n = 10_000
        y = np.full(n, 85.0)
        y[4321] = 154.0  # short CPU-temp spike
        x = np.arange(n, dtype=float)

        xo, yo = min_max_downsample(x, y, max_points=200)

        assert 154.0 in yo, "High spike was removed by downsampling"
        assert len(yo) <= 210  # allow small overhead from first/last

    def test_preserves_low_spike(self) -> None:
        """A single low spike (e.g. clock drop) must survive."""
        n = 10_000
        y = np.full(n, 4800.0)
        y[7777] = 800.0  # clock drop
        x = np.arange(n, dtype=float)

        xo, yo = min_max_downsample(x, y, max_points=200)

        assert 800.0 in yo, "Low spike was removed by downsampling"

    def test_preserves_both_extrema(self) -> None:
        """Both a high and low spike in the same dataset."""
        n = 10_000
        y = np.full(n, 50.0)
        y[1111] = 99.0   # high
        y[8888] = 5.0    # low
        x = np.arange(n, dtype=float)

        xo, yo = min_max_downsample(x, y, max_points=200)

        assert 99.0 in yo, "High spike lost"
        assert 5.0 in yo, "Low spike lost"

    def test_output_ordered(self) -> None:
        """Output indices must be in ascending (chronological) order."""
        rng = np.random.default_rng(42)
        x = np.arange(5000, dtype=float)
        y = rng.standard_normal(5000)

        xo, yo = min_max_downsample(x, y, max_points=200)

        assert np.all(np.diff(xo) >= 0), "Output x is not sorted"

    def test_respects_max_points(self) -> None:
        """Output length must not grossly exceed max_points."""
        x = np.arange(50_000, dtype=float)
        y = np.random.default_rng(0).standard_normal(50_000)

        xo, yo = min_max_downsample(x, y, max_points=500)
        # Allow modest overhead (first + last + dedup)
        assert len(yo) <= 520


class TestEdgeCases:
    """Edge-case inputs."""

    def test_empty(self) -> None:
        x = np.array([], dtype=float)
        y = np.array([], dtype=float)
        xo, yo = min_max_downsample(x, y)
        assert len(xo) == 0

    def test_single_point(self) -> None:
        x = np.array([1.0])
        y = np.array([42.0])
        xo, yo = min_max_downsample(x, y, max_points=100)
        np.testing.assert_array_equal(yo, [42.0])

    def test_two_points(self) -> None:
        x = np.array([0.0, 1.0])
        y = np.array([10.0, 20.0])
        xo, yo = min_max_downsample(x, y, max_points=100)
        np.testing.assert_array_equal(yo, [10.0, 20.0])

    def test_all_nan(self) -> None:
        """All-NaN input must not crash."""
        x = np.arange(100, dtype=float)
        y = np.full(100, np.nan)
        xo, yo = min_max_downsample(x, y, max_points=20)
        assert len(xo) > 0

    def test_some_nan(self) -> None:
        """NaN values interspersed — extrema of valid data preserved."""
        n = 5000
        y = np.full(n, 50.0)
        y[::3] = np.nan
        y[2500] = 100.0
        x = np.arange(n, dtype=float)

        xo, yo = min_max_downsample(x, y, max_points=200)
        assert 100.0 in yo

    def test_max_points_equals_input(self) -> None:
        """max_points == len(input) → no reduction."""
        x = np.arange(500, dtype=float)
        y = np.arange(500, dtype=float)
        xo, yo = min_max_downsample(x, y, max_points=500)
        np.testing.assert_array_equal(xo, x)
