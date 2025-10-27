#!/usr/bin/env python3
"""
Presentation Plots for MD Simulation Data

This script creates presentation-quality plots from processed MD simulation data.
Loads from the pickle file created by diameter_nozzle_fiber_simulations.py
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for headless plotting
import matplotlib.pyplot as plt
import pickle
import subprocess
from pathlib import Path

def load_simulation_data(script_dir):
    """
    Load simulation data from pickle file, or run processing script if needed.
    """
    pickle_file = script_dir / "md_simulation_data.pkl" 
    
    if pickle_file.exists():
        print("Loading simulation data from pickle file...")
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
        print(f"✓ Loaded simulation data: {len(data)} data points from {data['MD'].nunique()} simulations")
        return data
    else:
        print("Pickle file not found. Running data processing script...")
        try:
            # Run the data processing script
            result = subprocess.run(['python', 'diameter_nozzle_fiber_simulations.py'], 
                                  capture_output=True, text=True, check=True)
            print("✓ Data processing completed")
            
            # Try loading again
            if pickle_file.exists():
                with open(pickle_file, 'rb') as f:
                    data = pickle.load(f)
                print(f"✓ Loaded simulation data: {len(data)} data points from {data['MD'].nunique()} simulations")
                return data
            else:
                raise FileNotFoundError("Pickle file still not found after processing")
                
        except subprocess.CalledProcessError as e:
            print(f"Error running data processing script: {e}")
            print(f"stdout: {e.stdout}")
            print(f"stderr: {e.stderr}")
            return None
        except Exception as e:
            print(f"Error: {e}")
            return None

def create_plots_directory(script_dir):
    """Create plots directory if it doesn't exist."""
    plots_dir = script_dir / "plots"
    plots_dir.mkdir(exist_ok=True)
    return plots_dir

def plot_all_cores_time_series(data, plots_dir):
    """
    Create a time series plot showing all cores for selected MD simulations.
    """
    print("Creating time series plot for all cores...")
    
    # Plotting configuration
    plt.rcParams.update({
        'figure.figsize': (16, 9), 
        'figure.dpi': 300,
        'savefig.dpi': 600,
        'lines.linewidth': 1.0,
        'axes.linewidth': 0.5,
        'grid.linewidth': 0.3,
        'font.size': 16,
        'axes.labelsize': 16,
        'axes.titlesize': 20,
        'legend.fontsize': 14,
        'xtick.labelsize': 16,
        'ytick.labelsize': 16,
        'figure.titlesize': 20
    })
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    axes = axes.flatten()
    
    # Select a few representative MD simulations for clarity
    selected_mds = ['md1', 'md5', 'md10', 'md15', 'md20']
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    
    cores = ['Core_A', 'Core_B', 'Core_C', 'Core_D']
    core_titles = ['Core A', 'Core B', 'Core C', 'Core D']
    
    for i, (core, title) in enumerate(zip(cores, core_titles)):
        ax = axes[i]
        
        for j, (md, color) in enumerate(zip(selected_mds, colors)):
            md_data = data[data['MD'] == md].copy()
            if not md_data.empty:
                ax.plot(md_data['Time_min'], md_data[core], 
                       color=color, label=md.upper(), linewidth=1.5)
        
        ax.set_xlabel('Time (minutes)')
        ax.set_ylabel('Temperature (°C)')
        ax.set_title(title, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # Set consistent y-axis limits for comparison
        temp_min = data[core].min() - 1
        temp_max = data[core].max() + 1
        ax.set_ylim(temp_min, temp_max)
    
    plt.suptitle('MD Simulation Heat Curves - All Cores Comparison', fontweight='bold')
    plt.tight_layout()
    
    output_file = plots_dir / "MD_simulation_all_cores_time_series.png"
    plt.savefig(output_file, bbox_inches='tight')
    plt.close()
    
    print(f"  ✓ Plot saved: {output_file}")
    return output_file

def plot_core_b_comparison(data, plots_dir):
    """
    Create a focused plot showing Core B for all MD simulations.
    """
    print("Creating Core B comparison plot...")
    
    plt.figure(figsize=(16, 9))
    
    # Get all unique MD simulations
    md_list = sorted(data['MD'].unique(), key=lambda x: int(x[2:]))  # Sort by number
    
    # Use a colormap for many simulations
    colors = plt.cm.tab20(np.linspace(0, 1, len(md_list)))
    
    for i, md in enumerate(md_list):
        md_data = data[data['MD'] == md].copy()
        if not md_data.empty:
            plt.plot(md_data['Time_min'], md_data['Core_B'], 
                    color=colors[i], label=md.upper(), linewidth=1.0, alpha=0.8)
    
    plt.xlabel('Time (minutes)')
    plt.ylabel('Temperature (°C)')
    plt.title('Core B Temperature Evolution - All MD Simulations', fontweight='bold')
    plt.grid(True, alpha=0.3)
    
    # Create a more compact legend
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', ncol=2)
    
    output_file = plots_dir / "MD_simulation_Core_B_all_comparison.png"
    plt.savefig(output_file, bbox_inches='tight')
    plt.close()
    
    print(f"  ✓ Plot saved: {output_file}")
    return output_file

def main():
    """
    Main function to create presentation plots for MD simulations.
    """
    script_dir = Path(__file__).parent
    
    print("MD Simulation Presentation Plots")
    print(f"Working directory: {script_dir}")
    print()
    
    # Load simulation data
    data = load_simulation_data(script_dir)
    if data is None:
        print("Failed to load simulation data. Exiting.")
        return
    
    # Create plots directory
    plots_dir = create_plots_directory(script_dir)
    print(f"Plots will be saved to: {plots_dir}")
    print()
    
    # Create plots
    generated_plots = []
    
    # Plot 1: All cores time series
    plot_file = plot_all_cores_time_series(data, plots_dir)
    generated_plots.append(plot_file)
    
    # Plot 2: Core B comparison
    plot_file = plot_core_b_comparison(data, plots_dir) 
    generated_plots.append(plot_file)
    
    # Summary
    print()
    print("="*60)
    print("MD SIMULATION plot generation completed successfully!")
    print("="*60)
    print("Generated plots:")
    for plot_file in generated_plots:
        print(f"  - {plot_file.name}")
    print("="*60)

if __name__ == "__main__":
    main()