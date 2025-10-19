{ Fill in the following sections (removing comment marks ! if necessary),
  and delete those that are unused.}
TITLE 'md6'     { the problem identification }

COORDINATES cartesian2  { coordinate system, 1D,2D,3D, etc }
VARIABLES      
	Temp(1)
SELECT         { method controls }
	aspect 1
DEFINITIONS
	tday=24*3600
	Runtime=(5000)
    Width=1													{Width of grid	[m]}
	Height=1													{Height of grid	[m]}
    transfer('head_optie1_output\head_Darcy19.2.dat', head)

{---------------------------------------------Properties tank and sediment-------------------------------------------------------------------------------}
{groundwater properties}
	rhow=999																							{Density groundwater} {kg/m3}
	cw=4186																							{Specific head groundwater}{J/kg*K}
	Kf = 0.591      																					{Thermal conductivity of water                 	[W/m/K]}
    kx=1																								{horizontal k value}{m/d}
{Sediment properties}
	T0= 25			 																			{average background temperature at T=0}
    inflowTemp=T0
	n = 0.41																								{porositiy}
	rhos = 2650 																						{Density sediment} {kg/m3}
	cs=830																								{Specific head sediment}{J/kg*K}
	Ks = {2.3}5{7.59}      																			{Thermal conductivity of solid particles   [W/m/K]}

{Combined properties}
	cb=n*rhow*cw+(1-n)*rhos*cs														{Combined specific head}{J/{m**3*K}}
	Kb=	(n*Kf)+((1-n)*Ks) 																	{Combined thermal conductivity}{J/{m*sec*K}}
	qx=(-kx/tday)*dx(head)																	{flux in x direction}
	qy=(-kx/tday)*dy(head)																	{flux in y direction}
	q=vector(qx,qy)																				{combined flux}
	Source=0

{HEAT INPUT to Cables}
	Heatin=170												{Voltage for every timestep, will be calculated to heat input}
	Cableheat = Heatin*2.5
    t_cutoff = 1800										{time till heating turns off}
    t_transition = 2											{short transition time from full heat to zero}

