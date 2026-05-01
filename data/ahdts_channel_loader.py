#!/usr/bin/env python3
"""Generic channel-based DTS XML loading utilities.

This module contains reusable helpers for reading XML data from multiple channel
folders, converting the requested signal to dataframes, and saving the combined
result to a single pickle file. It intentionally contains no experiment-specific
settings.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from ahdts import (
    data_to_df,
    get_filepaths,
    save_as_pickle,
    xml_to_dict2,
)


def build_combined_channel_pickle(base_dir, channel_names, output_pickle_path, data_key="Temperature", use_multiprocessing=False, dtype="float32"):
    """Load XML data for channels under base_dir and save one combined pickle.

    Parameters
    ----------
    base_dir : str or Path
        Directory that contains channel subfolders.
    channel_names : list[str]
        Names of subfolders to load (for example: "channel 1", "channel 2").
    output_pickle_path : str or Path
        Full output pickle filepath, including filename and .pickle extension.
    data_key : str
        Signal key passed to data_to_df, defaults to "Temperature".
    use_multiprocessing : bool
        Whether to use multiprocessing, defaults to False.
    dtype : str or numpy.dtype
        Data type for temperature values, defaults to "float32".
        Options: "float32" (default), "float16", "int16" (with 100x scaling).
    """
    base_dir = Path(base_dir)
    output_pickle_path = Path(output_pickle_path)

    if not base_dir.exists():
        raise FileNotFoundError(f"Base directory not found: {base_dir}")

    all_channel_data = {}
    for channel_name in channel_names:
        channel_dir = base_dir / channel_name
        if not channel_dir.exists():
            logging.warning(f"Channel folder not found, skipping: {channel_dir}")
            continue

        xml_files = get_filepaths(channel_dir, "xml")
        if not xml_files:
            logging.warning(f"No XML files found in {channel_name}, skipping: {channel_dir}")
            continue

        print(f"Loading {channel_name}: {len(xml_files)} xml files")
        data_dict = xml_to_dict2(xml_files, use_multiprocessing=use_multiprocessing)
        df = data_to_df(data_dict, data_key).astype(dtype)

        all_channel_data[channel_name] = {
            "df": df,
            "n_files": len(xml_files),
            "distance_min": float(df.columns.min()),
            "distance_max": float(df.columns.max()),
        }

    if not all_channel_data:
        raise ValueError(f"No channels loaded successfully from {base_dir}. Check that channel folders exist and contain XML files.")

    output_dir = output_pickle_path.parent
    output_name = output_pickle_path.stem
    save_as_pickle(output_dir, all_channel_data, output_name)
    print(f"Saved combined pickle: {output_pickle_path} ({len(all_channel_data)} channels)")


def build_qc_snapshot_pickle(all_channel_data, timestamp_str, output_pickle_path):
    """Extract a snapshot at a specific timestamp from all channels and save to pickle.

    Parameters
    ----------
    all_channel_data : dict
        Combined channel data dictionary (output from build_combined_channel_pickle).
    timestamp_str : str
        Timestamp in ISO format (YYYY-MM-DD HH:MM:SS) to extract.
    output_pickle_path : str or Path
        Full output pickle filepath for the QC snapshot.
    """
    import pandas as pd
    from ahdts import save_as_pickle

    output_pickle_path = Path(output_pickle_path)
    timestamp = pd.to_datetime(timestamp_str)

    qc_snapshot = {}
    for channel_name, channel_payload in all_channel_data.items():
        df = channel_payload["df"]
        if timestamp not in df.index:
            nearest_idx = int(np.abs((df.index - timestamp).asi8).argmin())
            nearest_ts = df.index[nearest_idx]
            print(
                f"Timestamp {timestamp_str} not found in {channel_name}. "
                f"Using nearest: {nearest_ts}"
            )
            row = df.loc[nearest_ts]
            selected_timestamp = nearest_ts
        else:
            row = df.loc[timestamp]
            selected_timestamp = timestamp

        qc_snapshot[channel_name] = {
            "temperature": row.values,
            "distance": df.columns.values,
            "requested_timestamp": str(timestamp_str),
            "timestamp": str(selected_timestamp),
        }

    output_dir = output_pickle_path.parent
    output_name = output_pickle_path.stem
    save_as_pickle(output_dir, qc_snapshot, output_name)
    print(f"Saved QC snapshot pickle: {output_pickle_path}")


def summarize_peak_temperatures(
    all_channel_data,
    plot_locations,
    location_info,
    measurement_length_start,
    measurement_length_end,
):
    if not plot_locations:
        logging.warning("summarize_peak_temperatures called with no plot locations; returning empty summary.")
        return pd.DataFrame()

    rows = []
    for location_key in plot_locations:
        if location_key not in location_info:
            logging.warning(f"Unknown location key '{location_key}', skipping.")
            continue

        channel_name = location_info[location_key][3]
        if channel_name not in all_channel_data:
            logging.warning(f"Channel not found in combined data for '{location_key}': {channel_name}, skipping.")
            continue

        df = all_channel_data[channel_name]["df"]
        distance_mask = (
            (df.columns >= measurement_length_start)
            & (df.columns <= measurement_length_end)
        )
        if not distance_mask.any():
            logging.warning(
                f"No distance columns found for {location_key} within "
                f"{measurement_length_start} to {measurement_length_end} m; skipping."
            )
            continue

        interval_df = df.loc[:, distance_mask]
        values = interval_df.to_numpy(copy=False)
        peak_flat_index = np.nanargmax(values)
        time_idx, distance_idx = np.unravel_index(peak_flat_index, values.shape)

        peak_timestamp = interval_df.index[time_idx]
        peak_distance = float(interval_df.columns[distance_idx])
        peak_temperature = float(values[time_idx, distance_idx])
        relative_minutes = (peak_timestamp - interval_df.index[0]).total_seconds() / 60.0

        rows.append(
            {
                "location": location_key,
                "channel": channel_name,
                "peak_temp_C": round(peak_temperature, 3),
                "fiber_length_m": round(peak_distance, 3),
                "timestamp": peak_timestamp,
                "relative_minutes": round(relative_minutes, 2),
                "n_times": interval_df.shape[0],
                "n_positions": interval_df.shape[1],
                "interval_start_m": measurement_length_start,
                "interval_end_m": measurement_length_end,
            }
        )

    if not rows:
        logging.warning("No peak temperature rows generated; returning empty summary.")
        return pd.DataFrame()

    summary = pd.DataFrame(rows).sort_values(["peak_temp_C", "location"], ascending=[False, True])

    print("\nPeak temperature overview")
    print(
        summary[
            [
                "location",
                "channel",
                "peak_temp_C",
                "fiber_length_m",
                "timestamp",
                "relative_minutes",
            ]
        ].to_string(index=False)
    )

    return summary


if __name__ == "__main__":
    raise SystemExit(
        "This module is generic and imported by experiment scripts. "
        "Run data/ates_action_flush_experiment.py instead."
    )
