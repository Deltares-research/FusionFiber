#%%
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

#%%
# Selection settings
# GW_IDS = None  # None: plot measurements only (no simulations); []: include all available gw runs; [...]: plot specific runs
#GW_IDS = ['gw401', 'gw402', 'gw403', 'gw404', 'gw405', 'gw406', 'gw407', 'gw408', 'gw409', 'gw410', 'gw411', 'gw412','gw413', 'gw414', 'gw415', 'gw416', 'gw417', 'gw418', 'gw419', 'gw420']
GW_IDS = ['gw401', 'gw406', 'gw411', 'gw416', 'gw421']

#MEAS_IDS = []  # None: plot simulations only (no measurements); []: include all measured series; [...]: plot specific measured series
MEAS_IDS = ["Thermal response test", "P6 = 1.2 m/dag", "P4 = 2.8 m/dag",	"S5 = 11.6 m/dag", "S1 = 18.7 m/dag", "S4 = 19.6 m/dag", "S2 = 20.1 m/dag",	"S3 = 21.5 m/dag"]  # None: plot simulations only (no measurements); []: include all measured series; [...]: plot specific measured series
# MEAS_IDS = None

# Plot settings
LINE_WIDTH = 1.5  # line thickness for plotted curves
SIMULATION_COLORMAP_NAME = 'viridis'  # colormap name for simulation curves
SIMULATION_LINESTYLE = '--'  # line style for simulation/model curves (e.g. '-', '--', '-.', ':')
SIMULATION_ALPHA = 0.7  # transparency for simulation/model curves in [0, 1]
MEASUREMENT_COLORMAP_NAME = 'plasma'  # colormap name for measured curves
legend_label = 'darcy_flux'  # column in simulation data used for curve labels
legend_title = 'Darcy Flux (m/dag)'
legend_unit = 'm/dag'
legend_decimals = 1
max_flux_match_delta = 0.6  # maximum absolute delta in m/dag for auto-matching measured to simulated series
APPLY_SAVGOL_FILTER = True  # if True, smooth y-values before plotting (disabled by default due to edge effects)
SAVGOL_FILTER_TARGET = 'measurements'  # one of: 'measurements', 'simulations', 'both'
SAVGOL_WINDOW_LENGTH = 15  # odd number of samples used by the smoothing window
SAVGOL_POLYORDER = 3  # polynomial order for Savitzky-Golay smoothing
MEASUREMENT_NORMALIZE_TO_TEMP_C = 20.0  # shift each measured series so its first value equals this temperature; None disables normalization
MEASUREMENT_NORMALIZE_BASELINE_POINTS = 1  # number of initial samples used to compute normalization baseline; 1 matches first-point behavior
MEASUREMENT_NORMALIZE_VARIATION_WARNING_DEGC = 0.5  # warn if spread (max-min) of baseline points exceeds this threshold
MEASUREMENT_CROP_START_TIME_MIN = 0.3  # crop measured data before this elapsed time in minutes; retained data is re-zeroed
PLOT_TMAX_MIN = 40  # max x-axis time for plots in minutes; use None to keep full duration
PLOT_YMIN = 19  # lower y-axis limit (degC); None = automatic
PLOT_YMAX = 56  # upper y-axis limit (degC); None = automatic

# outfile_basename = 'Darcy_flow_core_average_vs_measurements'
outfile_basename = 'Simulations_vs_measurements'

required_columns = {'gw', 'Time_min', 'Core_average', 'darcy_flux'}
missing_columns = required_columns - set(simulation_data.columns)
if missing_columns:
	raise ValueError(f"Missing required columns in simulation pickle data: {sorted(missing_columns)}")

all_gw = sorted(simulation_data['gw'].dropna().astype(str).unique())
if GW_IDS is None:
	selected_gw = []
	missing_gw = []
elif not GW_IDS:
	selected_gw = all_gw
	missing_gw = []
else:
	selected_gw = [gw for gw in GW_IDS if gw in all_gw]
	missing_gw = [gw for gw in GW_IDS if gw not in all_gw]

if missing_gw:
	print(f"Warning: {len(missing_gw)} requested GW IDs not found in simulation data: {', '.join(missing_gw)}")
	for gw in missing_gw:
		suggestions = difflib.get_close_matches(gw, all_gw, n=3, cutoff=0.4)
		if suggestions:
			print(f"  - {gw} -> did you mean: {', '.join(suggestions)}?")
if not selected_gw and GW_IDS is not None:
	raise ValueError('No gw IDs selected for plotting.')
