import math
import numpy as np

"""
Coordinate conversion utilities for astronomical coordinates.
Handles conversion between RA/Dec and Cartesian (x,y,z) coordinates.
"""


def xyz_to_ra_dec(x, y, z):
    """
    Convert Cartesian (x, y, z) on unit sphere to RA/Dec in degrees.

    Args:
        x, y, z (float): Coordinates on unit sphere (will be normalized if needed)

    Returns:
        tuple: (ra_deg, dec_deg) in [0, 360) and [-90, 90]
    """
    x, y, z = float(x), float(y), float(z)
    n = math.sqrt(x * x + y * y + z * z)
    if n <= 0:
        return (0.0, 0.0)
    x, y, z = x / n, y / n, z / n
    dec_rad = math.asin(max(-1.0, min(1.0, z)))
    ra_rad = math.atan2(y, x)
    if ra_rad < 0:
        ra_rad += 2 * math.pi
    return (math.degrees(ra_rad), math.degrees(dec_rad))


def ra_dec_to_xyz(ra, dec):
    """
    Convert RA/Dec to Cartesian (x,y,z) coordinates.

    Args:
        ra (float): Right Ascension in degrees
        dec (float): Declination in degrees

    Returns:
        tuple: (x, y, z) coordinates on unit sphere (radius=1)
    """

    # Convert degrees to radians
    ra_rad = math.radians(ra)
    dec_rad = math.radians(dec)

    # Unit sphere conversion (r=1)
    x = math.cos(dec_rad) * math.cos(ra_rad)
    y = math.cos(dec_rad) * math.sin(ra_rad)
    z = math.sin(dec_rad)

    return (x, y, z)

def calculate_distance_3d(point1, point2):
    """
    Calculate Euclidean distance between two 3D points.

    Args:
        point1: Array-like (x, y, z) coordinates
        point2: Array-like (x, y, z) coordinates


    Returns:
        float: Distance between the two points
    """

    return np.linalg.norm(np.array(point1) - np.array(point2))

def ra_dec_to_lon_lat(ra, dec):
    """
    Convert RA/Dec to lon/lat.
    Convention: RA in [0, 360) -> lon in (-180, 180]; Dec = lat.

    :arg
    ra (float): Right Ascension in degrees [0, 360)
    dec (float): Declination in degrees (-90, 90]

    :returns
    tuple: (lon, lat), lon in (-180, 180]
    """
    ra = float(ra) % 360.0
    lon = ra if ra <= 180 else ra - 360.0
    lat = max(-90.0, min(90.0, float(dec)))
    return (lon, lat)

def lon_lat_to_ra_dec(lon, lat):
    """
    Convert longitude/latitude (degrees) to RA/Dec (degrees).

    Args:
        lon (float): Longitude in degrees (typically -180 to 180 or 0 to 360)
        lat (float): Latitude in degrees [-90, 90]

    Returns:
        tuple: (ra_deg, dec_deg), RA in [0, 360), Dec in [-90, 90]
    """
    lon = float(lon)
    lat = max(-90.0, min(90.0, float(lat)))
    ra = lon % 360.0
    if ra < 0:
        ra+=360.0
    return (ra, lat)

def lon_lat_to_xyz(lon, lat):
    """
    Convert longitude/latitude (degrees) to Cartesian (x, y, z) on unit sphere.
    Same as ra_dec_to_xyz(lon_lat_to_ra_dec(lon, lat)).
    """

    ra, dec = lon_lat_to_ra_dec(lon, lat)
    return ra_dec_to_xyz(ra, dec)


