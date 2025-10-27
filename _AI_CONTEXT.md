# AI ASSISTANT PREFERENCES & CONTEXT
**READ THIS FIRST** - Auto-load these preferences before any operations

## CRITICAL WORKFLOW RULES
1. **ALWAYS** use `pixi run python` (never direct python.exe)
2. **REQUIRED**: Configure Python environment before ANY Python operations
3. **MATPLOTLIB**: Use 'Agg' backend for headless plotting (no GUI)
4. **MEMORY**: Aggressive cleanup with `plt.close()` and `gc.collect()` after each plot
5. **PATHS**: Always use absolute paths, never relative paths

## PROJECT CONTEXT
**FusionFiber DTS Analysis**: Distributed Temperature Sensing for groundwater flow experiments
- **9 experiments** (MD1-MD9) with different Darcy flux rates (0.0 to 103.2 m/day)
- **4 fiber cores** (A, B, C, D) with vertical alignment corrections
- **12 depth measurements** from surface to 1.37m depth
- **XML → Pickle caching** for ultra-fast data loading (15ms vs 11s)

## DATA STRUCTURE
```
experiments = {
    'MD1': [103.2, 170], 'MD2': [86.4, 170], 'MD3': [69.6, 170],
    'MD4': [57.6, 170],  'MD5': [36.0, 170], 'MD6': [19.2, 170], 
    'MD7': [4.8, 170],   'MD8': [0.0, 170],  'MD9': [55.2, 230]
}
```

## PLOT ORGANIZATION (50 total plots)
**IMPORTANT**: All plots are saved in the `data/` directory (same directory as the script):
- **data/fluxes/** (18 plots): Sets 1&2 - Flux-based analyses
- **data/depths/** (24 plots): Sets 3&4 - Depth-based comparisons  
- **data/cores/** (8 plots): Sets 5&6 - Core-based analyses

**PLOT LOCATIONS**: Script uses `data_dir = Path(__file__).parent` which means plots are saved to the `data/` folder, NOT the repository root or the config.yaml data_dir location.

## TECHNICAL REQUIREMENTS
- **Environment**: Pixi package manager (critical for matplotlib)
- **Backend**: matplotlib.use('Agg') before ANY plotting
- **Caching**: Individual MD pickle files + combined dataset
- **Memory**: Explicit cleanup between plot generations
- **Format**: PowerPoint-ready plots (16:9, 300 DPI)

## DATA LOCATIONS
- **Local cache**: `data/{md1-md9}_data.pickle` and `data/all_experiment_data.pickle`
- **Original source**: `D:\Projects\MOOI Diameter\{MD1-MD9}/` (from config.yaml)
- **Plot output**: `data/fluxes/`, `data/depths/`, `data/cores/` (script directory)
- **Auto-recovery**: Script can rebuild from XML if pickles missing

## PERFORMANCE TARGETS
- **Data loading**: ~0.015s per experiment (from pickle)
- **Total runtime**: ~30 seconds for all 50 plots
- **Memory efficient**: No crashes, proper cleanup

## DEVELOPMENT PRIORITIES
1. **Reliability**: Never break existing functionality
2. **Performance**: Maintain ultra-fast pickle loading
3. **Organization**: Clean folder structure with logical naming
4. **Recovery**: Self-healing from missing data files
5. **Documentation**: Clear code comments and structure

## COMMON ISSUES & SOLUTIONS
- **matplotlib crashes**: Always use `pixi run python`
- **Memory issues**: Aggressive `plt.close()` + `gc.collect()`
- **Missing data**: Auto-load from original XML sources
- **Path issues**: Use absolute paths consistently
- **Environment issues**: Configure Python environment first
- **PowerShell syntax**: Use `;` not `&&` for command chaining, use PowerShell cmdlets like `Get-ChildItem` instead of `dir` with cmd flags
- **Plot location confusion**: Plots are ALWAYS in `data/fluxes/`, `data/depths/`, `data/cores/` - never in repository root or config data_dir

## PLOT STYLING PREFERENCES

### Color Palettes
- **Flux/Flow comparisons**: Use `plt.cm.plasma` colormap
- **Depth comparisons**: Use `plt.cm.viridis` colormap  
- **Avoid**: Discrete color dictionaries, prefer continuous colormaps from matplotlib

### Plot Labeling
- **Do NOT reference "MD" in plot labels or legends**
- Use descriptive values instead (e.g., "57.6 m/day" instead of "MD4: 57.6 m/day")
- Keep legends clean and focused on the scientific parameters

### Consistent Styling
- High DPI output (600 DPI for saved figures)
- Font sizes: 16pt for axes, 20pt for titles, 14pt for legends
- Right-side vertical legends for multi-line plots
- Alpha transparency: 0.7-0.8 for overlapping lines
- Line width: 1.2px for data lines (thinner than previous 1.5px)
- Grid transparency: alpha=0.5 (less transparent than previous alpha=0.3)

### Color Map Direction for Darcy Flows
- **Dark colors for low flows**: Use `np.linspace(0, 1, n)` with plasma colormap
- Low Darcy flows (0.0 m/day) = dark purple/blue colors
- High Darcy flows (103.2 m/day) = bright yellow/pink colors  
- Legend order: ascending (0.0 to 103.2 m/day) with natural color progression

---
*This file guides AI assistants working on the FusionFiber DTS analysis project*