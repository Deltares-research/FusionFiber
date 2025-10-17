import os
import subprocess
import time
import threading

# Path to FlexPDE executable
FLEXPDE_EXE = r"C:\Program Files\FlexPDE8\FlexPDE8n.exe"  # Console version for true headless operation
THREADS = 16  # Number of parallel threads to run

# Read the template
with open("template_nozzle.pde", "r") as f:
    template = f.read()

# Read variable sets
runs = []
with open("model_variables_nozzle.txt", "r") as f:
    lines = f.readlines()
    for line in lines:
        if line.strip() and not line.startswith("id"):
            parts = [p.strip() for p in line.split(",")]
            run_id = parts[0]
            darcy_flux = parts[1]
            temperature = parts[2]
            voltage = parts[3]
            amperage = parts[4]
            heating_time = parts[5]
            buildup_time = parts[6]
            runs.append({
                "id": run_id,                   # Unique identifier for the run, MD for Mooi Diameter
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
    content = content.replace("transfer('head_optie1_output\\head_Darcy52.8.dat', head)", f"transfer('head_optie1_output\\head_Darcy{run['qx']}.dat', head)")
    content = content.replace("T0= 25", f"T0= {run['T0']}")
    content = content.replace("Heatin=170", f"Heatin={run['Heatin']}")
    content = content.replace("Cableheat = Heatin*3.5", f"Cableheat = Heatin*{run['amperage']}")
    content = content.replace("t_cutoff = 1800", f"t_cutoff = {run['t_cutoff']}")
    content = content.replace("t_transition = 2", f"t_transition = {run['t_transition']}")
  

    # Write new PDE file
    pde_filename = f"{run['id']}.pde"
    with open(pde_filename, "w") as f:
        f.write(content)
    # Run FlexPDE with real-time output and progress tracking
    print(f"Running {pde_filename}...")
    start_time = time.time()
    
    # Use the most aggressive approach to prevent any GUI
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    
    # Function to print elapsed time periodically
    def print_progress():
        while True:
            elapsed = time.time() - start_time
            minutes, seconds = divmod(int(elapsed), 60)
            print(f"   ⏱️  Running for {minutes}m {seconds}s...", end='\r')
            time.sleep(30)  # Update every 30 seconds
    
    # Start progress thread
    progress_thread = threading.Thread(target=print_progress, daemon=True)
    progress_thread.start()
    
    try:
        # Run without capturing output to see real-time progress
        result = subprocess.run([FLEXPDE_EXE, f"-T{THREADS}", pde_filename], 
                              creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
                              startupinfo=startupinfo,
                              cwd=os.getcwd(),
                              timeout=1800)  # 15 minutes timeout
        
        elapsed = time.time() - start_time
        minutes, seconds = divmod(int(elapsed), 60)
        print(f"\n   ✅ Completed in {minutes}m {seconds}s")
        
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        minutes, seconds = divmod(int(elapsed), 60)
        print(f"\n   ⏰ TIMEOUT after {minutes}m {seconds}s")
        return False
    
    # Check if output files were generated to verify success
    expected_output_files = [f"{run['id']}.pdf", f"{run['id']}.out"]
    missing_outputs = []
    generated_outputs = []
    
    for output_file in expected_output_files:
        if os.path.exists(output_file):
            generated_outputs.append(output_file)
        else:
            missing_outputs.append(output_file)
    
    # Determine success based on return code and output files
    if result.returncode == 0 and len(generated_outputs) > 0:
        print(f"   ✅ SUCCESS: Generated {', '.join(generated_outputs)}")
        return True
    else:
        print(f"   ❌ FAILED: Return code {result.returncode}")
        if missing_outputs:
            print(f"   Missing outputs: {', '.join(missing_outputs)}")
        return False

# Run all sequentially to avoid GUI conflicts
if __name__ == '__main__':
    print(f"Processing {len(runs)} model runs...")
    
    successful_runs = []
    failed_runs = []
    
    for i, run in enumerate(runs, 1):
        print(f"\n--- Run {i}/{len(runs)}: {run['id']} ---")
        success = make_and_run(run)
        
        if success:
            successful_runs.append(run['id'])
        else:
            failed_runs.append(run['id'])
    
    print(f"\n{'='*50}")
    print(f"SUMMARY:")
    print(f"✅ Successful: {len(successful_runs)}/{len(runs)}")
    if successful_runs:
        print(f"   {', '.join(successful_runs)}")
    
    if failed_runs:
        print(f"❌ Failed: {len(failed_runs)}/{len(runs)}")
        print(f"   {', '.join(failed_runs)}")
        print(f"\nRecommendations:")
        print(f"- Check that all required input files exist")
        print(f"- Verify template parameters are correct")
        print(f"- Review FlexPDE output above for specific errors")
    else:
        print(f"🎉 All models completed successfully!")
    
    print(f"{'='*50}")