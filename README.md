# HWInfo64 Visualizer

Desktop application for visualizing HWiNFO64 hardware sensor logs.

## About HWiNFO64

[HWiNFO®](https://www.hwinfo.com/) is a professional hardware analysis and diagnostic software for Windows.

### How to Create Compatible CSV Logs

1. Download and install **[HWiNFO64](https://www.hwinfo.com/download/)**.
2. Start HWiNFO64 and ensure **Sensors-only** is selected (or open the Sensors window).
3. In the Sensors window, click the **Logging Start** icon (sheet icon at the bottom right) to specify a `.csv` target location.
4. Run your benchmark, gaming session, or stress test.
5. Click **Logging Stop** to finish and save the log file.
6. Open the generated CSV in this application via **Open CSV File**.

> [!TIP]
> - **Polling Rate**: In HWiNFO64 *Configure Sensors* → *General*, you can adjust the polling frequency (e.g., 500ms or 1000ms for more granular telemetry).
> - **Localization**: Both German and English sensor names are automatically parsed and categorized.
> - Ensure Date and Time columns are kept intact (default HWiNFO behavior).


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
