# -*- coding: utf-8 -*-
"""
Created on Fri Oct 17 11:57:05 2025
@author: pefkos and nieboer
"""
from xml.parsers.expat import ExpatError
from datetime import datetime
import pandas as pd
import numpy as np
import xmltodict
import time
import glob
import pickle

def extract_dates(filepaths):
    """
    Extract datetime strings from file paths based on file naming conventions.
    
    This function parses file paths to extract datetime information using different
    parsing strategies based on the number of dots in the filename and presence
    of specific keywords like 'UTC' and 'DS'. Optimized for batch processing.
    
    Parameters
    ----------
    filepaths : list of str
        List of file paths to extract dates from. The function analyzes the first
        file path to determine the naming convention and applies it to all files.
    
    Returns
    -------
    list of str
        List of datetime strings extracted from the file paths. Format varies
        depending on the detected file naming convention.
    
    Notes
    -----
    The function handles three main naming conventions:
    - Single dot or double dot without 'UTC': extracts from underscore-separated parts
    - Files with 'DS' keyword: joins last two underscore-separated parts
    - Files with 'UTC' but no 'DS': extracts UTC timestamp and formats it
    
    Examples
    --------
    >>> filepaths = ['path\\to\\file_20231017123.xml']
    >>> extract_dates(filepaths)
    ['20231017123']
    """
    if not filepaths:
        return []
    
    # Use pathlib for more robust path handling
    from pathlib import Path
    
    # Analyze first file to determine pattern
    first_file = Path(filepaths[0]).name
    counts = first_file.count(".")
    
    # Pre-compile pattern decisions to avoid repeated string operations
    has_utc = "UTC" in first_file
    has_ds = "DS" in first_file
    
    if (counts == 1) or (counts == 2 and not has_utc):
        # Optimized: use list comprehension with pre-split logic
        datetimes = [Path(fp).stem.split("_")[-1][:-3] for fp in filepaths]
    elif counts == 2:
        if has_ds:
            datetimes = [Path(fp).stem.split("_", -2)[-2] + Path(fp).stem.split("_", -1)[-1] for fp in filepaths]
        elif has_utc and not has_ds:
            datetimes = [Path(fp).stem.split(".")[0].split("UTC_")[-1].replace("_", " ") for fp in filepaths]
        else:
            datetimes = []
    else:
        datetimes = []
    
    return datetimes


