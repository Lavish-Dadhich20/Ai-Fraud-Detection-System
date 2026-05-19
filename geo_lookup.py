

# ── Master lookup table ────────────────────────────────────────────────────────
# Format: "normalized name": (lat, lon, "display name")
# Normalized = lowercase, stripped, common aliases included

LOCATION_DB = {
    # ── MAJOR CITIES ──────────────────────────────────────────────────────────
    "mumbai":          (19.0760,  72.8777, "Mumbai, Maharashtra"),
    "bombay":          (19.0760,  72.8777, "Mumbai, Maharashtra"),
    "delhi":           (28.6139,  77.2090, "New Delhi"),
    "new delhi":       (28.6139,  77.2090, "New Delhi"),
    "bangalore":       (12.9716,  77.5946, "Bengaluru, Karnataka"),
    "bengaluru":       (12.9716,  77.5946, "Bengaluru, Karnataka"),
    "bengalore":       (12.9716,  77.5946, "Bengaluru, Karnataka"),
    "hyderabad":       (17.3850,  78.4867, "Hyderabad, Telangana"),
    "chennai":         (13.0827,  80.2707, "Chennai, Tamil Nadu"),
    "madras":          (13.0827,  80.2707, "Chennai, Tamil Nadu"),
    "kolkata":         (22.5726,  88.3639, "Kolkata, West Bengal"),
    "calcutta":        (22.5726,  88.3639, "Kolkata, West Bengal"),
    "pune":            (18.5204,  73.8567, "Pune, Maharashtra"),
    "ahmedabad":       (23.0225,  72.5714, "Ahmedabad, Gujarat"),
    "surat":           (21.1702,  72.8311, "Surat, Gujarat"),
    "jaipur":          (26.9124,  75.7873, "Jaipur, Rajasthan"),
    "lucknow":         (26.8467,  80.9462, "Lucknow, Uttar Pradesh"),
    "kanpur":          (26.4499,  80.3319, "Kanpur, Uttar Pradesh"),
    "nagpur":          (21.1458,  79.0882, "Nagpur, Maharashtra"),
    "indore":          (22.7196,  75.8577, "Indore, Madhya Pradesh"),
    "bhopal":          (23.2599,  77.4126, "Bhopal, Madhya Pradesh"),
    "visakhapatnam":   (17.6868,  83.2185, "Visakhapatnam, Andhra Pradesh"),
    "vizag":           (17.6868,  83.2185, "Visakhapatnam, Andhra Pradesh"),
    "patna":           (25.5941,  85.1376, "Patna, Bihar"),
    "vadodara":        (22.3072,  73.1812, "Vadodara, Gujarat"),
    "ghaziabad":       (28.6692,  77.4538, "Ghaziabad, Uttar Pradesh"),
    "ludhiana":        (30.9010,  75.8573, "Ludhiana, Punjab"),
    "agra":            (27.1767,  78.0081, "Agra, Uttar Pradesh"),
    "nashik":          (19.9975,  73.7898, "Nashik, Maharashtra"),
    "faridabad":       (28.4089,  77.3178, "Faridabad, Haryana"),
    "meerut":          (28.9845,  77.7064, "Meerut, Uttar Pradesh"),
    "rajkot":          (22.3039,  70.8022, "Rajkot, Gujarat"),
    "varanasi":        (25.3176,  82.9739, "Varanasi, Uttar Pradesh"),
    "banaras":         (25.3176,  82.9739, "Varanasi, Uttar Pradesh"),
    "amritsar":        (31.6340,  74.8723, "Amritsar, Punjab"),
    "allahabad":       (25.4358,  81.8463, "Prayagraj, Uttar Pradesh"),
    "prayagraj":       (25.4358,  81.8463, "Prayagraj, Uttar Pradesh"),
    "jabalpur":        (23.1815,  79.9864, "Jabalpur, Madhya Pradesh"),
    "coimbatore":      (11.0168,  76.9558, "Coimbatore, Tamil Nadu"),
    "vijayawada":      (16.5062,  80.6480, "Vijayawada, Andhra Pradesh"),
    "madurai":         ( 9.9252,  78.1198, "Madurai, Tamil Nadu"),
    "guwahati":        (26.1445,  91.7362, "Guwahati, Assam"),
    "chandigarh":      (30.7333,  76.7794, "Chandigarh"),
    "hubli":           (15.3647,  75.1240, "Hubballi, Karnataka"),
    "hubballi":        (15.3647,  75.1240, "Hubballi, Karnataka"),
    "mysuru":          (12.2958,  76.6394, "Mysuru, Karnataka"),
    "mysore":          (12.2958,  76.6394, "Mysuru, Karnataka"),
    "jodhpur":         (26.2389,  73.0243, "Jodhpur, Rajasthan"),
    "udaipur":         (24.5854,  73.7125, "Udaipur, Rajasthan"),
    "kota":            (25.2138,  75.8648, "Kota, Rajasthan"),
    "ajmer":           (26.4499,  74.6399, "Ajmer, Rajasthan"),
    "bikaner":         (28.0229,  73.3119, "Bikaner, Rajasthan"),
    "dehradun":        (30.3165,  78.0322, "Dehradun, Uttarakhand"),
    "haridwar":        (29.9457,  78.1642, "Haridwar, Uttarakhand"),
    "shimla":          (31.1048,  77.1734, "Shimla, Himachal Pradesh"),
    "manali":          (32.2432,  77.1892, "Manali, Himachal Pradesh"),
    "srinagar":        (34.0837,  74.7973, "Srinagar, J&K"),
    "jammu":           (32.7266,  74.8570, "Jammu, J&K"),
    "leh":             (34.1526,  77.5771, "Leh, Ladakh"),
    "raipur":          (21.2514,  81.6296, "Raipur, Chhattisgarh"),
    "bhubaneswar":     (20.2961,  85.8245, "Bhubaneswar, Odisha"),
    "puri":            (19.8135,  85.8312, "Puri, Odisha"),
    "ranchi":          (23.3441,  85.3096, "Ranchi, Jharkhand"),
    "jamshedpur":      (22.8046,  86.2029, "Jamshedpur, Jharkhand"),
    "kochi":           ( 9.9312,  76.2673, "Kochi, Kerala"),
    "cochin":          ( 9.9312,  76.2673, "Kochi, Kerala"),
    "thiruvananthapuram": (8.5241, 76.9366, "Thiruvananthapuram, Kerala"),
    "trivandrum":      ( 8.5241,  76.9366, "Thiruvananthapuram, Kerala"),
    "kozhikode":       (11.2588,  75.7804, "Kozhikode, Kerala"),
    "calicut":         (11.2588,  75.7804, "Kozhikode, Kerala"),
    "thrissur":        (10.5276,  76.2144, "Thrissur, Kerala"),
    "mangaluru":       (12.9141,  74.8560, "Mangaluru, Karnataka"),
    "mangalore":       (12.9141,  74.8560, "Mangaluru, Karnataka"),
    "goa":             (15.2993,  74.1240, "Goa"),
    "panaji":          (15.4989,  73.8278, "Panaji, Goa"),
    "kolhapur":        (16.7050,  74.2433, "Kolhapur, Maharashtra"),
    "aurangabad":      (19.8762,  75.3433, "Chhatrapati Sambhajinagar, Maharashtra"),
    "solapur":         (17.6599,  75.9064, "Solapur, Maharashtra"),
    "noida":           (28.5355,  77.3910, "Noida, Uttar Pradesh"),
    "gurugram":        (28.4595,  77.0266, "Gurugram, Haryana"),
    "gurgaon":         (28.4595,  77.0266, "Gurugram, Haryana"),
    "navi mumbai":     (19.0330,  73.0297, "Navi Mumbai, Maharashtra"),
    "thane":           (19.2183,  72.9781, "Thane, Maharashtra"),
    "agartala":        (23.8315,  91.2868, "Agartala, Tripura"),
    "imphal":          (24.8170,  93.9368, "Imphal, Manipur"),
    "shillong":        (25.5788,  91.8933, "Shillong, Meghalaya"),
    "aizawl":          (23.7271,  92.7176, "Aizawl, Mizoram"),
    "kohima":          (25.6701,  94.1077, "Kohima, Nagaland"),
    "itanagar":        (27.0844,  93.6053, "Itanagar, Arunachal Pradesh"),
    "gangtok":         (27.3314,  88.6138, "Gangtok, Sikkim"),
    "port blair":      (11.6234,  92.7265, "Port Blair, Andaman & Nicobar"),
    "panipat":         (29.3909,  76.9635, "Panipat, Haryana"),
    "ambala":          (30.3752,  76.7821, "Ambala, Haryana"),
    "rohtak":          (28.8955,  76.6066, "Rohtak, Haryana"),
    "hisar":           (29.1492,  75.7217, "Hisar, Haryana"),
    "karnal":          (29.6857,  76.9905, "Karnal, Haryana"),
    "bhilai":          (21.1938,  81.3509, "Bhilai, Chhattisgarh"),
    "bilaspur":        (22.0797,  82.1409, "Bilaspur, Chhattisgarh"),
    "korba":           (22.3595,  82.7501, "Korba, Chhattisgarh"),
    "gorakhpur":       (26.7606,  83.3732, "Gorakhpur, Uttar Pradesh"),
    "bareilly":        (28.3670,  79.4304, "Bareilly, Uttar Pradesh"),
    "aligarh":         (27.8974,  78.0880, "Aligarh, Uttar Pradesh"),
    "moradabad":       (28.8386,  78.7733, "Moradabad, Uttar Pradesh"),
    "saharanpur":      (29.9640,  77.5461, "Saharanpur, Uttar Pradesh"),
    "bhilwara":        (25.3407,  74.6313, "Bhilwara, Rajasthan"),
    "alwar":           (27.5530,  76.6346, "Alwar, Rajasthan"),
    "sikar":           (27.6094,  75.1398, "Sikar, Rajasthan"),
    "sri ganganagar":  (29.9038,  73.8772, "Sri Ganganagar, Rajasthan"),
    "dhanbad":         (23.7957,  86.4304, "Dhanbad, Jharkhand"),
    "bokaro":          (23.6693,  86.1511, "Bokaro, Jharkhand"),
    "durgapur":        (23.5204,  87.3119, "Durgapur, West Bengal"),
    "asansol":         (23.6835,  86.9735, "Asansol, West Bengal"),
    "siliguri":        (26.7271,  88.3953, "Siliguri, West Bengal"),
    "dibrugarh":       (27.4728,  94.9120, "Dibrugarh, Assam"),
    "silchar":         (24.8333,  92.7789, "Silchar, Assam"),
    "tirupati":        (13.6288,  79.4192, "Tirupati, Andhra Pradesh"),
    "nellore":         (14.4426,  79.9865, "Nellore, Andhra Pradesh"),
    "guntur":          (16.3067,  80.4365, "Guntur, Andhra Pradesh"),
    "kakinada":        (16.9891,  82.2475, "Kakinada, Andhra Pradesh"),
    "rajahmundry":     (17.0005,  81.8040, "Rajahmundry, Andhra Pradesh"),
    "salem":           (11.6643,  78.1460, "Salem, Tamil Nadu"),
    "tiruchy":         (10.7905,  78.7047, "Tiruchirappalli, Tamil Nadu"),
    "tiruchirappalli": (10.7905,  78.7047, "Tiruchirappalli, Tamil Nadu"),
    "tirunelveli":     ( 8.7139,  77.7567, "Tirunelveli, Tamil Nadu"),
    "vellore":         (12.9165,  79.1325, "Vellore, Tamil Nadu"),
    "erode":           (11.3410,  77.7172, "Erode, Tamil Nadu"),

    # ── STATES / UTs (centroid coordinates) ───────────────────────────────
    "andhra pradesh":      (15.9129,  79.7400, "Andhra Pradesh"),
    "arunachal pradesh":   (28.2180,  94.7278, "Arunachal Pradesh"),
    "assam":               (26.2006,  92.9376, "Assam"),
    "bihar":               (25.0961,  85.3131, "Bihar"),
    "chhattisgarh":        (21.2787,  81.8661, "Chhattisgarh"),
    "goa state":           (15.2993,  74.1240, "Goa"),
    "gujarat":             (22.2587,  71.1924, "Gujarat"),
    "haryana":             (29.0588,  76.0856, "Haryana"),
    "himachal pradesh":    (31.1048,  77.1734, "Himachal Pradesh"),
    "jharkhand":           (23.6102,  85.2799, "Jharkhand"),
    "karnataka":           (15.3173,  75.7139, "Karnataka"),
    "kerala":              (10.8505,  76.2711, "Kerala"),
    "madhya pradesh":      (22.9734,  78.6569, "Madhya Pradesh"),
    "mp":                  (22.9734,  78.6569, "Madhya Pradesh"),
    "maharashtra":         (19.7515,  75.7139, "Maharashtra"),
    "manipur":             (24.6637,  93.9063, "Manipur"),
    "meghalaya":           (25.4670,  91.3662, "Meghalaya"),
    "mizoram":             (23.1645,  92.9376, "Mizoram"),
    "nagaland":            (26.1584,  94.5624, "Nagaland"),
    "odisha":              (20.9517,  85.0985, "Odisha"),
    "orissa":              (20.9517,  85.0985, "Odisha"),
    "punjab":              (31.1471,  75.3412, "Punjab"),
    "rajasthan":           (27.0238,  74.2179, "Rajasthan"),
    "sikkim":              (27.5330,  88.5122, "Sikkim"),
    "tamil nadu":          (11.1271,  78.6569, "Tamil Nadu"),
    "tn":                  (11.1271,  78.6569, "Tamil Nadu"),
    "telangana":           (18.1124,  79.0193, "Telangana"),
    "tripura":             (23.9408,  91.9882, "Tripura"),
    "uttar pradesh":       (26.8467,  80.9462, "Uttar Pradesh"),
    "up":                  (26.8467,  80.9462, "Uttar Pradesh"),
    "uttarakhand":         (30.0668,  79.0193, "Uttarakhand"),
    "west bengal":         (22.9868,  87.8550, "West Bengal"),
    "wb":                  (22.9868,  87.8550, "West Bengal"),
    "jammu and kashmir":   (33.7782,  76.5762, "Jammu & Kashmir"),
    "jk":                  (33.7782,  76.5762, "Jammu & Kashmir"),
    "ladakh":              (34.1526,  77.5771, "Ladakh"),
    "delhi state":         (28.6139,  77.2090, "Delhi"),
    "ncr":                 (28.6139,  77.2090, "Delhi NCR"),
    "puducherry":          (11.9416,  79.8083, "Puducherry"),
    "pondicherry":         (11.9416,  79.8083, "Puducherry"),
    "chandigarh state":    (30.7333,  76.7794, "Chandigarh"),
    "andaman":             (11.6234,  92.7265, "Andaman & Nicobar"),
    "lakshadweep":         (10.5667,  72.6417, "Lakshadweep"),
    "daman":               (20.3974,  72.8328, "Daman & Diu"),
    "dadra":               (20.1809,  73.0169, "Dadra & Nagar Haveli"),

    # ── COMMON ALIASES / INFORMAL NAMES ───────────────────────────────────
    "navi mumbai":         (19.0330,  73.0297, "Navi Mumbai"),
    "greater mumbai":      (19.0760,  72.8777, "Mumbai"),
    "silicon valley india":(12.9716,  77.5946, "Bengaluru"),
    "pink city":           (26.9124,  75.7873, "Jaipur"),
    "city of nawabs":      (26.8467,  80.9462, "Lucknow"),
    "city of lakes":       (24.5854,  73.7125, "Udaipur"),
    "golden city":         (26.3011,  73.0169, "Jodhpur"),
}


