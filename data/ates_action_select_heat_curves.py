#!/usr/bin/env python3
"""Select, align, and compare ATES heating curves from DTS data.

Interpretation of "episodes of heating" (heating curves):
- A heating curve is the local temperature rise event that starts after an
  operational trigger (for example a pumping/heating action).
- This script detects the heating start near each user-provided seed timestamp,
  extracts a fixed window around it, and then compares events in a common frame.

Plots generated:
1) Full temperature-over-time plot (datetime x-axis) for each channel/distance,
   with pumping rate on a secondary y-axis.
2) Raw extracted heating windows in minutes, including PRE_START_MINUTES.
3) Aligned + normalized heating-only curves (t >= 0 min).
4) Pump companion figure (raw-window and heating-only panels), in the same
   color order as the heating curves.
"""

from __future__ import annotations

import logging
import pickle
from dataclasses import dataclass
from pathlib import Path

import matplotlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

matplotlib.use("Agg")

# -----------------------------------------------------------------------------
# User configuration
# -----------------------------------------------------------------------------

CONFIG_KEY_DATA_DIR = "data_dir_ates_spui_en_afterspui"

# Same seed timestamp list is applied to each selection.
SELECTIONS: list[dict[str, object]] = [
    {"channel": "channel 1", "distance_m": 546.5},
]

HEATING_SEED_TIMESTAMPS: list[str] = [
    "2026-04-18 07:30:00", # geen stroming
    "2026-04-28 18:00:00", # constant of 5.5 m3/h
    "2026-04-26 03:00:00",
    "2026-04-24 01:30:00",
    "2026-04-20 09:00:00", #fastest after spui
    "2026-04-16 13:15:00", #spui in
    "2026-04-16 13:56:00", #spui uit
]

# Window and detection settings
PRE_START_MINUTES = 5.0
TOTAL_WINDOW_MINUTES = 50.0
SEARCH_FORWARD_MINUTES = 40.0
BASELINE_LOOKBACK_MINUTES = 15.0
SUSTAINED_RISE_SAMPLES = 3
MIN_DERIVATIVE_C_PER_MIN = 0.04
DERIV_STD_MULTIPLIER = 3.0
FALLBACK_LOOKBACK_MINUTES = 12.0

# Normalization settings (same logic style as gwflows script, but target auto-derived)
NORMALIZE_BASELINE_SAMPLES = 5
BASELINE_SPREAD_WARNING_DEGC = 0.5

# Plot settings
CMAP_NAME = "viridis"
LINE_WIDTH = 1.8
PUMP_LINE_WIDTH = 2.4
PUMP_ALPHA = 0.5
SAVE_DPI = 300
FULL_TIMELINE_FIGSIZE = (130, 20)

# Pump data source settings (robust matching, same principle as interactive viewer)
PUMP_FILE_GLOB = "Debiet*.xlsx"
PUMP_SHEET_NAME = "debiet koudebron kb-1"
PUMP_TIME_COLUMN = "Systeemtijd"
PUMP_RATE_COLUMN = "Debiet WB-1 m3/h"

# -----------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent
REPO_DIR = DATA_DIR.parent
CONFIG_FILE = REPO_DIR / "config.yaml"


@dataclass
class SelectionResult:
    selection_key: str
    channel: str
    requested_distance_m: float
    actual_distance_m: float
    full_temp_series: pd.Series


@dataclass
class HeatingCurveRecord:
    selection_key: str
    channel: str
    actual_distance_m: float
    seed_ts: pd.Timestamp
    detected_start_ts: pd.Timestamp
    start_method: str
    raw_temp_rel: pd.Series      # minutes relative to detected start, includes negative pre-window
    raw_pump_rel: pd.Series | None
    normalized_rel: pd.Series    # same x as raw_temp_rel
    aligned_norm_rel: pd.Series  # minutes >= 0
    aligned_pump_rel: pd.Series | None
    baseline_mean_c: float
    peak_aligned_c: float


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


