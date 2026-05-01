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

import logging
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


@dataclass(frozen=True)
class QCContext:
    """Container for QC interval data and metadata."""
    location_key: str
    interval_df: pd.DataFrame
    channel_name: str
    start_pos: float
    end_pos: float
    distances: np.ndarray

# Dataset selection: use "data_dir_ates_afterspui" for after-SPUI only, or
# "data_dir_ates_spui_en_afterspui" to include both SPUI and after-SPUI data
CONFIG_KEY_DATA_DIR = "data_dir_ates_spui_en_afterspui"

# Pickle compression: "float32" (default, full precision) or "float16" (smaller file)
PICKLE_DTYPE = "float32"

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

PLOT_LOCATIONS = ["a-ch1"]
QC_TIMESTAMP = "2026-04-16 13:10:00"
QC_POSITION = 546.5


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


def _prepare_qc_context(all_channel_data: dict, location_key: str) -> QCContext:
    """Extract and validate QC context for a location."""
    if location_key not in LOCATIONS:
        raise KeyError(f"Unknown location key: {location_key}")

    spec = LOCATIONS[location_key]
    df = _channel_df(all_channel_data, spec.channel_name)
    
    interval_min, interval_max = min(spec.start_m, spec.end_m), max(spec.start_m, spec.end_m)
    interval_df = df.loc[:, (df.columns >= interval_min) & (df.columns <= interval_max)]
    
    if interval_df.empty:
        raise ValueError(
            f"No distance columns found for {location_key} in [{interval_min:.2f}, {interval_max:.2f}] m"
        )
    
    return QCContext(
        location_key=location_key,
        interval_df=interval_df,
        channel_name=spec.channel_name,
        start_pos=spec.start_m,
        end_pos=spec.end_m,
        distances=interval_df.columns.to_numpy(dtype=float),
    )


def _qc_output_file(prefix: str, location_key: str, start_pos: float, end_pos: float) -> Path:
    """Generate output path for QC plots."""
    start_token = f"{start_pos:.2f}".replace(".", "p")
    end_token = f"{end_pos:.2f}".replace(".", "p")
    return DATA_DIR / f"{prefix}_{location_key}_start-{start_token}_end-{end_token}.png"


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


def plot_qc_position_profile(ctx: QCContext, qc_position: float) -> None:
    """Plot temperature over time at one fiber distance."""
    if not (ctx.distances.min() <= qc_position <= ctx.distances.max()):
        raise ValueError(
            f"QC_POSITION {qc_position} m outside [{ctx.distances.min():.2f}, {ctx.distances.max():.2f}] m"
        )

    nearest_idx = int(np.abs(ctx.distances - qc_position).argmin())
    actual_dist = float(ctx.distances[nearest_idx])
    series = ctx.interval_df.iloc[:, nearest_idx]

    fig, ax = plt.subplots(figsize=(12, 6), dpi=200)
    ax.plot(_minutes_from_start(series.index), series.values, alpha=0.8)
    ax.set_title(
        f"QC Position Profile - {ctx.location_key} ({ctx.channel_name})\n"
        f"Requested: {qc_position} m | Nearest: {actual_dist:.3f} m"
    )
    ax.set_xlabel("Time (minutes)")
    ax.set_ylabel("Temperature (degC)")
    ax.grid(True, alpha=0.3)

    pos_token = f"{qc_position:.2f}".replace(".", "p")
    output_file = _qc_output_file(f"qc_position-{pos_token}", ctx.location_key, ctx.start_pos, ctx.end_pos)
    _save_figure(fig, output_file, "QC position profile")


def plot_qc_imshow(ctx: QCContext, qc_timestamp: str, qc_position: float | None) -> None:
    """Plot temperature heatmap for a QC interval."""
    image_data = ctx.interval_df.to_numpy(copy=False).T
    nearest_idx, nearest_ts = _nearest_timestamp(ctx.interval_df.index, qc_timestamp)
    
    times = mdates.date2num(ctx.interval_df.index.to_pydatetime())
    
    print(
        f"QC imshow: {ctx.location_key} ({ctx.channel_name})\n"
        f"  Time: {ctx.interval_df.index[0]} to {ctx.interval_df.index[-1]} "
        f"({ctx.interval_df.shape[0]} samples)\n"
        f"  Distance: {ctx.distances.min():.2f} to {ctx.distances.max():.2f} m "
        f"({ctx.interval_df.shape[1]} positions)\n"
        f"  Image: {image_data.shape}"
    )

    fig, ax = plt.subplots(figsize=(12, 6), dpi=200)
    im = ax.imshow(
        image_data, cmap="plasma", aspect="auto", origin="upper",
        extent=[times[0], times[-1], ctx.distances.max(), ctx.distances.min()],
    )
    ax.axvline(mdates.date2num(nearest_ts.to_pydatetime()), color="white", linestyle="--", lw=1.2, alpha=0.9)
    
    if qc_position is not None:
        if ctx.distances.min() <= qc_position <= ctx.distances.max():
            ax.axhline(qc_position, color="white", linestyle="--", lw=1.2, alpha=0.9)

    ax.set_title(f"QC Imshow - {ctx.location_key} ({ctx.channel_name})")
    ax.set_xlabel("Time")
    ax.set_ylabel("Fiber length (m)")
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d\n%H:%M:%S"))
    fig.autofmt_xdate(rotation=0)
    fig.colorbar(im, ax=ax).set_label("Temperature (degC)")
    
    _save_figure(fig, _qc_output_file("qc_imshow", ctx.location_key, ctx.start_pos, ctx.end_pos), "QC imshow")


