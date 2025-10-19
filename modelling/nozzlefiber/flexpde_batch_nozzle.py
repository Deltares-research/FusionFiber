import os
import subprocess
from pathlib import Path

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent

# FlexPDE Configuration
FLEXPDE_EXE = "FlexPDE8n"
THREADS = 8

# Read the template (using pathlib)
template_path = SCRIPT_DIR / "template_nozzle.pde"
with open(template_path, "r") as f:
    template = f.read()

# Read variable sets (using pathlib)
variables_path = SCRIPT_DIR / "2_batch_heat_variables_nozzle.txt"
runs = []
with open(variables_path, "r") as f:
    lines = f.readlines()
    for line in lines:
        if line.strip() and not line.startswith("id"):
            parts = [p.strip() for p in line.split(",")]
            run_id = parts[0]
            runtime = parts[1]
            darcy_flux = parts[2]
            temperature = parts[3]
            voltage = parts[4]
            amperage = parts[5]
            heating_time = parts[6]
            buildup_time = parts[7]
            runs.append({
                "id": run_id,                   # Unique identifier for the run, MD for Mooi Diameter
                "runtime": runtime,             # Total runtime in seconds
                "qx": darcy_flux,               # Darcy flux value in meters per day
                "T0": temperature,              # Initial temperature in Celsius
                "Heatin": voltage,              # Heating voltage
                "amperage": amperage,           # Cable amperage
                "t_cutoff": heating_time,       # Total heating time of cable in seconds
                "t_transition": buildup_time    # Built-up (and down) time for/from full power through heating cable seconds

            })

def make_and_run(run):
    # Replace variables in template
    content = template
    content = content.replace("TITLE 'Bommelerwaard_V170_q52.8'", f"TITLE '{run['id']}'")
    content = content.replace("Runtime=(7200)", f"Runtime=({run['runtime']})")
    content = content.replace("transfer('head_optie1_output\\head_Darcy52.8.dat', head)", f"transfer('head_optie1_output\\head_Darcy{run['qx']}.dat', head)")
    content = content.replace("T0= 25", f"T0= {run['T0']}")
    content = content.replace("Heatin=170", f"Heatin={run['Heatin']}")
    content = content.replace("Cableheat = Heatin*3.5", f"Cableheat = Heatin*{run['amperage']}")
    content = content.replace("t_cutoff = 1800", f"t_cutoff = {run['t_cutoff']}")
    content = content.replace("t_transition = 2", f"t_transition = {run['t_transition']}")

    # Write new PDE file
    pde_filename = f"{run['id']}.pde"
    pde_filepath = SCRIPT_DIR / pde_filename
    with open(pde_filepath, "w") as f:
        f.write(content)
    
    # Run FlexPDE using subprocess for better path handling
    cmd = [FLEXPDE_EXE, f"-T{THREADS}", "-Q", "-NC", "-NM", pde_filename]
    print(f"Command: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, cwd=SCRIPT_DIR, timeout=1800)
    except subprocess.TimeoutExpired:
        print(f"Model {run['id']} timed out after 1/2 hour")

# Run all models sequentially
if __name__ == '__main__':
    print(f"Processing {len(runs)} model runs...")
    
    for i, run in enumerate(runs, 1):
        print(f"\n--Run {i}/{len(runs)}: {run['id']}--")
        make_and_run(run)
        
