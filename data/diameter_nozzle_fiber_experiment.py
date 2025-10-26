#!/usr/bin/env python3
"""
Complete Fiber Optic DTS Analysis for Darcy Flux Experiments

Analyzes distributed temperature sensing (DTS) data from fiber optic cables to study
the effects of different Darcy flux rates on temperature distribution patterns across
various depths in groundwater flow experiments.

Features:
- 9 experiments (MD1-MD9) with Darcy flux rates from 0.0 to 103.2 m/day
- 4 fiber cores (A,B,C,D) with 12 depth measurements each
- 6 plot sets organized by analysis type (50 total plots)
- PowerPoint-ready format (16:9, 300 DPI)
- Self-healing data loading with pickle caching

Output Structure:
- fluxes/  (18 plots): Sets 1&2 - flux-based analyses
- depths/  (24 plots): Sets 3&4 - depth-based comparisons  
- cores/   (8 plots):  Sets 5&6 - core-based analyses

CRITICAL NOTE FOR AI ASSISTANT: Load preferences from _AI_CONTEXT.md before any operations
"""

# Imports and setup
import pandas as pd
import numpy as np
import yaml
from pathlib import Path
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for headless plotting
import matplotlib.pyplot as plt
from ahdts import xml_to_dict2, get_filepaths, data_to_df, find_nearest, save_as_pickle, load_pickle
import gc

# Configuration
experiments = {
    'MD1': [103.2, 170], 'MD2': [86.4, 170], 'MD3': [69.6, 170],
    'MD4': [57.6, 170],  'MD5': [36.0, 170], 'MD6': [19.2, 170],
    'MD7': [4.8, 170],   'MD8': [0.0, 170],  'MD9': [55.2, 230]
}

# Core locations and reversal configuration
# Format: 'core_id': [start_position, end_position, reverse_direction]
locations = {
    'a': [32.75, 34.12, True],   # Core A: reverse for vertical alignment
    'b': [58.45, 59.82, False],  # Core B: no reverse
    'c': [118.25, 119.64, True], # Core C: reverse for vertical alignment
    'd': [143.95, 145.26, False] # Core D: no reverse
}

# Get directories
repo_dir = Path(__file__).parent.parent  # Repository root
data_dir = Path(__file__).parent  # Script location for output files


# Data loading with fallback strategy
print("Loading experiment data...")
combined_pickle_file = data_dir / "all_experiment_data.pickle"

if combined_pickle_file.exists():
    # Load compressed pickle file
    import pickle
    import gzip
    try:
        with gzip.open(str(combined_pickle_file), 'rb') as f:
            all_data = pickle.load(f)
        print(f"Loaded optimized combined data: {len(all_data)} experiments")
    except:
        # Fallback for uncompressed files
        all_data = load_pickle(str(combined_pickle_file))
        print(f"Loaded combined data: {len(all_data)} experiments")
    
    for md_id, exp_data in all_data.items():
        df = exp_data['df']
        print(f"  {md_id}: {exp_data['darcy_flux']} m/day, {exp_data['voltage']}V - {df.shape[0]}×{df.shape[1]}")
        
