
# -*- coding: utf-8 -*-
"""
Diameter nozzle fiber experiment analysis script
"""

import yaml

# Import functions from ahdts module
from ahdts import extract_dates, xml_to_dict2, get_filepaths, data_to_df, find_nearest, save_as_pickle, load_pickle


data_dir = yaml.safe_load(open(r"..\config.yaml"))["data_dir"] # Set data directory in config.yaml
filepaths = get_filepaths(data_dir, 'xml')

data_dict = xml_to_dict2(filepaths)

# To save into pickle format and load it
# save_as_pickle(pickle_dir, data_dict, name)  # pickle_dir: directory to save the pickle file, name: name for the file
# data_dict = load_pickle(filepath)  # filepath: path where the pickle file is stored (full path including filename.pickle)

df = data_to_df(data_dict, "Temperature") # Convert raw data to a dataframe (index: datetimes, columns, distance)


#%%
##----Separate into sections----##
loc_dict = {
            "h1": {"a":[32.75,34.12],"b":[58.45,59.82],"c":[118.25,119.64],"d":[143.95,145.26]},
            "h2": {"a":[35.17,36.55],"b":[55.9,57.28],"c":[120.68,122.05],"d":[141.4,142.81]},
            "h3": {"a":[37.3,38.67],"b":[53.77,55.14],"c":[122.81,124.19],"d":[139.28,140.64]},
            "h4": {"a":[39.73,41.10],"b":[51.34,52.72],"c":[125.23,126.6],"d":[136.85,138.23]},
            "h5": {"a":[41.85,43.31],"b":[49.21,50.58],"c":[127.36,128.76],"d":[134.72,136.08]},
            "h6": {"a":[44.38,45.82],"b":[46.73,48.15],"c":[129.82,131.27],"d":[132.17,133.66]}    
           }


for section in list(loc_dict.keys()):
    for seg in list(loc_dict[section].keys()):
        start = loc_dict[section][seg][0]
        end = loc_dict[section][seg][1]
        
        sub_df = df.iloc[:,find_nearest(df.columns,start):find_nearest(df.columns,end)]
        
        

        
        