def plot_qc_timestamp_profile(ctx: QCContext, qc_timestamp: str) -> None:
    """Plot temperature profile across fiber distance at a QC timestamp."""
    nearest_idx, nearest_ts = _nearest_timestamp(ctx.interval_df.index, qc_timestamp)
    profile = ctx.interval_df.iloc[nearest_idx, :]

    fig, ax = plt.subplots(figsize=(12, 6), dpi=200)
    ax.plot(profile.index.to_numpy(dtype=float), profile.values, alpha=0.8)
    ax.set_title(f"QC Timestamp Profile - {ctx.location_key} ({ctx.channel_name})\nNearest: {nearest_ts}")
    ax.set_xlabel("Distance along fiber (m)")
    ax.set_ylabel("Temperature (degC)")
    ax.grid(True, alpha=0.3)

    _save_figure(fig, _qc_output_file("qc_profile", ctx.location_key, ctx.start_pos, ctx.end_pos), "QC profile")


def plot_midpoint_profiles(all_channel_data: dict, plot_locations: list[str]) -> None:
    """Plot temperature over time at the midpoint of each selected location."""
    if not plot_locations:
        logging.warning("No valid plot locations available for midpoint mode; skipping midpoint plot.")
        return

    fig, ax = plt.subplots(figsize=(12, 6), dpi=200)

    for location_key in plot_locations:
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
    """Get min/max positions across all selected plot locations."""
    starts = [LOCATIONS[key].start_m for key in PLOT_LOCATIONS]
    ends = [LOCATIONS[key].end_m for key in PLOT_LOCATIONS]
    return min(min(starts), min(ends)), max(max(starts), max(ends))


def main() -> None:
    # Setup and load data
    base_dir = _read_config_dir(CONFIG_KEY_DATA_DIR)
    pickle_file = _pickle_file_from_base_dir(base_dir)

    if not pickle_file.exists():
        channel_names = sorted({spec.channel_name for spec in LOCATIONS.values()})
        dtype = np.dtype(PICKLE_DTYPE) if isinstance(PICKLE_DTYPE, str) else PICKLE_DTYPE
        build_combined_channel_pickle(base_dir, channel_names, pickle_file, use_multiprocessing=True, dtype=dtype)

    all_channel_data = load_pickle(str(pickle_file))
    
    # Filter locations to only those with available channels
    available_channels = set(all_channel_data.keys())
    missing_channels = {spec.channel_name for spec in LOCATIONS.values()} - available_channels
    if missing_channels:
        logging.warning(f"Missing channels: {sorted(missing_channels)}. Some locations will be skipped.")
    
    filtered_plot_locations = [
        loc for loc in PLOT_LOCATIONS
        if loc in LOCATIONS and LOCATIONS[loc].channel_name in available_channels
    ]
    if filtered_plot_locations != PLOT_LOCATIONS:
        skipped = set(PLOT_LOCATIONS) - set(filtered_plot_locations)
        logging.warning(f"Skipped PLOT_LOCATIONS due to missing channels: {skipped}")

    if not filtered_plot_locations:
        logging.warning("No valid PLOT_LOCATIONS remain after channel filtering.")
    
    # Summarize peak temperatures for all locations
    measurement_start, measurement_end = _selected_measurement_bounds()
    locations_list = {
        key: [spec.start_m, spec.end_m, spec.reverse_direction, spec.channel_name]
        for key, spec in LOCATIONS.items()
        if spec.channel_name in available_channels
    }
    if filtered_plot_locations:
        summarize_peak_temperatures(
            all_channel_data,
            filtered_plot_locations,
            locations_list,
            measurement_start,
            measurement_end,
        )
    else:
        logging.warning("Skipping peak temperature summary because no valid plot locations are available.")

    # Execute mode: QC mode (single location detailed analysis) or midpoint mode (multi-location overview)
    if QC_TIMESTAMP is not None:
        if len(filtered_plot_locations) == 0:
            logging.warning("QC mode enabled but no valid PLOT_LOCATIONS are available; skipping QC plots.")
            return
        if len(filtered_plot_locations) != 1:
            raise ValueError(f"QC mode requires exactly one location. Found {len(filtered_plot_locations)}: {filtered_plot_locations}")
        
        location_key = filtered_plot_locations[0]
        ctx = _prepare_qc_context(all_channel_data, location_key)
        
        plot_qc_imshow(ctx, QC_TIMESTAMP, QC_POSITION)
        plot_qc_timestamp_profile(ctx, QC_TIMESTAMP)
        if QC_POSITION is not None:
            plot_qc_position_profile(ctx, QC_POSITION)
    else:
        plot_midpoint_profiles(all_channel_data, filtered_plot_locations)


if __name__ == "__main__":
    main()