def _load_combined_pickle(pickle_path: Path) -> dict[str, pd.DataFrame]:
    if not pickle_path.exists():
        raise FileNotFoundError(
            f"Pickle not found: {pickle_path}. Build it first (e.g. via ates_action_flush_experiment.py)."
        )

    with pickle_path.open("rb") as fh:
        payload = pickle.load(fh)

    if not isinstance(payload, dict) or not payload:
        raise ValueError("Pickle payload must be a non-empty dict.")

    channel_dfs: dict[str, pd.DataFrame] = {}
    for channel_name, channel_payload in payload.items():
        if not isinstance(channel_payload, dict) or "df" not in channel_payload:
            continue

        df = channel_payload["df"]
        if not isinstance(df, pd.DataFrame) or df.empty:
            continue

        idx = pd.to_datetime(df.index, errors="coerce")
        if idx.isna().any():
            raise ValueError(f"Channel '{channel_name}' contains non-datetime index values.")

        numeric_cols = pd.to_numeric(df.columns, errors="coerce")
        mask = ~np.isnan(numeric_cols)
        if not mask.any():
            raise ValueError(f"Channel '{channel_name}' contains no numeric distance columns.")

        cleaned = df.loc[:, mask].copy()
        cleaned.columns = numeric_cols[mask].astype(float)
        cleaned.index = idx
        cleaned = cleaned.sort_index().sort_index(axis=1)
        channel_dfs[str(channel_name)] = cleaned

    if not channel_dfs:
        raise ValueError("No valid channel dataframes found in pickle.")

    return channel_dfs


def _norm_text(text: object) -> str:
    return "".join(ch for ch in str(text).lower() if ch.isalnum())


def _resolve_sheet_name(excel_file: Path, requested_sheet: str) -> str:
    xls = pd.ExcelFile(excel_file)
    wanted = _norm_text(requested_sheet)
    for sheet_name in xls.sheet_names:
        if _norm_text(sheet_name) == wanted:
            return sheet_name
    for sheet_name in xls.sheet_names:
        sn = _norm_text(sheet_name)
        if "debiet" in sn and "koudebron" in sn and "kb1" in sn:
            return sheet_name
    raise ValueError(f"Worksheet matching '{requested_sheet}' not found")


def _resolve_column_name(columns: pd.Index, preferred: str, required_parts: list[str]) -> str | None:
    col_list = [str(col) for col in columns]
    preferred_norm = _norm_text(preferred)

    for col in col_list:
        if _norm_text(col) == preferred_norm:
            return col

    required_norm = [_norm_text(part) for part in required_parts]
    for col in col_list:
        col_norm = _norm_text(col)
        if all(part in col_norm for part in required_norm):
            return col
    return None


def _load_pump_rate_series() -> tuple[pd.Series | None, str | None]:
    search_dirs = [REPO_DIR / "ates-app", DATA_DIR]
    candidate_files: list[Path] = []
    for search_dir in search_dirs:
        if search_dir.exists():
            candidate_files.extend(search_dir.glob(PUMP_FILE_GLOB))

    pump_files = sorted(candidate_files, key=lambda path: path.stat().st_mtime, reverse=True)
    if not pump_files:
        msg = f"No pump file found ({PUMP_FILE_GLOB})"
        logging.warning(msg)
        return None, msg

    selected_file = pump_files[0]
    try:
        sheet_name = _resolve_sheet_name(selected_file, PUMP_SHEET_NAME)
        pump_df = pd.read_excel(selected_file, sheet_name=sheet_name)
    except Exception as exc:  # pragma: no cover
        msg = f"Pump file read failed: {type(exc).__name__}"
        logging.warning("Failed to read pump data from %s: %s", selected_file, exc)
        return None, msg

    time_col = _resolve_column_name(pump_df.columns, PUMP_TIME_COLUMN, ["systeemtijd"])
    rate_col = _resolve_column_name(pump_df.columns, PUMP_RATE_COLUMN, ["debiet", "m3", "h"])
    if time_col is None or rate_col is None:
        msg = "Pump columns missing"
        logging.warning("Pump file %s is missing expected time/rate columns.", selected_file)
        return None, msg

    timestamps = pd.to_datetime(pump_df[time_col], errors="coerce", dayfirst=True)
    rates = pd.to_numeric(pump_df[rate_col], errors="coerce")
    series = pd.Series(rates.values, index=timestamps, name="pump_rate").dropna()
    if series.empty:
        msg = "Pump data empty after parsing"
        logging.warning(msg)
        return None, msg

    series = series[~series.index.duplicated(keep="last")].sort_index()
    logging.info("Loaded pump data with %d samples from %s", len(series), selected_file.name)
    return series, None


