#!/usr/bin/env python3
"""Interactive QC viewer for combined channel DTS pickle files.

This tool only reads a user-provided pickle that contains combined channel data
in the form:
    {
        "channel 1": {"df": <pandas.DataFrame>, ...},
        "channel 2": {"df": <pandas.DataFrame>, ...},
        ...
    }

Features:
- Imshow-like heatmap (time on x-axis, fiber position on y-axis)
- Time and fiber range sliders that control visible axis limits
- Hover readout of temperature
- Click on heatmap to place white dashed QC crosshair lines
- Linked QC plots:
  - Time series at clicked fiber position (below heatmap)
  - Fiber profile at clicked timestamp (right side)
"""

from __future__ import annotations

import argparse
import base64
import logging
import os
import pickle
import threading
import time
import webbrowser
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from dash import Dash, Input, Output, State, ctx, dcc, html
import plotly.graph_objects as go

#CONFIG_KEY_DATA_DIR = "data_dir_ates"
#CONFIG_KEY_DATA_DIR = "data_dir_ates_spui"
CONFIG_KEY_DATA_DIR = "data_dir_ates_afterspui"

CONFIG_FILE = Path(__file__).resolve().parent.parent / "config.yaml"


def _default_pickle_path() -> Path:
    """Resolve default pickle from config key folder name (e.g. WKO_K1_active3.pickle)."""
    data_dir = Path(__file__).resolve().parent.parent / "data"

    if not CONFIG_FILE.exists():
        return data_dir / "ates_action_flush_experiment.pickle"

    with CONFIG_FILE.open("r", encoding="utf-8") as file_handle:
        config = yaml.safe_load(file_handle) or {}

    configured_dir = config.get(CONFIG_KEY_DATA_DIR)
    if not configured_dir:
        return data_dir / "ates_action_flush_experiment.pickle"

    folder_name = Path(configured_dir).name
    if not folder_name:
        return data_dir / "ates_action_flush_experiment.pickle"

    return data_dir / f"{folder_name}.pickle"


DEFAULT_PICKLE_PATH = _default_pickle_path()
HEARTBEAT_TIMEOUT_SECONDS = 15.0
HEARTBEAT_POLL_SECONDS = 2.0
HEATMAP_MAX_TIME_POINTS = 600
HEATMAP_MAX_FIBER_POINTS = 350
MIN_PHYSICAL_TEMP_C = -5.0
MAX_PHYSICAL_TEMP_C = 120.0
IMSHOW_HEIGHT_PX = 620
FIBER_SLIDER_WRAPPER_SHIFT_TOP_PX = -17
FIBER_SLIDER_TOP_OFFSET_PX = 0
FIBER_SLIDER_HEIGHT_PX = 548
FIBER_SLIDER_BOTTOM_OFFSET_PX = IMSHOW_HEIGHT_PX - FIBER_SLIDER_TOP_OFFSET_PX - FIBER_SLIDER_HEIGHT_PX
TEMP_SLIDER_TOP_OFFSET_PX = 23
TEMP_SLIDER_HEIGHT_PX = 505
TEMP_SLIDER_BOTTOM_OFFSET_PX = IMSHOW_HEIGHT_PX - TEMP_SLIDER_TOP_OFFSET_PX - TEMP_SLIDER_HEIGHT_PX
HEATMAP_TIME_AXIS_LEFT_OFFSET_PX = 81
HEATMAP_TIME_AXIS_RIGHT_OFFSET_PX = 109

CMAP_OPTIONS = ["plasma", "turbo", "inferno", "magma", "viridis", "cividis", "rocket", "mako"]

# Seaborn-exact rocket colorscale (dark red -> bright orange-red)
ROCKET_COLORSCALE = [
    [0.0, "rgb(1,0,1)"],
    [0.03, "rgb(10,0,13)"],
    [0.06, "rgb(18,0,23)"],
    [0.09, "rgb(26,0,31)"],
    [0.12, "rgb(34,0,39)"],
    [0.15, "rgb(41,2,45)"],
    [0.18, "rgb(47,5,50)"],
    [0.21, "rgb(52,8,54)"],
    [0.24, "rgb(56,12,57)"],
    [0.27, "rgb(59,16,60)"],
    [0.30, "rgb(61,20,62)"],
    [0.33, "rgb(63,25,63)"],
    [0.36, "rgb(64,30,63)"],
    [0.39, "rgb(64,35,63)"],
    [0.42, "rgb(64,40,62)"],
    [0.45, "rgb(63,45,60)"],
    [0.48, "rgb(62,50,57)"],
    [0.51, "rgb(60,56,54)"],
    [0.54, "rgb(58,61,49)"],
    [0.57, "rgb(56,66,44)"],
    [0.60, "rgb(54,70,38)"],
    [0.63, "rgb(52,75,31)"],
    [0.66, "rgb(51,79,23)"],
    [0.69, "rgb(51,83,14)"],
    [0.72, "rgb(53,86,4)"],
    [0.75, "rgb(61,88,0)"],
    [0.78, "rgb(76,89,0)"],
    [0.81, "rgb(95,89,0)"],
    [0.84, "rgb(119,87,0)"],
    [0.87, "rgb(145,83,0)"],
    [0.90, "rgb(171,76,0)"],
    [0.93, "rgb(198,65,0)"],
    [0.96, "rgb(224,48,0)"],
    [1.0, "rgb(248,0,0)"],
]

