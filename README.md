# HWInfo64 Visualizer

Desktop application for visualizing HWiNFO64 hardware sensor logs.

## Features

- **CSV Import** — Load HWiNFO64 CSV log files with automatic timestamp parsing
- **Sensor Categorization** — Automatic classification into CPU, GPU, Memory, Storage, Mainboard, Network
- **Category Filters** — Quick filter pills to narrow 300+ sensors
- **Live Search** — Real-time text filtering across all sensor names
- **Multi-Unit Plotting** — Overlay (1–2 units) or stacked subplots (3+ units)
- **Peak-Preserving Downsampling** — Min/max bucket algorithm preserves spikes and drops
- **Interactive Plot** — Pan, zoom, annotations with data tooltips
- **Time Range Slider** — Control visible time window
- **Paginated Data Inspector** — Tabular view with pagination (500 rows/page)
- **Presets** — Save, load, and delete sensor selections
- **Dark Theme** — Apple-inspired dark UI throughout

## Requirements

- Python 3.10+
- Dependencies listed in `requirements.txt`

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

1. Click **Open CSV File** and select an HWiNFO64 log
2. Use category pills and search to find sensors
3. Check the sensors you want to plot
4. Click **Visualize**

## Project Structure

```
├── main.py                    # Entry point
├── app.py                     # Application window
├── data/
│   ├── sensors.py             # Sensor metadata & categorization
│   ├── downsampling.py        # Peak-preserving min/max downsampling
│   └── loader.py              # CSV loading & normalization
├── plotting/
│   └── plot_manager.py        # Matplotlib lifecycle & plot modes
├── ui/
│   ├── sensor_selector.py     # Category filters, search, checkboxes
│   ├── data_inspector.py      # Paginated data table
│   └── toolbar.py             # Plot toolbar
├── config/
│   └── presets.py             # Versioned preset persistence
├── tests/
│   ├── test_sensors.py
│   ├── test_downsampling.py
│   └── test_presets.py
└── requirements.txt
```

## Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```
