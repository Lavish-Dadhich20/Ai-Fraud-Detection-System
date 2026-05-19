

import numpy as np
import pandas as pd
from math import radians, sin, cos, sqrt, atan2


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


INDIA_LAT = (8.0, 37.0)
INDIA_LON = (68.0, 97.0)


def random_india_location():
    return np.random.uniform(*INDIA_LAT), np.random.uniform(*INDIA_LON)


def random_location_at_distance(usual_lat, usual_lon, target_km):
    """Generate a location approximately target_km away."""
    angle   = np.random.uniform(0, 2 * np.pi)
    delta   = target_km / 111.0
    lat     = usual_lat + delta * np.cos(angle)
    lon     = usual_lon + delta / max(np.cos(np.radians(usual_lat)), 0.1) * np.sin(angle)
    return lat, lon


def _suspicion_score(amt_ratio, loc_km, new_device, hour, v15):
    """
    Compute a combined suspicion score from 0 to 1.

    Each feature contributes proportionally — no feature dominates alone.
    The score reflects COMBINED risk, not any single signal.
    """
    score = 0.0

    # ── Amount deviation (0-45 points) ──────────────────────────────────────
    # Extreme spikes (20x+) are fraud even without other signals
    if   amt_ratio >= 20: score += 45
    elif amt_ratio >= 15: score += 36
    elif amt_ratio >= 10: score += 27
    elif amt_ratio >= 5:  score += 16
    elif amt_ratio >= 3:  score += 7
    else:                 score += 0

    # ── Location deviation (0-25 points) ────────────────────────────────────
    if   loc_km >= 5000:  score += 25
    elif loc_km >= 2000:  score += 20
    elif loc_km >= 1000:  score += 15
    elif loc_km >= 500:   score += 10
    elif loc_km >= 200:   score += 5
    elif loc_km >= 50:    score += 2
    else:                 score += 0

    # ── New device (0-25 points) ─────────────────────────────────────────────
    if new_device:
        score += 25

    # ── Night hour 0-5am (0-10 points) ──────────────────────────────────────
    if   0 <= hour <= 2:  score += 10
    elif 3 <= hour <= 5:  score += 7
    else:                 score += 0

    # ── Velocity last 15 min (0-50 points) ──────────────────────────────────
    # 10+ txns in 15 min is always fraud regardless of other signals
    if   v15 >= 12: score += 50
    elif v15 >= 8:  score += 40
    elif v15 >= 5:  score += 28
    elif v15 >= 3:  score += 13
    elif v15 >= 2:  score += 5
    else:           score += 0

    # Normalise to 0-1
    return score / 155.0


