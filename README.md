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
pixi run install
```

## Update fusionfiber
To update fusionfiber with the latest version from gitlab, open a shell in the fusionfiber folder and:
```
git pull
```
And the same as with installation type:
```
pixi run install
```

## Run the main scripts to reproduce data (en optional model) results
 
To reproduce the data results (50 plots) you can run the main script in the data folder:
```
pixi run python /data/diameter_nozzle_fiber_experiment
```

You can also reproduce the modelling data, but this requires a FlexPDE installation on your machine, which is a proprietary  
licensed software. But if you have this and if the executable is in your PATH environment variable, try:

```
pixi run python /modelling/nozzlefiber/flexpde_batch_nozzle.py
```

This will create subfolders MD* of the different tests associated with the experiments,   
which have typical FlexPDE output files in them, for instance the PG8 model result file.

In the script you can set to different bath_variable_file txt files:
- 1_batch_flux_variables_nozzle.txt (default)
- 2_batch_heat_variables_nozzle.txt
- 3_batch_flux_rotated30deg_variables_nozzle.txt (un construction)