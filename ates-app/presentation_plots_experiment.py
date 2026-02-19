#!/usr/bin/env python3
"""Custom experimental plots for fiber optic temperature analysis."""

import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ahdts import find_nearest
import pickle
import gzip
import gc

# Core locations [start, end, reverse_order]
locations = {
    'a': [32.75, 34.12, True], 'b': [58.45, 59.82, False],
    'c': [118.25, 119.64, True], 'd': [143.95, 145.26, False]
}

# Load data
data_dir = Path(__file__).parent
pickle_file = data_dir / "all_experiment_data.pickle"

try:
    with gzip.open(pickle_file, 'rb') as f:
        all_data = pickle.load(f)
except:
    with open(pickle_file, 'rb') as f:
        all_data = pickle.load(f)

print(f"Loaded {len(all_data)} experiments")

# Setup plotting and core indices
plt.rcParams.update({'figure.figsize': (16, 8), 'font.size': 14, 'savefig.dpi': 600})

sample_df = list(all_data.values())[0]['df']
core_indices = {}
for core, (start, end, reverse) in locations.items():
    indices = list(range(find_nearest(sample_df.columns, start), find_nearest(sample_df.columns, end) + 1))
    if reverse:
        indices.reverse()
    core_indices[core] = indices

depth_spacing = abs(locations['a'][1] - locations['a'][0]) / (max(len(indices) for indices in core_indices.values()) - 1)
depths = [i * depth_spacing for i in range(max(len(indices) for indices in core_indices.values()))]

(data_dir / "custom").mkdir(exist_ok=True)

def save_plot(filename):
    plt.tight_layout()
    plt.savefig(data_dir / "custom" / filename, dpi=600, bbox_inches='tight', facecolor='white')
    plt.close()
    gc.collect()
    print(f"  Saved: {filename}")

def get_data(exp_data, core, depth_idx):
    col_idx = core_indices[core][depth_idx]
    temp = exp_data['df'].iloc[:, col_idx]
    time = (temp.index - temp.index[0]).total_seconds() / 60
    return time, temp

def setup_axis(ax, title, ylim):
    ax.set_title(title)
    ax.set_xlabel('Time (minutes)')
    ax.set_ylabel('Temperature (°C)')
    ax.set_ylim(ylim)
    ax.grid(True, alpha=0.5)

def add_legend(ax_or_fig, title, is_fig=False):
    loc = 'center left'
    bbox = (1.02, 0.5) if not is_fig else (0.99, 0.5)
    target = ax_or_fig if not is_fig else ax_or_fig
    if is_fig:
        handles, labels = ax_or_fig.axes[0].get_legend_handles_labels()
        target.legend(handles, labels, loc=loc, bbox_to_anchor=bbox, title=title, ncol=1, frameon=True)
    else:
        target.legend(loc=loc, bbox_to_anchor=bbox, title=title, ncol=1, frameon=True)

# Plot 1: Core B Darcy Flow Comparison at 0.5m
print("Creating Core B Darcy flow comparison...")
fig, ax = plt.subplots(figsize=(16, 8))
fig.suptitle('Effect of different flow velocities on temperature evolution (fixed 0.5m depth)', fontweight='bold')

depth_idx = find_nearest(depths, 0.5)
experiments_170v = [(name, data['darcy_flux']) for name, data in all_data.items() if name != 'MD9']
experiments_170v.sort(key=lambda x: x[1])
flux_colors = plt.cm.plasma(np.linspace(0, 1, len(experiments_170v)))

for idx, (exp_name, darcy_flow) in enumerate(experiments_170v):
    time, temp = get_data(all_data[exp_name], 'b', depth_idx)
    ax.plot(time, temp, color=flux_colors[idx], alpha=0.8, linewidth=1.2,
            label=f'{darcy_flow} m/day')

setup_axis(ax, '', (22, 42))
ax.grid(True, alpha=0.8)
add_legend(ax, 'Darcy Flow')
save_plot("Core_B_darcy_flows_05m_depth.png")

# Plot 2: Core B All Depths - 57.6 m/day
print("Creating Core B all depths plot...")
fig, ax = plt.subplots(figsize=(16, 8))
fig.suptitle('Effect of depth along the filter on temperature evolution (fixed 57 m/day Darcy flow)', fontweight='bold')

md4_data = all_data['MD4']
valid_depth_indices = [i for i in range(len(core_indices['b'])) if depths[i] <= 1.00]
depth_colors = plt.cm.viridis(np.linspace(0, 1, len(valid_depth_indices)))

for color_idx, depth_idx in enumerate(valid_depth_indices):
    time, temp = get_data(md4_data, 'b', depth_idx)
    ax.plot(time, temp, color=depth_colors[color_idx], alpha=0.8, linewidth=1.2,
           label=f'{depths[depth_idx]:.2f}m')