else:
    # Load config for local data directory
    config_file = repo_dir / "config.yaml"
    if not config_file.exists():
        print("ERROR: No combined data pickle found and no path to pointing to subfolders with raw xml data available!")
        print(f"Config file not found: {config_file}")
        print("If you have the raw xml data, add a config.yaml in the main repo directory that contains:")
        print('data_dir: "path\\to\\main_data_folder"')
        exit(1)

    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        local_data_dir = Path(config['data_dir'])
        print(f"Local data directory: {local_data_dir}")
    except KeyError:
        print("ERROR: Config file exists but 'data_dir' key not found!")
        print("Please add 'data_dir: \"path\\to\\main_data_folder\"' to config.yaml")
        exit(1)

    print("Combined pickle not found. Loading from local data directory...")
    all_data = {}
    for experiment_name, params in experiments.items():
        darcy_flux = params[0]
        voltage = params[1]
        
        print(f"Loading {experiment_name} (Darcy: {darcy_flux} m/day)...")
        
        # Load from local data directory (from config.yaml)
        experiment_path = local_data_dir / experiment_name
        if experiment_path.exists():
            # First check if there's already a pickle file in the experiment directory
            experiment_pickle = experiment_path / "diameter_experiment_data.pickle"
            if experiment_pickle.exists():
                print(f"  Loading existing pickle from experiment directory...")
                data_dict = load_pickle(str(experiment_pickle))
            else:
                # Load from XML files - use glob pattern as fallback for complex filenames
                xml_files_glob = list(experiment_path.glob("*.xml"))
                if xml_files_glob:
                    xml_files = [str(f) for f in xml_files_glob]
                    print(f"  Processing {len(xml_files)} XML files...")
                    data_dict = xml_to_dict2(xml_files)  # Process all XML files
                else:
                    print(f"  No XML files found in {experiment_path}")
                    continue
            
            # Convert to DataFrame and store with experiment info
            df = data_to_df(data_dict, "Temperature")
            all_data[experiment_name] = {
                'df': df,
                'darcy_flux': darcy_flux,
                'voltage': voltage,
                'md_id': experiment_name
            }
            
        else:
            print(f"  Experiment directory not found: {experiment_path}")
            continue

    print(f"Successfully loaded {len(all_data)} experiments")
    
    if len(all_data) == 0:
        print("ERROR: No experiment data could be loaded!")
        print("Please check that:")
        print(f"1. Local data directory exists: {local_data_dir}")
        print("2. Experiment folders (MD1-MD9) exist in the local data directory")
        print("3. XML files or pickle files are present in the experiment folders")
        exit(1)
    
    # Save optimized combined pickle file to repository for future use
    print(f"Optimizing and saving combined data to {combined_pickle_file.name}...")
    
    # Optimize data before saving
    optimized_data = {}
    for md_id, exp_data in all_data.items():
        df = exp_data['df']
        print(f"  Optimizing {md_id}: {df.shape[0]}×{df.shape[1]} -> ", end="")
        
        # Keep broader range to include all core locations (32-150m covers all cores)
        distance_cols = [col for col in df.columns if isinstance(col, (int, float)) and 30 <= col <= 150]
        
        # Create optimized dataframe (keep all timestamps)
        df_optimized = df[distance_cols].copy()
        
        # Convert to float32 to halve memory usage (sufficient precision for temperature data)
        df_optimized = df_optimized.astype('float32')
        
        optimized_data[md_id] = {
            'df': df_optimized,
            'darcy_flux': exp_data['darcy_flux'],
            'voltage': exp_data['voltage'],
            'md_id': exp_data['md_id']
        }
        print(f"{df_optimized.shape[0]}×{df_optimized.shape[1]}")
    
    # Save with compression
    import pickle
    import gzip
    with gzip.open(str(combined_pickle_file), 'wb') as f:
        pickle.dump(optimized_data, f, protocol=pickle.HIGHEST_PROTOCOL)
    
    file_size_mb = combined_pickle_file.stat().st_size / 1024 / 1024
    print(f"Optimized pickle file saved ({file_size_mb:.1f} MB)")

# Plotting configuration
plt.rcParams.update({
    'figure.figsize': (16, 9), 
    'figure.dpi': 300,
    'savefig.dpi': 600,  # Higher DPI for saved figures
    'lines.linewidth': 0.8,  # Thinner default line width
    'axes.linewidth': 0.5,   # Thinner axes
    'grid.linewidth': 0.3,   # Thinner grid lines
    'font.size': 8,          # Smaller font for better scaling
    'axes.labelsize': 9,     # Axis label size
    'axes.titlesize': 10,    # Title size
    'legend.fontsize': 8,    # Legend font size
    'xtick.labelsize': 7,    # X-tick label size
    'ytick.labelsize': 7     # Y-tick label size
})

# Get indices for each core (use first experiment as reference)
core_indices = {}
sample_df = list(all_data.values())[0]['df']
for core, (start, end, reverse) in locations.items():
    indices = list(range(find_nearest(sample_df.columns, start), find_nearest(sample_df.columns, end) + 1))
    if reverse:  # Use the reverse flag from the locations dictionary
        indices.reverse()
    core_indices[core] = indices