if PLOT_TMAX_MIN is not None and PLOT_TMAX_MIN <= 0:
	raise ValueError('PLOT_TMAX_MIN must be > 0 or None.')

# Plot configuration
plt.rcParams.update({'figure.figsize': (12, 7), 'font.size': 12, 'savefig.dpi': 600, 'lines.linewidth': LINE_WIDTH})

# Fixed plot-area dimensions; figure height is adjusted dynamically to accommodate the legend.
# Increase PLOT_AREA_HEIGHT_IN to make the axes taller; the figure grows automatically.
FIG_WIDTH_IN = 12.0
PLOT_AREA_HEIGHT_IN = 5.0   # height of the axes (plot area), kept constant across all figures
TOP_MARGIN_IN = 0.5         # space above the axes
BOTTOM_MARGIN_IN = 0.2      # space below the legend
LEGEND_ANCHOR_Y = -0.16     # bbox_to_anchor y-coordinate (axes fraction); must match legend calls below
LEGEND_ROW_HEIGHT_IN = 0.22 # estimated height per legend row in inches
LEGEND_TITLE_HEIGHT_IN = 0.3  # estimated height of the legend title in inches


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
	if cmap_name == 'plasma':
		return plt.get_cmap('plasma')
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


def measurement_sort_key(series_name):
	name_lower = str(series_name).strip().lower()
	if name_lower == 'thermal response test':
		return (-1, 0.0, name_lower)
	flux = parse_flux_from_measurement_key(series_name)
	if flux is not None:
		return (0, float(flux), name_lower)
	return (1, float('inf'), name_lower)


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


def normalize_measurements_to_reference_temperature(measurement_series_dict, target_temp_c):
	if target_temp_c is None:
		return measurement_series_dict
	if MEASUREMENT_NORMALIZE_BASELINE_POINTS < 1:
		raise ValueError('MEASUREMENT_NORMALIZE_BASELINE_POINTS must be >= 1.')

	normalized = {}
	for series_name, series in measurement_series_dict.items():
		if series.empty:
			continue
		baseline_count = min(int(MEASUREMENT_NORMALIZE_BASELINE_POINTS), len(series))
		baseline_window = series.iloc[:baseline_count]
		baseline_value = float(baseline_window.mean())
		baseline_spread = float(baseline_window.max() - baseline_window.min())
		offset = float(target_temp_c) - baseline_value
		if baseline_count == 1:
			print(
				f"Normalize '{series_name}': "
				f"starting temperature = {baseline_value:.4f} degC "
				f"-> target {target_temp_c:.4f} degC (offset = {offset:+.4f} degC)"
			)
		else:
			point_strs = ', '.join(f'{v:.4f}' for v in baseline_window.values)
			print(
				f"Normalize '{series_name}': "
				f"baseline points (n={baseline_count}) = [{point_strs}] degC, "
				f"mean = {baseline_value:.4f} degC "
				f"-> target {target_temp_c:.4f} degC (offset = {offset:+.4f} degC)"
			)
		if baseline_spread > float(MEASUREMENT_NORMALIZE_VARIATION_WARNING_DEGC):
			print(
				f"  Warning: normalization baseline spread for '{series_name}' is {baseline_spread:.3f} degC "
				f"over first {baseline_count} points (> {MEASUREMENT_NORMALIZE_VARIATION_WARNING_DEGC} degC)."
			)
		normalized_series = series + offset
		normalized_series.index.name = series.index.name
		normalized[series_name] = normalized_series

	if not normalized:
		raise ValueError('No measured data available after temperature normalization step.')

	return normalized


def crop_measurements_to_start_time(measurement_series_dict, crop_start_time_min):
	if crop_start_time_min is None:
		return measurement_series_dict
	if crop_start_time_min < 0:
		raise ValueError('MEASUREMENT_CROP_START_TIME_MIN must be >= 0 or None.')

	cropped = {}
	fully_trimmed = []
	for series_name, series in measurement_series_dict.items():
		trimmed_series = series[series.index >= crop_start_time_min].copy()
		if trimmed_series.empty:
			fully_trimmed.append(series_name)
			continue
		trimmed_series.index = trimmed_series.index - float(trimmed_series.index[0])
		trimmed_series.index.name = 'elapsed_time_min'
		cropped[series_name] = trimmed_series

	if not cropped:
		raise ValueError(
			'No measured data remains after applying MEASUREMENT_CROP_START_TIME_MIN='
			f'{crop_start_time_min}.'
		)

	if fully_trimmed:
		print(
			f"Skipped {len(fully_trimmed)} measured series fully before crop start "
			f"({crop_start_time_min} min): {', '.join(fully_trimmed)}"
		)

	return cropped


