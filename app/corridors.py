"""Illustrative road bends keyed by adjacent stops in the seeded network."""

WAYPOINTS = {
    ("Dwarka", "Uttam Nagar"): [(28.595, 77.059), (28.606, 77.056)],
    ("Dwarka", "Palam"): [(28.578, 77.068), (28.580, 77.080)],
    ("Dwarka Sector 21", "Aerocity"): [(28.543, 77.077), (28.532, 77.098), (28.541, 77.118)],
    ("Palam", "Delhi Cantt"): [(28.590, 77.089), (28.593, 77.110)],
    ("Delhi Cantt", "Dhaula Kuan"): [(28.601, 77.132), (28.596, 77.149)],
    ("Delhi Cantt", "Mayapuri"): [(28.605, 77.116), (28.620, 77.122)],
    ("Dhaula Kuan", "Chanakyapuri"): [(28.595, 77.167), (28.598, 77.179)],
    ("Chanakyapuri", "Central Secretariat"): [(28.602, 77.196), (28.606, 77.207)],
    ("Chanakyapuri", "Sarojini Nagar"): [(28.591, 77.192), (28.579, 77.191)],
    ("Punjabi Bagh", "Karol Bagh"): [(28.662, 77.143), (28.654, 77.152), (28.650, 77.172)],
    ("Rajouri Garden", "Patel Nagar"): [(28.650, 77.137), (28.648, 77.155)],
    ("Kashmiri Gate", "Red Fort"): [(28.665, 77.234), (28.660, 77.236)],
    ("ISBT Kashmiri Gate", "Geeta Colony"): [(28.668, 77.241), (28.657, 77.250), (28.655, 77.263)],
    ("ISBT Kashmiri Gate", "Seelampur"): [(28.675, 77.240), (28.674, 77.253)],
    ("ITO", "Laxmi Nagar"): [(28.632, 77.254), (28.632, 77.269)],
    ("ITO", "Akshardham"): [(28.624, 77.249), (28.621, 77.265)],
    ("Mayur Vihar", "Noida Sector 15"): [(28.597, 77.291), (28.590, 77.298)],
    ("Anand Vihar", "Vaishali"): [(28.653, 77.324), (28.652, 77.336)],
    ("Indirapuram", "Ghaziabad"): [(28.640, 77.382), (28.647, 77.402), (28.654, 77.418)],
    ("Aerocity", "Vasant Vihar"): [(28.563, 77.129), (28.566, 77.143), (28.562, 77.152)],
    ("Mahipalpur", "Udyog Vihar"): [(28.535, 77.123), (28.522, 77.106), (28.517, 77.090)],
    ("DLF Cyber City", "Gurugram"): [(28.491, 77.071), (28.468, 77.055)],
    ("Botanical Garden, Noida", "Noida Sector 93"): [(28.554, 77.343), (28.538, 77.357), (28.516, 77.380)],
    ("Noida Sector 93", "Pari Chowk"): [(28.494, 77.414), (28.479, 77.450), (28.467, 77.485)],
    ("Pari Chowk", "Greater Noida"): [(28.465, 77.518)],
    ("Okhla", "Badarpur Border"): [(28.536, 77.274), (28.526, 77.286), (28.507, 77.302)],
    ("Sarai Khawaja", "Faridabad"): [(28.450, 77.304), (28.431, 77.309)],
    ("Saket", "Surajkund"): [(28.518, 77.224), (28.513, 77.247), (28.503, 77.269)],
    ("Surajkund", "Badarpur Border"): [(28.492, 77.292)],
    ("Badarpur Border", "Kalindi Kunj"): [(28.516, 77.314), (28.535, 77.317)],
    ("Kalindi Kunj", "Botanical Garden, Noida"): [(28.549, 77.322), (28.557, 77.328)],
}


def segment_geometry(source, target):
    names = source["name"], target["name"]
    bends = WAYPOINTS.get(names)
    if bends is None:
        bends = WAYPOINTS.get(names[::-1], ())[::-1]
    return [(source["lat"], source["lon"]), *bends, (target["lat"], target["lon"])]
