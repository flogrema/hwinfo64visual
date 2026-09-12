"""Tests for data.sensors — unit extraction, categorisation, measurement types."""

import pytest
from data.sensors import (
    CATEGORY_CPU,
    CATEGORY_GPU,
    CATEGORY_MAINBOARD,
    CATEGORY_MEMORY,
    CATEGORY_NETWORK,
    CATEGORY_OTHER,
    CATEGORY_STORAGE,
    MEAS_BANDWIDTH,
    MEAS_CLOCK,
    MEAS_CURRENT,
    MEAS_FAN,
    MEAS_FPS,
    MEAS_FRAMETIME,
    MEAS_IO,
    MEAS_OTHER,
    MEAS_POWER,
    MEAS_TEMPERATURE,
    MEAS_UTILIZATION,
    MEAS_VOLTAGE,
    Sensor,
    extract_unit,
    parse_sensor,
    parse_sensors,
)


# ---------------------------------------------------------------------------
# Unit extraction
# ---------------------------------------------------------------------------

class TestExtractUnit:
    @pytest.mark.parametrize("col, expected", [
        ("CPU Temperature [°C]", "°C"),
        ("+12V [V]", "V"),
        ("Core 0 Takt (perf #1/1) [MHz]", "MHz"),
        ("Core 0 VID [V].1", "V"),
        ("Gesamtfehler []", ""),
        ("Gesamte GPU-Leistung [% von TDP] [%]", "%"),
        ("Some Column Without Unit", None),
        ("", None),
    ])
    def test_extraction(self, col: str, expected: str | None) -> None:
        assert extract_unit(col) == expected


# ---------------------------------------------------------------------------
# Category classification
# ---------------------------------------------------------------------------

class TestCategory:
    @pytest.mark.parametrize("col, expected", [
        ("CPU (Tctl/Tdie) [°C]", CATEGORY_CPU),
        ("Core 0 VID [V]", CATEGORY_CPU),
        ("Core 0 Takt (perf #1/1) [MHz]", CATEGORY_CPU),
        ("Kern-Takte (avg) [MHz]", CATEGORY_CPU),
        ("CPU PPT [W]", CATEGORY_CPU),
        ("Vcore [V]", CATEGORY_CPU),
        # GPU
        ("GPU-Temperatur [°C]", CATEGORY_GPU),
        ("GPU-Takt [MHz]", CATEGORY_GPU),
        ("GPU Leistung [W]", CATEGORY_GPU),
        ("GPU D3D-Auslastung [%]", CATEGORY_GPU),
        ("Bildrate Presented (avg) [FPS]", CATEGORY_GPU),
        ("GPU Core (NVVDD) Eingangsleistung (sum) [W]", CATEGORY_GPU),
        # Memory
        ("Virtueller Speicher zugewiesen [MB]", CATEGORY_MEMORY),
        ("Physikalischer Speicher verwendet [MB]", CATEGORY_MEMORY),
        ("Speichertakt [MHz]", CATEGORY_MEMORY),
        ("SPD Hub Temperatur [°C]", CATEGORY_MEMORY),
        ("DRAM-Lesebandbreite [GB/s]", CATEGORY_MEMORY),
        # Storage
        ("Laufwerkstemperatur [°C]", CATEGORY_STORAGE),
        ("Host-Schreibvorgänge insgesamt [GB]", CATEGORY_STORAGE),
        ("Verbleibende Lebensdauer der Festplatte [%]", CATEGORY_STORAGE),
        ("Leserate [MB/s]", CATEGORY_STORAGE),
        # Network
        ("Summe Download [MB]", CATEGORY_NETWORK),
        ("Aktuelle Upload-Rate [KB/s]", CATEGORY_NETWORK),
        # Mainboard
        ("+12V [V]", CATEGORY_MAINBOARD),
        ("+5V [V]", CATEGORY_MAINBOARD),
        ("MOS [°C]", CATEGORY_MAINBOARD),
        ("Chipsatz A [°C]", CATEGORY_MAINBOARD),
        ("PUMP SYS1 [RPM]", CATEGORY_MAINBOARD),
        # Other
        ("Gesamtfehler []", CATEGORY_OTHER),
    ])
    def test_category(self, col: str, expected: str) -> None:
        sensor = parse_sensor(col)
        assert sensor.category == expected, (
            f"{col!r} → {sensor.category} (expected {expected})"
        )


# ---------------------------------------------------------------------------
# Measurement-type classification
# ---------------------------------------------------------------------------

class TestMeasurement:
    @pytest.mark.parametrize("col, expected", [
        ("CPU (Tctl/Tdie) [°C]", MEAS_TEMPERATURE),
        ("Core 0 Takt (perf #1/1) [MHz]", MEAS_CLOCK),
        ("GPU Leistung [W]", MEAS_POWER),
        ("+12V [V]", MEAS_VOLTAGE),
        ("CPU-Kernstrom (SVI3 TFN) [A]", MEAS_CURRENT),
        ("Gesamte CPU-Auslastung [%]", MEAS_UTILIZATION),
        ("CPU [RPM]", MEAS_FAN),
        ("DRAM-Lesebandbreite [GB/s]", MEAS_BANDWIDTH),
        ("Bildrate Presented (avg) [FPS]", MEAS_FPS),
        ("Frame Time Presented (avg) [ms]", MEAS_FRAMETIME),
        ("Host-Schreibvorgänge insgesamt [GB]", MEAS_IO),
        ("Gesamtfehler []", MEAS_OTHER),
    ])
    def test_measurement(self, col: str, expected: str) -> None:
        sensor = parse_sensor(col)
        assert sensor.measurement == expected, (
            f"{col!r} → {sensor.measurement} (expected {expected})"
        )


# ---------------------------------------------------------------------------
# Sensor name cleaning
# ---------------------------------------------------------------------------

class TestCleanName:
    def test_removes_unit(self) -> None:
        s = parse_sensor("CPU Temperature [°C]")
        assert s.name == "CPU Temperature"

    def test_removes_duplicate_suffix(self) -> None:
        s = parse_sensor("1,0V VOUT Spannung [V].1")
        assert s.name == "1,0V VOUT Spannung"

    def test_preserves_content(self) -> None:
        s = parse_sensor("+12V [V]")
        assert s.name == "+12V"


# ---------------------------------------------------------------------------
# parse_sensors batch
# ---------------------------------------------------------------------------

class TestParseSensors:
    def test_returns_list(self) -> None:
        result = parse_sensors(["A [V]", "B [°C]"])
        assert len(result) == 2
        assert all(isinstance(s, Sensor) for s in result)

    def test_empty_input(self) -> None:
        assert parse_sensors([]) == []