def _nearest_value(values: np.ndarray, target: float) -> tuple[int, float]:
    idx = int(np.abs(values - target).argmin())
    return idx, float(values[idx])


def _selection_key(channel: str, distance_m: float) -> str:
    ch_token = channel.replace(" ", "-")
    return f"{ch_token}_d-{distance_m:.2f}m"


def _extract_selection_series(channel_dfs: dict[str, pd.DataFrame]) -> list[SelectionResult]:
    selections: list[SelectionResult] = []
    for cfg in SELECTIONS:
        channel = str(cfg["channel"])
        requested_distance_m = float(cfg["distance_m"])

        if channel not in channel_dfs:
            raise KeyError(f"Requested channel not found in pickle: {channel}")

        df = channel_dfs[channel]
        idx, actual_dist = _nearest_value(df.columns.to_numpy(dtype=float), requested_distance_m)
        series = df.iloc[:, idx].copy()
        series = pd.to_numeric(series, errors="coerce").dropna()

        if series.empty:
            raise ValueError(f"No valid temperature values for {channel} at nearest distance {actual_dist:.3f} m")

        selections.append(
            SelectionResult(
                selection_key=_selection_key(channel, actual_dist),
                channel=channel,
                requested_distance_m=requested_distance_m,
                actual_distance_m=actual_dist,
                full_temp_series=series,
            )
        )

    return selections


def _sustained_true_start(mask: np.ndarray, min_run: int) -> int | None:
    run = 0
    for i, flag in enumerate(mask):
        run = run + 1 if flag else 0
        if run >= min_run:
            return i - min_run + 1
    return None


def _median_step_minutes(index: pd.DatetimeIndex) -> float:
    if len(index) < 2:
        return 1.0
    deltas = np.diff(index.view("i8")) / 60_000_000_000
    deltas = deltas[deltas > 0]
    if len(deltas) == 0:
        return 1.0
    return float(np.median(deltas))


def _detect_heating_start(temp_series: pd.Series, seed_ts: pd.Timestamp) -> tuple[pd.Timestamp, str]:
    ts = temp_series.sort_index().dropna()
    if ts.empty:
        raise ValueError("Empty temperature series for start detection.")

    seed_ts = pd.to_datetime(seed_ts)
    step_min = _median_step_minutes(ts.index)
    smooth_samples = max(3, int(round(2.0 / max(step_min, 0.05))))
    if smooth_samples % 2 == 0:
        smooth_samples += 1

    smooth = ts.rolling(window=smooth_samples, center=True, min_periods=1).mean()
    dt_minutes = smooth.index.to_series().diff().dt.total_seconds() / 60.0
    derivative = smooth.diff() / dt_minutes.values

    search_end = seed_ts + pd.Timedelta(minutes=SEARCH_FORWARD_MINUTES)
    search_deriv = derivative.loc[(derivative.index >= seed_ts) & (derivative.index <= search_end)].dropna()
    if search_deriv.empty:
        idx = int(np.abs((ts.index - seed_ts).asi8).argmin())
        return pd.Timestamp(ts.index[idx]), "nearest-sample-fallback"

    baseline_start = seed_ts - pd.Timedelta(minutes=BASELINE_LOOKBACK_MINUTES)
    baseline_deriv = derivative.loc[(derivative.index >= baseline_start) & (derivative.index < seed_ts)].dropna()
    base_mean = float(baseline_deriv.mean()) if not baseline_deriv.empty else 0.0
    base_std = float(baseline_deriv.std()) if len(baseline_deriv) > 1 else 0.0
    threshold = max(base_mean + DERIV_STD_MULTIPLIER * base_std, MIN_DERIVATIVE_C_PER_MIN)

    mask = (search_deriv.values > threshold)
    start_pos = _sustained_true_start(mask, SUSTAINED_RISE_SAMPLES)
    if start_pos is not None:
        start_ts = pd.Timestamp(search_deriv.index[start_pos])
        return start_ts, "sustained-rise"

    peak_idx = int(np.nanargmax(search_deriv.values))
    peak_ts = pd.Timestamp(search_deriv.index[peak_idx])
    fallback_window_start = max(seed_ts, peak_ts - pd.Timedelta(minutes=FALLBACK_LOOKBACK_MINUTES))
    fallback_temp = smooth.loc[(smooth.index >= fallback_window_start) & (smooth.index <= peak_ts)]

    if fallback_temp.empty:
        return peak_ts, "peak-derivative-fallback"

    start_ts = pd.Timestamp(fallback_temp.idxmin())
    return start_ts, "local-min-before-peak-fallback"