# Seaborn-exact mako colorscale (dark blue -> bright cyan-white)
MAKO_COLORSCALE = [
    [0.0, "rgb(0,0,4)"],
    [0.03, "rgb(0,1,11)"],
    [0.06, "rgb(1,2,19)"],
    [0.09, "rgb(2,3,26)"],
    [0.12, "rgb(3,4,33)"],
    [0.15, "rgb(4,5,39)"],
    [0.18, "rgb(5,7,44)"],
    [0.21, "rgb(6,9,49)"],
    [0.24, "rgb(7,11,52)"],
    [0.27, "rgb(8,13,55)"],
    [0.30, "rgb(9,16,57)"],
    [0.33, "rgb(10,19,59)"],
    [0.36, "rgb(11,22,60)"],
    [0.39, "rgb(12,25,60)"],
    [0.42, "rgb(13,29,60)"],
    [0.45, "rgb(14,33,59)"],
    [0.48, "rgb(16,37,57)"],
    [0.51, "rgb(18,41,55)"],
    [0.54, "rgb(21,45,51)"],
    [0.57, "rgb(25,49,47)"],
    [0.60, "rgb(29,53,41)"],
    [0.63, "rgb(34,57,34)"],
    [0.66, "rgb(40,60,26)"],
    [0.69, "rgb(47,62,16)"],
    [0.72, "rgb(55,63,4)"],
    [0.75, "rgb(69,61,0)"],
    [0.78, "rgb(86,58,0)"],
    [0.81, "rgb(105,52,0)"],
    [0.84, "rgb(127,44,0)"],
    [0.87, "rgb(151,33,0)"],
    [0.90, "rgb(177,19,0)"],
    [0.93, "rgb(203,0,0)"],
    [0.96, "rgb(228,0,0)"],
    [1.0, "rgb(252,252,252)"],
]

PLOTLY_COLORSCALE_MAP = {
    "magma": "Magma",
    "inferno": "Inferno",
    "plasma": "Plasma",
    "viridis": "Viridis",
    "cividis": "Cividis",
    "rocket": ROCKET_COLORSCALE,
    "mako": MAKO_COLORSCALE,
    "turbo": "Turbo",
}

# Colormap start colors for dropdown outlines (extracted from colorscales)
CMAP_START_COLORS = {
    "magma": "rgb(0,0,4)",
    "inferno": "rgb(0,0,4)",
    "plasma": "rgb(13,0,51)",
    "viridis": "rgb(68,1,84)",
    "cividis": "rgb(0,32,76)",
    "rocket": "rgb(1,0,1)",
    "mako": "rgb(0,0,4)",
    "turbo": "rgb(48,18,59)",
}


def _image_data_uri(image_path: Path) -> str:
    if not image_path.exists():
        return ""
    suffix = image_path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "application/octet-stream"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"



def _load_combined_pickle(pickle_path: Path) -> dict[str, pd.DataFrame]:
    if not pickle_path.exists():
        raise FileNotFoundError(f"Pickle file not found: {pickle_path}")

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

        # Normalize index and columns for plotting.
        idx = pd.to_datetime(df.index, errors="coerce")
        if idx.isna().any():
            raise ValueError(
                f"Channel '{channel_name}' has non-datetime index values; cannot plot time axis."
            )

        numeric_cols = pd.to_numeric(df.columns, errors="coerce")
        col_mask = ~np.isnan(numeric_cols)
        if not col_mask.any():
            raise ValueError(
                f"Channel '{channel_name}' has no numeric distance columns; cannot plot fiber axis."
            )

        cleaned = df.loc[:, col_mask].copy()
        cleaned.columns = numeric_cols[col_mask].astype(float)
        cleaned.index = idx

        # Ensure deterministic order for axes.
        cleaned = cleaned.sort_index().sort_index(axis=1)
        channel_dfs[str(channel_name)] = cleaned

    if not channel_dfs:
        raise ValueError(
            "No valid channel DataFrames found. Expected format: channel -> {'df': DataFrame}."
        )

    return channel_dfs


