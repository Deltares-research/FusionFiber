#!/usr/bin/env python3
'''
Create comparison plots for groundwater-flow simulation runs and measured data.

Workflow and outcomes:
1. Load processed simulation data from gw_simulation_data.pkl.
2. Load measured data from a user-defined pickle file.
3. Select which gw runs to include.
4. Pair measured series to simulations using nearest darcy_flux.
5. Generate three figures from the same data:
	- Time in minutes (linear x-axis)
	- Time in seconds (linear x-axis)
	- Time in seconds (logarithmic x-axis)
6. Save all figures to the local plots folder.

Simulation curves and measured curves each use their own configurable
colormap. Measured curves use solid line style.
'''

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import pickle
import math
import numpy as np
import pandas as pd
import re
import difflib
from pathlib import Path

# Setup and data loading
script_dir = Path(__file__).parent
simulation_pickle_file = script_dir / 'gw_simulation_data.pkl'
measurement_pickle_file = script_dir / 'gw_measured_data_position_4.pickle'
plots_dir = script_dir / 'plots'
plots_dir.mkdir(exist_ok=True)

# Load simulation data
with open(simulation_pickle_file, 'rb') as f:
	simulation_data = pickle.load(f)

# Load measured data
with open(measurement_pickle_file, 'rb') as f:
	measurement_raw = pickle.load(f)

# Selection settings
GW_IDS = ['gw300', 'gw301', 'gw302', 'gw303', 'gw304', 'gw305', 'gw306', 'gw307', 'gw308', 'gw309', 'gw310']
# GW_IDS = [f"gw{i:02d}" for i in range(100, 108)]

# Plot settings
LINE_WIDTH = 1.5  # line thickness for plotted curves
SIMULATION_COLORMAP_NAME = 'cividis'  # colormap name for simulation curves
MEASUREMENT_COLORMAP_NAME = 'rocket'  # colormap name for measured curves; includes a built-in fallback for 'rocket'
legend_label = 'darcy_flux'  # column in simulation data used for curve labels
legend_title = 'Darcy Flux (m/dag)'
legend_unit = 'm/dag'
legend_decimals = 1
max_flux_match_delta = 0.6  # maximum absolute delta in m/dag for auto-matching measured to simulated series
APPLY_SAVGOL_FILTER = True  # if True, smooth y-values before plotting
SAVGOL_FILTER_TARGET = 'measurements'  # one of: 'measurements', 'simulations', 'both'
SAVGOL_WINDOW_LENGTH = 21  # odd number of samples used by the smoothing window
SAVGOL_POLYORDER = 3  # polynomial order for Savitzky-Golay smoothing

# outfile_basename = 'Darcy_flow_core_average_vs_measurements'
outfile_basename = 'Thermal_conductivity_vs_measurements'

required_columns = {'gw', 'Time_min', 'Core_average', 'darcy_flux'}
missing_columns = required_columns - set(simulation_data.columns)
if missing_columns:
	raise ValueError(f"Missing required columns in simulation pickle data: {sorted(missing_columns)}")

all_gw = sorted(simulation_data['gw'].dropna().astype(str).unique())
selected_gw = [gw for gw in GW_IDS if gw in all_gw]
missing_gw = [gw for gw in GW_IDS if gw not in all_gw]

if missing_gw:
	print(f"Warning: {len(missing_gw)} requested GW IDs not found in simulation data: {', '.join(missing_gw)}")
	for gw in missing_gw:
		suggestions = difflib.get_close_matches(gw, all_gw, n=3, cutoff=0.4)
		if suggestions:
			print(f"  - {gw} -> did you mean: {', '.join(suggestions)}?")
if not selected_gw:
	raise ValueError('No gw IDs selected for plotting.')

# Plot configuration
plt.rcParams.update({'figure.figsize': (12, 7), 'font.size': 12, 'savefig.dpi': 600, 'lines.linewidth': LINE_WIDTH})


def format_legend_label(value, unit='', decimals=1):
	if isinstance(value, (int, float, np.integer, np.floating)) and not np.isnan(value):
		formatted = f"{float(value):.{decimals}f}"
		return f"{formatted} {unit}".strip() if unit else formatted
	return str(value)


def get_configured_colormap(cmap_name):
	if cmap_name == 'rocket':
		rocket_colors = [
			'#03051a', '#221331', '#451c47', '#6a1f56', '#942667',
			'#bc3754', '#da5a49', '#f28b49', '#f8c56b', '#faf0b3'
		]
		return LinearSegmentedColormap.from_list('rocket', rocket_colors)
	return plt.get_cmap(cmap_name)


