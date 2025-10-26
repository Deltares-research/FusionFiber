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
- **fluxes/** (18 plots): Sets 1&2 - Flux-based analyses
- **depths/** (24 plots): Sets 3&4 - Depth-based comparisons  
- **cores/** (8 plots): Sets 5&6 - Core-based analyses

## TECHNICAL REQUIREMENTS
- **Environment**: Pixi package manager (critical for matplotlib)
- **Backend**: matplotlib.use('Agg') before ANY plotting
- **Caching**: Individual MD pickle files + combined dataset
- **Memory**: Explicit cleanup between plot generations
- **Format**: PowerPoint-ready plots (16:9, 300 DPI)

## DATA LOCATIONS
- **Local cache**: `data/{md1-md9}_data.pickle`
- **Original source**: `D:\Projects\MOOI Diameter\{MD1-MD9}/`
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

---
*This file guides AI assistants working on the FusionFiber DTS analysis project*