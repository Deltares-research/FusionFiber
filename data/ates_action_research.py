#!/usr/bin/env python3
"""ATES flush analysis and QC plotting.

This script is configured directly through the constants below.

Modes:
- Midpoint mode: set `QC_TIMESTAMP = None` to plot temperature over time at the
  midpoint of each selected location.
- QC mode: set `QC_TIMESTAMP` to a timestamp string to generate a QC imshow,
  a vertical profile at that time, and optionally a time series at
  `QC_POSITION`.

The script builds the combined channel pickle automatically when needed.
"""

from pathlib import Path
from dataclasses import dataclass

import matplotlib
import numpy as np
import pandas as pd
import yaml

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from ahdts import find_nearest, load_pickle
from ahdts_channel_loader import build_combined_channel_pickle, summarize_peak_temperatures


@dataclass(frozen=True)
class LocationSpec:
    start_m: float
    end_m: float
    reverse_direction: bool
    channel_name: str


# Format: location_key -> LocationSpec(start_m, end_m, reverse_direction, channel_name)
LOCATIONS = {
    "a-ch1": LocationSpec(529.6, 549.6, False, "channel 1"),
    "b-ch1": LocationSpec(549.6, 569.6, True, "channel 1"),
    "c-ch1": LocationSpec(924.8, 944.8, False, "channel 1"),
    "d-ch1": LocationSpec(944.8, 964.8, True, "channel 1"),
    "a-ch2": LocationSpec(529.6, 549.6, True, "channel 2"),
    "b-ch2": LocationSpec(924.8, 944.8, False, "channel 2"),
    "c-ch2": LocationSpec(549.6, 569.6, True, "channel 2"),
    "d-ch2": LocationSpec(529.6, 549.6, False, "channel 2"),
    "e-ch3": LocationSpec(529.35, 549.35, False, "channel 3"),
    "f-ch3": LocationSpec(549.35, 569.35, True, "channel 3"),
    "g-ch3": LocationSpec(924.3, 944.3, False, "channel 3"),
    "h-ch3": LocationSpec(944.3, 964.3, True, "channel 3"),
    "e-ch4": LocationSpec(944.8, 964.8, True, "channel 4"),
    "f-ch4": LocationSpec(549.6, 569.6, True, "channel 4"),
    "g-ch4": LocationSpec(924.8, 944.8, False, "channel 4"),
    "h-ch4": LocationSpec(944.8, 964.8, True, "channel 4"),
}

PLOT_LOCATIONS = ["a-ch2"]
QC_TIMESTAMP = "2026-04-16 13:10:00"
QC_POSITION = 530

CONFIG_KEY_DATA_DIR = "data_dir_ates_afterspui"

DATA_DIR = Path(__file__).parent
REPO_DIR = DATA_DIR.parent
CONFIG_FILE = REPO_DIR / "config.yaml"
OUTPUT_FILE = DATA_DIR / "midpoint_selected_locations.png"


def _read_config_dir(config_key: str) -> Path:
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"Missing config file: {CONFIG_FILE}")

    with CONFIG_FILE.open("r", encoding="utf-8") as file_handle:
        config = yaml.safe_load(file_handle) or {}

    if config_key not in config:
        raise KeyError(f"Missing '{config_key}' in {CONFIG_FILE.name}")

    base_dir = Path(config[config_key])
    if not base_dir.exists():
        raise FileNotFoundError(f"Configured path does not exist: {base_dir}")

    return base_dir


def _pickle_file_from_base_dir(base_dir: Path) -> Path:
    return DATA_DIR / f"{base_dir.name}.pickle"


def _channel_df(all_channel_data: dict, channel_name: str) -> pd.DataFrame:
    try:
        return all_channel_data[channel_name]["df"]
    except KeyError as exc:
        raise KeyError(f"Missing channel dataframe for: {channel_name}") from exc


def _single_qc_location() -> str:
    if len(PLOT_LOCATIONS) != 1:
        raise ValueError("QC mode requires exactly one location in PLOT_LOCATIONS.")
    return PLOT_LOCATIONS[0]


def _interval_data(all_channel_data: dict, location_key: str) -> tuple[pd.DataFrame, str, float, float]:
    if location_key not in LOCATIONS:
        raise KeyError(f"Unknown location key: {location_key}")

    spec = LOCATIONS[location_key]
    start_pos = spec.start_m
    end_pos = spec.end_m
    channel_name = spec.channel_name
    df = _channel_df(all_channel_data, channel_name)

    interval_min = min(start_pos, end_pos)
    interval_max = max(start_pos, end_pos)
    interval_df = df.loc[:, (df.columns >= interval_min) & (df.columns <= interval_max)]
    if interval_df.empty:
        raise ValueError(
            f"No distance columns found for {location_key} within {interval_min} to {interval_max} m"
        )

    return interval_df, channel_name, start_pos, end_pos


