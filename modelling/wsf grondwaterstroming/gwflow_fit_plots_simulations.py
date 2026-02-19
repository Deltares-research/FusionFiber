#!/usr/bin/env python3
"""
Create log-x (seconds) Core_average plots with linear fit(s) over a user-defined
interval [t1, t2] in seconds.

This script intentionally focuses on one figure type only:
- x-axis in seconds (log scale)
- y-axis Core_average temperature
- dotted fitted line over [t1, t2]
- textbox with t1 and t2
- legend entries include per-curve ΔT = T_fit(t2) - T_fit(t1)
"""

import math
import pickle
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


# -------------------------- User settings --------------------------
GW_IDS = ['gw100', 'gw101', 'gw102', 'gw103', 'gw104', 'gw105', 'gw106', 'gw107']
LINE_WIDTH = 1.5
CMAP_NAME = 'plasma'
OUTFILE_BASENAME = 'Power_no_flow'
FIT_LINE_WIDTH = 2.8
FIT_MARKER_SIZE = 90

# Legend label source
LEGEND_LABEL_COLUMN = 'voltage'   # e.g. darcy_flux, runtime, temperature, voltage, amperage
LEGEND_LABEL_TITLE = 'Voltage (V)'
LEGEND_LABEL_UNIT = 'V'
LEGEND_LABEL_DECIMALS = 1

# Fit interval in seconds (user input)
FIT_T1_SEC = 600
FIT_T2_SEC = 1700

# Overall plot range in seconds (user input)
PLOT_TIME_START_SEC = 3
PLOT_TIME_END_SEC = 5000
# ------------------------------------------------------------------


def format_legend_label(value, unit='', decimals=1):
	if isinstance(value, (int, float, np.integer, np.floating)) and not np.isnan(value):
		formatted = f"{float(value):.{decimals}f}"
		return f"{formatted} {unit}".strip() if unit else formatted
	return str(value)


def fit_logx_line(x_seconds, y_values, t1, t2):
	"""
	Fit y = a*log10(x) + b over [t1, t2], then return fitted line and ΔT.
	ΔT is computed from fitted values only: y_fit(t2) - y_fit(t1).
	"""
	fit_mask = (x_seconds >= t1) & (x_seconds <= t2) & np.isfinite(y_values)
	x_fit = x_seconds[fit_mask]
	y_fit = y_values[fit_mask]

	if len(x_fit) < 2:
		raise ValueError('Need at least 2 points in [t1, t2] to fit a line.')

	coeff_a, coeff_b = np.polyfit(np.log10(x_fit), y_fit, 1)
	x_line = np.geomspace(t1, t2, 200)
	y_line = coeff_a * np.log10(x_line) + coeff_b
	y_t1 = coeff_a * np.log10(t1) + coeff_b
	y_t2 = coeff_a * np.log10(t2) + coeff_b
	delta_t = y_t2 - y_t1
	return x_line, y_line, delta_t, y_t1, y_t2