def savgol_smooth(y_values, window_length, polyorder):
	if window_length < 3:
		return y_values
	if window_length % 2 == 0:
		window_length -= 1
	if window_length <= polyorder:
		window_length = polyorder + 2 + ((polyorder + 2) % 2 == 0)
	if len(y_values) < window_length:
		window_length = len(y_values) if len(y_values) % 2 == 1 else len(y_values) - 1
	if window_length < 3 or window_length <= polyorder:
		return y_values

	half_window = window_length // 2
	x = np.arange(-half_window, half_window + 1, dtype=float)
	design = np.vander(x, polyorder + 1, increasing=True)
	coefficients = np.linalg.pinv(design)[0]
	padded = np.pad(y_values, (half_window, half_window), mode='edge')
	return np.convolve(padded, coefficients[::-1], mode='valid')


def maybe_smooth_y(y_values, target_kind):
	if not APPLY_SAVGOL_FILTER:
		return y_values
	if SAVGOL_FILTER_TARGET not in {'measurements', 'simulations', 'both'}:
		raise ValueError("SAVGOL_FILTER_TARGET must be 'measurements', 'simulations', or 'both'")
	if SAVGOL_FILTER_TARGET not in {target_kind, 'both'}:
		return y_values
	return savgol_smooth(y_values, SAVGOL_WINDOW_LENGTH, SAVGOL_POLYORDER)


def parse_flux_from_measurement_key(series_name):
	match = re.search(r'([-+]?\d*\.?\d+)\s*m\s*/\s*dag', str(series_name), flags=re.IGNORECASE)
	if match:
		return float(match.group(1))
	return None


def normalize_measurements(raw):
	if isinstance(raw, dict):
		measurement_dict = raw
	elif isinstance(raw, pd.DataFrame):
		measurement_dict = {col: raw[col].dropna() for col in raw.columns}
	else:
		raise ValueError(
			"Unsupported measurement pickle format. Expected dict[str, Series] or pandas DataFrame."
		)

	cleaned = {}
	for key, value in measurement_dict.items():
		if isinstance(value, pd.Series):
			series = value.dropna().copy()
		elif isinstance(value, (list, tuple, np.ndarray)):
			series = pd.Series(value)
		else:
			continue

		if series.empty:
			continue

		series.index = pd.to_numeric(series.index, errors='coerce')
		series = pd.to_numeric(series, errors='coerce')
		valid = (~pd.isna(series.index)) & (~pd.isna(series.values))
		series = pd.Series(series.values[valid], index=series.index[valid]).sort_index()
		if not series.empty:
			series.index.name = 'elapsed_time_min'
			cleaned[str(key)] = series

	if not cleaned:
		raise ValueError('No valid measured series found in measurement pickle file.')

	return cleaned


def choose_measurement_mapping(plot_data, measurement_series_dict, max_delta):
	simulation_flux_by_gw = {}
	simulation_fluxes = []
	for gw_name, gw_data in plot_data:
		flux = pd.to_numeric(gw_data['darcy_flux'], errors='coerce').iloc[0]
		if pd.isna(flux):
			continue
		simulation_flux_by_gw[gw_name] = float(flux)
		simulation_fluxes.append(float(flux))

	simulation_fluxes = np.array(sorted(set(simulation_fluxes)), dtype=float)
	mapping = {}
	unmapped = []
	for series_name in measurement_series_dict:
		measured_flux = parse_flux_from_measurement_key(series_name)
		if measured_flux is None or simulation_fluxes.size == 0:
			mapping[series_name] = None
			unmapped.append(series_name)
			continue

		nearest_flux = float(simulation_fluxes[np.argmin(np.abs(simulation_fluxes - measured_flux))])
		if abs(nearest_flux - measured_flux) > max_delta:
			mapping[series_name] = None
			unmapped.append(series_name)
			continue
		candidates = sorted([gw for gw, flux in simulation_flux_by_gw.items() if abs(flux - nearest_flux) < 1e-12])
		mapping[series_name] = candidates[0] if candidates else None
		if mapping[series_name] is None:
			unmapped.append(series_name)

	return mapping, unmapped, simulation_flux_by_gw