def xml_to_dict2(filepaths, use_multiprocessing=None, n_workers=None):
    """
    Parse multiple XML files containing DTS (Distributed Temperature Sensing) data.
    
    This function reads XML files with optional parallel processing, extracts temperature 
    measurements, Stokes and anti-Stokes signals, probe temperatures, and timing information.
    It handles corrupted files gracefully and provides progress feedback.
    
    Parameters
    ----------
    filepaths : list of str
        List of paths to XML files containing DTS measurement data.
        Files are expected to follow a specific XML structure with log data.
    use_multiprocessing : bool or None, optional
        If True, use parallel processing to speed up XML parsing. 
        If None (default), automatically decide based on file count and execution context.
        If False, force sequential processing.
    n_workers : int, optional
        Number of worker processes. If None, uses CPU count. Default is None.
    
    Returns
    -------
    dict
        Dictionary containing the following keys:
        - 'Temperature' : numpy.ndarray
            2D array of temperature measurements (files x distance points)
        - 'Stokes' : numpy.ndarray
            2D array of Stokes signal measurements
        - 'Anti-Stokes' : numpy.ndarray
            2D array of anti-Stokes signal measurements
        - 'Probe 1' : numpy.ndarray
            1D array of probe 1 temperature readings
        - 'Probe 2' : numpy.ndarray
            1D array of probe 2 temperature readings
        - 'Reference Temperature' : numpy.ndarray
            1D array of reference temperature readings
        - 'Distance' : numpy.ndarray
            1D array of distance points along the fiber
        - 'Datetimes' : pandas.DatetimeIndex
            Timestamps extracted from filenames
        - 'User Acquisition Time' : float
            Duration of measurement acquisition in seconds
        - 'Corrupted files' : list
            List of file paths that couldn't be parsed due to XML errors
    
    Notes
    -----
    The function processes the first file separately to determine array dimensions
    for memory pre-allocation. With multiprocessing enabled, remaining files are
    processed in parallel for significant speed improvements.
    
    Corrupted XML files are skipped and their paths are recorded in the output
    dictionary for later inspection.
    
    Examples
    --------
    >>> filepaths = ['file1.xml', 'file2.xml']
    >>> data = xml_to_dict2(filepaths, use_multiprocessing=True)
    >>> print(data['Temperature'].shape)
    (2, 1000)  # 2 files, 1000 distance points
    """
    start = time.time()
    
    # Auto-decide multiprocessing if not explicitly set
    if use_multiprocessing is None:
        # For Windows, disable multiprocessing by default due to complexity
        # Users can explicitly enable it if they structure their code properly
        import sys
        use_multiprocessing = False
        
        if len(filepaths) > 100:
            print(f"Large dataset detected ({len(filepaths)} files). Multiprocessing disabled by default.")
            print("To enable multiprocessing: xml_to_dict2(filepaths, use_multiprocessing=True)")
            print("Note: On Windows, this requires proper script structure with 'if __name__ == \"__main__\"':")
    
    # Extract dates once for all files
    dates = extract_dates(filepaths)
    
    # Process first file to get dimensions and structure
    print("Reading file: 0 of", len(filepaths))
    first_result = _parse_single_xml(filepaths[0], 0, get_timing=True)
    
    if first_result is None:
        raise ValueError(f"Could not parse first file: {filepaths[0]}")
    
    # Unpack first file results
    distance, stokes_d, anti_stokes_d, temps, probe1_temp, probe2_temp, ref_temp, user_acquisition_time = first_result
    
    # Pre-allocate arrays with known dimensions
    n_files = len(filepaths)
    n_points = len(distance)
    
    temperatures = np.zeros((n_files, n_points), dtype=np.float64)
    stokes = np.zeros((n_files, n_points), dtype=np.float64)
    anti_stokes = np.zeros((n_files, n_points), dtype=np.float64)
    probe_1 = np.zeros(n_files, dtype=np.float64)
    probe_2 = np.zeros(n_files, dtype=np.float64)
    reference_temp = np.zeros(n_files, dtype=np.float64)
    
    # Store first file data
    temperatures[0, :] = temps
    stokes[0, :] = stokes_d
    anti_stokes[0, :] = anti_stokes_d
    probe_1[0] = probe1_temp
    probe_2[0] = probe2_temp
    reference_temp[0] = ref_temp
    
    corrupted_files = []
    
    if len(filepaths) > 1:
        if use_multiprocessing and len(filepaths) > 10:  # Only use multiprocessing for larger datasets
            # Parallel processing for remaining files
            try:
                from multiprocessing import Pool, cpu_count
                import os
                
                n_workers = n_workers or min(cpu_count(), len(filepaths) - 1)
                
                print(f"Using {n_workers} workers for parallel processing...")
                
                # Prepare arguments for parallel processing
                remaining_files = [(filepaths[i], i) for i in range(1, len(filepaths))]
                
                with Pool(n_workers) as pool:
                    # Use imap for progress tracking
                    results = []
                    for i, result in enumerate(pool.imap(_parse_single_xml_wrapper, remaining_files)):
                        if (i + 1) % 50 == 0 or i == len(remaining_files) - 1:
                            print(f"Reading file: {i + 1} of {len(remaining_files)} remaining files")
                        results.append(result)
                
                # Process results (map back to correct indices)
                for result_idx, result in enumerate(results):
                    file_idx = result_idx + 1  # +1 because we skipped the first file
                    if result is not None:
                        _, stokes_vals, anti_stokes_vals, temp_vals, probe1_val, probe2_val, ref_val, _ = result
                        stokes[file_idx, :] = stokes_vals
                        anti_stokes[file_idx, :] = anti_stokes_vals
                        temperatures[file_idx, :] = temp_vals
                        probe_1[file_idx] = probe1_val
                        probe_2[file_idx] = probe2_val
                        reference_temp[file_idx] = ref_val
                    else:
                        corrupted_files.append(filepaths[file_idx])
            
            except (ImportError, RuntimeError) as e:
                # Fall back to sequential processing if multiprocessing fails
                print(f"Multiprocessing failed ({e}), falling back to sequential processing...")
                use_multiprocessing = False
        
        if not use_multiprocessing:
            # Sequential processing for smaller datasets or when multiprocessing is disabled/failed
            for j in range(1, len(filepaths)):
                if j % 100 == 0 or j == len(filepaths) - 1:
                    print(f"Reading file: {j} of {len(filepaths)}")
                
                result = _parse_single_xml(filepaths[j], j)
                if result is not None:
                    _, stokes_vals, anti_stokes_vals, temp_vals, probe1_val, probe2_val, ref_val, _ = result
                    stokes[j, :] = stokes_vals
                    anti_stokes[j, :] = anti_stokes_vals
                    temperatures[j, :] = temp_vals
                    probe_1[j] = probe1_val
                    probe_2[j] = probe2_val
                    reference_temp[j] = ref_val
                else:
                    corrupted_files.append(filepaths[j])
    
    end = time.time()
    reading_time = end - start
    
    print("------------------")
    print(f"Data read successfully. Data reading time: {reading_time:.3f} s.")
    print(f"Datetime range: {dates[0]} to {dates[-1]}")
    print(f"Distance range: {distance[0]:.3f} m to {distance[-1]:.3f} m.")
    print(f"Temperature values range: {np.min(temperatures):.3f} C to {np.max(temperatures):.3f} C.")
    print("------------------")
    
    # Build result dictionary
    my_dict = {
        "Temperature": temperatures,
        "Probe 1": probe_1,
        "Probe 2": probe_2,
        "Reference Temperature": reference_temp,
        "Stokes": stokes,
        "Anti-Stokes": anti_stokes,
        "Distance": distance,
        "Datetimes": pd.to_datetime(dates),
        "User Acquisition Time": user_acquisition_time,
        "Corrupted files": corrupted_files
    }
    
    return my_dict