def main():
	script_dir = Path(__file__).parent
	pickle_file = script_dir / 'gw_simulation_data.pkl'
	plots_dir = script_dir / 'plots'
	plots_dir.mkdir(exist_ok=True)

	if FIT_T1_SEC <= 0 or FIT_T2_SEC <= 0:
		raise ValueError('FIT_T1_SEC and FIT_T2_SEC must be > 0 for a logarithmic x-axis.')
	if FIT_T2_SEC <= FIT_T1_SEC:
		raise ValueError('FIT_T2_SEC must be greater than FIT_T1_SEC.')
	if PLOT_TIME_START_SEC <= 0 or PLOT_TIME_END_SEC <= 0:
		raise ValueError('PLOT_TIME_START_SEC and PLOT_TIME_END_SEC must be > 0 for a logarithmic x-axis.')
	if PLOT_TIME_END_SEC <= PLOT_TIME_START_SEC:
		raise ValueError('PLOT_TIME_END_SEC must be greater than PLOT_TIME_START_SEC.')

	with open(pickle_file, 'rb') as f:
		data = pickle.load(f)

	required_columns = {'gw', 'Time_min', 'Core_average', LEGEND_LABEL_COLUMN}
	missing_columns = required_columns - set(data.columns)
	if missing_columns:
		raise ValueError(f"Missing required columns in pickle data: {sorted(missing_columns)}")

	all_gw = sorted(data['gw'].dropna().astype(str).unique())
	selected_gw = [gw for gw in GW_IDS if gw in all_gw]
	if not selected_gw:
		raise ValueError('No selected GW IDs found in data.')

	plt.rcParams.update({
		'figure.figsize': (12, 7),
		'font.size': 12,
		'savefig.dpi': 600,
		'lines.linewidth': LINE_WIDTH,
	})

	cmap = plt.get_cmap(CMAP_NAME)
	color_values = np.linspace(0, 1, len(selected_gw)) if len(selected_gw) > 1 else np.array([0.5])

	fig, ax = plt.subplots()
	has_fits = False

	for gw_name, color_value in zip(selected_gw, color_values):
		gw_data = data[data['gw'] == gw_name]
		if gw_data.empty:
			continue

		x_seconds = (gw_data['Time_min'].to_numpy(dtype=float)) * 60.0
		y_values = gw_data['Core_average'].to_numpy(dtype=float)
		plot_mask = (x_seconds >= PLOT_TIME_START_SEC) & (x_seconds <= PLOT_TIME_END_SEC)
		x_seconds = x_seconds[plot_mask]
		y_values = y_values[plot_mask]
		if x_seconds.size == 0:
			continue

		label_value = gw_data[LEGEND_LABEL_COLUMN].iloc[0]
		base_label = format_legend_label(label_value, unit=LEGEND_LABEL_UNIT, decimals=LEGEND_LABEL_DECIMALS)
		line_color = cmap(color_value)

		x_line, y_line, delta_t, y_t1, y_t2 = fit_logx_line(x_seconds, y_values, FIT_T1_SEC, FIT_T2_SEC)
		curve_label = f"{base_label} (ΔT={delta_t:.2f} °C)"
		ax.semilogx(x_seconds, y_values, alpha=0.8, label=curve_label, color=line_color, zorder=2)
		ax.semilogx(
			x_line,
			y_line,
			linestyle='--',
			linewidth=FIT_LINE_WIDTH,
			color=line_color,
			alpha=1.0,
			zorder=4,
		)
		ax.scatter(
			[FIT_T1_SEC, FIT_T2_SEC],
			[y_t1, y_t2],
			s=FIT_MARKER_SIZE,
			facecolor=line_color,
			edgecolor='black',
			linewidth=0.8,
			zorder=5,
		)
		has_fits = True

	if not has_fits:
		raise ValueError('No curves had enough points in [FIT_T1_SEC, FIT_T2_SEC] to fit.')

	ax.set_title('Temperature Evolution (Core_average) - Log Time with Fit', fontweight='bold')
	ax.set_xlabel('Time (seconds, log scale)')
	ax.set_ylabel('Temperature (°C)')
	ax.grid(True, alpha=0.3)
	ax.set_xlim(left=PLOT_TIME_START_SEC, right=PLOT_TIME_END_SEC)

	legend_entries = len(selected_gw)
	legend_cols = min(8, max(2, math.ceil(legend_entries / 6)))
	legend_rows = math.ceil(legend_entries / legend_cols)
	fig.subplots_adjust(bottom=min(0.4, 0.12 + 0.05 * legend_rows))
	ax.legend(
		loc='upper center',
		bbox_to_anchor=(0.5, -0.14),
		ncol=legend_cols,
		title=LEGEND_LABEL_TITLE,
		frameon=True,
		fontsize=8,
	)

	# Show only fit interval in textbox
	textbox_text = (
		f"t1 = {FIT_T1_SEC:.0f} seconds\n"
		f"t2 = {FIT_T2_SEC:.0f} seconds"
	)
	ax.text(
		0.02,
		0.98,
		textbox_text,
		transform=ax.transAxes,
		ha='left',
		va='top',
		bbox={'boxstyle': 'round', 'facecolor': 'white', 'alpha': 0.9, 'edgecolor': 'gray'},
	)

	plt.tight_layout()
	output_path = plots_dir / f'{OUTFILE_BASENAME}_fit_seconds_logx.png'
	plt.savefig(output_path, bbox_inches='tight')
	plt.close(fig)

	print('✓ Log-x fit plot generated successfully!')
	print(f'  Saved: {output_path}')
	print(f'  Fit interval: t1={FIT_T1_SEC:.0f}s, t2={FIT_T2_SEC:.0f}s')
	print('  ΔT values in legend are from fitted lines, not raw data points.')


if __name__ == '__main__':
	main()
