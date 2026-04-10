import numpy as np

def darcy_flux_m_per_day(flow_rate_m3_per_day, well_screen_height_m, well_screen_radius_m, distance_from_screen_m):
    """
    Radial Darcy flux q(r) around a well, returned in m/day.

    Parameters
    ----------
    flow_rate_m3_per_day : float
        Pumping or injection rate [m^3/day]
    well_screen_height_m : float
        Well screen length [m]
    well_screen_radius_m : float
        Well screen radius [m]
    distance_from_screen_m : float or array
        Distance from well screen surface [m]

    Returns
    -------
    q_day : float or array
        Darcy flux at distance from well screen surface [m/day]
    """
    distance_from_screen_m = np.asarray(distance_from_screen_m)
    radial_distance_from_center_m = well_screen_radius_m + distance_from_screen_m
    cylindrical_flow_area_m2 = 2 * np.pi * radial_distance_from_center_m * well_screen_height_m
    q_day = flow_rate_m3_per_day / cylindrical_flow_area_m2
    return q_day

# Example 1: Parking lot K1, Utrecht
pumping_rate_m3_per_day = 5*24             # m3/day, pumping rate
well_screen_height_m = 4.8 + 3.0 + 8.5     # m, 3 sections in K1 at parking lot
well_screen_radius_m = 0.315/2             # m radius pipe, 315 mm diameter
distance_from_screen_m = 0.05              # m separation distance between screen and FO cable

# Example 2: Experiment geohal
# pumping_rate_m3_per_day = 1.5*24          # m3/day
# well_screen_height_m = 1.1               # m, 3 sections in K1 at parking lot
# well_screen_radius_m = 0.1           # m radius pipe
# distance_from_screen_m = 0.0  # m

# Example 3: Planned for Bommelerwaard
# pumping_rate_m3_per_day = 150*24          # m3/day
# well_screen_height_m = 80                # m, 3 sections in K1 at parking lot
# well_screen_radius_m = 0.139           # m radius pipe
# distance_from_screen_m = 0.0  # m

print(darcy_flux_m_per_day(
    pumping_rate_m3_per_day,
    well_screen_height_m,
    well_screen_radius_m,
    distance_from_screen_m,
))