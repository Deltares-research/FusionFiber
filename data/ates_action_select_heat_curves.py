#!/usr/bin/env python3
"""Selected heating curves using exact start timestamps from the all-curves detector.

Reuses detection, filtering, normalization, and plotting from
ates_action_all_heat_curves.py. Curves are specified by their detected
start timestamps rather than by seed hints.
"""

from __future__ import annotations

import logging

import pandas as pd

import ates_action_all_heat_curves as core


# -----------------------------------------------------------------------------
# User configuration
# -----------------------------------------------------------------------------

# medium flow depth
# channel = "channel 1"
# fiber_distance_m = 548.8
# depth_bsl_m = 178

# slow flow depth
# channel = "channel 1"
# fiber_distance_m = 546.5
# depth_bsl_m = 176

# fast flow depth
channel = "channel 1"
fiber_distance_m = 543.5
depth_bsl_m = 173

SELECTIONS: list[dict[str, object]] = [
    {"channel": channel, "distance_m": fiber_distance_m, "depth_bsl_m": depth_bsl_m},
]


# Exact start timestamps as detected by the all-curves script.
HEATING_START_TIMESTAMPS: list[str] = [
    "2026-04-16 13:58:45",  # peak ~29.97
    "2026-04-16 13:20:58",  # peak ~30.82  (spui in)
    "2026-04-23 19:47:39",  # peak ~35.14
    "2026-04-24 01:47:52",  # peak ~35.99
    "2026-04-20 19:48:15",  # peak ~37.00
    "2026-04-20 04:48:37",  # peak ~38.00
    ]

# Optional per-start tail trim (minutes), keyed by full start timestamp string.
START_TAIL_TRIM_MINUTES: dict[str, float] = {
    "2026-04-16 13:20:58": 6.5,  # spui in curve: trim last 6.5 min
}

# Maximum allowed distance (minutes) between requested start and a detected start.
# Keeps the script robust to minor re-detection jitter.
MAX_MATCH_MINUTES = 5.0
PUMP_REPORT_OFFSET_MINUTES = 2.0


def _trim_segment_tail(segment: pd.Series, trim_minutes: float) -> pd.Series:
    if segment.empty or trim_minutes <= 0:
        return segment
    return segment.loc[segment.index <= float(segment.index.max()) - float(trim_minutes)].copy()


def _print_pump_rates_at_offset(records: list[core.HeatingCurveRecord], offset_minutes: float) -> None:
    print(f"Pumping rates at {offset_minutes:g} minutes after selected curve starts:")
    for record in records:
        pump_rel = record.raw_pump_rel
        if pump_rel is None or pump_rel.empty:
            rate_text = "no pump data"
        else:
            pump_at_offset = pump_rel.reindex(pump_rel.index.union([offset_minutes])).sort_index().interpolate(method="index").get(offset_minutes)
            if pd.isna(pump_at_offset):
                rate_text = "no pump data"
            else:
                rate_text = f"{float(pump_at_offset):.3f} m3/h"

        print(f"  {record.detected_start_ts:%Y-%m-%d %H:%M:%S}: {rate_text}")


def _configured_depth_bsl_m(selection: core.SelectionResult) -> float | None:
    for cfg in SELECTIONS:
        if str(cfg.get("channel")) != selection.channel:
            continue
        cfg_distance = float(cfg.get("distance_m", float("nan")))
        if abs(cfg_distance - float(selection.actual_distance_m)) > 2.0:
            continue
        depth = cfg.get("depth_bsl_m")
        if depth is None:
            return None
        return float(depth)
    return None


def _evolution_plot_title(selection: core.SelectionResult) -> str:
    depth_bsl_m = _configured_depth_bsl_m(selection)
    if depth_bsl_m is None:
        depth_text = "the selected depth"
    else:
        depth_text = f"{depth_bsl_m:.0f} m below surface"
    return f"Pumping rate: heating curves at {depth_text}"