def create_plot(
	x_mode='minutes',
	log_x=False,
	file_name='Darcy_flow_core_average_vs_measurements.png',
	time_start=None,
	time_end=None,
	label_column='darcy_flux',
	label_title='Darcy flux',
	label_unit='m/dag',
	label_decimals=1,
	simulation_cmap_name='cividis',
	measurement_cmap_name='rocket',
	cmap_start=0.0,
	cmap_end=1.0
):
	'''
	Create and save one Core_average plot for selected simulation runs and measured data.
	'''
	if x_mode not in {'minutes', 'seconds'}:
		raise ValueError("x_mode must be 'minutes' or 'seconds'")
	if cmap_start < 0 or cmap_end > 1 or cmap_start > cmap_end:
		raise ValueError('cmap_start/cmap_end must satisfy 0 <= cmap_start <= cmap_end <= 1')
	if label_column not in simulation_data.columns:
		available_cols = ', '.join(sorted(simulation_data.columns))
		raise ValueError(
			f"label_column '{label_column}' not found in simulation data columns. "
			f"Run gwflow_process_simulations.py to refresh the pickle with batch variables. "
			f"Available columns: {available_cols}"
		)

	if x_mode == 'seconds':
		filter_time_start = (time_start / 60.0) if time_start is not None else None
		filter_time_end = (time_end / 60.0) if time_end is not None else None
	else:
		filter_time_start = time_start
		filter_time_end = time_end

	plot_data = []
	for gw_name in selected_gw:
		gw_mask = simulation_data['gw'] == gw_name
		if filter_time_start is not None:
			gw_mask &= simulation_data['Time_min'] >= filter_time_start
		if filter_time_end is not None:
			gw_mask &= simulation_data['Time_min'] <= filter_time_end
		gw_data = simulation_data[gw_mask]
		if gw_data.empty:
			continue
		plot_data.append((gw_name, gw_data))

	if not plot_data:
		raise ValueError('No simulation data available for the selected gw IDs and time range.')

	measurement_series = normalize_measurements(measurement_raw)
	measurement_mapping, unmapped_measurements, sim_flux_by_gw = choose_measurement_mapping(
		plot_data,
		measurement_series,
		max_flux_match_delta
	)

	simulation_cmap = get_configured_colormap(simulation_cmap_name)
	measurement_cmap = get_configured_colormap(measurement_cmap_name)
	if len(plot_data) == 1:
		simulation_color_values = np.array([(cmap_start + cmap_end) / 2])
	else:
		simulation_color_values = np.linspace(cmap_start, cmap_end, len(plot_data))

	measurement_names = list(measurement_series.keys())
	if len(measurement_names) == 1:
		measurement_color_values = np.array([(cmap_start + cmap_end) / 2])
	else:
		measurement_color_values = np.linspace(cmap_start, cmap_end, len(measurement_names))
	measurement_color_map = {
		series_name: measurement_cmap(color_value)
		for series_name, color_value in zip(measurement_names, measurement_color_values)
	}

	fig, ax = plt.subplots()
	plotted_sim_curves = 0
	skipped_missing_label = []
	gw_color_map = {}

	for (gw_name, gw_data), color_value in zip(plot_data, simulation_color_values):
		label_value = gw_data[label_column].iloc[0]
		if (not isinstance(label_value, (str, bytes)) and np.isnan(label_value)) or (
			isinstance(label_value, str) and not label_value.strip()
		):
			skipped_missing_label.append(gw_name)
			continue

		label = f"Sim {format_legend_label(label_value, unit=label_unit, decimals=label_decimals)}"
		line_color = simulation_cmap(color_value)
		gw_color_map[gw_name] = line_color

		if x_mode == 'seconds':
			x_values = gw_data['Time_min'] * 60.0
		else:
			x_values = gw_data['Time_min']
		y_values = maybe_smooth_y(gw_data['Core_average'].to_numpy(dtype=float), 'simulations')

		if log_x:
			positive_mask = x_values > 0
			x_values = x_values[positive_mask]
			y_values = y_values[positive_mask]
			if x_values.empty:
				continue
			ax.semilogx(x_values, y_values, alpha=0.9, label=label, color=line_color)
			plotted_sim_curves += 1
		else:
			ax.plot(x_values, y_values, alpha=0.9, label=label, color=line_color)
			plotted_sim_curves += 1

	if plotted_sim_curves == 0:
		raise ValueError(
			f"No simulation curves left to plot. All selected GW runs are missing '{label_column}' values "
			"(often caused by commenting out rows in batch_variables_gwflow.txt)."
		)

	plotted_meas_curves = 0
	for series_name, series in measurement_series.items():
		mapped_gw = measurement_mapping.get(series_name)
		series_color = measurement_color_map[series_name]

		if x_mode == 'seconds':
			x_values = series.index.to_numpy(dtype=float) * 60.0
		else:
			x_values = series.index.to_numpy(dtype=float)
		y_values = maybe_smooth_y(series.to_numpy(dtype=float), 'measurements')

		if time_start is not None:
			mask = x_values >= time_start
			x_values = x_values[mask]
			y_values = y_values[mask]
		if time_end is not None:
			mask = x_values <= time_end
			x_values = x_values[mask]
			y_values = y_values[mask]

		if x_values.size == 0:
			continue

		if log_x:
			positive_mask = x_values > 0
			x_values = x_values[positive_mask]
			y_values = y_values[positive_mask]
			if x_values.size == 0:
				continue
			ax.semilogx(x_values, y_values, linestyle='-', linewidth=LINE_WIDTH * 0.9, alpha=0.85, color=series_color, label=f"Meas {series_name}")
		else:
			ax.plot(x_values, y_values, linestyle='-', linewidth=LINE_WIDTH * 0.9, alpha=0.85, color=series_color, label=f"Meas {series_name}")
		plotted_meas_curves += 1

	ax.set_title('Temperature Evolution (Core_average) - Simulation vs Measurement', fontweight='bold')
	ax.set_ylabel('Temperature (degC)')
	ax.grid(True, alpha=0.3)

	if x_mode == 'seconds':
		ax.set_xlabel('Time (seconds)')
	else:
		ax.set_xlabel('Time (minutes)')

	if log_x:
		log_x_start = time_start if (time_start is not None and time_start > 0) else None
		log_x_end = time_end if (time_end is not None and time_end > 0) else None
		if log_x_start is not None or log_x_end is not None:
			ax.set_xlim(left=log_x_start, right=log_x_end)
	else:
		if time_start is not None or time_end is not None:
			ax.set_xlim(left=time_start, right=time_end)

	legend_entries = plotted_sim_curves + plotted_meas_curves
	legend_cols = min(10, max(5, math.ceil(max(1, legend_entries) / 6)))
	legend_rows = math.ceil(max(1, legend_entries) / legend_cols)
	fig.subplots_adjust(bottom=min(0.6, 0.12 + 0.05 * legend_rows))
	ax.legend(
		loc='upper center',
		bbox_to_anchor=(0.5, -0.16),
		ncol=legend_cols,
		title=label_title,
		frameon=True,
		fontsize=8
	)

	plt.tight_layout()
	output_path = plots_dir / file_name
	plt.savefig(output_path, bbox_inches='tight')
	plt.close(fig)

	if skipped_missing_label:
		print(
			f"Skipped {len(skipped_missing_label)} GW runs with missing '{label_column}' values: "
			f"{', '.join(skipped_missing_label)}"
		)

	if unmapped_measurements:
		print(
			f"Warning: {len(unmapped_measurements)} measured series could not be mapped to simulation runs by darcy_flux "
			f"(max_delta={max_flux_match_delta}); plotted with measurement colormap: {', '.join(unmapped_measurements)}"
		)

	for series_name, mapped_gw in measurement_mapping.items():
		if mapped_gw is None:
			continue
		flux = sim_flux_by_gw.get(mapped_gw)
		print(f"Mapped measured '{series_name}' -> simulation {mapped_gw} (darcy_flux={flux})")

	return output_path


