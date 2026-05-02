#!/usr/bin/env python3
"""Build delta-T imshow over a fiber interval for detected heating episodes.

Method summary:
- Detect episode starts with the same detector used in ates_action_select_heat_curves.py.
- Use one reference distance to define the episode grid.
- Also detect starts per distance and warn when nearest start differs > 1 minute.
- For each distance and episode:
  - compute start temperature as the mean of the 3 samples closest to t = -5 min
  - compute max temperature in t in [0, 50] min (within available window)
  - delta T = Tmax - Tstart
- Assign each delta-T value to episode timestamp (start + 15 min).
- Plot delta-T as imshow with a secondary depth-bsl axis.
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path

import matplotlib
import matplotlib.colors as mcolors
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import ates_action_all_heat_curves as core

matplotlib.use("Agg")


# -----------------------------------------------------------------------------
# User configuration
# -----------------------------------------------------------------------------

CHANNEL = "channel 1"

FIBER_LENGTH_MIN_M = 538.5
FIBER_LENGTH_MAX_M = 551.8

DEPTH_BSL_MIN_M = 168.6
DEPTH_BSL_MAX_M = 181.0

# Optional reference distance for episode-grid detection.
# Use None to auto-pick nearest to interval midpoint.
REFERENCE_FIBER_DISTANCE_M: float | None = None

START_TEMP_TARGET_MINUTES = -5.0
START_TEMP_SAMPLES = 3
# One-off special case: second high-flow test is too close to the first,
# so the -5 min baseline can be contaminated by the previous peak.
SPECIAL_MIN_PREZERO_STARTS = [
    "2026-04-16 13:58:45",
]
SPECIAL_MIN_PREZERO_STARTS_TS = {pd.Timestamp(ts) for ts in SPECIAL_MIN_PREZERO_STARTS}
DELTA_T_ASSIGN_OFFSET_MINUTES = 15.0
MAX_TEMP_WINDOW_MINUTES = 50.0

START_MISMATCH_WARNING_MINUTES = 1.0
ENABLE_QC_WARNINGS = False

IMSHOW_CMAP = "turbo"
RELATIVE_IMSHOW_CMAP = "mako"
RELATIVE_IMSHOW_CMAP_TURBO = "turbo"
RELATIVE_CBAR_LABEL = "Delta T relative to dominant profile (°C)"
RELATIVE_OUTPUT_SUFFIX = "_relative_to_dominant_profile"
RELATIVE_OUTPUT_SUFFIX_TURBO = "_relative_to_dominant_profile_turbo"
RELATIVE_SCALE_PERCENTILES = (5.0, 95.0)
RELATIVE_CLIP_FLOOR = -5.0
RELATIVE_CLIP_CEILING = -1.5
SAVE_DPI = 300
FIGSIZE = (26, 7)

# Typography / spacing
TITLE_FONT_SIZE = 20
LABEL_FONT_SIZE = 16
TICK_FONT_SIZE = 14
CBAR_LABEL_FONT_SIZE = 16
CBAR_TICK_FONT_SIZE = 13


def _distance_interval_df(channel_dfs: dict[str, pd.DataFrame], channel: str, dmin: float, dmax: float) -> pd.DataFrame:
    if channel not in channel_dfs:
        raise KeyError(f"Requested channel not found in pickle: {channel}")

    df = channel_dfs[channel].copy()
    cols = pd.to_numeric(df.columns, errors="coerce")
    mask = (~np.isnan(cols)) & (cols >= min(dmin, dmax)) & (cols <= max(dmin, dmax))
    if not mask.any():
        raise ValueError(
            f"No distance columns found in [{min(dmin, dmax):.2f}, {max(dmin, dmax):.2f}] m for {channel}."
        )

    out = df.loc[:, mask].copy()
    out.columns = cols[mask].astype(float)
    out = out.sort_index().sort_index(axis=1)
    return out


def _choose_reference_distance(distances: np.ndarray, requested: float | None) -> float:
    if requested is None:
        requested = float((np.min(distances) + np.max(distances)) / 2.0)
    idx = int(np.abs(distances - float(requested)).argmin())
    return float(distances[idx])


def _three_point_start_temp(raw_segment: pd.Series, target_minutes: float, n_samples: int) -> float | None:
    if raw_segment.empty or len(raw_segment) < n_samples:
        return None
    idx_values = raw_segment.index.to_numpy(dtype=float)
    nearest = np.argsort(np.abs(idx_values - float(target_minutes)))[:n_samples]
    values = pd.to_numeric(raw_segment.iloc[nearest], errors="coerce").dropna()
    if len(values) < n_samples:
        return None
    return float(values.mean())


def _min_prezero_start_temp(raw_segment: pd.Series) -> float | None:
    if raw_segment.empty:
        return None
    pre = pd.to_numeric(raw_segment.loc[raw_segment.index < 0.0], errors="coerce").dropna()
    if pre.empty:
        return None
    return float(pre.min())


def _episode_delta_t(temp_series: pd.Series, start_ts: pd.Timestamp) -> float | None:
    raw_seg = core._extract_relative_segment(temp_series, start_ts)
    if raw_seg.empty:
        return None

    if pd.Timestamp(start_ts) in SPECIAL_MIN_PREZERO_STARTS_TS:
        start_temp = _min_prezero_start_temp(raw_seg)
    else:
        start_temp = _three_point_start_temp(raw_seg, START_TEMP_TARGET_MINUTES, START_TEMP_SAMPLES)

    if start_temp is None:
        return None

    heat_seg = raw_seg.loc[(raw_seg.index >= 0.0) & (raw_seg.index <= MAX_TEMP_WINDOW_MINUTES)]
    heat_seg = pd.to_numeric(heat_seg, errors="coerce").dropna()
    if heat_seg.empty:
        return None

    max_temp = float(heat_seg.max())
    return max_temp - float(start_temp)


def _warn_start_mismatch(
    distance_m: float,
    reference_starts: list[pd.Timestamp],
    detected_starts: list[pd.Timestamp],
    warn_minutes: float,
) -> None:
    if not ENABLE_QC_WARNINGS:
        return

    if not detected_starts:
        logging.warning("Distance %.2f m: no starts detected for QC comparison.", distance_m)
        return

    if len(detected_starts) != len(reference_starts):
        logging.warning(
            "Distance %.2f m: start count differs from reference (%d vs %d).",
            distance_m,
            len(detected_starts),
            len(reference_starts),
        )

    for ref_ts in reference_starts:
        nearest = min(detected_starts, key=lambda ts: abs((ts - ref_ts).total_seconds()))
        delta_min = abs((nearest - ref_ts).total_seconds()) / 60.0
        if delta_min > warn_minutes:
            logging.warning(
                "Distance %.2f m: start mismatch %.2f min (ref=%s, nearest=%s).",
                distance_m,
                delta_min,
                ref_ts,
                nearest,
            )


def _center_times_from_starts(starts: list[pd.Timestamp], offset_minutes: float) -> list[pd.Timestamp]:
    centers = [pd.Timestamp(ts) + pd.Timedelta(minutes=offset_minutes) for ts in starts]
    if len(centers) != len(set(centers)):
        raise ValueError(
            "Duplicate center timestamps found after assigning start + 15 minutes. "
            "This should not happen; aborting as requested."
        )
    return centers


def _depth_from_fiber(fiber_vals: np.ndarray, fiber_min: float, fiber_max: float, depth_min: float, depth_max: float) -> np.ndarray:
    if abs(fiber_max - fiber_min) < 1e-12:
        return np.full_like(fiber_vals, fill_value=depth_min, dtype=float)
    scale = (depth_max - depth_min) / (fiber_max - fiber_min)
    return depth_min + (fiber_vals - fiber_min) * scale


def _fiber_from_depth(depth_vals: np.ndarray, fiber_min: float, fiber_max: float, depth_min: float, depth_max: float) -> np.ndarray:
    if abs(depth_max - depth_min) < 1e-12:
        return np.full_like(depth_vals, fill_value=fiber_min, dtype=float)
    scale = (fiber_max - fiber_min) / (depth_max - depth_min)
    return fiber_min + (depth_vals - depth_min) * scale


def _plot_imshow(
    matrix: np.ndarray,
    distances: np.ndarray,
    center_times: list[pd.Timestamp],
    pump_rates: np.ndarray | None,
    channel: str,
    output_png: Path,
    *,
    cmap_name: str,
    cbar_label: str,
    vmin: float | None = None,
    vmax: float | None = None,
) -> None:
    fig = plt.figure(figsize=FIGSIZE, dpi=SAVE_DPI, constrained_layout=True)
    gs = fig.add_gridspec(
        nrows=2,
        ncols=2,
        width_ratios=[40, 1],
        height_ratios=[3, 1],
        wspace=0.03,
        hspace=0.03,
    )
    ax = fig.add_subplot(gs[0, 0])
    ax_pump = fig.add_subplot(gs[1, 0], sharex=ax)
    cax = fig.add_subplot(gs[0, 1])

    x_nums = mdates.date2num(pd.to_datetime(center_times).to_pydatetime())
    if len(x_nums) == 1:
        half_width_days = (1.0 / 60.0) / 2.0
        x0, x1 = x_nums[0] - half_width_days, x_nums[0] + half_width_days
    else:
        x0, x1 = float(x_nums.min()), float(x_nums.max())

    y0, y1 = float(distances.min()), float(distances.max())

    im = ax.imshow(
        matrix,
        aspect="auto",
        origin="lower",
        extent=[x0, x1, y0, y1],
        cmap=_resolve_cmap(cmap_name),
        interpolation="kaiser",
        vmin=vmin,
        vmax=vmax,
    )

    ax.invert_yaxis()
    fiber_min = float(distances.min())
    fiber_max = float(distances.max())

    # Primary y-axis: depth below surface (left)
    depth_ticks = np.linspace(DEPTH_BSL_MIN_M, DEPTH_BSL_MAX_M, 6)
    fiber_ticks = _fiber_from_depth(depth_ticks, fiber_min, fiber_max, DEPTH_BSL_MIN_M, DEPTH_BSL_MAX_M)
    ax.set_yticks(fiber_ticks)
    ax.set_yticklabels([f"{d:.0f}" for d in depth_ticks])
    ax.set_ylabel("Depth below surface (m)", fontsize=LABEL_FONT_SIZE, labelpad=2)
    ax.tick_params(axis="both", labelsize=TICK_FONT_SIZE)

    # Secondary y-axis: fiber length (right)
    secax = ax.secondary_yaxis(
        "right",
        functions=(
            lambda y: y,
            lambda y: y,
        ),
    )
    secax.set_ylabel("Fiber length (m)", fontsize=LABEL_FONT_SIZE, labelpad=2)
    secax.tick_params(axis="y", labelsize=TICK_FONT_SIZE)

    ax.xaxis_date()
    ax.set_xlim(x0, x1)
    ax.tick_params(axis="x", labelbottom=False)

    if pump_rates is not None and len(pump_rates) == len(center_times):
        ax_pump.plot(center_times, pump_rates, color="black", lw=1.2)
        ax_pump.fill_between(center_times, pump_rates, 0.0, color="lightblue", alpha=0.7)
    else:
        ax_pump.text(0.5, 0.5, "No pump data available", transform=ax_pump.transAxes, ha="center", va="center")

    ax_pump.set_ylabel("Pump\n(m3/h)", fontsize=LABEL_FONT_SIZE, labelpad=2)
    ax_pump.grid(True, axis="y", alpha=0.3)
    ax_pump.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax_pump.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax_pump.tick_params(
        axis="x",
        rotation=0,
        top=True,
        labeltop=True,
        bottom=False,
        labelbottom=False,
        labelsize=TICK_FONT_SIZE,
        pad=1,
    )
    ax_pump.tick_params(axis="y", labelsize=TICK_FONT_SIZE)
    ax_pump.margins(x=0)

    cbar = fig.colorbar(im, cax=cax)
    cbar.set_label(cbar_label, fontsize=CBAR_LABEL_FONT_SIZE)
    cbar.ax.tick_params(labelsize=CBAR_TICK_FONT_SIZE)

    fig.savefig(output_png)
    plt.close(fig)


def _resolve_cmap(name: str):
    """Resolve colormap name with a fallback for seaborn-style 'mako'."""
    if str(name).lower() == "mako":
        # Approximation of seaborn 'mako' for environments where it is unavailable.
        return mcolors.LinearSegmentedColormap.from_list(
            "mako_approx",
            ["#0b0f2f", "#243b73", "#2f6b8d", "#55a38b", "#9fd28f", "#dff2b0"],
            N=256,
        )
    return name


def _robust_color_limits(matrix: np.ndarray, q_low: float, q_high: float) -> tuple[float | None, float | None]:
    valid = matrix[np.isfinite(matrix)]
    if valid.size == 0:
        return None, None
    vmin = float(np.percentile(valid, q_low))
    vmax = float(np.percentile(valid, q_high))
    if np.isclose(vmin, vmax):
        return None, None
    return vmin, vmax


def _dominant_profile_index(matrix: np.ndarray) -> tuple[int, np.ndarray, np.ndarray]:
    """Select the most dominant time profile by depth-wise win count.

    For each depth, determine which time column has the highest Delta T.
    The dominant profile is the time with the largest number of depth wins.
    Ties are split equally and then broken using summed winning margins.
    """
    if matrix.ndim != 2:
        raise ValueError("matrix must be 2D (depth x time)")

    n_depths, n_times = matrix.shape
    wins = np.zeros(n_times, dtype=float)
    margins = np.zeros(n_times, dtype=float)

    for i in range(n_depths):
        row = matrix[i, :]
        valid = np.isfinite(row)
        if not np.any(valid):
            continue

        valid_vals = row[valid]
        row_max = float(np.max(valid_vals))
        winner_mask = valid & np.isclose(row, row_max, rtol=1e-10, atol=1e-12)
        winner_idx = np.flatnonzero(winner_mask)
        if winner_idx.size == 0:
            continue

        vote = 1.0 / float(winner_idx.size)
        wins[winner_idx] += vote

        remaining = row[valid & ~winner_mask]
        second_best = float(np.max(remaining)) if remaining.size > 0 else row_max
        margin = max(0.0, row_max - second_best)
        margins[winner_idx] += margin * vote

    if not np.any(np.isfinite(wins)):
        raise ValueError("Could not determine dominant profile from matrix.")

    # Primary criterion: win count. Secondary: summed margins.
    best_wins = np.nanmax(wins)
    candidates = np.flatnonzero(np.isclose(wins, best_wins, rtol=1e-12, atol=1e-12))
    if candidates.size == 1:
        best_idx = int(candidates[0])
    else:
        best_idx = int(candidates[np.argmax(margins[candidates])])

    reference_profile = matrix[:, best_idx].copy()
    return best_idx, reference_profile, wins


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    base_dir = core._read_config_dir(core.CONFIG_KEY_DATA_DIR)
    pickle_path = core._pickle_file_from_base_dir(base_dir)
    channel_dfs = core._load_combined_pickle(pickle_path)
    pump_series, _ = core._load_pump_rate_series()

    interval_df = _distance_interval_df(channel_dfs, CHANNEL, FIBER_LENGTH_MIN_M, FIBER_LENGTH_MAX_M)
    distances = interval_df.columns.to_numpy(dtype=float)

    reference_distance = _choose_reference_distance(distances, REFERENCE_FIBER_DISTANCE_M)
    ref_series = pd.to_numeric(interval_df[reference_distance], errors="coerce").dropna().sort_index()
    _excluded = {pd.Timestamp(ts) for ts in core.EXCLUDED_START_TIMESTAMPS}
    reference_starts = [ts for ts in core._detect_episode_starts(ref_series) if ts not in _excluded]
    if not reference_starts:
        raise ValueError("No heating episodes detected on the reference distance.")

    center_times = _center_times_from_starts(reference_starts, DELTA_T_ASSIGN_OFFSET_MINUTES)

    delta_t_matrix = np.full((len(distances), len(reference_starts)), np.nan, dtype=float)
    for i, distance_m in enumerate(distances):
        series = pd.to_numeric(interval_df[distance_m], errors="coerce").dropna().sort_index()

        if ENABLE_QC_WARNINGS:
            detected_here = [ts for ts in core._detect_episode_starts(series) if ts not in _excluded]
            _warn_start_mismatch(distance_m, reference_starts, detected_here, START_MISMATCH_WARNING_MINUTES)

        for j, start_ts in enumerate(reference_starts):
            delta_t = _episode_delta_t(series, start_ts)
            if delta_t is None:
                continue
            delta_t_matrix[i, j] = float(delta_t)

    # Build matrix referenced to one dominant vertical profile (full profile subtraction).
    dominant_idx, dominant_profile, dominant_wins = _dominant_profile_index(delta_t_matrix)
    relative_matrix = delta_t_matrix - dominant_profile[:, np.newaxis]

    pump_rates = None
    if pump_series is not None and not pump_series.empty:
        center_index = pd.DatetimeIndex(center_times)
        pump_aligned = (
            pump_series.reindex(pump_series.index.union(center_index))
            .sort_index()
            .interpolate(method="time")
            .reindex(center_index)
        )
        pump_rates = pump_aligned.to_numpy(dtype=float)

    output_dir = core.DATA_DIR
    channel_token = CHANNEL.replace(" ", "-")
    stem = f"{channel_token}_fiber-{distances.min():.2f}_to_{distances.max():.2f}".replace(".", "p")
    output_png = output_dir / f"delta_t_imshow_{stem}.png"
    output_pkl = output_dir / f"delta_t_imshow_{stem}.pickle"
    output_png_relative = output_dir / f"delta_t_imshow_{stem}{RELATIVE_OUTPUT_SUFFIX}.png"
    output_pkl_relative = output_dir / f"delta_t_imshow_{stem}{RELATIVE_OUTPUT_SUFFIX}.pickle"
    output_png_relative_turbo = output_dir / f"delta_t_imshow_{stem}{RELATIVE_OUTPUT_SUFFIX_TURBO}.png"

    _plot_imshow(
        delta_t_matrix,
        distances,
        center_times,
        pump_rates,
        CHANNEL,
        output_png,
        cmap_name=IMSHOW_CMAP,
        cbar_label="Delta T (°C)",
    )

    rel_vmin, rel_vmax = _robust_color_limits(
        relative_matrix,
        RELATIVE_SCALE_PERCENTILES[0],
        RELATIVE_SCALE_PERCENTILES[1],
    )

    relative_matrix_plot = relative_matrix.copy()
    clip_floor = RELATIVE_CLIP_FLOOR if rel_vmin is None else max(rel_vmin, RELATIVE_CLIP_FLOOR)
    clip_ceiling = RELATIVE_CLIP_CEILING if rel_vmax is None else min(rel_vmax, RELATIVE_CLIP_CEILING)
    relative_matrix_plot = np.clip(relative_matrix_plot, clip_floor, clip_ceiling)
    rel_vmin = clip_floor
    rel_vmax = clip_ceiling

    _plot_imshow(
        relative_matrix_plot,
        distances,
        center_times,
        pump_rates,
        CHANNEL,
        output_png_relative,
        cmap_name=RELATIVE_IMSHOW_CMAP,
        cbar_label=RELATIVE_CBAR_LABEL,
        vmin=rel_vmin,
        vmax=rel_vmax,
    )
    _plot_imshow(
        relative_matrix_plot,
        distances,
        center_times,
        pump_rates,
        CHANNEL,
        output_png_relative_turbo,
        cmap_name=RELATIVE_IMSHOW_CMAP_TURBO,
        cbar_label=RELATIVE_CBAR_LABEL,
        vmin=rel_vmin,
        vmax=rel_vmax,
    )

    payload = {
        "channel": CHANNEL,
        "fiber_length_interval_m": [float(distances.min()), float(distances.max())],
        "depth_bsl_interval_m": [float(DEPTH_BSL_MIN_M), float(DEPTH_BSL_MAX_M)],
        "reference_fiber_distance_m": float(reference_distance),
        "reference_starts": [pd.Timestamp(ts) for ts in reference_starts],
        "center_times": [pd.Timestamp(ts) for ts in center_times],
        "distances_m": distances.astype(float),
        "delta_t_degC": delta_t_matrix,
        "pump_rate_at_center_m3h": None if pump_rates is None else pump_rates,
        "start_temp_definition": f"mean of {START_TEMP_SAMPLES} samples closest to t={START_TEMP_TARGET_MINUTES:g} min",
    }
    with output_pkl.open("wb") as fh:
        pickle.dump(payload, fh)

    payload_relative = {
        "channel": CHANNEL,
        "fiber_length_interval_m": [float(distances.min()), float(distances.max())],
        "depth_bsl_interval_m": [float(DEPTH_BSL_MIN_M), float(DEPTH_BSL_MAX_M)],
        "reference_fiber_distance_m": float(reference_distance),
        "reference_starts": [pd.Timestamp(ts) for ts in reference_starts],
        "center_times": [pd.Timestamp(ts) for ts in center_times],
        "distances_m": distances.astype(float),
        "delta_t_relative_to_dominant_profile_degC": relative_matrix,
        "profile_reference": "dominant full vertical profile selected by depth-wise win count",
        "dominant_profile_time_index": int(dominant_idx),
        "dominant_profile_time": pd.Timestamp(center_times[dominant_idx]),
        "dominant_profile_depth_wins": dominant_wins,
        "dominant_profile_values_degC": dominant_profile,
        "pump_rate_at_center_m3h": None if pump_rates is None else pump_rates,
        "start_temp_definition": f"mean of {START_TEMP_SAMPLES} samples closest to t={START_TEMP_TARGET_MINUTES:g} min",
    }
    with output_pkl_relative.open("wb") as fh:
        pickle.dump(payload_relative, fh)

    print(f"Reference distance used: {reference_distance:.2f} m")
    print(f"Detected episodes: {len(reference_starts)}")
    print(f"Saved imshow: {output_png}")
    print(f"Saved pickle: {output_pkl}")
    print(f"Saved relative imshow: {output_png_relative}")
    print(f"Saved relative imshow (turbo): {output_png_relative_turbo}")
    print(f"Saved relative pickle: {output_pkl_relative}")
    print(f"Dominant profile time: {pd.Timestamp(center_times[dominant_idx])}")


if __name__ == "__main__":
    main()