max_pos = max(len(indices) for indices in core_indices.values())
depth_spacing = abs(locations['a'][1] - locations['a'][0]) / (max_pos - 1) if max_pos > 1 else 1
depths = [i * depth_spacing for i in range(max_pos)]

core_labels = ['A', 'B', 'C', 'D']
colors = ['C0', 'C1', 'C2', 'C3']
depth_colors = plt.cm.viridis(np.linspace(0, 1, max_pos))

print(f"Setup complete: {max_pos} depths per core, {len(core_labels)} cores")

# Create output folders
for folder in ["fluxes", "depths", "cores"]:
    (data_dir / folder).mkdir(exist_ok=True)

# Plot generation - 6 sets, 50 plots total
print("\nGenerating plot sets...")

# Sets 1-2: Flux-based plots (fluxes/ folder)
print("Creating Sets 1-2: Flux analysis...")

for experiment_name, exp_data in all_data.items():
    df = exp_data['df']
    darcy_flux = exp_data['darcy_flux']
    
    # Create z-dataframes for cross-sectional analysis
    z_dataframes = {f"z{pos+1}": pd.concat([df.iloc[:, core_indices[core][pos]] 
                                            for core in ['a', 'b', 'c', 'd'] if pos < len(core_indices[core])], axis=1)
                    for pos in range(max_pos)}
    
    # SET 1: Depths (subplots) × Cores (curves) × Flux (separate plots)
    fig, axes = plt.subplots(3, 4, figsize=(16, 9))
    fig.suptitle(f'Temperature Profiles by Depth - Darcy Flux {darcy_flux} m/day', fontsize=16, fontweight='bold')
    
    axes = axes.flatten()
    start_time = list(z_dataframes.values())[0].index[0]
    relative_times = {name: (df_z.index - start_time).total_seconds() / 60 
                      for name, df_z in z_dataframes.items()}

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

    for i in range(len(z_dataframes), len(axes)):
        axes[i].set_visible(False)
    
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, -0.02), 
               ncol=len(labels), frameon=True, fancybox=True, shadow=True)

    plt.tight_layout()
    filename_depths = f"Darcy_flux_{str(darcy_flux).replace('.', '_')}_mday_depths.png"
    plt.savefig(data_dir / "fluxes" / filename_depths, dpi=600, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    plt.close()
    gc.collect()
    print(f"  Plot saved: fluxes/{filename_depths}")

    # SET 2: Cores (subplots) × Depths (curves) × Flux (separate plots)
    fig, axes = plt.subplots(2, 2, figsize=(16, 9))
    fig.suptitle(f'Temperature Profiles by Core - Darcy Flux {darcy_flux} m/day', fontsize=16, fontweight='bold')
    
    axes = axes.flatten()

    for core_idx, core in enumerate(['a', 'b', 'c', 'd']):
        ax = axes[core_idx]
        
        for pos in range(max_pos):
            if pos < len(core_indices[core]):
                col_idx = core_indices[core][pos]
                temp_data = df.iloc[:, col_idx]
                relative_time = (temp_data.index - start_time).total_seconds() / 60
                
                ax.plot(relative_time, temp_data, color=depth_colors[pos], alpha=0.7,
                       label=f'{depths[pos]:.2f}m' if core_idx == 0 else "")
        
        ax.set_title(f'Core {core_labels[core_idx]}')
        ax.set_xlabel('Time (minutes)')
        ax.set_ylabel('Temperature (°C)')
        ax.set_ylim(20, 50)
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=45)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, -0.02), 
               title='Depth', ncol=len(labels), frameon=True, fancybox=True, shadow=True)

    plt.tight_layout()
    filename_cores = f"Darcy_flux_{str(darcy_flux).replace('.', '_')}_mday_cores.png"
    plt.savefig(data_dir / "fluxes" / filename_cores, dpi=600, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    plt.close()
    gc.collect()
    print(f"  Plot saved: fluxes/{filename_cores}")

# =============================================================================
# SET 3 & 4: Fluxes × Cores × Depths - Save in depths/ folder
# =============================================================================
print("Creating Sets 3 & 4: Depth-based plots...")

# SET 3: Fluxes (subplots) × Cores (curves) × Depth (separate plots)
for depth_idx in range(max_pos):
    fig, axes = plt.subplots(3, 3, figsize=(16, 9))
    fig.suptitle(f'Temperature Comparison Across Fluxes - Depth: {depths[depth_idx]:.2f}m', 
                 fontsize=16, fontweight='bold')
    
    axes = axes.flatten()
    
    for flux_idx, (experiment_name, exp_data) in enumerate(all_data.items()):
        df = exp_data['df']
        darcy_flux = exp_data['darcy_flux']
        
        ax = axes[flux_idx]
        start_time = df.index[0]
        relative_time = (df.index - start_time).total_seconds() / 60
        
        for core_idx, core in enumerate(['a', 'b', 'c', 'd']):
            if depth_idx < len(core_indices[core]):
                col_idx = core_indices[core][depth_idx]
                temp_data = df.iloc[:, col_idx]
                ax.plot(relative_time, temp_data, color=colors[core_idx], alpha=0.7,
                       label=f'Core {core_labels[core_idx]}' if flux_idx == 0 else "")
        
        ax.set_title(f'{darcy_flux} m/day')
        ax.set_xlabel('Time (minutes)')
        ax.set_ylabel('Temperature (°C)')
        ax.set_ylim(20, 50)
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=45)
    
    # Add legend
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, -0.02), 
               ncol=len(labels), frameon=True, fancybox=True, shadow=True)
    
    plt.tight_layout()
    filename = f"Depth_{depths[depth_idx]:.2f}m_fluxes.png"
    plt.savefig(data_dir / "depths" / filename, dpi=600, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    plt.close()
    gc.collect()
    print(f"  Plot saved: depths/{filename}")

# SET 4: Cores (subplots) × Fluxes (curves) × Depth (separate plots)
for depth_idx in range(max_pos):
    fig, axes = plt.subplots(2, 2, figsize=(16, 9))
    fig.suptitle(f'Core Comparison Across Fluxes - Depth: {depths[depth_idx]:.2f}m', 
                 fontsize=16, fontweight='bold')
    
    axes = axes.flatten()
    flux_colors = plt.cm.plasma(np.linspace(0, 1, len(all_data)))
    
    for core_idx, core in enumerate(['a', 'b', 'c', 'd']):
        ax = axes[core_idx]
        
        if depth_idx < len(core_indices[core]):
            for flux_idx, (experiment_name, exp_data) in enumerate(all_data.items()):
                df = exp_data['df']
                darcy_flux = exp_data['darcy_flux']
                
                start_time = df.index[0]
                relative_time = (df.index - start_time).total_seconds() / 60
                
                col_idx = core_indices[core][depth_idx]
                temp_data = df.iloc[:, col_idx]
                ax.plot(relative_time, temp_data, color=flux_colors[flux_idx], alpha=0.7,
                       label=f'{darcy_flux} m/day' if core_idx == 0 else "")
        
        ax.set_title(f'Core {core_labels[core_idx]}')
        ax.set_xlabel('Time (minutes)')
        ax.set_ylabel('Temperature (°C)')
        ax.set_ylim(20, 50)
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=45)
    
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, -0.02), 
               title='Darcy Flux', ncol=len(labels), frameon=True, fancybox=True, shadow=True)
    
    plt.tight_layout()
    filename = f"Depth_{depths[depth_idx]:.2f}m_cores.png"
    plt.savefig(data_dir / "depths" / filename, dpi=600, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    plt.close()
    gc.collect()
    print(f"  Plot saved: depths/{filename}")

# =============================================================================
# SET 5 & 6: Core-based plots - Save in cores/ folder
# =============================================================================
print("Creating Sets 5 & 6: Core-based plots...")

# SET 5: Fluxes (subplots) × Depths (curves) × Core (separate plots)
for core_idx, core in enumerate(['a', 'b', 'c', 'd']):
    fig, axes = plt.subplots(3, 3, figsize=(16, 9))
    fig.suptitle(f'Core {core_labels[core_idx]} - Depth Comparison Across Fluxes', 
                 fontsize=16, fontweight='bold')
    
    axes = axes.flatten()
    
    for flux_idx, (experiment_name, exp_data) in enumerate(all_data.items()):
        df = exp_data['df']
        darcy_flux = exp_data['darcy_flux']
        
        ax = axes[flux_idx]
        start_time = df.index[0]
        relative_time = (df.index - start_time).total_seconds() / 60
        
        for depth_idx in range(min(max_pos, len(core_indices[core]))):
            col_idx = core_indices[core][depth_idx]
            temp_data = df.iloc[:, col_idx]
            ax.plot(relative_time, temp_data, color=depth_colors[depth_idx], alpha=0.7,
                   label=f'{depths[depth_idx]:.2f}m' if flux_idx == 0 else "")
        
        ax.set_title(f'{darcy_flux} m/day')
        ax.set_xlabel('Time (minutes)')
        ax.set_ylabel('Temperature (°C)')
        ax.set_ylim(20, 50)
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=45)
    
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, -0.02), 
               title='Depth', ncol=len(labels), frameon=True, fancybox=True, shadow=True)
    
    plt.tight_layout()
    filename = f"Core_{core_labels[core_idx]}_fluxes.png"
    plt.savefig(data_dir / "cores" / filename, dpi=600, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    plt.close()
    gc.collect()
    print(f"  Plot saved: cores/{filename}")

# SET 6: Depths (subplots) × Fluxes (curves) × Core (separate plots)
for core_idx, core in enumerate(['a', 'b', 'c', 'd']):
    fig, axes = plt.subplots(3, 4, figsize=(16, 9))
    fig.suptitle(f'Core {core_labels[core_idx]} - Flux Comparison Across Depths', 
                 fontsize=16, fontweight='bold')
    
    axes = axes.flatten()
    flux_colors = plt.cm.plasma(np.linspace(0, 1, len(all_data)))
    
    for depth_idx in range(min(max_pos, len(core_indices[core]))):
        ax = axes[depth_idx]
        
        for flux_idx, (experiment_name, exp_data) in enumerate(all_data.items()):
            df = exp_data['df']
            darcy_flux = exp_data['darcy_flux']
            
            start_time = df.index[0]
            relative_time = (df.index - start_time).total_seconds() / 60
            
            col_idx = core_indices[core][depth_idx]
            temp_data = df.iloc[:, col_idx]
            ax.plot(relative_time, temp_data, color=flux_colors[flux_idx], alpha=0.7,
                   label=f'{darcy_flux} m/day' if depth_idx == 0 else "")
        
        ax.set_title(f'Depth: {depths[depth_idx]:.2f}m')
        ax.set_xlabel('Time (minutes)')
        ax.set_ylabel('Temperature (°C)')
        ax.set_ylim(20, 50)
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=45)
    
    # Hide unused subplots
    for i in range(len(core_indices[core]), len(axes)):
        axes[i].set_visible(False)
    
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, -0.02), 
               title='Darcy Flux', ncol=len(labels), frameon=True, fancybox=True, shadow=True)
    
    plt.tight_layout()
    filename = f"Core_{core_labels[core_idx]}_depths.png"
    plt.savefig(data_dir / "cores" / filename, dpi=600, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    plt.close()
    gc.collect()
    print(f"  Plot saved: cores/{filename}")

# Final summary
print(f"\n{'='*60}")
print("COMPLETE plot generation finished successfully!")
print(f"{'='*60}")
print(f"Generated all 50 plots:")
print(f"- Set 1 (Depths by Flux): 9 plots in fluxes/")
print(f"- Set 2 (Cores by Flux): 9 plots in fluxes/")
print(f"- Set 3 (Fluxes by Depth): 12 plots in depths/")
print(f"- Set 4 (Cores by Depth): 12 plots in depths/")
print(f"- Set 5 (Fluxes by Core): 4 plots in cores/")
print(f"- Set 6 (Depths by Core): 4 plots in cores/")
print(f"All plots organized in:")
print(f"- fluxes/ folder: 18 plots (Sets 1&2)")
print(f"- depths/ folder: 24 plots (Sets 3&4)")
print(f"- cores/ folder: 8 plots (Sets 5&6)")
print(f"{'='*60}")