def generate_transaction_dataset(n_samples=50000, fraud_ratio=0.05, random_state=42):
    """
    Generate transactions from a single unified population.
    Label is determined by combined suspicion score, not by population membership.
    """
    rng = np.random.RandomState(random_state)

    # We'll generate more than needed then sample to get exact fraud_ratio
    rows = []

    for _ in range(n_samples * 3):   # generate 3x, then sample down
        sender_avg = min(rng.exponential(1500) + 200, 80000)

        # ── Amount ──────────────────────────────────────────────────────────
        # Pull from a distribution that spans the full realistic range
        # Most transactions are normal; tail extends to fraud territory
        amt_ratio = rng.choice(
            [rng.uniform(0.1, 1.5),    # 60% — well below average
             rng.uniform(1.5, 4.0),    # 25% — moderately above average
             rng.uniform(4.0, 10.0),   # 10% — significantly above (often fraud)
             rng.uniform(10.0, 30.0)], # 5%  — extreme spike (almost always fraud)
            p=[0.60, 0.25, 0.10, 0.05]
        )
        txn_amount = max(10, min(sender_avg * amt_ratio, 500000))

        # ── Location ────────────────────────────────────────────────────────
        usual_lat, usual_lon = random_india_location()
        loc_km = rng.choice(
            [rng.uniform(0, 50),       # 60% — same area
             rng.uniform(50, 300),     # 20% — nearby city
             rng.uniform(300, 800),    # 12% — domestic travel
             rng.uniform(800, 3000),   # 5%  — far/cross-country
             rng.uniform(3000, 15000)],# 3%  — international
            p=[0.60, 0.20, 0.12, 0.05, 0.03]
        )
        curr_lat, curr_lon = random_location_at_distance(usual_lat, usual_lon, loc_km)
        loc_dev = haversine_km(usual_lat, usual_lon, curr_lat, curr_lon)

        # ── Device ──────────────────────────────────────────────────────────
        new_device = int(rng.random() < 0.12)  # 12% new device overall

        # ── Hour ────────────────────────────────────────────────────────────
        hour = rng.choice(
            [rng.randint(0, 6),    # 10% night
             rng.randint(6, 23)],  # 90% day
            p=[0.10, 0.90]
        )

        # ── Velocity ────────────────────────────────────────────────────────
        v15 = rng.choice(
            [0, 1,
             rng.randint(2, 5),
             rng.randint(5, 12),
             rng.randint(12, 22)],
            p=[0.55, 0.25, 0.12, 0.05, 0.03]
        )

        # ── Suspicion score ──────────────────────────────────────────────────
        score = _suspicion_score(amt_ratio, loc_dev, new_device, hour, v15)

        # Add noise — prevents the model from learning a hard threshold
        score += rng.normal(0, 0.04)
        score  = float(np.clip(score, 0, 1))

        rows.append({
            "transaction_amount":      txn_amount,
            "transaction_hour":        hour,
            "device_id_match":         1 - new_device,
            "sender_avg_txn_amount":   sender_avg,
            "sender_usual_lat":        usual_lat,
            "sender_usual_lon":        usual_lon,
            "current_txn_lat":         curr_lat,
            "current_txn_lon":         curr_lon,
            "location_deviation_km":   loc_dev,
            "amount_deviation_ratio":  amt_ratio,
            "transactions_last_15min": v15,
            "_score":                  score,
        })

    # ── Add explicit high-velocity-on-known-device fraud examples ──────────
    # These are account drain attacks where hacker has both credentials AND
    # the device (e.g. stolen phone). Score-based labelling undersells this
    # because known device normally scores low. We inject ~200 explicit examples.
    n_vel_fraud = int(n_samples * fraud_ratio * 0.15)
    rng2 = np.random.RandomState(random_state + 99)
    for _ in range(n_vel_fraud):
        sender_avg = min(rng2.exponential(1500) + 200, 80000)
        usual_lat, usual_lon = random_india_location()
        amt_ratio  = rng2.uniform(1.5, 6.0)
        txn_amount = min(sender_avg * amt_ratio, 500000)
        loc_km     = rng2.uniform(0, 200)
        curr_lat, curr_lon = random_location_at_distance(usual_lat, usual_lon, loc_km)
        rows_extra = {
            "transaction_amount":      txn_amount,
            "transaction_hour":        rng2.randint(0, 24),
            "device_id_match":         rng2.choice([0, 1], p=[0.3, 0.7]),
            "sender_avg_txn_amount":   sender_avg,
            "sender_usual_lat":        usual_lat,
            "sender_usual_lon":        usual_lon,
            "current_txn_lat":         curr_lat,
            "current_txn_lon":         curr_lon,
            "location_deviation_km":   haversine_km(usual_lat, usual_lon, curr_lat, curr_lon),
            "amount_deviation_ratio":  amt_ratio,
            "transactions_last_15min": rng2.randint(8, 22),   # always high velocity
            "_score":                  0.95,                   # forced fraud score
        }
        rows.append(rows_extra)

    df = pd.DataFrame(rows)

    # ── Label based on score threshold ──────────────────────────────────────
    # Find threshold that gives exactly the desired fraud_ratio
    threshold = df["_score"].quantile(1 - fraud_ratio)
    df["label"] = (df["_score"] >= threshold).astype(int)

    # ── Sample to exact n_samples, preserving fraud ratio ───────────────────
    fraud_df = df[df.label == 1].sample(
        int(n_samples * fraud_ratio), random_state=random_state, replace=False)
    legit_df = df[df.label == 0].sample(
        n_samples - int(n_samples * fraud_ratio), random_state=random_state, replace=False)
    df = pd.concat([fraud_df, legit_df]).sample(
        frac=1, random_state=random_state).reset_index(drop=True)

    df = df.drop(columns=["_score"])

    # ── Missing values (~2% GPS dropout) ───────────────────────────────────
    for col in ["location_deviation_km", "current_txn_lat", "current_txn_lon"]:
        mask = np.random.RandomState(random_state).rand(len(df)) < 0.02
        df.loc[mask, col] = np.nan

    # ── Diagnostics ──────────────────────────────────────────────────────────
    fraud = df[df.label == 1]
    legit = df[df.label == 0]
    print(f"[DataGen] Rows: {len(df)} | Fraud: {df['label'].sum()} ({df['label'].mean()*100:.1f}%)")
    print(f"\n[DataGen] Feature ranges — fraud vs legit (OVERLAP IS INTENTIONAL):")
    for c in ["amount_deviation_ratio", "location_deviation_km",
              "transactions_last_15min"]:
        fm = f"{fraud[c].min():.1f}–{fraud[c].max():.1f}"
        lm = f"{legit[c].min():.1f}–{legit[c].max():.1f}"
        print(f"  {c:<35} fraud={fm:<20} legit={lm}")
    mv = df.isnull().sum(); mv = mv[mv > 0]
    if len(mv):
        print(f"\n[DataGen] Missing: {dict(mv)}")
    print()
    return df


if __name__ == "__main__":
    df = generate_transaction_dataset()
    df.to_csv("transactions.csv", index=False)
    print("Saved → transactions.csv")