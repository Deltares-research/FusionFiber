import os
import subprocess
from pathlib import Path

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent

batch_variable_file = SCRIPT_DIR / "batch_variables_gwflow.txt"

# FlexPDE configuration
FLEXPDE_EXE = "FlexPDE8n"
THREADS = 8
timeout = 1800

# Read the template
with open(SCRIPT_DIR / "template_gwflow.pde", "r") as f:
    template = f.read()

# Read variable sets
runs = []
with open(batch_variable_file, "r") as f:
    lines = f.readlines()

    # Skip empty/comment lines to find the header
    data_lines = [line for line in lines if line.strip() and not line.lstrip().startswith("#")]
    header = [col.strip() for col in data_lines[0].split(",")]

    for line in data_lines[1:]:
        values = [val.strip() for val in line.split(",")]
        runs.append(dict(zip(header, values)))

def make_and_run(run):
    # replace placeholders with values from the run dictionary
    content = template
    for key, value in run.items():
        content = content.replace(f"{{{key}}}", str(value))

    # create output subfolder and write PDE file
    output_folder = SCRIPT_DIR / f"{run['id']}_output"
    output_folder.mkdir(exist_ok=True)
    
    with open(output_folder / f"{run['id']}.pde", "w") as f:
        f.write(content)
    
    # Run FlexPDE
    subprocess.run([FLEXPDE_EXE, f"-T{THREADS}", "-Q", "-NC", "-NM", f"{run['id']}.pde"], 
                   cwd=output_folder, timeout=timeout)

# Run all models
if __name__ == '__main__':
    for i, run in enumerate(runs, 1):
        print(f"Run {i}/{len(runs)}: {run['id']}")
        make_and_run(run)
        
