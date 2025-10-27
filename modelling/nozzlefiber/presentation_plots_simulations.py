#!/usr/bin/env python3
"""Darcy flow comparison plot from MD simulation data."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pickle
from pathlib import Path

# Setup and data loading
script_dir = Path(__file__).parent
pickle_file = script_dir / "md_simulation_data.pkl"
plots_dir = script_dir / "plots"
plots_dir.mkdir(exist_ok=True)

# Load data
with open(pickle_file, 'rb') as f:
    data = pickle.load(f)

# Plot configuration
plt.rcParams.update({'figure.figsize': (16, 8), 'font.size': 14, 'savefig.dpi': 600})

# Create comparison plot
fig, axes = plt.subplots(1, 2, figsize=(16, 8))
core_colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
cores = ['Core_A', 'Core_B', 'Core_C', 'Core_D']
core_labels = ['A', 'B', 'C', 'D']

# Plot both conditions
for ax, md_name, title in [(axes[0], 'md8', '0.0 m/day'), (axes[1], 'md4', '57.6 m/day')]:
    md_data = data[(data['MD'] == md_name) & (data['Time_min'] <= 55)]
    
    for core, color, label in zip(cores, core_colors, core_labels):
        ax.plot(md_data['Time_min'], md_data[core], color=color, linewidth=1.2, 
               alpha=0.8, label=label)
    
    ax.set_title(title, fontweight='bold')
    ax.set_xlabel('Time (minutes)')
    ax.set_ylabel('Temperature (°C)')
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 55)
    ax.legend(loc='upper right', title='Core', frameon=True)

# Consistent y-axis
all_temps = []
for md_name in ['md8', 'md4']:
    md_data = data[(data['MD'] == md_name) & (data['Time_min'] <= 55)]
    for core in cores:
        all_temps.extend(md_data[core].values)

temp_min, temp_max = min(all_temps) - 1, max(all_temps) + 1
axes[0].set_ylim(temp_min, temp_max)
axes[1].set_ylim(temp_min, temp_max)

plt.suptitle('Temperature Evolution Comparison', fontweight='bold')
plt.tight_layout()
plt.savefig(plots_dir / "Darcy_flow_comparison.png", bbox_inches='tight')
plt.close()

print("✓ Darcy flow comparison plot generated successfully!")
print(f"  Saved: {plots_dir}/Darcy_flow_comparison.png")