def _parse_single_xml(filepath, index, get_timing=False):
    """
    Parse a single XML file and extract measurement data.
    
    Helper function for parallel processing of XML files.
    
    Parameters
    ----------
    filepath : str
        Path to the XML file to parse.
    index : int
        Index of the file in the processing sequence.
    get_timing : bool, optional
        If True, also extract timing information. Default is False.
    
    Returns
    -------
    tuple or None
        Tuple containing (distance, stokes, anti_stokes, temperatures, 
        probe1_temp, probe2_temp, ref_temp, user_acquisition_time) if successful,
        None if parsing failed.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            content = file.read()
            
        doc = xmltodict.parse(content)
        data_dict = doc["logs"]["log"]["logData"]["data"]
        
        # More efficient array construction using list comprehension and direct numpy conversion
        # Split all lines at once, then convert to float64
        lines = [data_dict[i].split(',') for i in range(len(data_dict))]
        measurement = np.array(lines, dtype=np.float64)
        
        distance = measurement[:, 0]
        stokes_vals = measurement[:, 1]
        anti_stokes_vals = measurement[:, 2]
        temps = measurement[:, -1]
        
        # Extract probe temperatures more efficiently
        custom_data = doc["logs"]["log"]["customData"]
        probe1_temp = float(custom_data["probe1Temperature"]["#text"])
        probe2_temp = float(custom_data["probe2Temperature"]["#text"])
        ref_temp = float(custom_data["referenceTemperature"]["#text"])
        
        user_acquisition_time = None
        if get_timing:
            # More efficient datetime parsing
            end_time_str = doc["logs"]["log"]["endDateTimeIndex"].split('.')[0]
            start_time_str = doc["logs"]["log"]["startDateTimeIndex"].split('.')[0]
            
            # Use pandas for faster datetime parsing
            end_dt = pd.to_datetime(end_time_str)
            start_dt = pd.to_datetime(start_time_str)
            user_acquisition_time = (end_dt - start_dt).total_seconds()
        
        return (distance, stokes_vals, anti_stokes_vals, temps, 
                probe1_temp, probe2_temp, ref_temp, user_acquisition_time)
        
    except (ExpatError, KeyError, ValueError, FileNotFoundError) as e:
        return None


def _parse_single_xml_wrapper(args):
    """
    Wrapper function for multiprocessing pool.map.
    
    Parameters
    ----------
    args : tuple
        Tuple containing (filepath, index) arguments.
    
    Returns
    -------
    tuple or None
        Result from _parse_single_xml function.
    """
    filepath, index = args
    return _parse_single_xml(filepath, index, get_timing=False)


def get_filepaths(parent_dir, ext):
    """
    Get sorted list of file paths with specified extension from a directory.
    
    Parameters
    ----------
    parent_dir : str or Path
        Path to the directory containing the files to search.
        Can be a string or pathlib.Path object.
    ext : str
        File extension to filter by (without the dot, e.g., 'xml', 'txt').
    
    Returns
    -------
    list of str
        Sorted list of absolute file paths matching the specified extension.
        Files are sorted alphabetically by filename.
    
    Examples
    --------
    >>> filepaths = get_filepaths(r'C:\\data\\xml_files', 'xml')
    >>> print(filepaths[:2])
    ['C:\\data\\xml_files\\file1.xml', 'C:\\data\\xml_files\\file2.xml']
    """
    from pathlib import Path
    
    # Convert to Path object to handle both strings and Path inputs
    parent_path = Path(parent_dir)
    
    # Use Path.glob() which is more robust than string concatenation
    filepaths = sorted([str(p) for p in parent_path.glob(f"*.{ext}")])
        
    return(filepaths)


def data_to_df(data_dict, key):
    """
    Convert data dictionary to a pandas DataFrame for a specific measurement type.
    
    Assembles measurement data, distance vector, and datetimes into a structured
    DataFrame according to the chosen property. The resulting DataFrame has
    datetimes as the index and distance points as columns, sorted by timestamp.
    Optimized for memory efficiency and speed.
    
    Parameters
    ----------
    data_dict : dict
        Dictionary containing measurement data as returned by xml_to_dict2().
        Must contain keys for the specified measurement type, 'Datetimes', and 'Distance'.
    key : str
        Type of measurement data to extract. Valid options include:
        'Temperature', 'Stokes', 'Anti-Stokes'.
    
    Returns
    -------
    pandas.DataFrame
        DataFrame with:
        - Index: datetime timestamps (sorted chronologically)
        - Columns: distance points along the fiber (in meters)
        - Values: measurement data for the specified key
    
    Examples
    --------
    >>> data_dict = xml_to_dict2(filepaths)
    >>> temp_df = data_to_df(data_dict, "Temperature")
    >>> print(temp_df.shape)
    (100, 1000)  # 100 time points, 1000 distance points
    >>> print(temp_df.index.dtype)
    datetime64[ns]
    """
    # More efficient: slice data once and avoid redundant datetime conversion
    n_times = len(data_dict["Datetimes"])
    data = data_dict[key][:n_times, :]
    
    # Datetimes are already pandas datetime objects from xml_to_dict2
    datetimes = data_dict["Datetimes"][:n_times]
    
    # Create DataFrame more efficiently by avoiding redundant to_datetime conversion
    df = pd.DataFrame(data=data, index=datetimes, columns=data_dict["Distance"])
    
    # Use sort_index with optimized parameters for better performance
    if not datetimes.is_monotonic_increasing:
        df = df.sort_index()
    
    return df


def find_nearest(array, value):
    """
    Find the index of the element in array closest to the given value.
    
    Parameters
    ----------
    array : array-like
        Array of numerical values to search through.
    value : float or int
        Target value to find the closest match for.
    
    Returns
    -------
    int
        Index of the array element with the smallest absolute difference
        from the target value.
    
    Examples
    --------
    >>> distances = np.array([0.0, 1.5, 3.2, 5.1, 7.8])
    >>> idx = find_nearest(distances, 3.0)
    >>> print(idx)
    2
    >>> print(distances[idx])
    3.2
    """
    array = np.asarray(array)
    idx = (np.abs(array - value)).argmin()
    
    return(idx)


def save_as_pickle(pickle_dir, data_dict, name):
    """
    Save a data dictionary to a pickle file for efficient storage and retrieval.
    
    Parameters
    ----------
    pickle_dir : str or Path
        Directory path where the pickle file will be saved.
    data_dict : dict
        Dictionary containing the data to be pickled. Typically the output
        from xml_to_dict2().
    name : str
        Base name for the pickle file (without extension). The '.pickle'
        extension will be automatically added.
    
    Returns
    -------
    None
        The function saves the file and returns nothing.
    
    Notes
    -----
    Uses the highest available pickle protocol for optimal performance
    and compatibility with future Python versions. Cross-platform compatible
    using pathlib.
    
    Examples
    --------
    >>> data = xml_to_dict2(filepaths)
    >>> save_as_pickle(r'C:\\data\\processed', data, 'measurement_2023')
    # Creates: C:\\data\\processed\\measurement_2023.pickle
    """
    from pathlib import Path
    
    # Use pathlib for cross-platform compatibility
    pickle_path = Path(pickle_dir) / f"{name}.pickle"
    
    # Ensure directory exists
    pickle_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(pickle_path, 'wb') as handle:
        pickle.dump(data_dict, handle, protocol=pickle.HIGHEST_PROTOCOL)
    

def load_pickle(filepath):
    """
    Load a previously saved pickle file containing data dictionary.
    
    Automatically displays a summary of the loaded data including timing,
    datetime range, distance range, and temperature range, similar to
    the summary shown when loading XML files.
    
    Parameters
    ----------
    filepath : str or Path
        Full path to the pickle file to load, including filename and
        '.pickle' extension.
    
    Returns
    -------
    dict or pandas.DataFrame
        The data structure that was previously saved to the pickle file.
        Typically a dictionary containing measurement data or a DataFrame.
    
    Examples
    --------
    >>> data = load_pickle(r'C:\\data\\processed\\measurement_2023.pickle')
    >>> print(type(data))
    <class 'dict'>
    >>> temp_df = load_pickle(r'C:\\data\\processed\\temperature_df.pickle')
    >>> print(temp_df.shape)
    (100, 1000)
    """
    from pathlib import Path
    import time
    
    start = time.time()
    
    # Use pathlib for cross-platform compatibility and better error handling
    file_path = Path(filepath)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Pickle file not found: {file_path}")
    
    # Use pickle.load directly for better performance than pd.read_pickle
    with open(file_path, 'rb') as file:
        data = pickle.load(file)
    
    end = time.time()
    loading_time = end - start
    
    # Display data summary if data is a dictionary with expected keys
    if isinstance(data, dict) and all(key in data for key in ['Datetimes', 'Distance', 'Temperature']):
        dates = data['Datetimes']
        distance = data['Distance']
        temperatures = data['Temperature']
        print("------------------")
        print(f"Data loaded successfully. Data loading time: {loading_time:.3f} s.")
        print(f"Datetime range: {dates[0]} to {dates[-1]}")
        print(f"Distance range: {distance[0]:.3f} m to {distance[-1]:.3f} m.")
        print(f"Temperature values range: {np.min(temperatures):.3f} C to {np.max(temperatures):.3f} C.")
        print("------------------")
        
    return data

















