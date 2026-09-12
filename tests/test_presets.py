"""Tests for config.presets — versioned format, legacy migration, error handling."""

import json
from pathlib import Path

import pytest
from config.presets import CURRENT_VERSION, Preset, PresetManager, get_app_data_dir


@pytest.fixture
def preset_dir(tmp_path: Path, monkeypatch) -> Path:
    """Redirect PresetManager storage to a temporary directory."""
    monkeypatch.setattr("config.presets.get_app_data_dir", lambda: tmp_path)
    return tmp_path


class TestPresetManager:
    """Basic CRUD operations."""

    def test_empty_on_fresh_start(self, preset_dir: Path, monkeypatch) -> None:
        # Change CWD so legacy presets.json in the project root isn't found
        monkeypatch.chdir(preset_dir)
        mgr = PresetManager()
        assert mgr.list_presets() == []

    def test_save_and_load(self, preset_dir: Path) -> None:
        mgr = PresetManager()
        assert mgr.save_preset("Test", ["A [V]", "B [°C]"])
        assert "Test" in mgr.list_presets()
        p = mgr.get_preset("Test")
        assert p is not None
        assert p.columns == ["A [V]", "B [°C]"]

    def test_delete(self, preset_dir: Path) -> None:
        mgr = PresetManager()
        mgr.save_preset("X", ["col"])
        assert mgr.delete_preset("X")
        assert mgr.get_preset("X") is None

    def test_delete_nonexistent(self, preset_dir: Path) -> None:
        mgr = PresetManager()
        assert not mgr.delete_preset("nope")

    def test_persistence(self, preset_dir: Path) -> None:
        mgr1 = PresetManager()
        mgr1.save_preset("Saved", ["c1", "c2"], time_range=50)

        mgr2 = PresetManager()
        p = mgr2.get_preset("Saved")
        assert p is not None
        assert p.columns == ["c1", "c2"]
        assert p.time_range == 50

    def test_overwrite(self, preset_dir: Path) -> None:
        mgr = PresetManager()
        mgr.save_preset("P", ["a"])
        mgr.save_preset("P", ["b", "c"])
        assert mgr.get_preset("P").columns == ["b", "c"]


class TestVersionedFormat:
    """Verify the on-disk JSON structure."""

    def test_writes_version(self, preset_dir: Path) -> None:
        mgr = PresetManager()
        mgr.save_preset("V", ["x"])

        raw = json.loads((preset_dir / "presets.json").read_text("utf-8"))
        assert raw["version"] == CURRENT_VERSION
        assert "V" in raw["presets"]
        assert raw["presets"]["V"]["columns"] == ["x"]

    def test_stores_plot_mode(self, preset_dir: Path) -> None:
        mgr = PresetManager()
        mgr.save_preset("M", ["a"], plot_mode="grouped")
        raw = json.loads((preset_dir / "presets.json").read_text("utf-8"))
        assert raw["presets"]["M"]["plot_mode"] == "grouped"


class TestLegacyMigration:
    """Legacy format: ``{"name": ["col1", "col2"]}``."""

    def test_migrates_legacy(self, preset_dir: Path, tmp_path: Path, monkeypatch) -> None:
        # Write legacy file in "working directory"
        legacy = Path("presets_legacy_test.json")
        # Simulate legacy by placing in the appdata dir path
        # Instead, we test _parse_legacy directly
        mgr = PresetManager()
        mgr._parse_legacy({"Gaming": ["+12V [V]", "GPU Temp [°C]"]})
        p = mgr.get_preset("Gaming")
        assert p is not None
        assert p.columns == ["+12V [V]", "GPU Temp [°C]"]
        assert p.plot_mode == "auto"


class TestErrorHandling:
    """Malformed / missing files must not crash."""

    def test_malformed_json(self, preset_dir: Path) -> None:
        (preset_dir / "presets.json").write_text("NOT JSON", encoding="utf-8")
        mgr = PresetManager()
        assert mgr.list_presets() == []

    def test_wrong_type_root(self, preset_dir: Path) -> None:
        (preset_dir / "presets.json").write_text("[1,2,3]", encoding="utf-8")
        mgr = PresetManager()
        assert mgr.list_presets() == []

    def test_future_version(self, preset_dir: Path) -> None:
        data = {"version": 999, "presets": {"X": {"columns": ["a"]}}}
        (preset_dir / "presets.json").write_text(
            json.dumps(data), encoding="utf-8")
        mgr = PresetManager()
        assert mgr.get_preset("X") is not None

    def test_missing_columns_field(self, preset_dir: Path) -> None:
        data = {"version": 1, "presets": {"Bad": {"plot_mode": "auto"}}}
        (preset_dir / "presets.json").write_text(
            json.dumps(data), encoding="utf-8")
        mgr = PresetManager()
        p = mgr.get_preset("Bad")
        assert p is not None
        assert p.columns == []

    def test_non_string_columns(self, preset_dir: Path) -> None:
        data = {"version": 1, "presets": {"Mix": {"columns": ["ok", 42, None]}}}
        (preset_dir / "presets.json").write_text(
            json.dumps(data), encoding="utf-8")
        mgr = PresetManager()
        assert mgr.get_preset("Mix").columns == ["ok"]


class TestAppDataDir:
    def test_returns_path(self) -> None:
        d = get_app_data_dir()
        assert isinstance(d, Path)
        assert "HWInfo64Visualizer" in str(d)
