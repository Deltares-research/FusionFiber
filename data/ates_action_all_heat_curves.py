#!/usr/bin/env python3
"""Detect, align, and compare all ATES heating curves from DTS data.

This version uses a fresh detection strategy built around what the heating
episodes share physically:
- a short stable local baseline before onset
- a clear upward break away from that baseline
- continued warming in the first minutes after onset

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
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import yaml

matplotlib.use("Agg")

# -----------------------------------------------------------------------------
# User configuration
# -----------------------------------------------------------------------------

CONFIG_KEY_DATA_DIR = "data_dir_ates_spui_en_afterspui"

SELECTIONS: list[dict[str, object]] = [
    {"channel": "channel 1", "distance_m": 546.5},
]

# Special-case rules already established during previous review.
AUTO_MIN_GAP_MINUTES = 60.0
AUTO_GAP_ENFORCE_FROM = "2026-04-16 16:00:00"
PRE_ENFORCE_MIN_GAP_MINUTES = 3.0
SPECIAL_FIRST_EPISODE_CAP_END = "2026-04-16 13:57:00"
# One-off cleanup for this dataset instance: remove two visually-off duplicate starts
# from the exceptional first two experiments on 2026-04-16.
EXCLUDED_START_TIMESTAMPS = [
    "2026-04-16 13:23:59",
    "2026-04-16 14:01:47",
]

# Window settings.
PRE_START_MINUTES = 5.0
TOTAL_WINDOW_MINUTES = 50.0

# Fresh onset detector settings.
DETECTION_SMOOTH_MINUTES = 1.5
BASELINE_WINDOW_MINUTES = 8.0
MIN_BASELINE_SAMPLES = 4
# Sustained-rise detection: evaluate 4 consecutive step-increases and anchor onset to
# the first strong step in that sequence. This avoids triggering on tiny pre-rise noise.
SUSTAINED_RISE_SAMPLES = 4
MIN_SUSTAINED_STEP_DEGC = 0.01
ONSET_ANCHOR_STEP_DEGC = 0.35
CONFIRM_WINDOW_MINUTES = 6.0
MIN_CONFIRM_RISE_DEGC = 0.8
MIN_EPISODE_RISE_DEGC = 2.0

# Normalization settings.
NORMALIZE_BASELINE_SAMPLES = 5
BASELINE_SPREAD_WARNING_DEGC = 0.5
SECOND_CURVE_BASELINE_MODE = "min-prestart"

# Plot settings.
CMAP_NAME = "viridis"
LINE_WIDTH = 1.8
PUMP_LINE_WIDTH = 2.4
PUMP_ALPHA = 0.5
SAVE_DPI = 300
FULL_TIMELINE_FIGSIZE = (130, 20)
PLOT_X_MAJOR_TICK_MINUTES = 5.0

# Pump data source settings.
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
    detected_start_ts: pd.Timestamp
    start_method: str
    raw_temp_rel: pd.Series
    raw_pump_rel: pd.Series | None
    normalized_rel: pd.Series
    aligned_norm_rel: pd.Series
    aligned_pump_rel: pd.Series | None
    baseline_mean_c: float
    peak_aligned_c: float
    peak_rise_c: float


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


def _selection_filename_token(selection: SelectionResult) -> str:
    channel_token = selection.channel.replace(" ", "-")
    dist_token = f"{selection.actual_distance_m:.2f}".replace(".", "p")
    return f"{channel_token}_fiber-{dist_token}m"


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
                full_temp_series=series.sort_index(),
            )
        )

    return selections


def _median_step_minutes(index: pd.DatetimeIndex) -> float:
    if len(index) < 2:
        return 1.0
    deltas = np.diff(index.view("i8")) / 60_000_000_000
    deltas = deltas[deltas > 0]
    if len(deltas) == 0:
        return 1.0
    return float(np.median(deltas))


def _smooth_series(series: pd.Series, smooth_minutes: float) -> pd.Series:
    step_min = _median_step_minutes(series.index)
    window_samples = max(3, int(round(smooth_minutes / max(step_min, 0.05))))
    return series.rolling(window=window_samples, center=False, min_periods=1).mean()


def _extract_relative_segment(series: pd.Series, start_ts: pd.Timestamp) -> pd.Series:
    win_start = start_ts - pd.Timedelta(minutes=PRE_START_MINUTES)
    win_end = win_start + pd.Timedelta(minutes=TOTAL_WINDOW_MINUTES)
    segment = series.loc[(series.index >= win_start) & (series.index <= win_end)].copy()
    if segment.empty:
        return segment

    rel_min = (segment.index - start_ts).total_seconds() / 60.0
    segment.index = pd.Index(rel_min, name="minutes")
    return segment


def _cap_segment_absolute_end(segment: pd.Series, start_ts: pd.Timestamp, abs_end_ts: pd.Timestamp) -> pd.Series:
    if segment.empty:
        return segment
    abs_index = pd.to_datetime(start_ts) + pd.to_timedelta(segment.index.values, unit="m")
    keep = abs_index <= pd.to_datetime(abs_end_ts)
    if not np.any(keep):
        return segment.iloc[0:0].copy()
    return segment.loc[keep].copy()


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
    rel = pd.Series(aligned.values, index=temp_segment.index.copy(), name="pump_rate").dropna()
    return rel if not rel.empty else None


def _segment_baseline(segment: pd.Series, mode: str) -> tuple[float, float]:
    pre = segment.loc[(segment.index >= -PRE_START_MINUTES) & (segment.index < 0.0)]
    if pre.empty:
        n = min(NORMALIZE_BASELINE_SAMPLES, len(segment))
        pre = segment.iloc[:n]

    spread = float(pre.max() - pre.min()) if not pre.empty else float("nan")
    if mode == "min-prestart":
        baseline = float(pre.min())
    else:
        baseline = float(pre.median())
    return baseline, spread


def _episode_metrics(segment: pd.Series) -> dict[str, float]:
    baseline, spread = _segment_baseline(segment, "median-prestart")
    post = segment.loc[segment.index >= 0.0]
    if post.empty:
        return {
            "baseline": baseline,
            "spread": spread,
            "confirm_rise": 0.0,
            "peak_rise": 0.0,
        }

    early = post.loc[post.index <= CONFIRM_WINDOW_MINUTES]
    confirm_rise = float(early.max() - baseline) if not early.empty else 0.0
    peak_rise = float(post.max() - baseline)
    return {
        "baseline": baseline,
        "spread": spread,
        "confirm_rise": confirm_rise,
        "peak_rise": peak_rise,
    }


def _build_detection_frame(temp_series: pd.Series) -> pd.DataFrame:
    ts = temp_series.sort_index().dropna()
    smooth = _smooth_series(ts, DETECTION_SMOOTH_MINUTES)
    shifted = smooth.shift(1)
    baseline = shifted.rolling(f"{BASELINE_WINDOW_MINUTES}min", min_periods=MIN_BASELINE_SAMPLES).median()
    return pd.DataFrame(
        {
            "temp": ts,
            "smooth": smooth,
            "baseline": baseline,
        }
    )


def _step_rises_window(smooth_values: np.ndarray, idx: int, num_steps: int) -> np.ndarray | None:
    """Return consecutive step rises starting at idx, or None if window is incomplete."""
    end_idx = idx + num_steps
    if end_idx >= len(smooth_values):
        return None
    window_values = smooth_values[idx : end_idx + 1]
    return np.diff(window_values)


def _first_anchor_offset(step_rises: np.ndarray) -> int | None:
    """Find first strong step inside a sustained-rise sequence.

    Returns the offset relative to the start index where the onset should be placed.
    """
    if np.any(step_rises < MIN_SUSTAINED_STEP_DEGC):
        return None
    strong_steps = np.flatnonzero(step_rises >= ONSET_ANCHOR_STEP_DEGC)
    if strong_steps.size == 0:
        return None
    return int(strong_steps[0])


def _candidate_start_times(frame: pd.DataFrame) -> list[pd.Timestamp]:
    ready = frame["baseline"].notna()
    smooth_values = frame["smooth"].values

    onset_mask = pd.Series(False, index=frame.index)
    for idx in range(len(frame)):
        step_rises = _step_rises_window(smooth_values, idx, SUSTAINED_RISE_SAMPLES)
        if step_rises is None:
            continue

        anchor_offset = _first_anchor_offset(step_rises)
        if anchor_offset is None:
            continue

        anchor_idx = idx + anchor_offset
        if anchor_idx >= len(frame):
            continue
        if not ready.iloc[anchor_idx]:
            continue

        onset_mask.iloc[anchor_idx] = True

    onset_ts = [pd.Timestamp(ts) for ts in frame.index[onset_mask]]
    return list(dict.fromkeys(onset_ts))


def _min_gap_minutes_for(start_ts: pd.Timestamp) -> float:
    enforce_from = pd.to_datetime(AUTO_GAP_ENFORCE_FROM)
    return AUTO_MIN_GAP_MINUTES if start_ts >= enforce_from else PRE_ENFORCE_MIN_GAP_MINUTES


def _detect_episode_starts(temp_series: pd.Series) -> list[pd.Timestamp]:
    ts = temp_series.sort_index().dropna()
    if ts.empty:
        return []

    frame = _build_detection_frame(ts)
    candidates = _candidate_start_times(frame)
    if not candidates:
        return []

    accepted: list[pd.Timestamp] = []
    for candidate_ts in candidates:
        if accepted:
            gap_minutes = (candidate_ts - accepted[-1]).total_seconds() / 60.0
            if gap_minutes < _min_gap_minutes_for(candidate_ts):
                continue

        raw_seg = _extract_relative_segment(ts, candidate_ts)
        if raw_seg.empty:
            continue

        metrics = _episode_metrics(raw_seg)
        if metrics["confirm_rise"] < MIN_CONFIRM_RISE_DEGC:
            continue
        if metrics["peak_rise"] < MIN_EPISODE_RISE_DEGC:
            continue

        if accepted and abs((candidate_ts - accepted[-1]).total_seconds()) <= 1.0:
            continue

        accepted.append(candidate_ts)

    return accepted


def _normalize_curves(raw_segments: list[pd.Series], baseline_modes: list[str]) -> tuple[list[pd.Series], float, list[float]]:
    if len(raw_segments) != len(baseline_modes):
        raise ValueError("raw_segments and baseline_modes must have equal length")

    baseline_means: list[float] = []
    normalized: list[pd.Series] = []
    for idx, (segment, mode) in enumerate(zip(raw_segments, baseline_modes)):
        if segment.empty:
            baseline_means.append(np.nan)
            normalized.append(segment)
            continue

        baseline_mean, baseline_spread = _segment_baseline(segment, mode)
        baseline_means.append(baseline_mean)
        if baseline_spread > BASELINE_SPREAD_WARNING_DEGC:
            logging.warning(
                "Curve %d baseline spread %.3f degC (> %.3f degC)",
                idx,
                baseline_spread,
                BASELINE_SPREAD_WARNING_DEGC,
            )

    valid_baselines = [value for value in baseline_means if np.isfinite(value)]
    if not valid_baselines:
        raise ValueError("Unable to compute baseline means for normalization.")

    target_temp = float(np.mean(valid_baselines))
    for segment, baseline_mean in zip(raw_segments, baseline_means):
        if segment.empty or not np.isfinite(baseline_mean):
            normalized.append(segment)
            continue
        normalized.append(segment + (target_temp - baseline_mean))

    return normalized, target_temp, baseline_means


def _build_heating_records(selection: SelectionResult, pump_series: pd.Series | None) -> list[HeatingCurveRecord]:
    start_ts_list = _detect_episode_starts(selection.full_temp_series)
    if not start_ts_list:
        return []

    excluded_ts = {pd.Timestamp(ts) for ts in EXCLUDED_START_TIMESTAMPS}
    if excluded_ts:
        before_count = len(start_ts_list)
        start_ts_list = [ts for ts in start_ts_list if pd.Timestamp(ts) not in excluded_ts]
        removed = before_count - len(start_ts_list)
        if removed > 0:
            logging.info("Removed %d one-off excluded start(s) for this dataset instance.", removed)

    special_cap_end = pd.to_datetime(SPECIAL_FIRST_EPISODE_CAP_END)
    special_day = special_cap_end.normalize()
    special_indices = [
        idx for idx, start_ts in enumerate(start_ts_list)
        if pd.to_datetime(start_ts).normalize() == special_day
    ]
    special_idx = min(special_indices) if special_indices else None

    kept_start_ts: list[pd.Timestamp] = []
    raw_segments: list[pd.Series] = []
    raw_pumps: list[pd.Series | None] = []
    peak_rises: list[float] = []

    for idx, start_ts in enumerate(start_ts_list):
        raw_seg = _extract_relative_segment(selection.full_temp_series, start_ts)
        if special_idx is not None and idx == special_idx:
            raw_seg = _cap_segment_absolute_end(raw_seg, start_ts, special_cap_end)
        if raw_seg.empty:
            continue

        metrics = _episode_metrics(raw_seg)
        if metrics["confirm_rise"] < MIN_CONFIRM_RISE_DEGC:
            continue
        if metrics["peak_rise"] < MIN_EPISODE_RISE_DEGC:
            continue

        raw_pump = _align_pump_to_temp_window(pump_series, raw_seg, start_ts)
        kept_start_ts.append(start_ts)
        raw_segments.append(raw_seg)
        raw_pumps.append(raw_pump)
        peak_rises.append(metrics["peak_rise"])

    if not raw_segments:
        return []

    baseline_modes = ["median-prestart"] * len(raw_segments)
    if len(baseline_modes) >= 2 and SECOND_CURVE_BASELINE_MODE == "min-prestart":
        baseline_modes[1] = "min-prestart"

    normalized_segments, target_temp, baseline_means = _normalize_curves(raw_segments, baseline_modes)
    logging.info(
        "Normalization target for %s: %.4f degC (average of per-curve baselines)",
        selection.selection_key,
        target_temp,
    )

    records: list[HeatingCurveRecord] = []
    for start_ts, raw_seg, raw_pump, norm_seg, baseline_mean, peak_rise in zip(
        kept_start_ts,
        raw_segments,
        raw_pumps,
        normalized_segments,
        baseline_means,
        peak_rises,
    ):
        aligned_norm = norm_seg.loc[norm_seg.index >= 0.0].copy()
        aligned_norm.index = pd.Index(aligned_norm.index.values, name="minutes")

        aligned_pump = None
        if raw_pump is not None:
            aligned_pump = raw_pump.loc[raw_pump.index >= 0.0].copy()
            if aligned_pump.empty:
                aligned_pump = None

        peak_aligned = float(aligned_norm.max()) if not aligned_norm.empty else float("nan")
        records.append(
            HeatingCurveRecord(
                selection_key=selection.selection_key,
                channel=selection.channel,
                actual_distance_m=selection.actual_distance_m,
                detected_start_ts=start_ts,
                start_method="sustained-rise-anchored+forward-confirmation",
                raw_temp_rel=raw_seg,
                raw_pump_rel=raw_pump,
                normalized_rel=norm_seg,
                aligned_norm_rel=aligned_norm,
                aligned_pump_rel=aligned_pump,
                baseline_mean_c=float(baseline_mean),
                peak_aligned_c=peak_aligned,
                peak_rise_c=float(peak_rise),
            )
        )

    return records


def _ordered_records(records: list[HeatingCurveRecord]) -> list[HeatingCurveRecord]:
    return sorted(
        records,
        key=lambda rec: (np.nan_to_num(rec.peak_aligned_c, nan=-1e9), rec.detected_start_ts.value),
    )


def _pump_rate_at_offset(pump_rel: pd.Series | None, offset_minutes: float) -> float | None:
    if pump_rel is None or pump_rel.empty:
        return None
    value = (
        pump_rel.reindex(pump_rel.index.union([offset_minutes]))
        .sort_index()
        .interpolate(method="index")
        .get(offset_minutes)
    )
    if pd.isna(value):
        return None
    return float(value)


def _curve_legend_label(record: HeatingCurveRecord, curve_id: int, q_offset_minutes: float) -> str:
    q_value = _pump_rate_at_offset(record.raw_pump_rel, q_offset_minutes)
    q_text = f"{q_value:.1f}" if q_value is not None else "NA"
    return f"t{curve_id} | Tmax = {record.peak_aligned_c:.1f} \N{DEGREE SIGN}C | Q = {q_text} m3/h"


def _draw_vertical_marker(ax: plt.Axes, x: float = 0.0) -> None:
    y0, y1 = ax.get_ylim()
    ax.plot([x, x], [y0, y1], color="black", lw=1.0, ls="--", alpha=0.65, zorder=3)


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

    valid_idx = selection.full_temp_series.dropna().index
    if len(valid_idx) > 1:
        ax.set_xlim(valid_idx[0], valid_idx[-1])

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
    out = output_dir / f"heat_curves_full_datetime_{_selection_filename_token(selection)}.png"
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    return out


def _plot_raw_windows(
    ordered: list[HeatingCurveRecord],
    cmap_name: str,
    output_file: Path,
    *,
    title: str | None = None,
    q_offset_minutes: float = 2.0,
) -> None:
    fig, ax = plt.subplots(figsize=(11.5, 6), dpi=SAVE_DPI)
    cmap = plt.get_cmap(cmap_name, len(ordered))
    n_curves = len(ordered)

    for idx, rec in enumerate(ordered):
        color = cmap(idx)
        ax.plot(
            rec.raw_temp_rel.index,
            rec.raw_temp_rel.values,
            color=color,
            lw=LINE_WIDTH,
            label=_curve_legend_label(rec, n_curves - idx, q_offset_minutes),
        )

    _draw_vertical_marker(ax, 0.0)
    ax.set_title(title or "Raw extracted heating windows (includes pre-start)")
    ax.set_xlabel("Time (minutes)")
    ax.set_ylabel("Temperature (\N{DEGREE SIGN}C)")
    ax.xaxis.set_major_locator(mticker.MultipleLocator(PLOT_X_MAJOR_TICK_MINUTES))
    ax.grid(True, which="major", alpha=0.35)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles[::-1], labels[::-1], loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_file)
    plt.close(fig)


def _plot_aligned_normalized(
    ordered: list[HeatingCurveRecord],
    cmap_name: str,
    output_file: Path,
    *,
    title: str | None = None,
    q_offset_minutes: float = 2.0,
) -> None:
    fig, ax = plt.subplots(figsize=(11.5, 6), dpi=SAVE_DPI)
    cmap = plt.get_cmap(cmap_name, len(ordered))
    n_curves = len(ordered)

    for idx, rec in enumerate(ordered):
        color = cmap(idx)
        ax.plot(
            rec.aligned_norm_rel.index,
            rec.aligned_norm_rel.values,
            color=color,
            lw=LINE_WIDTH,
            label=_curve_legend_label(rec, n_curves - idx, q_offset_minutes),
        )

    ax.set_title(title or "Aligned + normalized heating curves (heating-only, t >= 0)")
    ax.set_xlabel("Time (minutes)")
    ax.set_ylabel("Temperature (\N{DEGREE SIGN}C)")
    ax.set_xlim(left=0.0)
    ax.set_ylim(bottom=10.0, top=40.0)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(PLOT_X_MAJOR_TICK_MINUTES))
    ax.grid(True, which="major", alpha=0.35)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles[::-1], labels[::-1], loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_file)
    plt.close(fig)


def _plot_pump_companion(ordered: list[HeatingCurveRecord], cmap_name: str, output_file: Path) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(11.5, 8), dpi=SAVE_DPI, sharex=False)
    cmap = plt.get_cmap(cmap_name, len(ordered))

    has_any_pump = False
    for idx, rec in enumerate(ordered):
        color = cmap(idx)
        if rec.raw_pump_rel is not None and not rec.raw_pump_rel.empty:
            axes[0].plot(rec.raw_pump_rel.index, rec.raw_pump_rel.values, color=color, lw=PUMP_LINE_WIDTH)
            has_any_pump = True
        if rec.aligned_pump_rel is not None and not rec.aligned_pump_rel.empty:
            axes[1].plot(rec.aligned_pump_rel.index, rec.aligned_pump_rel.values, color=color, lw=PUMP_LINE_WIDTH)
            has_any_pump = True

    _draw_vertical_marker(axes[0], 0.0)
    axes[0].set_title("Pump rate for raw extracted windows")
    axes[0].set_xlabel("Minutes relative to detected heating start")
    axes[0].set_ylabel("Pumping rate (m³/h)")
    axes[0].xaxis.set_major_locator(mticker.MultipleLocator(PLOT_X_MAJOR_TICK_MINUTES))
    axes[0].grid(True, alpha=0.3)

    _draw_vertical_marker(axes[1], 0.0)
    axes[1].set_title("Pump rate for aligned heating-only windows")
    axes[1].set_xlabel("Minutes since detected heating start")
    axes[1].set_ylabel("Pumping rate (m³/h)")
    axes[1].xaxis.set_major_locator(mticker.MultipleLocator(PLOT_X_MAJOR_TICK_MINUTES))
    axes[1].grid(True, alpha=0.3)

    if not has_any_pump:
        axes[0].text(0.5, 0.5, "No pump data available", transform=axes[0].transAxes, ha="center", va="center")
        axes[1].text(0.5, 0.5, "No pump data available", transform=axes[1].transAxes, ha="center", va="center")

    fig.tight_layout()
    fig.savefig(output_file)
    plt.close(fig)


def _print_summary(records: list[HeatingCurveRecord]) -> None:
    if not records:
        print("No heating curves detected.")
        return

    print("\nDetected heating curves:")
    for rec in records:
        print(
            f"- {rec.selection_key} | start={rec.detected_start_ts} | "
            f"baseline={rec.baseline_mean_c:.3f} degC | peak={rec.peak_aligned_c:.3f} degC | "
            f"rise={rec.peak_rise_c:.3f} degC"
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    print(
        "Heating-curve extraction: scanning the full series with a local-baseline onset detector "
        "and forward rise confirmation."
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

        stem = _selection_filename_token(selection)
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