setup_axis(ax, '', (20, 47))
add_legend(ax, 'Depth')
save_plot("Core_B_all_depths_576_viridis.png")

# Plot 3: All Cores at 0.5m Depth - 57.6 m/day
print("Creating all cores comparison...")
fig, ax = plt.subplots(figsize=(16, 8))
fig.suptitle('All Cores at 0.5m Depth - 57.6 m/day Darcy Flux', fontweight='bold')

md4_data = all_data['MD4']
depth_idx = find_nearest(depths, 0.5)
core_colors = plt.cm.Accent(np.linspace(0, 1, 4))
cores = ['a', 'b', 'c', 'd']
core_names = ['A', 'B', 'C', 'D']

for core_idx, (core, core_name) in enumerate(zip(cores, core_names)):
    if depth_idx < len(core_indices[core]):
        time, temp = get_data(md4_data, core, depth_idx)
        ax.plot(time, temp, color=core_colors[core_idx], alpha=0.8, 
               linewidth=1.2, label=core_name)

setup_axis(ax, '', (22, 38))
add_legend(ax, 'Core')
save_plot("All_cores_05m_depth_576_flux.png")

# Plot 4: Effect of Increasing Heating at the Flow Velocity (MD4 vs MD9)
print("Creating voltage comparison plot...")
fig, axes = plt.subplots(1, 2, figsize=(16, 8))
fig.suptitle('Effect of Increasing Heating at the Flow Velocity', fontweight='bold')

md4_data = all_data['MD4']
md9_data = all_data['MD9']
valid_depth_indices = [i for i in range(len(core_indices['b'])) if depths[i] <= 1.00]
depth_colors = plt.cm.viridis(np.linspace(0, 1, len(valid_depth_indices)))

# Plot both voltage conditions
for ax, data, title in [(axes[0], md4_data, '170V (57.6 m/day)'), 
                        (axes[1], md9_data, '230V (55.2 m/day)')]:
    for color_idx, depth_idx in enumerate(valid_depth_indices):
        time, temp = get_data(data, 'b', depth_idx)
        ax.plot(time, temp, color=depth_colors[color_idx], alpha=0.8, linewidth=1.2,
               label=f'{depths[depth_idx]:.2f}m' if ax == axes[0] else '')
    setup_axis(ax, title, (20, 70))

add_legend(fig, 'Depth', is_fig=True)

save_plot("Core_B_voltage_comparison_170V_vs_230V.png")


# Plot: Core B at 0.5m depth, 0.0 m/day, log x-axis starting at 100 min
print("Creating Core B 0.0 m/day log-x plot...")
fig, ax = plt.subplots(figsize=(16, 8))
fig.suptitle('Core B at 0.5m Depth - 0.0 m/day Darcy Flux (Log Time)', fontweight='bold')

# Find MD8 experiment (0.0 m/day)
md8_data = all_data.get('MD8')
depth_idx = find_nearest(depths, 0.5)
if md8_data and depth_idx < len(core_indices['b']):
    time, temp = get_data(md8_data, 'b', depth_idx)
    mask = time >= 5.5
    ax.plot(time[mask], temp[mask], color='#1f77b4', alpha=0.8, linewidth=1.5, label='0.0 m/day')
    ax.set_xscale('log')
    ax.set_xlim(5, time.max())
    ax.set_xticks([10, 15, 20, 25, 30])  # 100, 1000, 10000 seconds in minutes
    ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    setup_axis(ax, '', (22, 42))
    add_legend(ax, 'Darcy Flow')

    # Fit a straight line in log-space so it appears straight on log-x plot
    fit_mask = (time >= 10) & (time <= 30)
    fit_time = time[fit_mask]
    fit_temp = temp[fit_mask]
    if len(fit_time) > 1:
        # Interpolate temperature at exactly 10 and 30 minutes
        T1 = np.interp(10, fit_time, fit_temp)
        T2 = np.interp(30, fit_time, fit_temp)
        delta_T = T2 - T1
        delta_t = 20.0
        # Fit in log-space for the line
        log_time = np.log10(fit_time)
        coeffs = np.polyfit(log_time, fit_temp, 1)
        fit_temp_line = np.polyval(coeffs, log_time)
        ax.plot(fit_time, fit_temp_line, color='red', linestyle='--', linewidth=2, label='Log-space fit')
    ax.text(0.05, 0.95, f'ΔT={delta_T:.2f}°C\nt1=10 min\nt2=30 min', transform=ax.transAxes,
        fontsize=14, color='red', verticalalignment='top', bbox=dict(facecolor='white', alpha=0.7, edgecolor='red'))

    save_plot("Core_B_0md_05m_depth_logx.png")
else:
    print("MD8 data or depth index not found, plot not created.")

print("All plots generated successfully!")
print("="*60)