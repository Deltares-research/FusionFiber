#!/usr/bin/env python3
'''
Create comparison plots for groundwater-flow simulation runs.

Workflow and outcomes:
1. Load processed simulation data from gw_simulation_data.pkl.
2. Select which gw runs to include.
3. Generate three figures from the same data:
	- Time in minutes (linear x-axis)
	- Time in seconds (linear x-axis)
	- Time in seconds (logarithmic x-axis)
4. Save all figures to the local plots folder.

Each curve is labeled by a configurable data column and colored by evenly
spaced samples from a configurable colormap (default: viridis).
'''

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pickle
import math
import numpy as np
import difflib
from pathlib import Path

# Setup and data loading
script_dir = Path(__file__).parent
pickle_file = script_dir / "gw_simulation_data.pkl"
plots_dir = script_dir / "plots"
plots_dir.mkdir(exist_ok=True)

# Load data
with open(pickle_file, 'rb') as f:
	data = pickle.load(f)

# Selection settings
#GW_IDS = ['gw301', 'gw302', 'gw303', 'gw304', 'gw305']
GW_IDS = [f"gw{i:02d}" for i in range(401, 421)]

# Plot settings
LINE_WIDTH = 1.5  # line thickness for plotted curves
cmap = 'viridis'  # matplotlib colormap name for curve colors
legend_label = 'darcy_flux'  # column in data used for curve labels	
legend_title = 'Darcy Flow (m/d)'  # title for the legend
legend_unit = 'm/d'  # unit appended to numeric labels in legend

#outfile_basename = 'Darcy_flow_core_average'
outfile_basename = 'Darcy_flow_core_average_gw401-420'

required_columns = {'gw', 'Time_min', 'bulk_conductivity'}
missing_columns = required_columns - set(data.columns)
if missing_columns:
	raise ValueError(f"Missing required columns in pickle data: {sorted(missing_columns)}")

all_gw = sorted(data['gw'].dropna().astype(str).unique())
selected_gw = [gw for gw in GW_IDS if gw in all_gw]
missing_gw = [gw for gw in GW_IDS if gw not in all_gw]

if missing_gw:
	print(f"Warning: {len(missing_gw)} requested GW IDs not found in data: {', '.join(missing_gw)}")
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