def _format_interval_token(value: float) -> str:
    return f"{float(value):.2f}".replace(".", "p")


def _qc_output_file(prefix: str, location_key: str, start_pos: float, end_pos: float) -> Path:
    return DATA_DIR / (
        f"{prefix}_{location_key}_start-{_format_interval_token(start_pos)}"
        f"_end-{_format_interval_token(end_pos)}.png"
    )


def _nearest_timestamp(index: pd.DatetimeIndex, timestamp: str) -> tuple[int, pd.Timestamp]:
    target_ts = pd.to_datetime(timestamp)
    nearest_idx = int(np.abs((index - target_ts).asi8).argmin())
    return nearest_idx, index[nearest_idx]


def _minutes_from_start(index: pd.DatetimeIndex) -> pd.Index:
    return (index - index[0]).total_seconds() / 60.0


def _save_figure(fig: plt.Figure, output_file: Path, message: str) -> None:
    fig.tight_layout()
    fig.savefig(output_file, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {message}: {output_file}")


def plot_qc_position_profile(all_channel_data: dict, qc_position: float) -> None:
    """Plot temperature over time at one fiber distance within the QC interval."""
    location_key = _single_qc_location()
    interval_df, channel_name, start_pos, end_pos = _interval_data(all_channel_data, location_key)

    distances = interval_df.columns.to_numpy(dtype=float)
    if not (distances.min() <= qc_position <= distances.max()):
        raise ValueError(
            f"QC_POSITION {qc_position} m is outside the interval "
            f"[{distances.min():.2f}, {distances.max():.2f}] m for {location_key}."
        )

    nearest_dist_idx = int(np.abs(distances - qc_position).argmin())
    actual_distance = float(distances[nearest_dist_idx])
    series = interval_df.iloc[:, nearest_dist_idx]

    fig, ax = plt.subplots(figsize=(12, 6), dpi=200)
    ax.plot(_minutes_from_start(series.index), series.values, alpha=0.8)
    ax.set_title(
        f"QC Position Profile - {location_key} ({channel_name})\n"
        f"Requested: {qc_position} m | Nearest in data: {actual_distance:.3f} m"
    )
    ax.set_xlabel("Time (minutes)")
    ax.set_ylabel("Temperature (degC)")
    ax.grid(True, alpha=0.3)

    output_file = _qc_output_file(
        f"qc_position-{_format_interval_token(qc_position)}", location_key, start_pos, end_pos
    )
    _save_figure(fig, output_file, "QC position profile")


def plot_qc_imshow(all_channel_data: dict, qc_timestamp: str, qc_position: float | None) -> None:
    """Plot temperature as an imshow for a single QC interval."""
    location_key = _single_qc_location()
    interval_df, channel_name, start_pos, end_pos = _interval_data(all_channel_data, location_key)
    image_data = interval_df.to_numpy(copy=False).T
    _, nearest_ts = _nearest_timestamp(interval_df.index, qc_timestamp)

    times = mdates.date2num(interval_df.index.to_pydatetime())
    distances = interval_df.columns.to_numpy(dtype=float)

    print(
        "QC imshow data window: "
        f"start={interval_df.index[0]}, end={interval_df.index[-1]}, "
        f"n_times={interval_df.shape[0]}, n_positions={interval_df.shape[1]}"
    )
    print(f"QC imshow image shape (rows, cols): {image_data.shape}")

    fig, ax = plt.subplots(figsize=(12, 6), dpi=200)
    image = ax.imshow(
        image_data,
        cmap="plasma",
        aspect="auto",
        origin="upper",
        extent=[times[0], times[-1], distances.max(), distances.min()],
    )
    ax.axvline(mdates.date2num(nearest_ts.to_pydatetime()), color="white", linestyle="--", linewidth=1.2, alpha=0.9)

    if qc_position is not None:
        if distances.min() <= qc_position <= distances.max():
            ax.axhline(qc_position, color="white", linestyle="--", linewidth=1.2, alpha=0.9)
        else:
            print(
                f"Warning: QC_POSITION {qc_position} m is outside interval "
                f"[{distances.min():.2f}, {distances.max():.2f}] m, skipping line."
            )

    ax.set_title(f"QC Imshow - {location_key} ({channel_name})")
    ax.set_xlabel("Time")
    ax.set_ylabel("Fiber length (m)")
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d\n%H:%M:%S"))
    fig.autofmt_xdate(rotation=0)
    fig.colorbar(image, ax=ax).set_label("Temperature (degC)")

    output_file = _qc_output_file("qc_imshow", location_key, start_pos, end_pos)
    _save_figure(fig, output_file, "QC imshow plot")


def plot_qc_timestamp_profile(all_channel_data: dict, qc_timestamp: str) -> None:
    """Plot the temperature profile across fiber distance at one QC timestamp."""
    location_key = _single_qc_location()
    interval_df, channel_name, start_pos, end_pos = _interval_data(all_channel_data, location_key)
    nearest_idx, nearest_ts = _nearest_timestamp(interval_df.index, qc_timestamp)
    profile = interval_df.iloc[nearest_idx, :]

    fig, ax = plt.subplots(figsize=(12, 6), dpi=200)
    ax.plot(profile.index.to_numpy(dtype=float), profile.values, alpha=0.8)
    ax.set_title(f"QC Timestamp Profile - {location_key} ({channel_name})\nNearest timestamp: {nearest_ts}")
    ax.set_xlabel("Distance along fiber (m)")
    ax.set_ylabel("Temperature (degC)")
    ax.grid(True, alpha=0.3)

    output_file = _qc_output_file("qc_profile", location_key, start_pos, end_pos)
    _save_figure(fig, output_file, "QC profile plot")


def plot_midpoint_profiles(all_channel_data: dict) -> None:
    """Plot temperature over time at the midpoint of each selected location."""
    fig, ax = plt.subplots(figsize=(12, 6), dpi=200)

    for location_key in PLOT_LOCATIONS:
        if location_key not in LOCATIONS:
            raise KeyError(f"Unknown location key in PLOT_LOCATIONS: {location_key}")

        spec = LOCATIONS[location_key]
        start_pos = spec.start_m
        end_pos = spec.end_m
        channel_name = spec.channel_name
        midpoint = (start_pos + end_pos) / 2.0
        df = _channel_df(all_channel_data, channel_name)
        midpoint_idx = find_nearest(df.columns, midpoint)
        distance_value = float(df.columns[midpoint_idx])
        series = df.iloc[:, midpoint_idx]

        ax.plot(_minutes_from_start(series.index), series, label=f"{location_key} ({distance_value:.2f} m)")

    ax.set_title("Temperature at Midpoint Positions")
    ax.set_xlabel("Time (minutes)")
    ax.set_ylabel("Temperature (degC)")
    ax.grid(True, alpha=0.3)
    ax.legend()
    _save_figure(fig, OUTPUT_FILE, "plot")


def _selected_measurement_bounds() -> tuple[float, float]:
    selected_starts = [LOCATIONS[key].start_m for key in PLOT_LOCATIONS]
    selected_ends = [LOCATIONS[key].end_m for key in PLOT_LOCATIONS]
    return min(min(selected_starts), min(selected_ends)), max(max(selected_starts), max(selected_ends))


def _locations_for_loader() -> dict[str, list[object]]:
    """Return legacy positional format required by summarize_peak_temperatures()."""
    return {
        key: [spec.start_m, spec.end_m, spec.reverse_direction, spec.channel_name]
        for key, spec in LOCATIONS.items()
    }


def main() -> None:
    base_dir = _read_config_dir(CONFIG_KEY_DATA_DIR)
    pickle_file = _pickle_file_from_base_dir(base_dir)

    if not pickle_file.exists():
        channel_names = sorted({spec.channel_name for spec in LOCATIONS.values()})
        build_combined_channel_pickle(base_dir, channel_names, pickle_file, use_multiprocessing=True)

    all_channel_data = load_pickle(str(pickle_file))
    measurement_start, measurement_end = _selected_measurement_bounds()
    loader_locations = _locations_for_loader()
    summarize_peak_temperatures(
        all_channel_data,
        PLOT_LOCATIONS,
        loader_locations,
        measurement_start,
        measurement_end,
    )

    if QC_TIMESTAMP is not None:
        _single_qc_location()
        plot_qc_imshow(all_channel_data, QC_TIMESTAMP, QC_POSITION)
        plot_qc_timestamp_profile(all_channel_data, QC_TIMESTAMP)
        if QC_POSITION is not None:
            plot_qc_position_profile(all_channel_data, QC_POSITION)
        return

    plot_midpoint_profiles(all_channel_data)


if __name__ == "__main__":
    main()
