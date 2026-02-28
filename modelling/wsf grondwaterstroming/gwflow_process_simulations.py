#!/usr/bin/env python3
"""
Import and process simulation heat curve data from diameter nozzle fiber experiments.

This script:
1. Imports  simulation data from *_05_A3_DTS_v5.txt files
2. Parses the temperature data for cores A, B, C, D and time
3. Converts time from seconds to minutes
4. Combines all data with GW identifiers
5. Adds Core_average column (average of Core_A, Core_B, Core_C, Core_D) 
6. Adds darcy_flux column by reading it from batch variable file
7. Saves to pickle file for fast loading, easy distirbution, and use in plotting scripts

This is the data processing script. For plotting, use presentation_plots_simulations.py
"""

import os
import pandas as pd
import pickle
from pathlib import Path

def parse_gw_file(file_path, gw_name):
    """
    Parse a single gw simulation output file.
    
    Args:
        file_path: Path to the gw*_05_A3_DTS_v5.txt file
        gw_name: Name identifier (e.g., 'gw1', 'gw2', etc.)
    
    Returns:
        DataFrame with columns: gw, Core_A, Core_B, Core_C, Core_D, Time_min
    """
    print(f"  Processing {gw_name}: {os.path.basename(file_path)}")
    
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
                    'gw': gw_name,
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

def find_gw_files(base_dir):
    """
    Find all gw*_05_A3_DTS_v5.txt files in gw*_output folders.
    
    Returns:
        List of tuples: (file_path, gw_name)
    """
    base_path = Path(base_dir)
    gw_files = []
    
    # Find all gw*_output folders
    for item in base_path.iterdir():
        if item.is_dir() and item.name.startswith('gw') and item.name.endswith('_output'):
            # Extract gw name (remove '_output' suffix)
            gw_name = item.name.replace('_output', '')
            
            # Look for the specific file
            target_file = item / f"{gw_name}_05_A3_DTS_v5.txt"
            if target_file.exists():
                gw_files.append((str(target_file), gw_name))
            else:
                print(f"Warning: Expected file not found: {target_file}")
    
    return gw_files

def read_batch_variables(file_path):
    """
    Read batch variable file and return a DataFrame keyed by gw id.

    Expected input columns include at least 'id' and may include runtime,
    darcy_flux, temperature, voltage, amperage, heating_time, buildup_time,
    rotate, etc.
    """
    with open(file_path, 'r') as f:
        lines = f.readlines()

    header = None
    rows = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        if header is None:
            header = [col.strip() for col in line.split(',')]
            continue

        # Keep real run rows even if disabled for FlexPDE with leading '#'
        # (e.g., '#gw01,...'), but skip descriptive comment lines.
        if line.startswith('#'):
            if len(line) > 1 and line[1:3].lower() == 'gw':
                line = line[1:].strip()
            else:
                continue

        values = [val.split('#', 1)[0].strip() for val in line.split(',')]
        if len(values) < len(header):
            continue

        rows.append(values[:len(header)])

    if header is None:
        raise ValueError(f"No header found in batch variable file: {file_path}")

    batch_df = pd.DataFrame(rows, columns=header)
    batch_df['id'] = batch_df['id'].astype(str).str.strip()
    batch_df = batch_df.rename(columns={'id': 'gw'})
    return batch_df

def main():
    """
    Main function to process all gw simulation data.
    """
    # Get the directory where this script is located
    script_dir = Path(__file__).parent
    
    print("Processing gw simulation heat curve data...")
    print(f"Working directory: {script_dir}")
    print()
    
    # Find all gw files
    gw_files = find_gw_files(script_dir)
    
    if not gw_files:
        print("No gw files found matching pattern 'gw*_output/gw*_05_A3_DTS_v5.txt'")
        return
    
    # Sort by gw number for consistent processing
    gw_files.sort(key=lambda x: x[1])  # Sort by gw_name
    
    print(f"Found {len(gw_files)} gw simulation files:")
    for file_path, gw_name in gw_files:
        print(f"  - {gw_name}: {os.path.basename(file_path)}")
    print()
    
    # Process all files
    all_dataframes = []
    successful_loads = 0
    
    for file_path, gw_name in gw_files:
        print(f"Processing {gw_name}...")
        df = parse_gw_file(file_path, gw_name)
        
        if df is not None:
            all_dataframes.append(df)
            successful_loads += 1
        print()
    
    if not all_dataframes:
        print("No data was successfully loaded!")
        return
    
    # Combine all data
    print("Combining all gw simulation data...")
    combined_data = pd.concat(all_dataframes, ignore_index=True)
    batch_data = read_batch_variables(script_dir / "batch_variables_gwflow.txt")
    
    # Sort by gw and time for consistent ordering
    combined_data = combined_data.sort_values(['gw', 'Time_min']).reset_index(drop=True)
    combined_data = combined_data.merge(batch_data, on='gw', how='left')
    combined_data['Core_average'] = combined_data[['Core_A', 'Core_B', 'Core_C', 'Core_D']].mean(axis=1)

    if 'darcy_flux' not in combined_data.columns:
        raise ValueError("Missing 'darcy_flux' column after joining batch_variables_gwflow.txt")

    batch_cols = [
        col for col in batch_data.columns
        if col != 'gw' and col in combined_data.columns
    ]

    # Keep core simulation columns grouped and include all batch variables.
    cols = [
        "gw",
        *batch_cols,
        "Time_min",
        "Core_A",
        "Core_B",
        "Core_C",
        "Core_D",
        "Core_average",
    ]
    combined_data = combined_data[cols]
    
    print(f"Combined dataset info:")
    print(f"  Total data points: {len(combined_data):,}")
    print(f"  gw simulations: {combined_data['gw'].nunique()}")
    print(f"  gw names: {sorted(combined_data['gw'].unique())}")
    print(f"  Time range: {combined_data['Time_min'].min():.3f} - {combined_data['Time_min'].max():.3f} minutes")
    print(f"  Temperature range:")
    for core in ['Core_A', 'Core_B', 'Core_C', 'Core_D']:
        temp_min = combined_data[core].min()
        temp_max = combined_data[core].max()
        print(f"    {core}: {temp_min:.3f} - {temp_max:.3f} °C")
    print()
    
    # Save to pickle
    output_file = script_dir / "gw_simulation_data.pkl"
    with open(output_file, 'wb') as f:
        pickle.dump(combined_data, f)
    
    print(f"✓ Successfully saved combined gw simulation data to: {output_file}")
    print(f"  File size: {output_file.stat().st_size / 1024:.1f} KB")
    
    # Show sample of the data
    print("\nSample of combined data:")
    print(combined_data.head(10))
    
    print("\nData summary by gw:")
    summary = combined_data.groupby('gw').agg({
        'Time_min': ['count', 'min', 'max'],
        'Core_A': ['min','max','mean'],
        'Core_B': ['min','max','mean'],
        'Core_C': ['min','max','mean'], 
        'Core_D': ['min','max','mean']
    }).round(3)
    print(summary)

if __name__ == "__main__":
    main()