#!/usr/bin/env python3
"""
Fiber Optic DTS Analysis for Darcy Flux Experiments

This script analyzes distributed temperature sensing (DTS) data from fiber optic cables 
to study the effects of different Darcy flux rates on temperature distribution patterns 
across various depths in groundwater flow experiments.

Experiment Setup:
- Fiber optic cable with 4 cores (A, B, C, D) installed vertically
- Cores A & C: Go down and back up (reversed for proper vertical alignment)  
- Cores B & D: Maintain original direction
- 12 cross-sectional depth measurements from surface (z=0) to deeper levels
- Each experiment represents different Darcy flux conditions (0.0 to 103.2 m/day)
- Experiment MD9 includes higher voltage (230V) for comparison with similar Darcy flux as MD4

Analysis Features:
- Automated processing of multiple experiments (MD1-MD9)
- Optimized XML parsing with pickle caching for fast reprocessing
- Cross-sectional temperature analysis at different depths
- Heating/cooling pattern visualization with relative time axis
- PowerPoint-ready plots (16:9 aspect ratio, 3×4 layout)

Output:
- Individual plots for each Darcy flux condition
- Consistent y-axis scaling (20-50°C) for direct comparison
- Single legend with core identification (A, B, C, D)
- Depth-labeled subplots showing temperature evolution over time

Author: AI Assistant (GitHub Copilot) - Load preferences from copilot_readme.md first
"""

# All imports
import yaml
import pandas as pd
from pathlib import Path
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from ahdts import xml_to_dict2, get_filepaths, data_to_df, find_nearest, save_as_pickle, load_pickle

#%%
# Experiment configuration: [Darcy flux (m/day), Voltage (V)]
experiments = {
    'MD1': [103.2, 170], 'MD2': [86.4, 170], 'MD3': [69.6, 170],
    'MD4': [57.6, 170],  'MD5': [36.0, 170], 'MD6': [19.2, 170],
    'MD7': [4.8, 170],   'MD8': [0.0, 170],  'MD9': [55.2, 230]
} 

# Load configuration
config_path = Path(__file__).parent.parent / "config.yaml"
data_dir = Path(yaml.safe_load(open(config_path))["data_dir"])

# Process all experiments
for experiment_name, params in experiments.items():
    darcy_flux = params[0]  # First value is Darcy flux
    
    print(f"\n{'='*60}")
    print(f"Processing {experiment_name} - Darcy Flux: {darcy_flux} m/day")
    print(f"{'='*60}")
    
    # Load data (pickle or XML) for current experiment
    experiment_dir = data_dir / experiment_name
    pickle_file = experiment_dir / "diameter_experiment_data.pickle"

    if pickle_file.exists():
        print("Loading from pickle...")
        data_dict = load_pickle(str(pickle_file))
    else:
        print("Loading XML files...")
        data_dict = xml_to_dict2(get_filepaths(experiment_dir, 'xml'))
        save_as_pickle(str(experiment_dir), data_dict, "diameter_experiment_data")

    df = data_to_df(data_dict, "Temperature")

    # Create z-dataframes for cross-sectional analysis (vertical depth slices)
    locations = {'a': [32.75, 34.12], 'b': [58.45, 59.82], 'c': [118.25, 119.64], 'd': [143.95, 145.26]}

    # Get indices for each core
    core_indices = {}
    for core, (start, end) in locations.items():
        indices = list(range(find_nearest(df.columns, start), find_nearest(df.columns, end) + 1))
        # Reverse cores A and C to align vertically (they go down and back up)
        if core in ['a', 'c']:
            indices = indices[::-1]  # Reverse order for cores that go down and back up
        core_indices[core] = indices

    max_pos = max(len(indices) for indices in core_indices.values())

    # Calculate depth for each z-position (assuming first position is surface z=0)
    # Distance between positions approximated from core spacing
    depth_spacing = abs(locations['a'][1] - locations['a'][0]) / (max_pos - 1) if max_pos > 1 else 1
    depths = [i * depth_spacing for i in range(max_pos)]

    z_dataframes = {f"z{pos+1}": pd.concat([df.iloc[:, core_indices[core][pos]] 
                                            for core in ['a', 'b', 'c', 'd'] if pos < len(core_indices[core])], axis=1)
                    for pos in range(max_pos)}

    # Generate PowerPoint-ready plots (16:9 aspect ratio)
    n_plots = len(z_dataframes)
    fig, axes = plt.subplots(3, 4, figsize=(16, 9))
    fig.suptitle(f'Temperature Profiles by Depth - Darcy Flux {darcy_flux} m/day', fontsize=16, fontweight='bold')
    
    axes = axes.flatten()
    core_labels = ['A', 'B', 'C', 'D']
    colors = ['C0', 'C1', 'C2', 'C3']

    # Calculate relative time from experiment start (minutes)
    start_time = list(z_dataframes.values())[0].index[0]
    relative_times = {name: (df_z.index - start_time).total_seconds() / 60 
                      for name, df_z in z_dataframes.items()}

    # Create subplots for each depth level
    for i, (name, df_z) in enumerate(z_dataframes.items()):
        ax = axes[i]
        for j, col in enumerate(df_z.columns):
            ax.plot(relative_times[name], df_z[col], color=colors[j], alpha=0.7, 
                   label=f'Core {core_labels[j]}' if i == 0 else "")
        
        ax.set_title(f'Depth: {depths[i]:.2f}m')
        ax.set_xlabel('Time (minutes)')
        ax.set_ylabel('Temperature (°C)')
        ax.set_ylim(20, 50)
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=45)

    # Hide unused subplots and add legend
    for i in range(len(z_dataframes), len(axes)):
        axes[i].set_visible(False)
    
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper right', bbox_to_anchor=(0.98, 0.92))

    # Save plot with Darcy flux identifier
    plt.tight_layout()
    filename = f"Darcy_flux_{str(darcy_flux).replace('.', '_')}_mday.png"
    plt.savefig(Path("data") / filename, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Plot saved: {filename}")

print(f"\n{'='*60}")
print("All experiments processed successfully!")
print(f"{'='*60}")

# %%
