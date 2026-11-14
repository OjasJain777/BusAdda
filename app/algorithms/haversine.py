from math import asin, cos, radians, sin, sqrt


def haversine(lat_a, lon_a, lat_b, lon_b):
    """Great-circle distance in kilometers between two latitude/longitude pairs."""
    phi_a, phi_b = radians(lat_a), radians(lat_b)
    half_lat = (phi_b - phi_a) / 2
    half_lon = radians(lon_b - lon_a) / 2
    a = sin(half_lat) ** 2 + cos(phi_a) * cos(phi_b) * sin(half_lon) ** 2
    return 2 * 6371 * asin(sqrt(min(1, max(0, a))))