def _build_time_marks(ts_index: pd.DatetimeIndex) -> dict[int, dict[str, object]]:
    n = len(ts_index)
    if n <= 1:
        one = int(ts_index[0].value // 10**9)
        return {
            one: {
                "label": ts_index[0].strftime("%Y-%m-%d\n%H:%M:%S"),
                "style": {"color": "#ffffff"},
            }
        }

    # Keep marks sparse to prevent UI clutter.
    mark_count = min(6, n)
    sample_positions = np.linspace(0, n - 1, mark_count).astype(int)
    marks = {}
    for pos in np.unique(sample_positions):
        ts = ts_index[pos]
        marks[int(ts.value // 10**9)] = {
            "label": ts.strftime("%m-%d\n%H:%M"),
            "style": {"color": "#ffffff"},
        }
    return marks


def _nearest_value(values: np.ndarray, target: float) -> tuple[int, float]:
    idx = int(np.abs(values - target).argmin())
    return idx, float(values[idx])


def _nearest_timestamp(index: pd.DatetimeIndex, target_ts: pd.Timestamp) -> tuple[int, pd.Timestamp]:
    idx = int(np.abs((index - target_ts).asi8).argmin())
    return idx, pd.Timestamp(index[idx])


def _window_df(df: pd.DataFrame, time_range: list[int], fiber_range: list[float]) -> pd.DataFrame:
    t0 = pd.to_datetime(time_range[0], unit="s")
    t1 = pd.to_datetime(time_range[1], unit="s")
    d0 = float(min(fiber_range))
    d1 = float(max(fiber_range))

    window_df = df.loc[(df.index >= t0) & (df.index <= t1), :]
    return window_df.loc[:, (window_df.columns >= d0) & (window_df.columns <= d1)]


def _downsample_for_heatmap(
    window_df: pd.DataFrame,
    max_time_points: int = HEATMAP_MAX_TIME_POINTS,
    max_fiber_points: int = HEATMAP_MAX_FIBER_POINTS,
) -> pd.DataFrame:
    """Return a reduced dataframe for fast heatmap rendering."""
    if window_df.empty:
        return window_df

    time_step = max(1, int(np.ceil(len(window_df.index) / max_time_points)))
    fiber_step = max(1, int(np.ceil(len(window_df.columns) / max_fiber_points)))
    return window_df.iloc[::time_step, ::fiber_step]


def _heatmap_figure(
    window_df: pd.DataFrame,
    click_ts: pd.Timestamp,
    click_dist: float,
    x_range: list[pd.Timestamp],
    y_range: list[float],
    temp_min: float,
    temp_max: float,
    cmap_name: str,
) -> go.Figure:
    z_data = np.clip(window_df.to_numpy(dtype=float).T, MIN_PHYSICAL_TEMP_C, MAX_PHYSICAL_TEMP_C)
    colorscale_name = PLOTLY_COLORSCALE_MAP.get(str(cmap_name).lower(), "Plasma")

    fig = go.Figure(
        data=[
            go.Heatmap(
                x=window_df.index,
                y=window_df.columns.to_numpy(dtype=float),
                z=z_data,
                colorscale=colorscale_name,
                zmin=temp_min,
                zmax=temp_max,
                hovertemplate=(
                    "Time: %{x}<br>Fiber: %{y:.1f} m"
                    "<br>Temperature: %{z:.3f} degC<extra></extra>"
                ),
                colorbar={
                    "title": "Temp (\u00b0C)",
                    "thickness": 14,
                    "x": 1.01,
                    "len": 1.0,
                    "y": 0.5,
                    "yanchor": "middle",
                },
            )
        ]
    )

    fig.add_vline(
        x=click_ts,
        line_color="white",
        line_dash="dot",
        line_width=1.5,
    )
    fig.add_hline(
        y=click_dist,
        line_color="white",
        line_dash="dot",
        line_width=1.5,
    )

    fig.update_layout(
        margin={"l": 50, "r": 30, "t": 4, "b": 26},
        template="plotly_dark",
        paper_bgcolor="black",
        plot_bgcolor="black",
        clickmode="event",
    )
    fig.update_xaxes(title_text="Time", range=x_range)
    fig.update_yaxes(
        title_text="Fiber length (m)",
        range=[y_range[1], y_range[0]],
        tickformat=".1f",
    )

    return fig


def _time_series_figure(
    window_df: pd.DataFrame,
    click_ts: pd.Timestamp,
    click_dist: float,
    channel_name: str,
    temp_min: float,
    temp_max: float,
) -> go.Figure:
    distances = window_df.columns.to_numpy(dtype=float)
    dist_idx, snapped_dist = _nearest_value(distances, click_dist)
    series = window_df.iloc[:, dist_idx]
    clipped_values = np.clip(series.values, MIN_PHYSICAL_TEMP_C, MAX_PHYSICAL_TEMP_C)

    fig = go.Figure(
        data=[
            go.Scatter(
                x=series.index,
                y=clipped_values,
                mode="lines",
                line={"width": 1.8},
                hovertemplate="Time: %{x}<br>Temperature: %{y:.3f} degC<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        title=f"Time profile at fiber {snapped_dist:.1f} m ({channel_name})",
        margin={"l": 50, "r": 20, "t": 28, "b": 34},
        template="plotly_dark",
        paper_bgcolor="black",
        plot_bgcolor="black",
        clickmode="event",
    )
    fig.update_xaxes(title_text="Time")
    fig.update_yaxes(title_text="Temp (\u00b0C)")
    return fig


def _fiber_profile_figure(
    window_df: pd.DataFrame,
    click_ts: pd.Timestamp,
    click_dist: float,
    channel_name: str,
    temp_min: float,
    temp_max: float,
) -> go.Figure:
    time_idx, snapped_ts = _nearest_timestamp(window_df.index, click_ts)
    profile = window_df.iloc[time_idx, :]
    clipped_values = np.clip(profile.values, MIN_PHYSICAL_TEMP_C, MAX_PHYSICAL_TEMP_C)

    fig = go.Figure(
        data=[
            go.Scatter(
                x=clipped_values,
                y=profile.index.to_numpy(dtype=float),
                mode="lines",
                line={"width": 1.8},
                hovertemplate="Temperature: %{x:.3f} degC<br>Fiber: %{y:.1f} m<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        title=f"Fiber profile at {snapped_ts} ({channel_name})",
        margin={"l": 55, "r": 20, "t": 28, "b": 34},
        template="plotly_dark",
        paper_bgcolor="black",
        plot_bgcolor="black",
        clickmode="event",
    )
    fig.update_xaxes(title_text="Temp (\u00b0C)")
    fig.update_yaxes(title_text="Fiber length (m)", autorange="reversed", tickformat=".1f")
    return fig


def _install_browser_lifecycle(app: Dash) -> None:
    # Reduce terminal noise from frequent lifecycle pings while keeping warnings/errors.
    werkzeug_logger = logging.getLogger("werkzeug")
    if not getattr(werkzeug_logger, "_ates_request_filter_installed", False):
        class _LifecycleRequestFilter(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:
                msg = record.getMessage()
                return "/_heartbeat" not in msg and "/_shutdown" not in msg

        werkzeug_logger.addFilter(_LifecycleRequestFilter())
        setattr(werkzeug_logger, "_ates_request_filter_installed", True)

    lifecycle_state = {
        "last_heartbeat": time.monotonic(),
        "heartbeat_seen": False,
        "shutdown_started": False,
    }
    state_lock = threading.Lock()

    app.index_string = """<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            body {
                background: #000000;
                color: #ffffff;
                font-family: Aptos, "Aptos Display", Calibri, "Segoe UI", sans-serif;
            }
            button,
            input,
            select,
            textarea,
            .dash-dropdown,
            .dash-dropdown-content,
            .dropdown-wrapper label {
                font-family: Aptos, "Aptos Display", Calibri, "Segoe UI", sans-serif !important;
            }
            .Select-control,
            .Select-menu-outer,
            .Select-menu,
            .Select-option,
            .Select-value-label,
            .Select-placeholder,
            .Select-input > input {
                background-color: #000000 !important;
                color: #ffffff !important;
            }
            .Select-option.is-focused {
                background-color: #222222 !important;
            }
            .rc-slider-mark-text {
                color: #ffffff !important;
            }
            .dash-range-slider-input,
            .dash-range-slider-min-input,
            .dash-range-slider-max-input {
                display: none !important;
            }
            .axis-slider-no-marks .rc-slider-mark {
                display: none !important;
            }
            .axis-slider-vertical-wrapper {
                position: relative;
                z-index: 8000;
                width: 46px;
                min-width: 46px;
                overflow: visible !important;
            }
            .axis-slider-horizontal-wrapper {
                position: relative;
                z-index: 8000;
                overflow: visible !important;
                margin-top: 2px;
            }
            .axis-slider-horizontal-inner {
                margin-left: 81px;
                margin-right: 109px;
                overflow: visible !important;
            }
            .axis-slider-no-marks .dash-slider-mark,
            .axis-slider-no-marks .dash-slider-mark-text {
                display: none !important;
            }
            .axis-slider-no-marks .dash-slider-thumb {
                font-size: 0 !important;
            }
            .axis-slider-no-marks .rc-slider-track {
                background-color: rgba(127, 75, 196, 1) !important;
            }
            .axis-slider-no-marks .rc-slider-rail {
                background-color: rgba(127, 75, 196, 0.3) !important;
            }
            .axis-slider-no-marks .dash-slider-range {
                background-color: rgba(127, 75, 196, 1) !important;
            }
            .axis-slider-no-marks .dash-slider-track {
                background-color: rgba(127, 75, 196, 0.3) !important;
            }
            #temp-slider .dash-slider-range,
            #temp-slider .rc-slider-track {
                background-color: rgba(120, 22, 22, 0.95) !important;
            }
            #temp-slider .dash-slider-track,
            #temp-slider .rc-slider-rail {
                background-color: rgba(120, 22, 22, 0.28) !important;
            }
            #temp-slider .dash-slider-thumb,
            #temp-slider .rc-slider-handle {
                background-color: #5f1414 !important;
                border: 2px solid #8e2a2a !important;
                box-shadow: none !important;
            }
            #imshow-graph,
            #imshow-graph .js-plotly-plot,
            #imshow-graph .plot-container,
            #imshow-graph .svg-container {
                position: relative;
                z-index: 0 !important;
            }
            #fiber-slider,
            #fiber-slider .dash-slider-container,
            #fiber-slider .dash-slider-wrapper {
                position: relative;
                z-index: 24000 !important;
                overflow: visible !important;
            }
            #fiber-slider .dash-slider-root {
                position: relative;
                z-index: 24000 !important;
                overflow: visible !important;
            }
            #fiber-slider .dash-slider-thumb {
                position: relative;
                z-index: 25000 !important;
            }
            #fiber-slider .dash-slider-tooltip {
                position: absolute !important;
                z-index: 25001 !important;
            }
            .rc-slider-tooltip {
                z-index: 1200 !important;
            }
            .rc-slider-tooltip-inner {
                background: linear-gradient(135deg, #141821 0%, #202938 100%) !important;
                color: #f5f7fb !important;
                border: 1px solid #3f4e66 !important;
                border-radius: 10px !important;
                box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35) !important;
                font-size: 12px !important;
                font-weight: 700 !important;
                min-height: 28px !important;
                line-height: 18px !important;
                padding: 4px 8px !important;
            }
            .rc-slider-tooltip-content {
                color: #f5f7fb !important;
            }
            .rc-slider-tooltip-arrow {
                border-top-color: #202938 !important;
                border-bottom-color: #202938 !important;
                border-left-color: #202938 !important;
                border-right-color: #202938 !important;
            }
            body .dash-slider-tooltip,
            div.dash-slider-tooltip {
                background: linear-gradient(135deg, #141821 0%, #202938 100%) !important;
                background-color: #202938 !important;
                color: #f5f7fb !important;
                position: absolute !important;
                z-index: 2147483647 !important;
                border: 1px solid #3f4e66 !important;
                border-radius: 10px !important;
                box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35) !important;
                font-size: 12px !important;
                font-weight: 700 !important;
                line-height: 18px !important;
                min-height: 28px !important;
                padding: 4px 8px !important;
            }
            .dash-slider-tooltip > div {
                color: #f5f7fb !important;
                font-weight: 700 !important;
            }
            body .dash-slider-tooltip::before,
            body .dash-slider-tooltip::after,
            div.dash-slider-tooltip::before,
            div.dash-slider-tooltip::after {
                border-top-color: #202938 !important;
                border-bottom-color: #202938 !important;
                border-left-color: #202938 !important;
                border-right-color: #202938 !important;
            }
            .dropdown-wrapper label {
                font-size: 12px;
                font-weight: bold;
                margin-bottom: 3px;
                display: block;
            }
            .top-controls-row {
                position: relative;
                z-index: 30000;
                display: flex;
                flex-direction: row;
                gap: 6px;
                width: 246px;
                margin-bottom: 0px;
            }
            /* Dash 4 dropdown button */
            .dash-dropdown {
                background-color: #000000 !important;
                color: #ffffff !important;
                border: 1px solid #555555 !important;
                border-radius: 4px !important;
                width: 100% !important;
                cursor: pointer !important;
                min-height: 32px !important;
            }
            .dash-dropdown:hover {
                border-color: #888888 !important;
            }
            /* Dropdown popup/menu */
            .dash-dropdown-content {
                background-color: #111111 !important;
                border: 1px solid #555555 !important;
                border-radius: 4px !important;
                color: #ffffff !important;
            }
            /* Search input inside dropdown */
            .dash-dropdown-search {
                background-color: #1a1a1a !important;
                color: #ffffff !important;
                border: none !important;
                border-bottom: 1px solid #333333 !important;
                outline: none !important;
            }
            .dash-dropdown-search::placeholder {
                color: #888888 !important;
            }
            /* Option items */
            .dash-dropdown-option {
                background-color: #111111 !important;
                color: #ffffff !important;
            }
            .dash-dropdown-option:hover {
                background-color: #2a2a2a !important;
            }
            .dash-dropdown-option.selected {
                background-color: #333333 !important;
                color: #ffffff !important;
            }
            .dash-options-list-option-text {
                color: #ffffff !important;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
        <script>
            window.dccFunctions = window.dccFunctions || {};
            window.dccFunctions.formatUnixToDateTime = function (value) {
                const n = Number(value);
                if (!Number.isFinite(n)) {
                    return String(value);
                }
                const d = new Date(n * 1000);
                const pad = (x) => String(x).padStart(2, '0');
                return (
                    d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) +
                    ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds())
                );
            };
            window.dccFunctions.formatOneDecimal = function (value) {
                const n = Number(value);
                if (!Number.isFinite(n)) {
                    return String(value);
                }
                return n.toFixed(1);
            };
            window.dccFunctions.formatNegatedOneDecimal = function (value) {
                const n = Number(value);
                if (!Number.isFinite(n)) {
                    return String(value);
                }
                return (-n).toFixed(1);
            };

            (function () {
                const heartbeat = () => {
                    fetch('/_heartbeat', {method: 'POST', keepalive: true}).catch(() => {});
                };

                heartbeat();
                const timerId = window.setInterval(heartbeat, 5000);

                window.addEventListener('beforeunload', function () {
                    window.clearInterval(timerId);
                    fetch('/_shutdown', {method: 'POST', keepalive: true}).catch(() => {});
                });
            })();
        </script>
    </body>
</html>"""

    @app.server.post("/_heartbeat")
    def _heartbeat_route():
        with state_lock:
            lifecycle_state["last_heartbeat"] = time.monotonic()
            lifecycle_state["heartbeat_seen"] = True
        return ("", 204)

    @app.server.post("/_shutdown")
    def _shutdown_route():
        with state_lock:
            if lifecycle_state["shutdown_started"]:
                return ("", 204)
            # Ignore stale-tab shutdown if another tab is still sending heartbeats
            if (time.monotonic() - lifecycle_state["last_heartbeat"]) < HEARTBEAT_TIMEOUT_SECONDS:
                return ("", 204)
            lifecycle_state["shutdown_started"] = True

        def _do_exit() -> None:
            time.sleep(0.2)
            os._exit(0)

        threading.Thread(target=_do_exit, daemon=True).start()
        return ("", 204)

    def _watchdog() -> None:
        while True:
            time.sleep(HEARTBEAT_POLL_SECONDS)
            with state_lock:
                should_shutdown = (
                    lifecycle_state["heartbeat_seen"]
                    and not lifecycle_state["shutdown_started"]
                    and (time.monotonic() - lifecycle_state["last_heartbeat"]) > HEARTBEAT_TIMEOUT_SECONDS
                )
                if should_shutdown:
                    lifecycle_state["shutdown_started"] = True
                else:
                    continue
            os._exit(0)

    threading.Thread(target=_watchdog, daemon=True).start()


def make_app(channel_dfs: dict[str, pd.DataFrame]) -> Dash:
    channel_names = sorted(channel_dfs.keys())
    default_channel = channel_names[0]
    default_df = channel_dfs[default_channel]

    time_min = int(default_df.index[0].value // 10**9)
    time_max = int(default_df.index[-1].value // 10**9)
    dist_min = round(float(default_df.columns.min()), 1)
    dist_max = round(float(default_df.columns.max()), 1)
    deltares_logo_src = _image_data_uri(Path(__file__).with_name("DELTARES-logo.png"))
    fusionfiber_logo_src = _image_data_uri(Path(__file__).with_name("FusionFiber_logo.png"))

    app = Dash(__name__)
    _install_browser_lifecycle(app)

    app.layout = html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.H3(
                                "ATES Interactive Viewer",
                                style={
                                    "fontSize": "34px",
                                    "fontWeight": "700",
                                    "letterSpacing": "0.3px",
                                    "margin": "0",
                                    "lineHeight": "1.1",
                                },
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Label("Channel"),
                                            dcc.Dropdown(
                                                id="channel-dropdown",
                                                options=[{"label": name, "value": name} for name in channel_names],
                                                value=default_channel,
                                                clearable=False,
                                                searchable=False,
                                                className="cmap-channel-dropdown",
                                            ),
                                        ],
                                        style={"width": "120px", "minWidth": "120px"},
                                        className="dropdown-wrapper",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Colormap"),
                                            dcc.Dropdown(
                                                id="cmap-dropdown",
                                                options=[{"label": name, "value": name} for name in CMAP_OPTIONS],
                                                value="plasma",
                                                clearable=False,
                                                searchable=False,
                                                className="cmap-channel-dropdown",
                                            ),
                                        ],
                                        style={"width": "120px", "minWidth": "120px"},
                                        className="dropdown-wrapper",
                                        id="cmap-wrapper-div",
                                    ),
                                ],
                                className="top-controls-row",
                            ),
                        ],
                        style={
                            "display": "flex",
                            "alignItems": "flex-end",
                            "gap": "14px",
                            "flexWrap": "wrap",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "alignItems": "flex-end",
                    "justifyContent": "flex-start",
                    "gap": "14px",
                    "flexWrap": "wrap",
                    "marginBottom": "10px",
                },
            ),
            dcc.Store(id="click-store"),
            dcc.Store(id="temp-store"),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            dcc.RangeSlider(
                                                id="fiber-slider",
                                                min=-dist_max,
                                                max=-dist_min,
                                                value=[-dist_max, -dist_min],
                                                step=0.1,
                                                marks={},
                                                updatemode="mouseup",
                                                allowCross=False,
                                                tooltip={"always_visible": False, "transform": "formatNegatedOneDecimal"},
                                                vertical=True,
                                                verticalHeight=FIBER_SLIDER_HEIGHT_PX,
                                                className="axis-slider-no-marks",
                                            )
                                        ],
                                        style={
                                            "width": "46px",
                                            "minWidth": "46px",
                                            "marginRight": "4px",
                                            "marginTop": f"{FIBER_SLIDER_WRAPPER_SHIFT_TOP_PX}px",
                                            "display": "flex",
                                            "alignItems": "center",
                                            "justifyContent": "center",
                                            "paddingTop": f"{FIBER_SLIDER_TOP_OFFSET_PX}px",
                                            "paddingBottom": f"{FIBER_SLIDER_BOTTOM_OFFSET_PX}px",
                                            "overflow": "visible",
                                        },
                                        className="axis-slider-vertical-wrapper",
                                    ),
                                    html.Div(
                                        [
                                            dcc.Graph(
                                                id="imshow-graph",
                                                style={"height": f"{IMSHOW_HEIGHT_PX}px"},
                                                config={
                                                    "editable": True,
                                                    "edits": {
                                                        "shapePosition": True,
                                                        "titleText": False,
                                                        "annotationText": False,
                                                    },
                                                },
                                            ),
                                            html.Div(
                                                [
                                                    dcc.RangeSlider(
                                                        id="time-slider",
                                                        min=time_min,
                                                        max=time_max,
                                                        value=[time_min, time_max],
                                                        marks={},
                                                        updatemode="mouseup",
                                                        allowCross=False,
                                                        tooltip={
                                                            "always_visible": False,
                                                            "transform": "formatUnixToDateTime",
                                                        },
                                                        className="axis-slider-no-marks",
                                                    )
                                                ],
                                                className="axis-slider-horizontal-inner",
                                            ),
                                        ],
                                        style={"flex": "1", "minWidth": "0"},
                                        className="axis-slider-horizontal-wrapper",
                                    ),
                                    html.Div(
                                        [
                                            dcc.RangeSlider(
                                                id="temp-slider",
                                                min=MIN_PHYSICAL_TEMP_C,
                                                max=MAX_PHYSICAL_TEMP_C,
                                                value=[MIN_PHYSICAL_TEMP_C, MAX_PHYSICAL_TEMP_C],
                                                step=0.5,
                                                marks={},
                                                updatemode="mouseup",
                                                allowCross=False,
                                                tooltip={
                                                    "always_visible": False,
                                                    "transform": "formatOneDecimal",
                                                },
                                                vertical=True,
                                                verticalHeight=TEMP_SLIDER_HEIGHT_PX,
                                                className="axis-slider-no-marks",
                                            )
                                        ],
                                        style={
                                            "width": "18px",
                                            "marginLeft": "1px",
                                            "display": "flex",
                                            "alignItems": "center",
                                            "justifyContent": "center",
                                            "paddingTop": f"{TEMP_SLIDER_TOP_OFFSET_PX}px",
                                            "paddingBottom": f"{TEMP_SLIDER_BOTTOM_OFFSET_PX}px",
                                            "overflow": "visible",
                                        },
                                        className="axis-slider-vertical-wrapper",
                                    ),
                                ],
                                style={"display": "flex", "alignItems": "stretch", "gap": "2px", "overflow": "visible"},
                            ),
                            dcc.Graph(id="timeseries-graph", style={"height": "30vh"}),
                            html.Button(
                                "Reset View",
                                id="reset-view-button",
                                n_clicks=0,
                                style={
                                    "marginTop": "4px",
                                    "padding": "8px 14px",
                                    "fontSize": "13px",
                                    "fontWeight": "700",
                                    "color": "#f5f7fb",
                                    "background": "linear-gradient(135deg, #141821 0%, #202938 100%)",
                                    "border": "1px solid #3f4e66",
                                    "borderRadius": "10px",
                                    "boxShadow": "0 6px 18px rgba(0, 0, 0, 0.35)",
                                    "maxWidth": "140px",
                                    "cursor": "pointer",
                                    "transition": "transform 120ms ease, border-color 120ms ease, box-shadow 120ms ease",
                                },
                            ),
                        ],
                        style={"flex": "3", "minWidth": "700px"},
                    ),
                    html.Div(
                        [
                            dcc.Graph(id="fiberprofile-graph", style={"height": "56vh"}),
                            html.Img(
                                src=fusionfiber_logo_src,
                                style={
                                    "display": "block",
                                    "width": "100%",
                                    "maxWidth": "500px",
                                    "height": "auto",
                                    "marginTop": "0px",
                                    "marginLeft": "60px",
                                    "marginRight": "0",
                                    "pointerEvents": "none",
                                },
                            ),
                        ],
                        style={"flex": "1.3", "minWidth": "320px", "display": "flex", "flexDirection": "column"},
                    ),
                ],
                style={
                    "display": "flex",
                    "gap": "12px",
                    "alignItems": "flex-start",
                    "flexWrap": "wrap",
                },
            ),
            html.Img(
                src=deltares_logo_src,
                style={
                    "position": "fixed",
                    "top": "4px",
                    "right": "10px",
                    "width": "280px",
                    "height": "auto",
                    "zIndex": "50000",
                    "pointerEvents": "none",
                },
            ),
        ],
        style={"padding": "6px 10px", "backgroundColor": "black", "color": "white", "minHeight": "100vh"},
    )

    @app.callback(
        Output("temp-slider", "min"),
        Output("temp-slider", "max"),
        Output("temp-slider", "value"),
        Output("temp-slider", "marks"),
        Output("temp-store", "data"),
        Input("channel-dropdown", "value"),
        Input("time-slider", "value"),
        Input("fiber-slider", "value"),
        Input("reset-view-button", "n_clicks"),
        State("temp-store", "data"),
    )
    def _update_temp_slider(channel_name, time_range, fiber_range, reset_clicks, temp_store):
        df = channel_dfs[channel_name]
        t0 = pd.to_datetime(time_range[0], unit="s")
        t1 = pd.to_datetime(time_range[1], unit="s")
        d0 = -float(max(fiber_range))
        d1 = -float(min(fiber_range))

        window_df = df.loc[(df.index >= t0) & (df.index <= t1), :]
        window_df = window_df.loc[:, (window_df.columns >= d0) & (window_df.columns <= d1)]

        if window_df.empty:
            return MIN_PHYSICAL_TEMP_C, 100, [MIN_PHYSICAL_TEMP_C, 100], {}, {"min": MIN_PHYSICAL_TEMP_C, "max": 100}

        window_min = float(window_df.to_numpy().min())
        window_max = float(window_df.to_numpy().max())
        window_max = min(window_max, MAX_PHYSICAL_TEMP_C)
        window_min = max(window_min, MIN_PHYSICAL_TEMP_C)
        margin = (window_max - window_min) * 0.05 if window_max > window_min else 1.0
        overall_min = max(MIN_PHYSICAL_TEMP_C, window_min - margin)
        overall_max = min(MAX_PHYSICAL_TEMP_C, window_max + margin)
        overall_min = round(overall_min, 1)
        overall_max = round(overall_max, 1)

        triggered_prop = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
        reset_requested = triggered_prop == "reset-view-button.n_clicks"

        if reset_requested:
            current_value = [window_min, window_max]
        elif temp_store and "min" in temp_store and "max" in temp_store:
            prev_min = float(temp_store["min"])
            prev_max = float(temp_store["max"])
            lo = max(overall_min, min(prev_min, prev_max))
            hi = min(overall_max, max(prev_min, prev_max))
            if lo >= hi:
                current_value = [window_min, window_max]
            else:
                current_value = [lo, hi]
        else:
            current_value = [window_min, window_max]

        current_value = [round(float(current_value[0]), 1), round(float(current_value[1]), 1)]

        marks = {
            int(overall_min): f"{overall_min:.1f}",
            int((overall_min + overall_max) / 2): f"{(overall_min + overall_max) / 2:.1f}",
            int(overall_max): f"{overall_max:.1f}",
        }

        return overall_min, overall_max, current_value, marks, {"min": current_value[0], "max": current_value[1]}

    @app.callback(
        Output("temp-store", "data", allow_duplicate=True),
        Input("temp-slider", "value"),
        prevent_initial_call=True,
    )
    def _sync_temp_store(temp_range):
        return {"min": float(temp_range[0]), "max": float(temp_range[1])}

    @app.callback(
        Output("time-slider", "min"),
        Output("time-slider", "max"),
        Output("time-slider", "value"),
        Output("time-slider", "marks"),
        Output("fiber-slider", "min"),
        Output("fiber-slider", "max"),
        Output("fiber-slider", "value"),
        Output("fiber-slider", "step"),
        Input("channel-dropdown", "value"),
        Input("reset-view-button", "n_clicks"),
    )
    def _reset_sliders(channel_name: str, reset_clicks: int):
        df = channel_dfs[channel_name]
        tmin = int(df.index[0].value // 10**9)
        tmax = int(df.index[-1].value // 10**9)
        dmin = round(float(df.columns.min()), 1)
        dmax = round(float(df.columns.max()), 1)
        step = 0.1

        return tmin, tmax, [tmin, tmax], {}, -dmax, -dmin, [-dmax, -dmin], step

    @app.callback(
        Output("click-store", "data"),
        Input("imshow-graph", "clickData"),
        Input("imshow-graph", "relayoutData"),
        Input("channel-dropdown", "value"),
        Input("time-slider", "value"),
        Input("fiber-slider", "value"),
        State("click-store", "data"),
    )
    def _update_click_store(
        heatmap_click_data,
        heatmap_relayout_data,
        channel_name,
        time_range,
        fiber_range,
        current_store,
    ):
        df = channel_dfs[channel_name]
        actual_fiber_range = [-fiber_range[1], -fiber_range[0]]
        window = _window_df(df, time_range, actual_fiber_range)

        if window.empty:
            return None

        selected_ts = current_store.get("ts") if current_store else None
        selected_dist = current_store.get("dist") if current_store else None

        if selected_ts is None:
            selected_ts = str(window.index[len(window.index) // 2])
        if selected_dist is None:
            selected_dist = float(window.columns[len(window.columns) // 2])

        trigger_prop = ctx.triggered[0]["prop_id"] if ctx.triggered else ""

        if trigger_prop == "imshow-graph.clickData" and heatmap_click_data and heatmap_click_data.get("points"):
            pt = heatmap_click_data["points"][0]
            selected_ts = str(pd.to_datetime(pt.get("x")))
            selected_dist = float(pt.get("y"))
        elif trigger_prop == "imshow-graph.relayoutData" and isinstance(heatmap_relayout_data, dict):
            if "shapes[0].x0" in heatmap_relayout_data:
                selected_ts = str(pd.to_datetime(heatmap_relayout_data["shapes[0].x0"]))
            elif "shapes[0].x1" in heatmap_relayout_data:
                selected_ts = str(pd.to_datetime(heatmap_relayout_data["shapes[0].x1"]))

            if "shapes[1].y0" in heatmap_relayout_data:
                selected_dist = float(heatmap_relayout_data["shapes[1].y0"])
            elif "shapes[1].y1" in heatmap_relayout_data:
                selected_dist = float(heatmap_relayout_data["shapes[1].y1"])

            if "shapes" in heatmap_relayout_data and isinstance(heatmap_relayout_data["shapes"], list):
                shapes = heatmap_relayout_data["shapes"]
                if len(shapes) > 0 and "x0" in shapes[0]:
                    selected_ts = str(pd.to_datetime(shapes[0]["x0"]))
                if len(shapes) > 1 and "y0" in shapes[1]:
                    selected_dist = float(shapes[1]["y0"])

        snapped_ts = _nearest_timestamp(window.index, pd.to_datetime(selected_ts))[1]
        snapped_dist = _nearest_value(window.columns.to_numpy(dtype=float), float(selected_dist))[1]

        return {"channel": channel_name, "ts": str(snapped_ts), "dist": snapped_dist}

    @app.callback(
        Output("imshow-graph", "figure"),
        Output("timeseries-graph", "figure"),
        Output("fiberprofile-graph", "figure"),
        Input("channel-dropdown", "value"),
        Input("cmap-dropdown", "value"),
        Input("time-slider", "value"),
        Input("fiber-slider", "value"),
        Input("click-store", "data"),
        Input("temp-slider", "value"),
    )
    def _update_figures(channel_name, cmap_name, time_range, fiber_range, click_store, temp_range):
        df = channel_dfs[channel_name]
        actual_fiber_range = [-fiber_range[1], -fiber_range[0]]
        d0 = float(min(actual_fiber_range))
        d1 = float(max(actual_fiber_range))

        window_df = _window_df(df, time_range, actual_fiber_range)

        if window_df.empty:
            empty_fig = go.Figure()
            empty_fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="black",
                plot_bgcolor="black",
                title="No data in selected axis limits",
            )
            return empty_fig, empty_fig, empty_fig

        if click_store is None:
            click_ts = window_df.index[len(window_df.index) // 2]
            click_dist = float(window_df.columns[len(window_df.columns) // 2])
        else:
            click_ts = pd.to_datetime(click_store["ts"])
            click_dist = float(click_store["dist"])

        # Snap click to nearest available sample in the currently visible window.
        ts_idx, snapped_ts = _nearest_timestamp(window_df.index, click_ts)
        dist_idx, snapped_dist = _nearest_value(window_df.columns.to_numpy(dtype=float), click_dist)

        # ts_idx and dist_idx are computed for snapping consistency.
        _ = ts_idx, dist_idx

        temp_min = float(temp_range[0])
        temp_max = float(temp_range[1])
        temp_min = max(temp_min, MIN_PHYSICAL_TEMP_C)
        temp_min = min(temp_min, MAX_PHYSICAL_TEMP_C)
        temp_max = max(temp_max, MIN_PHYSICAL_TEMP_C)
        temp_max = min(temp_max, MAX_PHYSICAL_TEMP_C)
        if temp_min >= temp_max:
            temp_min = float(window_df.to_numpy().min())
            temp_max = float(window_df.to_numpy().max())
            temp_min = max(temp_min, MIN_PHYSICAL_TEMP_C)
            temp_min = min(temp_min, MAX_PHYSICAL_TEMP_C)
            temp_max = max(temp_max, MIN_PHYSICAL_TEMP_C)
            temp_max = min(temp_max, MAX_PHYSICAL_TEMP_C)

        display_df = _downsample_for_heatmap(window_df)

        imshow_fig = _heatmap_figure(
            window_df=display_df,
            click_ts=snapped_ts,
            click_dist=snapped_dist,
            x_range=[window_df.index[0], window_df.index[-1]],
            y_range=[d0, d1],
            temp_min=temp_min,
            temp_max=temp_max,
            cmap_name=cmap_name,
        )

        time_fig = _time_series_figure(
            window_df,
            snapped_ts,
            snapped_dist,
            channel_name,
            temp_min,
            temp_max,
        )
        fiber_fig = _fiber_profile_figure(
            window_df,
            snapped_ts,
            snapped_dist,
            channel_name,
            temp_min,
            temp_max,
        )

        return imshow_fig, time_fig, fiber_fig

    @app.callback(
        Output("cmap-wrapper-div", "style"),
        Input("cmap-dropdown", "value"),
    )
    def _update_cmap_dropdown_style(selected_cmap):
        start_color = CMAP_START_COLORS.get(str(selected_cmap).lower(), "rgb(100,100,100)")
        return {
            "width": "120px",
            "minWidth": "120px",
            "marginBottom": "0px",
            "paddingBottom": "2px",
            "borderBottom": f"2px solid {start_color}",
        }

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive QC imshow viewer for combined channel pickle data."
    )
    parser.add_argument(
        "--pickle",
        default=str(DEFAULT_PICKLE_PATH),
        help=(
            "Path to combined channel pickle (channel -> {'df': DataFrame}). "
            f"Defaults to: {DEFAULT_PICKLE_PATH}"
        ),
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind Dash app.")
    parser.add_argument("--port", type=int, default=8050, help="Port to bind Dash app.")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable Dash debug mode.",
    )
    parser.add_argument(
        "--no-browser",
        dest="no_browser",
        action="store_true",
        help="Do not open a browser tab automatically on startup.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pickle_path = Path(args.pickle)
    channel_dfs = _load_combined_pickle(pickle_path)

    app = make_app(channel_dfs)
    url = f"http://{args.host}:{args.port}"
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)


if __name__ == "__main__":
    main()
