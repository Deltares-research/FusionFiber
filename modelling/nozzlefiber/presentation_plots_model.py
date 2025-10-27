#!/usr/bin/env python3
"""
Process model heat curve data and create presentation plots from MD simulation output files.

This script:
1. Imports MD simulation data from md*_05_A3_DTS_v5.txt files (if not already processed)
2. Parses the temperature data for cores A, B, C, D and time
3. Converts time from seconds to minutes
4. Combines all data with MD identifiers
5. Saves to pickle file for fast loading
6. Creates presentation-quality plots for model data analysis
"""

import os
import pandas as pd
import pickle
from pathlib import Path
import re

def parse_md_file(file_path, md_name):
    """
    Parse a single MD simulation output file.
    
    Args:
        file_path: Path to the md*_05_A3_DTS_v5.txt file
        md_name: Name identifier (e.g., 'md1', 'md2', etc.)
    
    Returns:
        DataFrame with columns: MD, Core_A, Core_B, Core_C, Core_D, Time_min
    """
    print(f"  Processing {md_name}: {os.path.basename(file_path)}")
    
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        # Find the end of the header (line with closing brace)
        data_start_idx = None
        for i, line in enumerate(lines):
            if line.strip() == '}':
                data_start_idx = i + 1
                break
        
        if data_start_idx is None:
            print(f"    Warning: Could not find header end in {file_path}")
            return None
        
        # Read the data section
        data_lines = lines[data_start_idx:]
        
        # Parse data
        data_rows = []
        for line_num, line in enumerate(data_lines):
            line = line.strip()
            if not line:  # Skip empty lines
                continue
                
            try:
                # Split by tab and convert to float
                values = [float(x) for x in line.split('\t')]
                if len(values) != 5:
                    print(f"    Warning: Expected 5 columns, got {len(values)} in line {line_num + data_start_idx + 1}")
                    continue
                
                # Extract temperature data and time
                core_a, core_b, core_c, core_d, time_sec = values
                time_min = time_sec / 60.0  # Convert seconds to minutes
                
                data_rows.append({
                    'MD': md_name,
                    'Core_A': core_a,
                    'Core_B': core_b, 
                    'Core_C': core_c,
                    'Core_D': core_d,
                    'Time_min': time_min
                })
                
            except ValueError as e:
                print(f"    Warning: Could not parse line {line_num + data_start_idx + 1}: {line}")
                continue
        
        if not data_rows:
            print(f"    Warning: No valid data found in {file_path}")
            return None
            
        df = pd.DataFrame(data_rows)
        print(f"    ✓ Loaded {len(df)} data points, time range: {df['Time_min'].min():.3f} - {df['Time_min'].max():.3f} minutes")
        return df
        
    except Exception as e:
        print(f"    Error processing {file_path}: {e}")
        return None

def find_md_files(base_dir):
    """
    Find all md*_05_A3_DTS_v5.txt files in md*_output folders.
    
    Returns:
        List of tuples: (file_path, md_name)
    """
    base_path = Path(base_dir)
    md_files = []
    
    # Find all md*_output folders
    for item in base_path.iterdir():
        if item.is_dir() and item.name.startswith('md') and item.name.endswith('_output'):
            # Extract MD name (remove '_output' suffix)
            md_name = item.name.replace('_output', '')
            
            # Look for the specific file
            target_file = item / f"{md_name}_05_A3_DTS_v5.txt"
            if target_file.exists():
                md_files.append((str(target_file), md_name))
            else:
                print(f"Warning: Expected file not found: {target_file}")
    
    return md_files

def main():
    """
    Main function to process all MD simulation data.
    """
    # Get the directory where this script is located
    script_dir = Path(__file__).parent
    
    print("Processing MD simulation heat curve data...")
    print(f"Working directory: {script_dir}")
    print()
    
    # Find all MD files
    md_files = find_md_files(script_dir)
    
    if not md_files:
        print("No MD files found matching pattern 'md*_output/md*_05_A3_DTS_v5.txt'")
        return
    
    # Sort by MD number for consistent processing
    md_files.sort(key=lambda x: x[1])  # Sort by md_name
    
    print(f"Found {len(md_files)} MD simulation files:")
    for file_path, md_name in md_files:
        print(f"  - {md_name}: {os.path.basename(file_path)}")
    print()
    
    # Process all files
    all_dataframes = []
    successful_loads = 0
    
    for file_path, md_name in md_files:
        print(f"Processing {md_name}...")
        df = parse_md_file(file_path, md_name)
        
        if df is not None:
            all_dataframes.append(df)
            successful_loads += 1
        print()
    
    if not all_dataframes:
        print("No data was successfully loaded!")
        return
    
    # Combine all data
    print("Combining all MD simulation data...")
    combined_data = pd.concat(all_dataframes, ignore_index=True)
    
    # Sort by MD and time for consistent ordering
    combined_data = combined_data.sort_values(['MD', 'Time_min']).reset_index(drop=True)
    
    print(f"Combined dataset info:")
    print(f"  Total data points: {len(combined_data):,}")
    print(f"  MD simulations: {combined_data['MD'].nunique()}")
    print(f"  MD names: {sorted(combined_data['MD'].unique())}")
    print(f"  Time range: {combined_data['Time_min'].min():.3f} - {combined_data['Time_min'].max():.3f} minutes")
    print(f"  Temperature range:")
    for core in ['Core_A', 'Core_B', 'Core_C', 'Core_D']:
        temp_min = combined_data[core].min()
        temp_max = combined_data[core].max()
        print(f"    {core}: {temp_min:.3f} - {temp_max:.3f} °C")
    print()
    
    # Save to pickle
    output_file = script_dir / "md_simulation_data.pkl"
    with open(output_file, 'wb') as f:
        pickle.dump(combined_data, f)
    
    print(f"✓ Successfully saved combined MD simulation data to: {output_file}")
    print(f"  File size: {output_file.stat().st_size / 1024:.1f} KB")
    
    # Show sample of the data
    print("\nSample of combined data:")
    print(combined_data.head(10))
    
    print("\nData summary by MD:")
    summary = combined_data.groupby('MD').agg({
        'Time_min': ['count', 'min', 'max'],
        'Core_A': ['mean', 'std'],
        'Core_B': ['mean', 'std'],
        'Core_C': ['mean', 'std'], 
        'Core_D': ['mean', 'std']
    }).round(3)
    print(summary)

if __name__ == "__main__":
    main()