def select_measurements(measurement_series_dict, measurement_ids):
	all_measurements = sorted(measurement_series_dict.keys(), key=measurement_sort_key)
	if measurement_ids is None:
		return {}, all_measurements, []
	if not measurement_ids:
		return measurement_series_dict, all_measurements, []

	selected = {name: measurement_series_dict[name] for name in measurement_ids if name in measurement_series_dict}
	missing = [name for name in measurement_ids if name not in measurement_series_dict]
	return selected, all_measurements, missing


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
	if SIMULATION_ALPHA < 0 or SIMULATION_ALPHA > 1:
		raise ValueError('SIMULATION_ALPHA must be in the range [0, 1].')
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

	if not plot_data and len(selected_gw) > 0:
		raise ValueError('No simulation data available for the selected gw IDs and time range.')

	# If measurement-only mode (selected_gw is empty), allow empty plot_data
	measurement_series = crop_measurements_to_start_time(
		normalize_measurements_to_reference_temperature(
			normalize_measurements(measurement_raw),
			MEASUREMENT_NORMALIZE_TO_TEMP_C
		),
		MEASUREMENT_CROP_START_TIME_MIN
	)
	measurement_series, all_measurements, missing_meas = select_measurements(measurement_series, MEAS_IDS)
	if missing_meas:
		print(
			f"Warning: {len(missing_meas)} requested measurement IDs not found in measurement data: "
			f"{', '.join(missing_meas)}"
		)
		for meas_name in missing_meas:
			suggestions = difflib.get_close_matches(meas_name, all_measurements, n=3, cutoff=0.4)
			if suggestions:
				print(f"  - {meas_name} -> did you mean: {', '.join(suggestions)}?")
	if not measurement_series and MEAS_IDS is not None:
		raise ValueError('No measurement IDs selected for plotting.')
	if not plot_data and not measurement_series:
		raise ValueError('Nothing to plot: both selected simulation runs and selected measurements are empty.')

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

	measurement_names = sorted(measurement_series.keys(), key=measurement_sort_key)
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
	simulation_handles = []
	measurement_handles = []
	is_darcy_flux_label = str(label_column).strip().lower() == 'darcy_flux'
	if is_darcy_flux_label:
		sim_legend_title_text = 'Simulations (Darcy Flux)'
		meas_legend_title_text = 'Measurements (Darcy Flux)'
	else:
		sim_legend_title_text = f"Simulations ({label_title})"
		meas_legend_title_text = 'Measurements'

	for (gw_name, gw_data), color_value in zip(plot_data, simulation_color_values):
		label_value = gw_data[label_column].iloc[0]
		if (not isinstance(label_value, (str, bytes)) and np.isnan(label_value)) or (
			isinstance(label_value, str) and not label_value.strip()
		):
			skipped_missing_label.append(gw_name)
			continue

		if is_darcy_flux_label:
			entry_unit = str(label_unit).strip()
			numeric_label_value = pd.to_numeric(pd.Series([label_value]), errors='coerce').iloc[0]
			if pd.isna(numeric_label_value):
				formatted_label_value = str(label_value).strip()
				if entry_unit and not re.search(rf'\b{re.escape(entry_unit)}\b', formatted_label_value, flags=re.IGNORECASE):
					formatted_label_value = f"{formatted_label_value} {entry_unit}"
			else:
				formatted_label_value = f"{float(numeric_label_value):.{label_decimals}f} {entry_unit}".strip()
		else:
			formatted_label_value = format_legend_label(label_value, unit=label_unit, decimals=label_decimals)

		label = f"Sim {gw_name[2:]} = {formatted_label_value}"
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
			line = ax.semilogx(
				x_values,
				y_values,
				linestyle=SIMULATION_LINESTYLE,
				alpha=SIMULATION_ALPHA,
				label=label,
				color=line_color
			)[0]
			simulation_handles.append(line)
			plotted_sim_curves += 1
		else:
			line = ax.plot(
				x_values,
				y_values,
				linestyle=SIMULATION_LINESTYLE,
				alpha=SIMULATION_ALPHA,
				label=label,
				color=line_color
			)[0]
			simulation_handles.append(line)
			plotted_sim_curves += 1

	if plotted_sim_curves == 0 and len(selected_gw) > 0:
		raise ValueError(
			f"No simulation curves left to plot. All selected GW runs are missing '{label_column}' values "
			"(often caused by commenting out rows in batch_variables_gwflow.txt)."
		)

	plotted_meas_curves = 0
	for series_name in measurement_names:
		series = measurement_series[series_name]
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
			line = ax.semilogx(
				x_values,
				y_values,
				linestyle='-',
				linewidth=LINE_WIDTH * 0.9,
				alpha=0.85,
				color=series_color,
				label=f"Meas {series_name}"
			)[0]
			measurement_handles.append(line)
		else:
			line = ax.plot(
				x_values,
				y_values,
				linestyle='-',
				linewidth=LINE_WIDTH * 0.9,
				alpha=0.85,
				color=series_color,
				label=f"Meas {series_name}"
			)[0]
			measurement_handles.append(line)
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

	if PLOT_YMIN is not None or PLOT_YMAX is not None:
		ax.set_ylim(bottom=PLOT_YMIN, top=PLOT_YMAX)

	if plotted_sim_curves > 0 and plotted_meas_curves > 0:
		sim_cols = min(6, max(1, math.ceil(plotted_sim_curves / 4)))
		meas_cols = min(6, max(1, math.ceil(plotted_meas_curves / 4)))
		sim_rows = math.ceil(plotted_sim_curves / sim_cols)
		meas_rows = math.ceil(plotted_meas_curves / meas_cols)
		legend_height_in = LEGEND_TITLE_HEIGHT_IN + max(sim_rows, meas_rows) * LEGEND_ROW_HEIGHT_IN
		legend_top_offset_in = abs(LEGEND_ANCHOR_Y) * PLOT_AREA_HEIGHT_IN
		below_axes_in = legend_top_offset_in + legend_height_in + BOTTOM_MARGIN_IN
		fig_height_in = TOP_MARGIN_IN + PLOT_AREA_HEIGHT_IN + below_axes_in
		fig.set_size_inches(FIG_WIDTH_IN, fig_height_in)
		fig.subplots_adjust(
			bottom=below_axes_in / fig_height_in,
			top=1.0 - TOP_MARGIN_IN / fig_height_in
		)

		sim_labels = [h.get_label() for h in simulation_handles]
		meas_labels = [h.get_label() for h in measurement_handles]

		sim_legend = ax.legend(
			handles=simulation_handles,
			labels=sim_labels,
			loc='upper center',
			bbox_to_anchor=(0.25, -0.16),
			ncol=sim_cols,
			title=sim_legend_title_text,
			frameon=True,
			fontsize=8
		)
		meas_legend = ax.legend(
			handles=measurement_handles,
			labels=meas_labels,
			loc='upper center',
			bbox_to_anchor=(0.75, -0.16),
			ncol=meas_cols,
			title=meas_legend_title_text,
			frameon=True,
			fontsize=8
		)
		ax.add_artist(sim_legend)
	else:
		legend_entries = plotted_sim_curves + plotted_meas_curves
		legend_cols = min(10, max(5, math.ceil(max(1, legend_entries) / 6)))
		legend_rows = math.ceil(max(1, legend_entries) / legend_cols)
		legend_height_in = LEGEND_TITLE_HEIGHT_IN + legend_rows * LEGEND_ROW_HEIGHT_IN
		legend_top_offset_in = abs(LEGEND_ANCHOR_Y) * PLOT_AREA_HEIGHT_IN
		below_axes_in = legend_top_offset_in + legend_height_in + BOTTOM_MARGIN_IN
		fig_height_in = TOP_MARGIN_IN + PLOT_AREA_HEIGHT_IN + below_axes_in
		fig.set_size_inches(FIG_WIDTH_IN, fig_height_in)
		fig.subplots_adjust(
			bottom=below_axes_in / fig_height_in,
			top=1.0 - TOP_MARGIN_IN / fig_height_in
		)
		legend_title_text = sim_legend_title_text if plotted_sim_curves > 0 else meas_legend_title_text
		ax.legend(
			loc='upper center',
			bbox_to_anchor=(0.5, -0.16),
			ncol=legend_cols,
			title=legend_title_text,
			frameon=True,
			fontsize=8
		)

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
	time_end=PLOT_TMAX_MIN,
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
	time_end=(PLOT_TMAX_MIN * 60) if PLOT_TMAX_MIN is not None else None,
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
	time_end=(PLOT_TMAX_MIN * 60) if PLOT_TMAX_MIN is not None else None,
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