def _extract_relative_segment(series: pd.Series, start_ts: pd.Timestamp) -> pd.Series:
    win_start = start_ts - pd.Timedelta(minutes=PRE_START_MINUTES)
    win_end = win_start + pd.Timedelta(minutes=TOTAL_WINDOW_MINUTES)
    segment = series.loc[(series.index >= win_start) & (series.index <= win_end)].copy()

    if segment.empty:
        return segment

    rel_min = (segment.index - start_ts).total_seconds() / 60.0
    segment.index = pd.Index(rel_min, name="minutes")
    return segment


def _align_pump_to_temp_window(
    pump_series: pd.Series | None,
    temp_segment: pd.Series,
    start_ts: pd.Timestamp,
) -> pd.Series | None:
    if pump_series is None or temp_segment.empty:
        return None

    abs_index = pd.to_datetime(start_ts) + pd.to_timedelta(temp_segment.index.values, unit="m")
    merged = pump_series.reindex(pump_series.index.union(abs_index)).sort_index().interpolate(method="time")
    aligned = merged.reindex(abs_index)

    rel = pd.Series(aligned.values, index=temp_segment.index.copy(), name="pump_rate")
    rel = rel.dropna()
    return rel if not rel.empty else None


def _normalize_curves(raw_segments: list[pd.Series]) -> tuple[list[pd.Series], float, list[float]]:
    if NORMALIZE_BASELINE_SAMPLES < 1:
        raise ValueError("NORMALIZE_BASELINE_SAMPLES must be >= 1")

    baseline_means: list[float] = []
    normalized: list[pd.Series] = []

    for i, segment in enumerate(raw_segments):
        if segment.empty:
            baseline_means.append(np.nan)
            normalized.append(segment)
            continue

        n = min(NORMALIZE_BASELINE_SAMPLES, len(segment))
        baseline_window = segment.iloc[:n]
        baseline_mean = float(baseline_window.mean())
        baseline_spread = float(baseline_window.max() - baseline_window.min())
        baseline_means.append(baseline_mean)

        if baseline_spread > BASELINE_SPREAD_WARNING_DEGC:
            logging.warning(
                "Curve %d baseline spread %.3f degC (> %.3f degC)",
                i,
                baseline_spread,
                BASELINE_SPREAD_WARNING_DEGC,
            )

    valid_baselines = [b for b in baseline_means if np.isfinite(b)]
    if not valid_baselines:
        raise ValueError("Unable to compute baseline means for normalization.")

    target_temp = float(np.mean(valid_baselines))
    for segment, baseline_mean in zip(raw_segments, baseline_means):
        if segment.empty or not np.isfinite(baseline_mean):
            normalized.append(segment)
            continue
        offset = target_temp - baseline_mean
        normalized.append(segment + offset)

    return normalized, target_temp, baseline_means