def create_plot(
	x_mode='minutes',
	log_x=False,
	file_name='Darcy_flow_core_average.png',
	time_start=None,
	time_end=None,
	label_column='darcy_flux',
	label_title='Darcy flux',
	label_unit='m/d',
	label_decimals=1,
	cmap_name='viridis',
	cmap_start=0.0,
	cmap_end=1.0
):
	'''
	Create and save one Core_average plot for the selected gw runs.

	Parameters
	----------
	x_mode : {'minutes', 'seconds'}
		Unit of the x-axis. This also defines the expected units for
		time_start and time_end.
	log_x : bool
		If True, apply logarithmic scaling to the x-axis only.
	file_name : str
		Output filename (saved in the plots directory).
	time_start : float | None
		Optional lower x-limit in the same unit as x_mode.
	time_end : float | None
		Optional upper x-limit in the same unit as x_mode.
	label_column : str
		Column in data used to create curve labels.
	label_title : str
		Legend title text.
	label_unit : str
		Optional unit appended to numeric labels.
	label_decimals : int
		Number of decimals for numeric labels.
	cmap_name : str
		Matplotlib colormap name used to color curves.
	cmap_start : float
		Start position in the colormap interval [0, 1].
	cmap_end : float
		End position in the colormap interval [0, 1].

	Returns
	-------
	pathlib.Path
		Path of the saved figure.
	'''
	if x_mode not in {'minutes', 'seconds'}:
		raise ValueError("x_mode must be 'minutes' or 'seconds'")
	if cmap_start < 0 or cmap_end > 1 or cmap_start > cmap_end:
		raise ValueError("cmap_start/cmap_end must satisfy 0 <= cmap_start <= cmap_end <= 1")
	if label_column not in data.columns:
		available_cols = ', '.join(sorted(data.columns))
		raise ValueError(
			f"label_column '{label_column}' not found in data columns. "
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
		gw_mask = data['gw'] == gw_name
		if filter_time_start is not None:
			gw_mask &= data['Time_min'] >= filter_time_start
		if filter_time_end is not None:
			gw_mask &= data['Time_min'] <= filter_time_end
		gw_data = data[gw_mask]
		if gw_data.empty:
			continue
		plot_data.append((gw_name, gw_data))

	if not plot_data:
		raise ValueError('No data available for the selected gw IDs and time range.')

	cmap = plt.get_cmap(cmap_name)
	if len(plot_data) == 1:
		color_values = np.array([(cmap_start + cmap_end) / 2])
	else:
		color_values = np.linspace(cmap_start, cmap_end, len(plot_data))

	fig, ax = plt.subplots()
	plotted_curves = 0
	skipped_missing_label = []
	for (gw_name, gw_data), color_value in zip(plot_data, color_values):
		label_value = gw_data[label_column].iloc[0]
		if (not isinstance(label_value, (str, bytes)) and np.isnan(label_value)) or (
			isinstance(label_value, str) and not label_value.strip()
		):
			skipped_missing_label.append(gw_name)
			continue
		label = format_legend_label(label_value, unit=label_unit, decimals=label_decimals)
		line_color = cmap(color_value)

		if x_mode == 'seconds':
			x_values = gw_data['Time_min'] * 60.0
		else:
			x_values = gw_data['Time_min']

		if log_x:
			positive_mask = x_values > 0
			x_values = x_values[positive_mask]
			y_values = gw_data.loc[positive_mask, 'Core_average']
			if x_values.empty:
				continue
			ax.semilogx(x_values, y_values, alpha=0.9, label=label, color=line_color)
			plotted_curves += 1
		else:
			ax.plot(x_values, gw_data['Core_average'], alpha=0.9, label=label, color=line_color)
			plotted_curves += 1

	if plotted_curves == 0:
		raise ValueError(
			f"No curves left to plot. All selected GW runs are missing '{label_column}' values "
			"(often caused by commenting out rows in batch_variables_gwflow.txt)."
		)

	ax.set_title('Temperature Evolution (Core_average)', fontweight='bold')
	ax.set_ylabel('Temperature (°C)')
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

	legend_entries = plotted_curves
	legend_cols = min(10, max(5, math.ceil(legend_entries / 6)))
	legend_rows = math.ceil(legend_entries / legend_cols)
	fig.subplots_adjust(bottom=min(0.5, 0.12 + 0.05 * legend_rows))
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
	return output_path


saved_minutes = create_plot(
	x_mode='minutes',
	log_x=False,
	time_start=0,
	time_end=55,
	cmap_name=cmap,
	label_column=legend_label,
	label_title=legend_title,
	label_unit=legend_unit,
	file_name=f'{outfile_basename}.png'
)

saved_seconds = create_plot(
	x_mode='seconds',
	log_x=False,
	time_start=0,
	time_end=55 * 60,
	cmap_name=cmap,
	label_column=legend_label,
	label_title=legend_title,
	label_unit=legend_unit,
	file_name=f'{outfile_basename}_seconds.png'
)

saved_seconds_logx = create_plot(
	x_mode='seconds',
	log_x=True,
	time_start=60,
	time_end=55 * 60,
	cmap_name=cmap,
	label_column=legend_label,
	label_title=legend_title,
	label_unit=legend_unit,
	file_name=f'{outfile_basename}_seconds_logx.png'
)

print("✓ Darcy flow Core_average plots generated successfully!")
print(f"  Saved: {saved_minutes}")
print(f"  Saved: {saved_seconds}")
print(f"  Saved: {saved_seconds_logx}")
