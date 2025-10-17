# -*- coding: utf-8 -*-
"""
Created on Fri Oct 17 11:57:05 2025
@author: pefkos
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
    of specific keywords like 'UTC' and 'DS'.
    
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
    counts = filepaths[0].split("\\")[-1].count(".")
    
    if (counts == 1) or (counts==2 and "UTC" not in filepaths[0]):
        datetimes = [filepaths[j].split("\\")[-1].split(".")[0].split("_")[-1][:-3] for j in range(len(filepaths))]
    elif counts == 2:
        if "DS" in filepaths[0]:
            datetimes = [''.join(filepaths[j].split("_")[-2:]).split(".")[0] for j in range(len(filepaths))] 
        if "UTC" in filepaths[0] and "DS" not in filepaths[0]:
            datetimes = [filepaths[j].split("\\")[-1].split(".xml")[0].split(".")[0].split("UTC_")[-1].replace("_"," ") for j in range(len(filepaths))]
    return(datetimes)


def xml_to_dict2(filepaths):
    """
    Parse multiple XML files containing DTS (Distributed Temperature Sensing) data.
    
    This function reads XML files sequentially, extracts temperature measurements,
    Stokes and anti-Stokes signals, probe temperatures, and timing information.
    It handles corrupted files gracefully and provides progress feedback.
    
    Parameters
    ----------
    filepaths : list of str
        List of paths to XML files containing DTS measurement data.
        Files are expected to follow a specific XML structure with log data.
    
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
    for memory pre-allocation. Progress is printed during processing, and a summary
    of the loaded data is displayed upon completion.
    
    Corrupted XML files are skipped and their paths are recorded in the output
    dictionary for later inspection.
    
    Examples
    --------
    >>> filepaths = ['file1.xml', 'file2.xml']
    >>> data = xml_to_dict2(filepaths)
    >>> print(data['Temperature'].shape)
    (2, 1000)  # 2 files, 1000 distance points
    """
    start = time.time()
      
    probe_1 = np.zeros(len(filepaths))
    probe_2 = np.zeros(len(filepaths))
    reference_temp = np.zeros(len(filepaths))
    
    dates = extract_dates(filepaths)
    
    corrupted_files = []
    
    for j in range(len(filepaths)):   
        print("Reading file:",str(j),"of",str(len(filepaths)))
    
        ##----Read first file separately to obtain distance vector in order to pre-allocate numpy array sizes----##
        if j == 0: 
            with open(filepaths[j]) as file:
                
                doc = xmltodict.parse(file.read())            
                data_dict = doc["logs"]["log"]["logData"]["data"]  
                measurement = np.array([data_dict[i].split(',') for i in range(len(data_dict))]).astype(np.float64)      
                distance = measurement[:,0]
                stokes_d = measurement[:,1]
                anti_stokes_d = measurement[:,2]
                temps = measurement[:,-1] 
                
                probe_1[0] = float(doc["logs"]["log"]["customData"]["probe1Temperature"]["#text"])
                probe_2[0] = float(doc["logs"]["log"]["customData"]["probe2Temperature"]["#text"])
                reference_temp[0] = float(doc["logs"]["log"]["customData"]["referenceTemperature"]["#text"])

                max_time = doc["logs"]["log"]["endDateTimeIndex"].split('.')[0].replace("T"," ")
                max_dt = datetime.strptime(max_time, '%Y-%m-%d %H:%M:%S')
                min_time = doc["logs"]["log"]["startDateTimeIndex"].split('.')[0].replace("T"," ")
                min_dt = datetime.strptime(min_time, '%Y-%m-%d %H:%M:%S')
                user_acquisition_time = float((max_dt-min_dt).seconds)
    
            temperatures = np.zeros((len(filepaths),len(data_dict)))
            stokes = np.zeros((len(filepaths),len(data_dict)))
            anti_stokes = np.zeros((len(filepaths),len(data_dict)))
            
            temperatures[0,:] = temps
            stokes[0,:] = stokes_d
            anti_stokes[0,:] = anti_stokes_d
            
            file.close()
    
        else:
            ##----Read remaining files----##
            try:
                with open(filepaths[j]) as file:
                    doc = xmltodict.parse(file.read())
                    data_dict = doc["logs"]["log"]["logData"]["data"]
                    measurement = np.array([data_dict[i].split(',') for i in range(len(data_dict))]).astype(np.float64)      
                    stokes[j,:] = measurement[:,1]
                    anti_stokes[j,:] = measurement[:,2]
                    temperatures[j,:] = measurement[:,-1]
                    
                    probe_1[j] = float(doc["logs"]["log"]["customData"]["probe1Temperature"]["#text"])
                    probe_2[j] = float(doc["logs"]["log"]["customData"]["probe2Temperature"]["#text"])
                    reference_temp[j] = float(doc["logs"]["log"]["customData"]["referenceTemperature"]["#text"])
                                       
                    file.close()
            except ExpatError:
                corrupted_files.append(filepaths[j])
                continue
                 
    end = time.time() 
    reading_time = end-start 
    
    print("------------------")
    print("Data read successfuly. Data reading time:",str(round(reading_time,3)),"s.") 
    print("Datetime range:",str(dates[0]),"to",str(dates[-1]))
    print("Distance range:",str(distance[0]),"m to",str(distance[-1]),"m.")    
    print("Temperature values range:",str(np.min(temperatures)),"C to",str(np.max(temperatures)),"C.")
    print("------------------")
    
    my_dict = dict()
    my_dict["Temperature"] = temperatures
    my_dict["Probe 1"] = probe_1
    my_dict["Probe 2"] = probe_2
    my_dict["Reference Temperature"] = reference_temp
    my_dict["Stokes"] = stokes
    my_dict["Anti-Stokes"] = anti_stokes
    my_dict["Distance"] = distance
    dates = pd.to_datetime(dates)
    my_dict["Datetimes"] = dates
    my_dict["User Acquisition Time"] = user_acquisition_time
    my_dict["Corrupted files"] = corrupted_files

    return(my_dict)


def get_filepaths(parent_dir, ext):
    """
    Get sorted list of file paths with specified extension from a directory.
    
    Parameters
    ----------
    parent_dir : str
        Path to the directory containing the files to search.
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
    filepaths = sorted(glob.glob(parent_dir+"\\*."+ext))
        
    return(filepaths)


def data_to_df(data_dict, key):
    """
    Convert data dictionary to a pandas DataFrame for a specific measurement type.
    
    Assembles measurement data, distance vector, and datetimes into a structured
    DataFrame according to the chosen property. The resulting DataFrame has
    datetimes as the index and distance points as columns, sorted by timestamp.
    
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
    data = data_dict[key][:len(data_dict["Datetimes"]),:]

    df = pd.DataFrame(data=data,index=pd.to_datetime(data_dict["Datetimes"]),columns=data_dict["Distance"])
    df = df.sort_index()
  
    return(df)


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
    pickle_dir : str
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
    and compatibility with future Python versions.
    
    Examples
    --------
    >>> data = xml_to_dict2(filepaths)
    >>> save_as_pickle(r'C:\\data\\processed', data, 'measurement_2023')
    # Creates: C:\\data\\processed\\measurement_2023.pickle
    """
    with open(pickle_dir+"\\"+name+'.pickle', 'wb') as handle:
        pickle.dump(data_dict, handle, protocol=pickle.HIGHEST_PROTOCOL)
    

def load_pickle(filepath):
    """
    Load a previously saved pickle file containing data dictionary.
    
    Parameters
    ----------
    filepath : str
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
    with open(filepath, 'rb') as file:
        df = pd.read_pickle(file)
        
    return df

