def _build_heating_records(
    selection: SelectionResult,
    pump_series: pd.Series | None,
) -> list[HeatingCurveRecord]:
    seed_ts_list = [pd.to_datetime(ts) for ts in HEATING_SEED_TIMESTAMPS]

    starts: list[tuple[pd.Timestamp, str]] = []
    raw_segments: list[pd.Series] = []
    raw_pumps: list[pd.Series | None] = []

    for seed_ts in seed_ts_list:
        detected_start_ts, method = _detect_heating_start(selection.full_temp_series, seed_ts)
        raw_seg = _extract_relative_segment(selection.full_temp_series, detected_start_ts)
        raw_pump = _align_pump_to_temp_window(pump_series, raw_seg, detected_start_ts)

        if raw_seg.empty:
            logging.warning(
                "Skipping seed %s for %s: extracted segment is empty.",
                seed_ts,
                selection.selection_key,
            )
            continue

        starts.append((detected_start_ts, method))
        raw_segments.append(raw_seg)
        raw_pumps.append(raw_pump)

    if not raw_segments:
        return []

    normalized_segments, target_temp, baseline_means = _normalize_curves(raw_segments)
    logging.info(
        "Normalization target for %s: %.4f degC (average of per-curve baselines)",
        selection.selection_key,
        target_temp,
    )

    records: list[HeatingCurveRecord] = []
    for seed_ts, (start_ts, method), raw_seg, raw_pump, norm_seg, baseline_mean in zip(
        seed_ts_list,
        starts,
        raw_segments,
        raw_pumps,
        normalized_segments,
        baseline_means,
    ):
        aligned_norm = norm_seg.loc[norm_seg.index >= 0.0]
        aligned_pump = None
        if raw_pump is not None:
            aligned_pump = raw_pump.loc[raw_pump.index >= 0.0]
            if aligned_pump.empty:
                aligned_pump = None

        peak_aligned = float(aligned_norm.max()) if not aligned_norm.empty else float("nan")

        records.append(
            HeatingCurveRecord(
                selection_key=selection.selection_key,
                channel=selection.channel,
                actual_distance_m=selection.actual_distance_m,
                seed_ts=seed_ts,
                detected_start_ts=start_ts,
                start_method=method,
                raw_temp_rel=raw_seg,
                raw_pump_rel=raw_pump,
                normalized_rel=norm_seg,
                aligned_norm_rel=aligned_norm,
                aligned_pump_rel=aligned_pump,
                baseline_mean_c=float(baseline_mean),
                peak_aligned_c=peak_aligned,
            )
        )

    return records


def _ordered_records(records: list[HeatingCurveRecord]) -> list[HeatingCurveRecord]:
    return sorted(
        records,
        key=lambda rec: (np.nan_to_num(rec.peak_aligned_c, nan=-1e9), rec.detected_start_ts.value),
    )


def _selection_filename_token(selection: SelectionResult) -> str:
    channel_token = selection.channel.replace(" ", "-")
    dist_token = f"{selection.actual_distance_m:.2f}".replace(".", "p")
    return f"{channel_token}_fiber-{dist_token}m"


