# FusionFiber
One cable, Three senses, Maximum insight
<p align="left">
  <img src="FusionFiber.png" alt="FusionFiber Logo" width="300">
</p>

## Installation process
The installation uses package manager pixi, for installation options see https://pixi.sh/latest/

To install pixi on windows, in powershell type:
```
winget install prefix-dev.pixi
```
Now clone fusionfiber to your local drive using:
```
git clone https://github.com/Deltares-research/FusionFiber.git
```
Then navigate into that folder with:
```
cd fusionfiber
```
To create a pixi enviroment and install fusionfiber in it type:
```
pixi install
```

## Update fusionfiber
To update fusionfiber with the latest version from gitlab, open a shell in the fusionfiber folder and:
```
git pull
```
And the same as with installation type:
```
pixi install
```

## Run the main scripts to reproduce data (en optional model) results
 
To reproduce the data results (50 plots) you can run the main script in the data folder:
```
pixi run python data/diameter_nozzle_fiber_experiment.py
```

## ATES flush workflow

The ATES flush workflow has two parts: generating static analysis plots and opening the interactive QC viewer.

### 1. Run the ATES research script

This script lives in `data/ates_action_research.py` and is configured directly in the file.

Run it with:
```
pixi run ates-research
```

What it does:
- Builds the combined channel pickle automatically if it does not exist yet.
- Summarizes peak temperatures over the selected measurement interval.
- Runs in one of two modes:
  - Midpoint mode: plots temperature over time at the midpoint of each selected location.
  - QC mode: when `QC_TIMESTAMP` is set, it creates a QC imshow, a vertical profile at the selected timestamp, and a time series at `QC_POSITION` when that value is set.

Main settings inside the script:
- `PLOT_LOCATIONS`: list of location keys to include.
- `QC_TIMESTAMP`: set to `None` for midpoint mode, or to a timestamp string for QC mode.
- `QC_POSITION`: optional fiber position for an extra QC time-series plot.

Output files are written to the `data` folder.

### 2. Open the interactive ATES QC viewer

Run the viewer without opening extra browser tabs:
```
pixi run ates-app-nobrowser
```

Or run the normal browser-opening task:
```
pixi run ates-app
```

Quick validation after editing the viewer script:
```
pixi run compile-ates-app
```

You can also reproduce the modelling data, but this requires a FlexPDE installation on your machine,  
which is a proprietary licensed software. But if you have this and if the executable is in your PATH  environment variable, try:

```
pixi run python modelling/nozzlefiber/flexpde_batch_nozzle.py
```

This will create subfolders MD* of the different tests associated with the experiments,   
which have typical FlexPDE output files in them, for instance the PG8 model result file.

In the script you can set to different bath_variable_file txt files:
- 1_batch_flux_variables_nozzle.txt (default)
- 2_batch_heat_variables_nozzle.txt
- 3_batch_flux_rotated30deg_variables_nozzle.txt (un construction)

## Presentation Plots

For creating publication-ready presentation plots, use the specialized plotting scripts:

### Experimental Data Plots
Generate 4 analysis plots of ah-dts experiment data:
```
pixi run python data/presentation_plots_experiment.py
```

### Simulation Data Plots
Generate Darcy flow comparison from simulated data:
```
pixi run python modelling/nozzlefiber/presentation_plots_simulations.py
```
All plots are saved as high-resolution PNG files (600 DPI) with professional styling and consistent formatting.