def _build_selected_records(
    selection: core.SelectionResult,
    pump_series: pd.Series | None,
) -> list[core.HeatingCurveRecord]:
    detected_starts = core._detect_episode_starts(selection.full_temp_series)
    available = [pd.Timestamp(ts) for ts in detected_starts]

    kept_starts: list[pd.Timestamp] = []
    raw_segments: list[pd.Series] = []
    raw_pumps: list[pd.Series | None] = []
    peak_rises: list[float] = []

    for ts_str in HEATING_START_TIMESTAMPS:
        requested = pd.Timestamp(ts_str)

        if available:
            deltas = [abs((s - requested).total_seconds()) / 60.0 for s in available]
            best_idx = int(pd.Series(deltas).idxmin())
            best_delta = deltas[best_idx]
            if best_delta <= MAX_MATCH_MINUTES:
                start_ts = available[best_idx]
            else:
                logging.warning("No detected start within %.1f min of %s (nearest %.1f min away); using requested timestamp.", MAX_MATCH_MINUTES, ts_str, best_delta)
                start_ts = requested
        else:
            start_ts = requested

        raw_seg = core._extract_relative_segment(selection.full_temp_series, start_ts)
        trim_minutes = START_TAIL_TRIM_MINUTES.get(ts_str, 0.0)
        raw_seg = _trim_segment_tail(raw_seg, trim_minutes)
        if raw_seg.empty:
            logging.warning("Skipping %s: empty segment after tail trim.", ts_str)
            continue

        metrics = core._episode_metrics(raw_seg)
        if metrics["confirm_rise"] < core.MIN_CONFIRM_RISE_DEGC:
            logging.warning("Skipping %s: confirm_rise %.2f < %.2f", ts_str, metrics["confirm_rise"], core.MIN_CONFIRM_RISE_DEGC)
            continue
        if metrics["peak_rise"] < core.MIN_EPISODE_RISE_DEGC:
            logging.warning("Skipping %s: peak_rise %.2f < %.2f", ts_str, metrics["peak_rise"], core.MIN_EPISODE_RISE_DEGC)
            continue

        raw_pump = core._align_pump_to_temp_window(pump_series, raw_seg, start_ts)
        kept_starts.append(start_ts)
        raw_segments.append(raw_seg)
        raw_pumps.append(raw_pump)
        peak_rises.append(float(metrics["peak_rise"]))

    if not raw_segments:
        return []

    baseline_modes = ["median-prestart"] * len(raw_segments)
    if len(baseline_modes) >= 2 and core.SECOND_CURVE_BASELINE_MODE == "min-prestart":
        baseline_modes[1] = "min-prestart"

    normalized_segments, target_temp, baseline_means = core._normalize_curves(raw_segments, baseline_modes)
    logging.info(
        "Normalization target for %s: %.4f degC (average of per-curve baselines)",
        selection.selection_key,
        target_temp,
    )

    records: list[core.HeatingCurveRecord] = []
    for start_ts, raw_seg, raw_pump, norm_seg, baseline_mean, peak_rise in zip(
        kept_starts, raw_segments, raw_pumps, normalized_segments, baseline_means, peak_rises,
    ):
        aligned_norm = norm_seg.loc[norm_seg.index >= 0.0].copy()
        aligned_norm.index = pd.Index(aligned_norm.index.values, name="minutes")
        aligned_pump = None
        if raw_pump is not None:
            aligned_pump = raw_pump.loc[raw_pump.index >= 0.0].copy()
            if aligned_pump.empty:
                aligned_pump = None

        records.append(
            core.HeatingCurveRecord(
                selection_key=selection.selection_key,
                channel=selection.channel,
                actual_distance_m=selection.actual_distance_m,
                detected_start_ts=start_ts,
                start_method="explicit-start+sustained-rise-anchored",
                raw_temp_rel=raw_seg,
                raw_pump_rel=raw_pump,
                normalized_rel=norm_seg,
                aligned_norm_rel=aligned_norm,
                aligned_pump_rel=aligned_pump,
                baseline_mean_c=float(baseline_mean),
                peak_aligned_c=float(aligned_norm.max()) if not aligned_norm.empty else float("nan"),
                peak_rise_c=float(peak_rise),
            )
        )

    return records


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    print("Heating-curve extraction: using explicit start timestamps (same methodology as all-curves script).")

    core.SELECTIONS = SELECTIONS

    base_dir = core._read_config_dir(core.CONFIG_KEY_DATA_DIR)
    pickle_path = core._pickle_file_from_base_dir(base_dir)
    channel_dfs = core._load_combined_pickle(pickle_path)
    pump_series, pump_msg = core._load_pump_rate_series()

    if pump_msg is not None:
        print(f"Pump data note: {pump_msg}")

    selections = core._extract_selection_series(channel_dfs)
    output_dir = core.DATA_DIR

    for selection in selections:
        records = _build_selected_records(selection, pump_series)
        ordered = core._ordered_records(records)

        if not ordered:
            full_plot_file = core._plot_full_series_with_pump(selection, pump_series, output_dir)
            print(f"No usable heating curves extracted for {selection.selection_key}; skipping curve plots.")
            print(f"Saved full series plot: {full_plot_file}")
            continue

        core._print_summary(ordered)
        _print_pump_rates_at_offset(ordered, PUMP_REPORT_OFFSET_MINUTES)
        evolution_title = _evolution_plot_title(selection)

        stem = core._selection_filename_token(selection)
        raw_file = output_dir / f"heat_curves_raw_{stem}.png"
        aligned_file = output_dir / f"heat_curves_aligned_normalized_{stem}.png"
        pump_file = output_dir / f"heat_curves_pump_companion_{stem}.png"

        core._plot_raw_windows(ordered, core.CMAP_NAME, raw_file, title=evolution_title, q_offset_minutes=PUMP_REPORT_OFFSET_MINUTES)
        core._plot_aligned_normalized(ordered, core.CMAP_NAME, aligned_file, title=evolution_title, q_offset_minutes=PUMP_REPORT_OFFSET_MINUTES)
        core._plot_pump_companion(ordered, core.CMAP_NAME, pump_file)
        full_plot_file = None
        try:
            full_plot_file = core._plot_full_series_with_pump(selection, pump_series, output_dir)
        except Exception as exc:
            logging.warning("Could not save full datetime plot for %s: %s", selection.selection_key, exc)
        if full_plot_file is not None:
            print(f"Saved full datetime plot: {full_plot_file}")
        print(f"Saved raw windows plot: {raw_file}")
        print(f"Saved aligned normalized plot: {aligned_file}")
        print(f"Saved pump companion plot: {pump_file}")


if __name__ == "__main__":
    main()