def _plot_full_series_with_pump(
    selection: SelectionResult,
    pump_series: pd.Series | None,
    output_dir: Path,
) -> Path:
    fig, ax = plt.subplots(figsize=FULL_TIMELINE_FIGSIZE, dpi=SAVE_DPI)
    ax.plot(selection.full_temp_series.index, selection.full_temp_series.values, color="#2E5AE8", lw=LINE_WIDTH)
    ax.set_title(
        f"Full time series - {selection.channel}, requested {selection.requested_distance_m:.2f} m, "
        f"nearest {selection.actual_distance_m:.3f} m"
    )
    ax.set_xlabel("Datetime")
    ax.set_ylabel("Temperature (degC)")
    ax.grid(True, alpha=0.3)

    if pump_series is not None and not pump_series.empty:
        merged = pump_series.reindex(pump_series.index.union(selection.full_temp_series.index)).sort_index()
        aligned = merged.interpolate(method="time").reindex(selection.full_temp_series.index)
        aligned_values = aligned.values.astype(float)
        valid_mask = ~np.isnan(aligned_values)
        ax2 = ax.twinx()
        ax2.fill_between(
            selection.full_temp_series.index,
            aligned_values,
            0.0,
            where=valid_mask,
            color="goldenrod",
            alpha=0.18,
            linewidth=0,
        )
        ax2.plot(
            selection.full_temp_series.index,
            aligned_values,
            color="goldenrod",
            lw=PUMP_LINE_WIDTH,
            alpha=PUMP_ALPHA,
        )
        ax2.set_ylim(bottom=0)
        ax2.set_ylabel("Pumping rate (m³/h)", color="goldenrod")
        ax2.tick_params(axis="y", colors="goldenrod")

    # Trim x-axis to actual data extent
    valid_idx = selection.full_temp_series.dropna().index
    if len(valid_idx) > 1:
        ax.set_xlim(valid_idx[0], valid_idx[-1])

    # Fixed 2-hour major ticks; show date below time every 12 h (00:00 and 12:00)
    class _DayAwareFmt(mdates.DateFormatter):
        def __call__(self, x, pos=None):
            dt = mdates.num2date(x)
            if dt.hour in (0, 12) and dt.minute == 0:
                return dt.strftime("%H:%M\n%Y-%m-%d")
            return dt.strftime("%H:%M")

    ax.xaxis.set_major_locator(mdates.HourLocator(byhour=range(0, 24, 2)))
    ax.xaxis.set_major_formatter(_DayAwareFmt("%H:%M"))
    ax.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 1)))
    ax.tick_params(axis="x", which="major", labelsize=8)
    ax.tick_params(axis="x", which="minor", length=3)
    ax.grid(True, which="minor", axis="x", alpha=0.15)
    fig.autofmt_xdate(rotation=0)
    fig.tight_layout()

    out = output_dir / f"heat_curves_full_datetime_{_selection_filename_token(selection)}.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def _plot_raw_windows(
    ordered: list[HeatingCurveRecord],
    cmap_name: str,
    output_file: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(11.5, 6), dpi=SAVE_DPI)
    cmap = plt.get_cmap(cmap_name, len(ordered))

    for i, rec in enumerate(ordered):
        color = cmap(i)
        ax.plot(
            rec.raw_temp_rel.index,
            rec.raw_temp_rel.values,
            color=color,
            lw=LINE_WIDTH,
            label=(
                f"seed {rec.seed_ts.strftime('%H:%M:%S')} | "
                f"start {rec.detected_start_ts.strftime('%H:%M:%S')} | "
                f"peak {rec.peak_aligned_c:.2f}"
            ),
        )

    ax.axvline(0.0, color="black", lw=1.0, ls="--", alpha=0.65)
    ax.set_title("Raw extracted heating windows (includes pre-start)")
    ax.set_xlabel("Minutes relative to detected heating start")
    ax.set_ylabel("Temperature (degC)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_file, bbox_inches="tight")
    plt.close(fig)


def _plot_aligned_normalized(
    ordered: list[HeatingCurveRecord],
    cmap_name: str,
    output_file: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(11.5, 6), dpi=SAVE_DPI)
    cmap = plt.get_cmap(cmap_name, len(ordered))

    for i, rec in enumerate(ordered):
        color = cmap(i)
        ax.plot(
            rec.aligned_norm_rel.index,
            rec.aligned_norm_rel.values,
            color=color,
            lw=LINE_WIDTH,
            label=(
                f"seed {rec.seed_ts.strftime('%H:%M:%S')} | "
                f"start {rec.detected_start_ts.strftime('%H:%M:%S')} | "
                f"peak {rec.peak_aligned_c:.2f}"
            ),
        )

    ax.axvline(0.0, color="black", lw=1.0, ls="--", alpha=0.65)
    ax.set_title("Aligned + normalized heating curves (heating-only, t >= 0)")
    ax.set_xlabel("Minutes since detected heating start")
    ax.set_ylabel("Normalized temperature (degC)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_file, bbox_inches="tight")
    plt.close(fig)


def _plot_pump_companion(
    ordered: list[HeatingCurveRecord],
    cmap_name: str,
    output_file: Path,
) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(11.5, 8), dpi=SAVE_DPI, sharex=False)
    cmap = plt.get_cmap(cmap_name, len(ordered))

    has_any_pump = False
    for i, rec in enumerate(ordered):
        color = cmap(i)
        if rec.raw_pump_rel is not None and not rec.raw_pump_rel.empty:
            axes[0].plot(rec.raw_pump_rel.index, rec.raw_pump_rel.values, color=color, lw=PUMP_LINE_WIDTH)
            has_any_pump = True
        if rec.aligned_pump_rel is not None and not rec.aligned_pump_rel.empty:
            axes[1].plot(rec.aligned_pump_rel.index, rec.aligned_pump_rel.values, color=color, lw=PUMP_LINE_WIDTH)
            has_any_pump = True

    axes[0].axvline(0.0, color="black", lw=1.0, ls="--", alpha=0.65)
    axes[0].set_title("Pump rate for raw extracted windows")
    axes[0].set_xlabel("Minutes relative to detected heating start")
    axes[0].set_ylabel("Pumping rate (m³/h)")
    axes[0].grid(True, alpha=0.3)

    axes[1].axvline(0.0, color="black", lw=1.0, ls="--", alpha=0.65)
    axes[1].set_title("Pump rate for aligned heating-only windows")
    axes[1].set_xlabel("Minutes since detected heating start")
    axes[1].set_ylabel("Pumping rate (m³/h)")
    axes[1].grid(True, alpha=0.3)

    if not has_any_pump:
        axes[0].text(0.5, 0.5, "No pump data available", transform=axes[0].transAxes, ha="center", va="center")
        axes[1].text(0.5, 0.5, "No pump data available", transform=axes[1].transAxes, ha="center", va="center")

    fig.tight_layout()
    fig.savefig(output_file, bbox_inches="tight")
    plt.close(fig)


def _selection_output_stem(selection: SelectionResult) -> str:
    return _selection_filename_token(selection)


def _print_summary(records: list[HeatingCurveRecord]) -> None:
    if not records:
        print("No heating curves detected.")
        return

    print("\nDetected heating curves:")
    for rec in records:
        print(
            f"- {rec.selection_key} | seed={rec.seed_ts} | start={rec.detected_start_ts} "
            f"({rec.start_method}) | baseline={rec.baseline_mean_c:.3f} degC | peak={rec.peak_aligned_c:.3f} degC"
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print(
        "Heating-curve extraction: treating each seed as an expected heating episode, "
        "then detecting the real start with a sustained-rise method."
    )

    base_dir = _read_config_dir(CONFIG_KEY_DATA_DIR)
    pickle_path = _pickle_file_from_base_dir(base_dir)
    channel_dfs = _load_combined_pickle(pickle_path)
    pump_series, pump_msg = _load_pump_rate_series()

    if pump_msg is not None:
        print(f"Pump data note: {pump_msg}")

    selections = _extract_selection_series(channel_dfs)
    output_dir = DATA_DIR

    for selection in selections:
        full_plot_file = _plot_full_series_with_pump(selection, pump_series, output_dir)

        records = _build_heating_records(selection, pump_series)
        ordered = _ordered_records(records)

        if not ordered:
            print(f"No usable heating curves extracted for {selection.selection_key}; skipping curve plots.")
            print(f"Saved full series plot: {full_plot_file}")
            continue

        stem = _selection_output_stem(selection)
        raw_file = output_dir / f"heat_curves_raw_{stem}.png"
        aligned_file = output_dir / f"heat_curves_aligned_normalized_{stem}.png"
        pump_file = output_dir / f"heat_curves_pump_companion_{stem}.png"

        _plot_raw_windows(ordered, CMAP_NAME, raw_file)
        _plot_aligned_normalized(ordered, CMAP_NAME, aligned_file)
        _plot_pump_companion(ordered, CMAP_NAME, pump_file)

        _print_summary(ordered)
        print(f"Saved full datetime plot: {full_plot_file}")
        print(f"Saved raw windows plot: {raw_file}")
        print(f"Saved aligned normalized plot: {aligned_file}")
        print(f"Saved pump companion plot: {pump_file}")


if __name__ == "__main__":
    main()