{------------------------------------------------------------------CABLE PROPERTIES-------------------------------------------------------------------------------}
{---------------------------------------------------------------------------------------------Strength cable}
{Strenght cable core}								{Felten}					{literatuur}									{aramid https://material-properties.org/kevlar-density-strength-melting-point-thermal-conductivity/}
	Rad_Strenght_Core=0.0004 				{0.0004}				{nvt}												{outer radius m}
	Kc_Strenght_Core =0.04						{0.04}						{0.04}												{Thermal conductivity W/m/K}
	rhoc_Strenght_Core=1440					{1440}					{1440}											{Density  [kg/m^3]}
	Cc_Strenght_Core= 1420						{1420}					{1420}											{Specific heate	[J/(kg*K)]}
{Strenght cable mantle}
	Rad_Strenght_Mantle=0.0025 			{0.0025}					{}														{outer radius m}
	Kc_Strenght_Mantle =0.29					{0.29}							{}														{Thermal conductivity W/m/K}
	rhoc_Strenght_Mantle=1210				{1210}						{}														{Density  [kg/m^3]}
	Cc_Strenght_Mantle= 1880					{1880}						{}														{Specific heate	[J/(kg*K)]}

{----------------------------------------------------------------------------------------------DTS cable}
{fiber self}													{Felten}						{literatuur}			
	Rad_DTS_glas=0.0000625 					{0.0000625}				{0.00005}									{outer radius m}
	Kc_DTS_glas =0.8									{0.8}							{2}												{Thermal conductivity W/m/K}
	rhoc_DTS_glas=2500							{2500}						{2200}										{Density  [kg/m^3]}
	Cc_DTS_glas= 1430								{1430}						{1430}										{Specific heat	[J/(kg*K)]}
{Acrylate}														{Felten}						{literatuur}			
	Rad_DTS_AcrH=0.000125 					{0.000125}				{0.00005}									{outer radius m}
	Kc_DTS_AcrH =0.2									{0.2}							{2}												{Thermal conductivity W/m/K}
	rhoc_DTS_AcrH=1200							{1200}						{2200}										{Density  [kg/m^3]}
	Cc_DTS_AcrH= 1400								{1360-1430}				{1430}										{Specific heat	[J/(kg*K)]}
{Acrylate soft}												{Felten}						{literatuur}			
	Rad_DTS_AcrS=0.00022 						{0.00022}					{0.00005}									{outer radius m}
	Kc_DTS_AcrS =0.2									{0.2}							{2}												{Thermal conductivity W/m/K}
	rhoc_DTS_AcrS=1200							{1200}						{2200}										{Density  [kg/m^3]}
	Cc_DTS_AcrS= 1400								{1360-1430}				{1430}										{Specific heat	[J/(kg*K)]}
{TPE}																{Felten}						{literatuur}			
	Rad_DTS_TPE=0.00045 						{0.00045}					{0.00005}									{outer radius m}
	Kc_DTS_TPE =0.3									{0.3}							{2}												{Thermal conductivity W/m/K}
	rhoc_DTS_TPE=1100							{900-1400}				{2200}										{Density  [kg/m^3]}
	Cc_DTS_TPE= 2000								{1700-2500}				{1430}										{Specific heat	[J/(kg*K)]}
{Aramid}														{Felten}						{literatuur}			
	Rad_DTS_Aram=0.0006 						{0.0006}					{0.00005}									{outer radius m}
	Kc_DTS_Aram =0.04								{0.04}							{2}												{Thermal conductivity W/m/K}
	rhoc_DTS_Aram=1440							{1440}						{2200}										{Density  [kg/m^3]}
	Cc_DTS_Aram= 1420							{1420}						{1430}										{Specific heat	[J/(kg*K)]}
{TPE-O Fibermantle}									{Felten}						{Literatuur}								{ thermoplastic polyester elastomer - http://www.hirosugi.jp/technical/material/TPEE.html, https://krusetraining.com/wp-content/uploads/2017/12/List-Of-Materials-Specific-Heat-Capacity-Ranges.pdf}	
	Rad_DTS_TPEO=0.0009 						{0.0009}					{0.0004}									{outer radius m}
	Kc_DTS_TPEO =1									{0.5-1.4}					{0.196}										{Thermal conductivity W/m/K}
	rhoc_DTS_TPEO=1100							{900-1400}				{1121}										{Density [kg/m^3]}
	Cc_DTS_TPEO= 2000							{1700-2500}				{1700-2500}								{Specific heat 	[J/(kg*K)]}

{-------------------------------------------------------------------------------------------Heating cable}
{Heating wire}												{Felten}						{literatuur}								{copper:  }
	Rad_heat_core=0.000211 					{0.000211}							{}													{Radius of heating part, 0.14 mm2 = 0.2111 mm						[m]}	
	Kc_heat_core= 45	 		 						{45}							{401}											{Thermal conductivity of metal wire heating cable 				 	[W/m/K]}
	rhoc_heat_core= 890							{890}							{8920}										{Density of metal wire inside heating cable								[kg/m^3]}
	Cc_heat_core= 380								{380}							{380}											{Specific heat metal wire inside heating cable							[J/(kg*K)]}
	R_heat_core= 1.47									{1.47}							{}													{resistance of metal heating wire [ohm/m]}
	L_heat_core= 64									{20}							{}													{Length of heating cable [m}
{Cable protection}
!HK	{Rad_heat_mantle=0.0008711}				{0.66 mm}					{nvt}											{Outer radius of heating cable core + wall tickness (0.66 mm) = 0.8711 mm					[m]}
    Rad_heat_mantle=0.000858				{0.66 mm}					{nvt}											{Outer radius of heating cable core + wall tickness (0.66 mm) = 0.8711 mm					[m]}
	Kc_heat_mantle=0.2 		 					{0.2}							{0.2}											{Thermal conductivity of cable protection material (silicone, 0.2)   	[W/m/K]}
	rhoc_heat_mantle=950						{950}							{1200}										{Density of cable protection material (PVC zacht, 1200)											[kg/m^3]}
	Cc_heat_mantle=1300							{1300 estimate}		{1000}										{Specific heat cable protection material										[J/(kg*K)]}

{-------------------------------------------------------------------------------------------Retour cable}
{Core}															{Felten}						{literatuur}								{copper: https://material-properties.org/copper-and-tin-comparison-properties/ }
	Rad_retour_core=0.000398942			{0.000398942}			{}													{Radius of core, 0.5 mm2 = 	0.398942 mm											[m]}
	Kc_retour_core= 410	 						{410}							{401}											{Thermal conductivity of metal wire heating cable 				 	[W/m/K]}
	rhoc_retour_core= 8920						{8920}							{8920}										{Density of metal wire inside heating cable								[kg/m^3]}
	Cc_retour_core= 380							{380}							{380}											{Specific heat metal wire inside heating cable							[J/(kg*K)]}
{Cable protection}
	Rad_retour_mantle=0.000838942		{0.000838942}			{nvt}											{Outer radius = core + wall tickness (0.44 mm) = 0.838942 mm [m]}
	Kc_retour_mantle=0.2 		 					{0.2}							{0.2}											{Thermal conductivity of cable protection material (silicone, 0.2)   	[W/m/K]}
	rhoc_retour_mantle=950						{950}							{1200}										{Density of cable protection material (PVC zacht, 1200)											[kg/m^3]}
	Cc_retour_mantle=1300						{1300 estimate}		{1000}										{Specific heat cable protection material										[J/(kg*K)]}

{------------------------------------------------------------------------------------------Open centre}
{Air}																{}										{literatuur}								
    !HK Rad_air=0.0009+0.0025+0.0009	+0.00005										{}										{}													{Radius 	[m]}
    Rad_air=Rad_Strenght_Mantle+2*Rad_DTS_TPEO	+0.00005									{}						{With extra to help meshing???}													{Radius 	[m]}
	Kc_air= 0.138											{0.1}								{}													{Thermal conductivity [W/m/K]}
	rhoc_air= 1.205										{1.205}							{}													{Density [kg/m^3]}
	Cc_air= 2300											{1.005}							{}													{Specific heat 	[J/(kg*K)]}

{------------------------------------------------------------------------------------------Outer mantle}
{Mantle}														{Felten}						{literatuur}								
	Rad_mantle=Rad_air+0.0005									{thickenss 0.0013}					{}													{Radius 	[m]}
	Kc_mantle= 0.35	 									{0.35}							{}													{Thermal conductivity [W/m/K]}
	rhoc_mantle= 920									{920}							{}													{Density [kg/m^3]}
	Cc_mantle= 2300									{2300}							{}													{Specific heat 	[J/(kg*K)]}

{--------------------------------------------------------------------------------------HEATING INPUT CALCULATION-----------------------------------------------------------------}

{Calculation of  heating by the core of the heating cable}
	A_heating=pi*Rad_heat_core^2 																			{Cross-sectional area of heating part      										[m^2]}
	!HK {Q_heating=((Cableheat^2)/(R_heat_core*L_heat_core))/L_heat_core}								{Calculated heat input for the cable}
	!Q_heating=(1-exp(-t/10))*((Cableheat^2)/(R_heat_core*L_heat_core))/L_heat_core								{Calculated heat input for the cable}
    
    Q_heating = (1 - exp(-t / t_transition)) *
    					(Cableheat^2 / (R_heat_core * L_heat_core^2)) *
    					(1 / (1 + exp(min((t - t_cutoff) / t_transition, 690))))

{----------------------------------------Cable orientation 1 / location A3}
{Centre location}
	Locx_A3=0
	Locy_A3=0
{Strenght cable}
	Locx_A3_SC = Locx_A3
	Locy_A3_SC = Locy_A3
{DTS cables}
	Locx_A3_DTS1 = Locx_A3+Rad_Strenght_Mantle+Rad_DTS_TPEO		{DTS right side}
	Locy_A3_DTS1 = Locy_A3
	Locx_A3_DTS2 = Locx_A3+((Rad_Strenght_Mantle+Rad_DTS_TPEO)*cos(90*(pi/180)))		{DTS Top side}
	Locy_A3_DTS2 = Locy_A3+((Rad_Strenght_Mantle+Rad_DTS_TPEO)*sin(90*(pi/180)))	
	Locx_A3_DTS3 = Locx_A3+((Rad_Strenght_Mantle+Rad_DTS_TPEO)*cos(180*(pi/180)))		{DTS Left side}
	Locy_A3_DTS3 = Locy_A3+((Rad_Strenght_Mantle+Rad_DTS_TPEO)*sin(180*(pi/180)))	
	Locx_A3_DTS4 = Locx_A3+((Rad_Strenght_Mantle+Rad_DTS_TPEO)*cos(270*(pi/180)))		{DTS bottom side}
	Locy_A3_DTS4 = Locy_A3+((Rad_Strenght_Mantle+Rad_DTS_TPEO)*sin(270*(pi/180)))	
{Heat cables}
	Locx_A3_heat1=Locx_A3+((Rad_Strenght_Mantle+Rad_DTS_TPEO)*cos(330*(pi/180))) {right low}
	Locy_A3_heat1=Locy_A3+((Rad_Strenght_Mantle+Rad_DTS_TPEO)*sin(330*(pi/180)))
	Locx_A3_heat2=Locx_A3+((Rad_Strenght_Mantle+Rad_DTS_TPEO)*cos(60*(pi/180))) {top right}
	Locy_A3_heat2=Locy_A3+((Rad_Strenght_Mantle+Rad_DTS_TPEO)*sin(60*(pi/180)))
	Locx_A3_heat3=Locx_A3+((Rad_Strenght_Mantle+Rad_DTS_TPEO)*cos(150*(pi/180))) {left above}
	Locy_A3_heat3=Locy_A3+((Rad_Strenght_Mantle+Rad_DTS_TPEO)*sin(150*(pi/180)))
	Locx_A3_heat4=Locx_A3+((Rad_Strenght_Mantle+Rad_DTS_TPEO)*cos(240*(pi/180))) {bottom left}
	Locy_A3_heat4=Locy_A3+((Rad_Strenght_Mantle+Rad_DTS_TPEO)*sin(240*(pi/180)))
{Retour cables}
	Locx_A3_retour1=Locx_A3+((Rad_Strenght_Mantle+Rad_DTS_TPEO)*cos(30*(pi/180))) {right high}
	Locy_A3_retour1=Locy_A3+((Rad_Strenght_Mantle+Rad_DTS_TPEO)*sin(30*(pi/180)))
	Locx_A3_retour2=Locx_A3+((Rad_Strenght_Mantle+Rad_DTS_TPEO)*cos(120*(pi/180))) {top left}
	Locy_A3_retour2=Locy_A3+((Rad_Strenght_Mantle+Rad_DTS_TPEO)*sin(120*(pi/180)))
	Locx_A3_retour3=Locx_A3+((Rad_Strenght_Mantle+Rad_DTS_TPEO)*cos(210*(pi/180))) {left down}
	Locy_A3_retour3=Locy_A3+((Rad_Strenght_Mantle+Rad_DTS_TPEO)*sin(210*(pi/180)))
	Locx_A3_retour4=Locx_A3+((Rad_Strenght_Mantle+Rad_DTS_TPEO)*cos(300*(pi/180))) {bottom right}
	Locy_A3_retour4=Locy_A3+((Rad_Strenght_Mantle+Rad_DTS_TPEO)*sin(300*(pi/180)))

INITIAL VALUES
	Temp=T0

EQUATIONS        { PDE's, one for each variable }
	Temp:             dt(cb*Temp)=-div(-Kb*grad(Temp))-div(rhow*cw*Temp*q)+Source 


BOUNDARIES
{-----------------------------------------------------------------------------------------------------Defining zones and boundaries-----------------------------------------------------------------------------------------------}
{------------------------------------------Tank/Flow simulator}       
  REGION 1 "Tank"    
       	START(-Width/2, -Height/2 )   
		{Lower border}
		natural(temp)=T0										
    	LINE TO (Width/2, -Height/2) 
		
		{Right border}
		natural(temp)=rhow*cw*qx*Temp
		LINE TO (Width/2,Height/2) 
		
		{Upper border}
		natural(temp)=T0
		LINE TO (-Width/2,Height/2) 

		{Left border}
		value(temp)=inflowTemp
		LINE TO CLOSE

{----------------------------------Cable orientation 1 / location A3}
{outer mantle}
	REGION 2 "Outer Mantle"
		Kb = Kc_mantle, rhos=rhoc_mantle, Cs=Cc_mantle, Kx=0.000000001, n=0 	
		START(Locx_A3-Rad_mantle, Locy_A3)
		ARC(CENTER=Locx_A3,Locy_A3) ANGLE=360
		LINE TO CLOSE

{open air} 
	REGION 3 "air in mantlee"
		Kb = Kc_air, rhos=rhoc_air, Cs=Cc_air, Kx=0.000000001, n=0 	
		START(Locx_A3-Rad_air, Locy_A3)
		ARC(CENTER=Locx_A3,Locy_A3) ANGLE=360
		LINE TO CLOSE

{Core}
	REGION 4 "Strenght cable mantle"
		Kb = Kc_Strenght_Mantle, rhos=rhoc_Strenght_Mantle, Cs=Cc_Strenght_Mantle, Kx=0.000000001, n=0 
		START(Locx_A3-Rad_Strenght_Mantle, Locy_A3)
		ARC(CENTER=Locx_A3,Locy_A3) ANGLE=360
		LINE TO CLOSE

	REGION 5 "Strenght cable core"
		Kb = Kc_Strenght_Core, rhos=rhoc_Strenght_Core, Cs=Cc_Strenght_Core, Kx=0.000000001, n=0 
		START(Locx_A3-Rad_Strenght_Core, Locy_A3)
		ARC(CENTER=Locx_A3,Locy_A3) ANGLE=360
		LINE TO CLOSE

{DTS right}
	REGION 6 "DTS1 TPE-O mantle"
		Kb = Kc_DTS_TPEO, rhos=rhoc_DTS_TPEO, Cs=Cc_DTS_TPEO, Kx=0.000000001, n=0 	
		START(Locx_A3_DTS1-Rad_DTS_TPEO, Locy_A3_DTS1)
		ARC(CENTER=Locx_A3_DTS1,Locy_A3_DTS1) ANGLE=360
		LINE TO CLOSE

	REGION 7 "DTS1 Aramid"
		Kb = Kc_DTS_Aram, rhos=rhoc_DTS_Aram, Cs=Cc_DTS_Aram, Kx=0.000000001, n=0 	
		START(Locx_A3_DTS1-Rad_DTS_Aram, Locy_A3_DTS1)
		ARC(CENTER=Locx_A3_DTS1,Locy_A3_DTS1) ANGLE=360
		LINE TO CLOSE

	REGION 8 "DTS1 TPE"
		Kb = Kc_DTS_TPE, rhos=rhoc_DTS_TPE, Cs=Cc_DTS_TPE, Kx=0.000000001, n=0 	
		START(Locx_A3_DTS1-Rad_DTS_TPE, Locy_A3_DTS1)
		ARC(CENTER=Locx_A3_DTS1,Locy_A3_DTS1) ANGLE=360
		LINE TO CLOSE

	REGION 9 "DTS1 Acrylate soft"
		Kb = Kc_DTS_AcrS, rhos=rhoc_DTS_AcrS, Cs=Cc_DTS_AcrS, Kx=0.000000001, n=0 	
		START(Locx_A3_DTS1-Rad_DTS_AcrS, Locy_A3_DTS1)
		ARC(CENTER=Locx_A3_DTS1,Locy_A3_DTS1) ANGLE=360
		LINE TO CLOSE

	REGION 10 "DTS1 Acrylate hard"
		Kb = Kc_DTS_AcrH, rhos=rhoc_DTS_AcrH, Cs=Cc_DTS_AcrH, Kx=0.000000001, n=0 	
		START(Locx_A3_DTS1-Rad_DTS_AcrH, Locy_A3_DTS1)
		ARC(CENTER=Locx_A3_DTS1,Locy_A3_DTS1) ANGLE=360
		LINE TO CLOSE

	REGION 11 "DTS1 Glas"
		Kb = Kc_DTS_glas, rhos=rhoc_DTS_glas, Cs=Cc_DTS_glas, Kx=0.000000001, n=0 	
		START(Locx_A3_DTS1-Rad_DTS_glas, Locy_A3_DTS1)
		ARC(CENTER=Locx_A3_DTS1,Locy_A3_DTS1) ANGLE=360
		LINE TO CLOSE
        
{DTS Top}
	REGION 12 "DTS2 TPE-O mantle"
		Kb = Kc_DTS_TPEO, rhos=rhoc_DTS_TPEO, Cs=Cc_DTS_TPEO, Kx=0.000000001, n=0 	
		START(Locx_A3_DTS2-Rad_DTS_TPEO, Locy_A3_DTS2)
		ARC(CENTER=Locx_A3_DTS2,Locy_A3_DTS2) ANGLE=360
		LINE TO CLOSE

	REGION 13 "DTS2 Aramid"
		Kb = Kc_DTS_Aram, rhos=rhoc_DTS_Aram, Cs=Cc_DTS_Aram, Kx=0.000000001, n=0 	
		START(Locx_A3_DTS2-Rad_DTS_Aram, Locy_A3_DTS2)
		ARC(CENTER=Locx_A3_DTS2,Locy_A3_DTS2) ANGLE=360
		LINE TO CLOSE

	REGION 14 "DTS2 TPE"
		Kb = Kc_DTS_TPE, rhos=rhoc_DTS_TPE, Cs=Cc_DTS_TPE, Kx=0.000000001, n=0 	
		START(Locx_A3_DTS2-Rad_DTS_TPE, Locy_A3_DTS2)
		ARC(CENTER=Locx_A3_DTS2,Locy_A3_DTS2) ANGLE=360
		LINE TO CLOSE

	REGION 15 "DTS2 Acrylate soft"
		Kb = Kc_DTS_AcrS, rhos=rhoc_DTS_AcrS, Cs=Cc_DTS_AcrS, Kx=0.000000001, n=0 	
		START(Locx_A3_DTS2-Rad_DTS_AcrS, Locy_A3_DTS2)
		ARC(CENTER=Locx_A3_DTS2,Locy_A3_DTS2) ANGLE=360
		LINE TO CLOSE

	REGION 16 "DTS2 Acrylate hard"
		Kb = Kc_DTS_AcrH, rhos=rhoc_DTS_AcrH, Cs=Cc_DTS_AcrH, Kx=0.000000001, n=0 	
		START(Locx_A3_DTS2-Rad_DTS_AcrH, Locy_A3_DTS2)
		ARC(CENTER=Locx_A3_DTS2,Locy_A3_DTS2) ANGLE=360
		LINE TO CLOSE

	REGION 17 "DTS2 Glas"
		Kb = Kc_DTS_glas, rhos=rhoc_DTS_glas, Cs=Cc_DTS_glas, Kx=0.000000001, n=0 	
		START(Locx_A3_DTS2-Rad_DTS_glas, Locy_A3_DTS2)
		ARC(CENTER=Locx_A3_DTS2,Locy_A3_DTS2) ANGLE=360
		LINE TO CLOSE

{DTS Left}
	REGION 18 "DTS3 TPE-O mantle"
		Kb = Kc_DTS_TPEO, rhos=rhoc_DTS_TPEO, Cs=Cc_DTS_TPEO, Kx=0.000000001, n=0 	
		START(Locx_A3_DTS3-Rad_DTS_TPEO, Locy_A3_DTS3)
		ARC(CENTER=Locx_A3_DTS3,Locy_A3_DTS3) ANGLE=360
		LINE TO CLOSE

	REGION 19 "DTS3 Aramid"
		Kb = Kc_DTS_Aram, rhos=rhoc_DTS_Aram, Cs=Cc_DTS_Aram, Kx=0.000000001, n=0 	
		START(Locx_A3_DTS3-Rad_DTS_Aram, Locy_A3_DTS3)
		ARC(CENTER=Locx_A3_DTS3,Locy_A3_DTS3) ANGLE=360
		LINE TO CLOSE

	REGION 20 "DTS3 TPE"
		Kb = Kc_DTS_TPE, rhos=rhoc_DTS_TPE, Cs=Cc_DTS_TPE, Kx=0.000000001, n=0 	
		START(Locx_A3_DTS3-Rad_DTS_TPE, Locy_A3_DTS3)
		ARC(CENTER=Locx_A3_DTS3,Locy_A3_DTS3) ANGLE=360
		LINE TO CLOSE

	REGION 21 "DTS3 Acrylate soft"
		Kb = Kc_DTS_AcrS, rhos=rhoc_DTS_AcrS, Cs=Cc_DTS_AcrS, Kx=0.000000001, n=0 	
		START(Locx_A3_DTS3-Rad_DTS_AcrS, Locy_A3_DTS3)
		ARC(CENTER=Locx_A3_DTS3,Locy_A3_DTS3) ANGLE=360
		LINE TO CLOSE

	REGION 22 "DTS3 Acrylate hard"
		Kb = Kc_DTS_AcrH, rhos=rhoc_DTS_AcrH, Cs=Cc_DTS_AcrH, Kx=0.000000001, n=0 	
		START(Locx_A3_DTS3-Rad_DTS_AcrH, Locy_A3_DTS3)
		ARC(CENTER=Locx_A3_DTS3,Locy_A3_DTS3) ANGLE=360
		LINE TO CLOSE

	REGION 23 "DTS3 Glas"
		Kb = Kc_DTS_glas, rhos=rhoc_DTS_glas, Cs=Cc_DTS_glas, Kx=0.000000001, n=0 	
		START(Locx_A3_DTS3-Rad_DTS_glas, Locy_A3_DTS3)
		ARC(CENTER=Locx_A3_DTS3,Locy_A3_DTS3) ANGLE=360
		LINE TO CLOSE

{DTS below}
	REGION 24 "DTS4 TPE-O mantle"
		Kb = Kc_DTS_TPEO, rhos=rhoc_DTS_TPEO, Cs=Cc_DTS_TPEO, Kx=0.000000001, n=0 	
		START(Locx_A3_DTS4-Rad_DTS_TPEO, Locy_A3_DTS4)
		ARC(CENTER=Locx_A3_DTS4,Locy_A3_DTS4) ANGLE=360
		LINE TO CLOSE

	REGION 25 "DTS4 Aramid"
		Kb = Kc_DTS_Aram, rhos=rhoc_DTS_Aram, Cs=Cc_DTS_Aram, Kx=0.000000001, n=0 	
		START(Locx_A3_DTS4-Rad_DTS_Aram, Locy_A3_DTS4)
		ARC(CENTER=Locx_A3_DTS4,Locy_A3_DTS4) ANGLE=360
		LINE TO CLOSE

	REGION 26 "DTS4 TPE"
		Kb = Kc_DTS_TPE, rhos=rhoc_DTS_TPE, Cs=Cc_DTS_TPE, Kx=0.000000001, n=0 	
		START(Locx_A3_DTS4-Rad_DTS_TPE, Locy_A3_DTS4)
		ARC(CENTER=Locx_A3_DTS4,Locy_A3_DTS4) ANGLE=360
		LINE TO CLOSE

	REGION 27 "DTS4 Acrylate soft"
		Kb = Kc_DTS_AcrS, rhos=rhoc_DTS_AcrS, Cs=Cc_DTS_AcrS, Kx=0.000000001, n=0 	
		START(Locx_A3_DTS4-Rad_DTS_AcrS, Locy_A3_DTS4)
		ARC(CENTER=Locx_A3_DTS4,Locy_A3_DTS4) ANGLE=360
		LINE TO CLOSE

	REGION 28 "DTS4 Acrylate hard"
		Kb = Kc_DTS_AcrH, rhos=rhoc_DTS_AcrH, Cs=Cc_DTS_AcrH, Kx=0.000000001, n=0 	
		START(Locx_A3_DTS4-Rad_DTS_AcrH, Locy_A3_DTS4)
		ARC(CENTER=Locx_A3_DTS4,Locy_A3_DTS4) ANGLE=360
		LINE TO CLOSE

	REGION 29 "DTS4 Glas"
		Kb = Kc_DTS_glas, rhos=rhoc_DTS_glas, Cs=Cc_DTS_glas, Kx=0.000000001, n=0 	
		START(Locx_A3_DTS4-Rad_DTS_glas, Locy_A3_DTS4)
		ARC(CENTER=Locx_A3_DTS4,Locy_A3_DTS4) ANGLE=360
		LINE TO CLOSE

{Heating right low}
	REGION 30 "Heat1 mantle"
		Kb = Kc_heat_mantle, rhos=rhoc_heat_mantle, Cs=Cc_heat_mantle, Kx=0.000000001, n=0 
		START(Locx_A3_heat1-Rad_heat_mantle, Locy_A3_heat1)
		ARC(CENTER=Locx_A3_heat1,Locy_A3_heat1) ANGLE=360
		LINE TO CLOSE

	REGION 31 "Heat1 core"
		source=(Q_heating)/A_heating,Kb = Kc_heat_core, rhos=rhoc_heat_core, Cs=Cc_heat_core, Kx=0.000000001, n=0 
		START(Locx_A3_heat1-Rad_heat_core, Locy_A3_heat1)
		ARC(CENTER=Locx_A3_heat1,Locy_A3_heat1) ANGLE=360
		LINE TO CLOSE

{Heating top right}
	REGION 32 "Heat2 mantle"
		Kb = Kc_heat_mantle, rhos=rhoc_heat_mantle, Cs=Cc_heat_mantle, Kx=0.000000001, n=0 
		START(Locx_A3_heat2-Rad_heat_mantle, Locy_A3_heat2)
		ARC(CENTER=Locx_A3_heat2,Locy_A3_heat2) ANGLE=360
		LINE TO CLOSE

	REGION 33 "Heat2 core"
		source=(Q_heating)/A_heating,Kb = Kc_heat_core, rhos=rhoc_heat_core, Cs=Cc_heat_core, Kx=0.000000001, n=0 
		START(Locx_A3_heat2-Rad_heat_core, Locy_A3_heat2)
		ARC(CENTER=Locx_A3_heat2,Locy_A3_heat2) ANGLE=360
		LINE TO CLOSE

{Heating left above}
	REGION 34 "Heat3 mantle"
		Kb = Kc_heat_mantle, rhos=rhoc_heat_mantle, Cs=Cc_heat_mantle, Kx=0.000000001, n=0 
		START(Locx_A3_heat3-Rad_heat_mantle, Locy_A3_heat3)
		ARC(CENTER=Locx_A3_heat3,Locy_A3_heat3) ANGLE=360
		LINE TO CLOSE

	REGION 35 "Heat3 core"
		source=(Q_heating)/A_heating,Kb = Kc_heat_core, rhos=rhoc_heat_core, Cs=Cc_heat_core, Kx=0.000000001, n=0 
		START(Locx_A3_heat3-Rad_heat_core, Locy_A3_heat3)
		ARC(CENTER=Locx_A3_heat3,Locy_A3_heat3) ANGLE=360
		LINE TO CLOSE

{Heating bottom left}
	REGION 36 "Heat4 mantle"
		Kb = Kc_heat_mantle, rhos=rhoc_heat_mantle, Cs=Cc_heat_mantle, Kx=0.000000001, n=0 
		START(Locx_A3_heat4-Rad_heat_mantle, Locy_A3_heat4)
		ARC(CENTER=Locx_A3_heat4,Locy_A3_heat4) ANGLE=360
		LINE TO CLOSE

	REGION 37 "Heat4 core"
		source=(Q_heating)/A_heating, Kb = Kc_heat_core, rhos=rhoc_heat_core, Cs=Cc_heat_core, Kx=0.000000001, n=0 
		START(Locx_A3_heat4-Rad_heat_core, Locy_A3_heat4)
		ARC(CENTER=Locx_A3_heat4,Locy_A3_heat4) ANGLE=360
		LINE TO CLOSE

{Retour right high}
	REGION 38 "Retour1 mantle"
		Kb = Kc_retour_mantle, rhos=rhoc_retour_mantle, Cs=Cc_retour_mantle, Kx=0.000000001, n=0 
		START(Locx_A3_retour1-Rad_retour_mantle, Locy_A3_retour1)
		ARC(CENTER=Locx_A3_retour1,Locy_A3_retour1) ANGLE=360
		LINE TO CLOSE

	REGION 39 "Retour1 core"
		Kb = Kc_retour_core, rhos=rhoc_retour_core, Cs=Cc_retour_core, Kx=0.000000001, n=0 
		START(Locx_A3_retour1-Rad_retour_core, Locy_A3_retour1)
		ARC(CENTER=Locx_A3_retour1,Locy_A3_retour1) ANGLE=360
		LINE TO CLOSE

{Retour high left}
	REGION 40 "Retour2 mantle"
		Kb = Kc_retour_mantle, rhos=rhoc_retour_mantle, Cs=Cc_retour_mantle, Kx=0.000000001, n=0 
		START(Locx_A3_retour2-Rad_retour_mantle, Locy_A3_retour2)
		ARC(CENTER=Locx_A3_retour2,Locy_A3_retour2) ANGLE=360
		LINE TO CLOSE

	REGION 41 "Retour2 core"
		Kb = Kc_retour_core, rhos=rhoc_retour_core, Cs=Cc_retour_core, Kx=0.000000001, n=0 
		START(Locx_A3_retour2-Rad_retour_core, Locy_A3_retour2)
		ARC(CENTER=Locx_A3_retour2,Locy_A3_retour2) ANGLE=360
		LINE TO CLOSE

{Retour left low}
	REGION 42 "Retour3 mantle"
		Kb = Kc_retour_mantle, rhos=rhoc_retour_mantle, Cs=Cc_retour_mantle, Kx=0.000000001, n=0 
		START(Locx_A3_retour3-Rad_retour_mantle, Locy_A3_retour3)
		ARC(CENTER=Locx_A3_retour3,Locy_A3_retour3) ANGLE=360
		LINE TO CLOSE

	REGION 43 "Retour3 core"
		Kb = Kc_retour_core, rhos=rhoc_retour_core, Cs=Cc_retour_core, Kx=0.000000001, n=0 
		START(Locx_A3_retour3-Rad_retour_core, Locy_A3_retour3)
		ARC(CENTER=Locx_A3_retour3,Locy_A3_retour3) ANGLE=360
		LINE TO CLOSE

{Retour low right}
	REGION 44 "Retour4 mantle"
		Kb = Kc_retour_mantle, rhos=rhoc_retour_mantle, Cs=Cc_retour_mantle, Kx=0.000000001, n=0 
		START(Locx_A3_retour4-Rad_retour_mantle, Locy_A3_retour4)
		ARC(CENTER=Locx_A3_retour4,Locy_A3_retour4) ANGLE=360
		LINE TO CLOSE

	REGION 45 "Retour4 core"
		Kb = Kc_retour_core, rhos=rhoc_retour_core, Cs=Cc_retour_core, Kx=0.000000001, n=0 
		START(Locx_A3_retour4-Rad_retour_core, Locy_A3_retour4)
		ARC(CENTER=Locx_A3_retour4,Locy_A3_retour4) ANGLE=360
		LINE TO CLOSE

TIME
	0 to (Runtime)

MONITORS 
	for t=0 by 10 to 100 by 100 to 1000 by 1000 to Runtime
PLOTS 
	for t=0 by 10 to 100 by 100 to 1000 by 1000 to Runtime
	contour(temp) painted nominmax as 'Temperature in complete tank'
	vector(q*tday) as 'velocity in complete tank'
{A3}
	contour(temp)  fixed range(24, 80)  zoom (Locx_A3-0.01,Locy_A3-0.01,0.02,0.02)  painted nominmax as 'detailed temperature around  location A3' 
	history(temp) at (Locx_A3_DTS1,Locy_A3_DTS1) (Locx_A3_DTS2,Locy_A3_DTS2) (Locx_A3_DTS3,Locy_A3_DTS3) (Locx_A3_DTS4,Locy_A3_DTS4)  fixed range (24,60) as 'DTS' export format"#1#b#2#b#3#b#4#b#t" file='Optie1_05_A3_DTS_v5.txt'
	!history(temp) at (Locx_A3_DTS2,Locy_A3_DTS2) as 'DTS2 temp A3' export format"#1#b#t" file='A3_DTS2.txt'	
	!history(temp) at (Locx_A3_DTS3,Locy_A3_DTS3) as 'DTS3 temp A3' export format"#1#b#t" file='A3_DTS3.txt'	
	!history(temp) at (Locx_A3_DTS4,Locy_A3_DTS4) as 'DTS4 temp A3' export format"#1#b#t" file='A3_DTS4.txt'	
	history(temp) at (Locx_A3_DTS1,Locy_A3_DTS1+(Rad_mantle+0.0001)) as 'temperature outside of A3 cable' {export format "#1#b#t" file='Optie1_05_A3_DTS_out_v5.txt' }


{control several locations}
!	history(A6MPT,temp) at (-0.8,0.236) as 'Control A6M PT100' export format"#1#b#2#b#t" file='20180730_A6MPT_ControlPT100.txt'	
!	history(B25MPT,temp) at (-0.519,-0.124) as 'Control B25M PT100' export format"#1#b#2#b#t" file='20180730_B25MPT_ControlPT100.txt'	
!	history(C15MPT,temp) at (-0.212,-0.236) as 'Control C15M PT100' export format"#1#b#2#b#t" file='20180730_C15MPT_ControlPT100.txt'	
!	history(D25MPT,temp) at (0.078,0.012) as 'Control D25M PT100' export format"#1#b#2#b#t" file='20180730_D25MPT_ControlPT100.txt'	
!	history(E35MPT,temp) at (0.237,0.218) as 'Control E35M PT100' export format"#1#b#2#b#t" file='20180730_E35MPT_ControlPT100.txt'	

END
