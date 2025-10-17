{ Fill in the following sections (removing comment marks ! if necessary),
  and delete those that are unused.}
TITLE 'CableDesign_optie1_05_Vel2'     { the problem identification }

COORDINATES cartesian2  { coordinate system, 1D,2D,3D, etc }
VARIABLES      
  	head (1)
SELECT         { method controls }
	{regrid on}
	aspect 1
	{NGRID=10}
DEFINITIONS
	tday=24*3600
    Width=1													{Width of grid	[m]}
	Height=1													{Height of grid	[m]}
    Darcy=55.2										{m/day}
{---------------------------------------------Properties tank and sediment-------------------------------------------------------------------------------}
{groundwater properties}
	rhow=999																							{Density groundwater} {kg/m3}
	cw=4186																							{Specific head groundwater}{J/kg*K}
	Kf = 0.591      																					{Thermal conductivity of water                 	[W/m/K]}
	Hleft=0																								{Hydraulic heat on the left side of the tank}
    kx=1																								{horizontal k value}{m/d}
	Hright=Darcy*Width/kx																						{Defines Darcy velocity with kxand Width}
{Sediment properties}

{Combined properties}
	qx=(-kx/tday)*dx(head)																	{flux in x direction}
	qy=(-kx/tday)*dy(head)																	{flux in y direction}
	q=vector(qx,qy)																				{combined flux}