def resolve_location(name: str):
    """
    Convert a city/state name to (lat, lon, display_name).

    Args:
        name: Any city name, state name, or alias (case-insensitive).

    Returns:
        (lat, lon, display_name) tuple if found.

    Raises:
        ValueError with suggestions if not found.
    """
    key = name.strip().lower()

    # Exact match
    if key in LOCATION_DB:
        lat, lon, display = LOCATION_DB[key]
        return lat, lon, display

    # Partial / substring match — find all entries that contain the input
    matches = {k: v for k, v in LOCATION_DB.items() if key in k or k in key}
    if len(matches) == 1:
        k = list(matches.keys())[0]
        lat, lon, display = matches[k]
        return lat, lon, display
    if len(matches) > 1:
        suggestions = ", ".join(sorted(matches.keys())[:8])
        raise ValueError(
            f"'{name}' matched multiple locations: {suggestions}\n"
            f"      Please be more specific."
        )

    # Nothing found — suggest similar names
    all_keys  = list(LOCATION_DB.keys())
    close     = [k for k in all_keys if any(w in k for w in key.split())][:6]
    hint      = f"  Did you mean: {', '.join(close)}" if close else \
                "  Try a major city or state name (e.g. 'Jaipur', 'Kerala', 'Mumbai')"
    raise ValueError(f"Location '{name}' not found in database.\n{hint}")


def list_all_locations() -> list:
    """Return sorted list of all supported location names."""
    return sorted(LOCATION_DB.keys())


if __name__ == "__main__":
    # Quick self-test
    tests = ["udaipur", "kerala", "new york", "Mumbai", "TN", "city of lakes"]
    for t in tests:
        try:
            lat, lon, name = resolve_location(t)
            print(f"  '{t}' → {name} ({lat:.4f}, {lon:.4f})")
        except ValueError as e:
            print(f"  '{t}' → ERROR: {e}")