saved_minutes = create_plot(
	x_mode='minutes',
	log_x=False,
	time_start=0,
	time_end=55,
	simulation_cmap_name=SIMULATION_COLORMAP_NAME,
	measurement_cmap_name=MEASUREMENT_COLORMAP_NAME,
	label_column=legend_label,
	label_title=legend_title,
	label_unit=legend_unit,
	label_decimals=legend_decimals,
	file_name=f'{outfile_basename}.png'
)

saved_seconds = create_plot(
	x_mode='seconds',
	log_x=False,
	time_start=0,
	time_end=55 * 60,
	simulation_cmap_name=SIMULATION_COLORMAP_NAME,
	measurement_cmap_name=MEASUREMENT_COLORMAP_NAME,
	label_column=legend_label,
	label_title=legend_title,
	label_unit=legend_unit,
	label_decimals=legend_decimals,
	file_name=f'{outfile_basename}_seconds.png'
)

saved_seconds_logx = create_plot(
	x_mode='seconds',
	log_x=True,
	time_start=60,
	time_end=55 * 60,
	simulation_cmap_name=SIMULATION_COLORMAP_NAME,
	measurement_cmap_name=MEASUREMENT_COLORMAP_NAME,
	label_column=legend_label,
	label_title=legend_title,
	label_unit=legend_unit,
	label_decimals=legend_decimals,
	file_name=f'{outfile_basename}_seconds_logx.png'
)

print('✓ Simulation vs measurement Core_average plots generated successfully!')
print(f'  Saved: {saved_minutes}')
print(f'  Saved: {saved_seconds}')
print(f'  Saved: {saved_seconds_logx}')