{------------------------------------------------------------------CABLE PROPERTIES-------------------------------------------------------------------------------}
{---------------------------------------------------------------------------------------------Strength cable}
{Strenght cable core}								{Felten}					{literatuur}									{aramid https://material-properties.org/kevlar-density-strength-melting-point-thermal-conductivity/}
	Rad_Strenght_Core=0.0004 				{0.0004}				{nvt}												{outer radius m}
{Strenght cable mantle}
	Rad_Strenght_Mantle=0.0025 			{0.0025}					{}														{outer radius m}

{----------------------------------------------------------------------------------------------DTS cable}
{fiber self}													{Felten}						{literatuur}			
	Rad_DTS_glas=0.0000625 					{0.0000625}				{0.00005}									{outer radius m}
{Acrylate}														{Felten}						{literatuur}			
	Rad_DTS_AcrH=0.000125 					{0.000125}				{0.00005}									{outer radius m}
{Acrylate soft}												{Felten}						{literatuur}			
	Rad_DTS_AcrS=0.00022 						{0.00022}					{0.00005}									{outer radius m}
{TPE}																{Felten}						{literatuur}			
	Rad_DTS_TPE=0.00045 						{0.00045}					{0.00005}									{outer radius m}
{Aramid}														{Felten}						{literatuur}			
	Rad_DTS_Aram=0.0006 						{0.0006}					{0.00005}									{outer radius m}
{TPE-O Fibermantle}									{Felten}						{Literatuur}								{ thermoplastic polyester elastomer - http://www.hirosugi.jp/technical/material/TPEE.html, https://krusetraining.com/wp-content/uploads/2017/12/List-Of-Materials-Specific-Heat-Capacity-Ranges.pdf}	
	Rad_DTS_TPEO=0.0009 						{0.0009}					{0.0004}									{outer radius m}

{-------------------------------------------------------------------------------------------Heating cable}
{Heating wire}												{Felten}						{literatuur}								{copper:  }
	Rad_heat_core=0.000211 					{0.000211}							{}													{Radius of heating part, 0.14 mm2 = 0.2111 mm						[m]}	

{Cable protection}
!HK	{Rad_heat_mantle=0.0008711}				{0.66 mm}					{nvt}											{Outer radius of heating cable core + wall tickness (0.66 mm) = 0.8711 mm					[m]}
    Rad_heat_mantle=0.000858				{0.66 mm}					{nvt}											{Outer radius of heating cable core + wall tickness (0.66 mm) = 0.8711 mm					[m]}

{-------------------------------------------------------------------------------------------Retour cable}
{Core}															{Felten}						{literatuur}								{copper: https://material-properties.org/copper-and-tin-comparison-properties/ }
	Rad_retour_core=0.000398942			{0.000398942}			{}													{Radius of core, 0.5 mm2 = 	0.398942 mm											[m]}
{Cable protection}
	Rad_retour_mantle=0.000838942		{0.000838942}			{nvt}											{Outer radius = core + wall tickness (0.44 mm) = 0.838942 mm [m]}

{------------------------------------------------------------------------------------------Open centre}
{Air}																{}										{literatuur}								
    !HK Rad_air=0.0009+0.0025+0.0009	+0.00005										{}										{}													{Radius 	[m]}
    Rad_air=Rad_Strenght_Mantle+2*Rad_DTS_TPEO	+0.00005									{}						{With extra to help meshing???}													{Radius 	[m]}

{------------------------------------------------------------------------------------------Outer mantle}
{Mantle}														{Felten}						{literatuur}								
	Rad_mantle=Rad_air+0.0005									{thickenss 0.0013}					{}													{Radius 	[m]}

{--------------------------------------------------------------------------------------HEATING INPUT CALCULATION-----------------------------------------------------------------}

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


EQUATIONS        { PDE's, one for each variable }
  	head:  dx(kx*dx(head))+dy(kx*dy(head))=0

BOUNDARIES
{-----------------------------------------------------------------------------------------------------Defining zones and boundaries-----------------------------------------------------------------------------------------------}
{------------------------------------------Tank/Flow simulator}       
  REGION 1 "Tank"    
       	START(-Width/2, -Height/2 )   
		{Lower border}
		natural(head)=0										{Set value for hydraulic head}
    	LINE TO (Width/2, -Height/2) 
		
		{Right border}
		value(head)=-Hright
		LINE TO (Width/2,Height/2) 
		
		{Upper border}
		natural(head)=0
		LINE TO (-Width/2,Height/2) 

		{Left border}
		value(head)=Hleft
		LINE TO CLOSE

{----------------------------------Cable orientation 1 / location A3}
{outer mantle}
	REGION 2 "Outer Mantle"
		Kx=0.000000001
		START(Locx_A3-Rad_mantle, Locy_A3)
		natural(head)=0
		ARC(CENTER=Locx_A3,Locy_A3) ANGLE=360
		LINE TO CLOSE

{open air} 
	REGION 3 "air in mantlee"
		Kx=0.000000001
		START(Locx_A3-Rad_air, Locy_A3)
		natural(head)=0
		ARC(CENTER=Locx_A3,Locy_A3) ANGLE=360
		LINE TO CLOSE

{Core}
	REGION 4 "Strenght cable mantle"
		Kx=0.000000001
		START(Locx_A3-Rad_Strenght_Mantle, Locy_A3)
		natural(head)=0
		ARC(CENTER=Locx_A3,Locy_A3) ANGLE=360
		LINE TO CLOSE

	REGION 5 "Strenght cable core"
		Kx=0.000000001
		START(Locx_A3-Rad_Strenght_Core, Locy_A3)
		natural(head)=0
		ARC(CENTER=Locx_A3,Locy_A3) ANGLE=360
		LINE TO CLOSE

{DTS right}
	REGION 6 "DTS1 TPE-O mantle"
		Kx=0.000000001
		START(Locx_A3_DTS1-Rad_DTS_TPEO, Locy_A3_DTS1)
		natural(head)=0
		ARC(CENTER=Locx_A3_DTS1,Locy_A3_DTS1) ANGLE=360
		LINE TO CLOSE

	REGION 7 "DTS1 Aramid"
		Kx=0.000000001
		START(Locx_A3_DTS1-Rad_DTS_Aram, Locy_A3_DTS1)
		natural(head)=0
		ARC(CENTER=Locx_A3_DTS1,Locy_A3_DTS1) ANGLE=360
		LINE TO CLOSE

	REGION 8 "DTS1 TPE"
		Kx=0.000000001
		START(Locx_A3_DTS1-Rad_DTS_TPE, Locy_A3_DTS1)
		natural(head)=0
		ARC(CENTER=Locx_A3_DTS1,Locy_A3_DTS1) ANGLE=360
		LINE TO CLOSE

	REGION 9 "DTS1 Acrylate soft"
		Kx=0.000000001
		START(Locx_A3_DTS1-Rad_DTS_AcrS, Locy_A3_DTS1)
		natural(head)=0
		ARC(CENTER=Locx_A3_DTS1,Locy_A3_DTS1) ANGLE=360
		LINE TO CLOSE

	REGION 10 "DTS1 Acrylate hard"
		Kx=0.000000001
		START(Locx_A3_DTS1-Rad_DTS_AcrH, Locy_A3_DTS1)
		natural(head)=0
		ARC(CENTER=Locx_A3_DTS1,Locy_A3_DTS1) ANGLE=360
		LINE TO CLOSE

	REGION 11 "DTS1 Glas"
		Kx=0.000000001	
		START(Locx_A3_DTS1-Rad_DTS_glas, Locy_A3_DTS1)
		natural(head)=0
		ARC(CENTER=Locx_A3_DTS1,Locy_A3_DTS1) ANGLE=360
		LINE TO CLOSE
        
{DTS Top}
	REGION 12 "DTS2 TPE-O mantle"
		Kx=0.000000001 	
		START(Locx_A3_DTS2-Rad_DTS_TPEO, Locy_A3_DTS2)
		natural(head)=0
		ARC(CENTER=Locx_A3_DTS2,Locy_A3_DTS2) ANGLE=360
		LINE TO CLOSE

	REGION 13 "DTS2 Aramid"
		Kx=0.000000001	
		START(Locx_A3_DTS2-Rad_DTS_Aram, Locy_A3_DTS2)
		natural(head)=0
		ARC(CENTER=Locx_A3_DTS2,Locy_A3_DTS2) ANGLE=360
		LINE TO CLOSE

	REGION 14 "DTS2 TPE"
		Kx=0.000000001	
		START(Locx_A3_DTS2-Rad_DTS_TPE, Locy_A3_DTS2)
		natural(head)=0
		ARC(CENTER=Locx_A3_DTS2,Locy_A3_DTS2) ANGLE=360
		LINE TO CLOSE

	REGION 15 "DTS2 Acrylate soft"
		Kx=0.000000001
		START(Locx_A3_DTS2-Rad_DTS_AcrS, Locy_A3_DTS2)
		natural(head)=0
		ARC(CENTER=Locx_A3_DTS2,Locy_A3_DTS2) ANGLE=360
		LINE TO CLOSE

	REGION 16 "DTS2 Acrylate hard"
		Kx=0.000000001
		START(Locx_A3_DTS2-Rad_DTS_AcrH, Locy_A3_DTS2)
		natural(head)=0
		ARC(CENTER=Locx_A3_DTS2,Locy_A3_DTS2) ANGLE=360
		LINE TO CLOSE

	REGION 17 "DTS2 Glas"
		Kx=0.000000001
		START(Locx_A3_DTS2-Rad_DTS_glas, Locy_A3_DTS2)
		natural(head)=0
		ARC(CENTER=Locx_A3_DTS2,Locy_A3_DTS2) ANGLE=360
		LINE TO CLOSE

{DTS Left}
	REGION 18 "DTS3 TPE-O mantle"
		Kx=0.000000001	
		START(Locx_A3_DTS3-Rad_DTS_TPEO, Locy_A3_DTS3)
		natural(head)=0
		ARC(CENTER=Locx_A3_DTS3,Locy_A3_DTS3) ANGLE=360
		LINE TO CLOSE

	REGION 19 "DTS3 Aramid"
		Kx=0.000000001
		START(Locx_A3_DTS3-Rad_DTS_Aram, Locy_A3_DTS3)
		natural(head)=0
		ARC(CENTER=Locx_A3_DTS3,Locy_A3_DTS3) ANGLE=360
		LINE TO CLOSE

	REGION 20 "DTS3 TPE"
		Kx=0.000000001
		START(Locx_A3_DTS3-Rad_DTS_TPE, Locy_A3_DTS3)
		natural(head)=0
		ARC(CENTER=Locx_A3_DTS3,Locy_A3_DTS3) ANGLE=360
		LINE TO CLOSE

	REGION 21 "DTS3 Acrylate soft"
		Kx=0.000000001
		START(Locx_A3_DTS3-Rad_DTS_AcrS, Locy_A3_DTS3)
		natural(head)=0
		ARC(CENTER=Locx_A3_DTS3,Locy_A3_DTS3) ANGLE=360
		LINE TO CLOSE

	REGION 22 "DTS3 Acrylate hard"
		Kx=0.000000001
		START(Locx_A3_DTS3-Rad_DTS_AcrH, Locy_A3_DTS3)
		natural(head)=0
		ARC(CENTER=Locx_A3_DTS3,Locy_A3_DTS3) ANGLE=360
		LINE TO CLOSE

	REGION 23 "DTS3 Glas"
		Kx=0.000000001
		START(Locx_A3_DTS3-Rad_DTS_glas, Locy_A3_DTS3)
		natural(head)=0
		ARC(CENTER=Locx_A3_DTS3,Locy_A3_DTS3) ANGLE=360
		LINE TO CLOSE

{DTS below}
	REGION 24 "DTS4 TPE-O mantle"
		Kx=0.000000001
		START(Locx_A3_DTS4-Rad_DTS_TPEO, Locy_A3_DTS4)
		natural(head)=0
		ARC(CENTER=Locx_A3_DTS4,Locy_A3_DTS4) ANGLE=360
		LINE TO CLOSE

	REGION 25 "DTS4 Aramid"
		Kx=0.000000001
		START(Locx_A3_DTS4-Rad_DTS_Aram, Locy_A3_DTS4)
		natural(head)=0
		ARC(CENTER=Locx_A3_DTS4,Locy_A3_DTS4) ANGLE=360
		LINE TO CLOSE

	REGION 26 "DTS4 TPE"
		Kx=0.000000001
		START(Locx_A3_DTS4-Rad_DTS_TPE, Locy_A3_DTS4)
		natural(head)=0
		ARC(CENTER=Locx_A3_DTS4,Locy_A3_DTS4) ANGLE=360
		LINE TO CLOSE

	REGION 27 "DTS4 Acrylate soft"
		Kx=0.000000001
		START(Locx_A3_DTS4-Rad_DTS_AcrS, Locy_A3_DTS4)
		natural(head)=0
		ARC(CENTER=Locx_A3_DTS4,Locy_A3_DTS4) ANGLE=360
		LINE TO CLOSE

	REGION 28 "DTS4 Acrylate hard"
		Kx=0.000000001
		START(Locx_A3_DTS4-Rad_DTS_AcrH, Locy_A3_DTS4)
		natural(head)=0
		ARC(CENTER=Locx_A3_DTS4,Locy_A3_DTS4) ANGLE=360
		LINE TO CLOSE

	REGION 29 "DTS4 Glas"
		Kx=0.000000001	
		START(Locx_A3_DTS4-Rad_DTS_glas, Locy_A3_DTS4)
		natural(head)=0
		ARC(CENTER=Locx_A3_DTS4,Locy_A3_DTS4) ANGLE=360
		LINE TO CLOSE

{Heating right low}
	REGION 30 "Heat1 mantle"
		Kx=0.000000001
		START(Locx_A3_heat1-Rad_heat_mantle, Locy_A3_heat1)
		natural(head)=0
		ARC(CENTER=Locx_A3_heat1,Locy_A3_heat1) ANGLE=360
		LINE TO CLOSE

	REGION 31 "Heat1 core"
		Kx=0.000000001
		START(Locx_A3_heat1-Rad_heat_core, Locy_A3_heat1)
		natural(head)=0
		ARC(CENTER=Locx_A3_heat1,Locy_A3_heat1) ANGLE=360
		LINE TO CLOSE

{Heating top right}
	REGION 32 "Heat2 mantle"
		Kx=0.000000001
		START(Locx_A3_heat2-Rad_heat_mantle, Locy_A3_heat2)
		natural(head)=0
		ARC(CENTER=Locx_A3_heat2,Locy_A3_heat2) ANGLE=360
		LINE TO CLOSE

	REGION 33 "Heat2 core"
		Kx=0.000000001
		START(Locx_A3_heat2-Rad_heat_core, Locy_A3_heat2)
		natural(head)=0
		ARC(CENTER=Locx_A3_heat2,Locy_A3_heat2) ANGLE=360
		LINE TO CLOSE

{Heating left above}
	REGION 34 "Heat3 mantle"
		Kx=0.000000001
		START(Locx_A3_heat3-Rad_heat_mantle, Locy_A3_heat3)
		natural(head)=0
		ARC(CENTER=Locx_A3_heat3,Locy_A3_heat3) ANGLE=360
		LINE TO CLOSE

	REGION 35 "Heat3 core"
		Kx=0.000000001
		START(Locx_A3_heat3-Rad_heat_core, Locy_A3_heat3)
		natural(head)=0
		ARC(CENTER=Locx_A3_heat3,Locy_A3_heat3) ANGLE=360
		LINE TO CLOSE

{Heating bottom left}
	REGION 36 "Heat4 mantle"
		Kx=0.000000001
		START(Locx_A3_heat4-Rad_heat_mantle, Locy_A3_heat4)
		natural(head)=0
		ARC(CENTER=Locx_A3_heat4,Locy_A3_heat4) ANGLE=360
		LINE TO CLOSE

	REGION 37 "Heat4 core"
		Kx=0.000000001
		START(Locx_A3_heat4-Rad_heat_core, Locy_A3_heat4)
		natural(head)=0
		ARC(CENTER=Locx_A3_heat4,Locy_A3_heat4) ANGLE=360
		LINE TO CLOSE

{Retour right high}
	REGION 38 "Retour1 mantle"
		Kx=0.000000001
		START(Locx_A3_retour1-Rad_retour_mantle, Locy_A3_retour1)
		natural(head)=0
		ARC(CENTER=Locx_A3_retour1,Locy_A3_retour1) ANGLE=360
		LINE TO CLOSE

	REGION 39 "Retour1 core"
		Kx=0.000000001
		START(Locx_A3_retour1-Rad_retour_core, Locy_A3_retour1)
		natural(head)=0
		ARC(CENTER=Locx_A3_retour1,Locy_A3_retour1) ANGLE=360
		LINE TO CLOSE

{Retour high left}
	REGION 40 "Retour2 mantle"
		Kx=0.000000001
		START(Locx_A3_retour2-Rad_retour_mantle, Locy_A3_retour2)
		natural(head)=0
		ARC(CENTER=Locx_A3_retour2,Locy_A3_retour2) ANGLE=360
		LINE TO CLOSE

	REGION 41 "Retour2 core"
		Kx=0.000000001
		START(Locx_A3_retour2-Rad_retour_core, Locy_A3_retour2)
		natural(head)=0
		ARC(CENTER=Locx_A3_retour2,Locy_A3_retour2) ANGLE=360
		LINE TO CLOSE

{Retour left low}
	REGION 42 "Retour3 mantle"
		Kx=0.000000001
		START(Locx_A3_retour3-Rad_retour_mantle, Locy_A3_retour3)
		natural(head)=0
		ARC(CENTER=Locx_A3_retour3,Locy_A3_retour3) ANGLE=360
		LINE TO CLOSE

	REGION 43 "Retour3 core"
		Kx=0.000000001
		START(Locx_A3_retour3-Rad_retour_core, Locy_A3_retour3)
		natural(head)=0
		ARC(CENTER=Locx_A3_retour3,Locy_A3_retour3) ANGLE=360
		LINE TO CLOSE

{Retour low right}
	REGION 44 "Retour4 mantle"
		Kx=0.000000001
		START(Locx_A3_retour4-Rad_retour_mantle, Locy_A3_retour4)
		natural(head)=0
		ARC(CENTER=Locx_A3_retour4,Locy_A3_retour4) ANGLE=360
		LINE TO CLOSE

	REGION 45 "Retour4 core"
		Kx=0.000000001
		START(Locx_A3_retour4-Rad_retour_core, Locy_A3_retour4)
		natural(head)=0
		ARC(CENTER=Locx_A3_retour4,Locy_A3_retour4) ANGLE=360
		LINE TO CLOSE

PLOTS 
	contour(head) painted nominmax as 'head in complete tank'
	vector(q*tday) as 'velocity in complete tank'
	contour(head)  zoom (Locx_A3-0.01,Locy_A3-0.01,0.02,0.02)  painted nominmax as 'detailed head field around  location A3' 
    transfer(head) file = "head_Darcy55.2.dat"

END
