
import joblib
import numpy as np
from math import radians, sin, cos, sqrt, atan2

_model      = None
_model_name = None


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def _get_model(model_name="xgboost"):
    global _model, _model_name
    if _model is None or _model_name != model_name:
        _model = joblib.load(f"models/{model_name}.joblib")
        _model_name = model_name
        print(f"[Predict] Model '{model_name}' loaded.")
    return _model


def _resolve_coords(transaction: dict) -> tuple:
    """
    Extract (usual_lat, usual_lon, curr_lat, curr_lon) from the transaction dict.

    Supports two input modes:
      Mode A — city/state name strings:
        sender_usual_location = "Udaipur"
        current_txn_location  = "New York"   ← will fail gracefully (not in DB)

      Mode B — raw lat/lon floats:
        sender_usual_lat = 24.58
        sender_usual_lon = 73.71
        current_txn_lat  = 40.71
        current_txn_lon  = -74.00

    Returns (usual_lat, usual_lon, curr_lat, curr_lon, usual_display, curr_display)
    """
    from geo_lookup import resolve_location

    # ── Usual location ─────────────────────────────────────────────────────
    if "sender_usual_location" in transaction:
        u_lat, u_lon, u_name = resolve_location(transaction["sender_usual_location"])
    elif "sender_usual_lat" in transaction and "sender_usual_lon" in transaction:
        u_lat  = transaction["sender_usual_lat"]
        u_lon  = transaction["sender_usual_lon"]
        u_name = f"{u_lat:.4f}, {u_lon:.4f}"
    else:
        return None, None, None, None, "unknown", "unknown"

    # ── Current location ───────────────────────────────────────────────────
    if "current_txn_location" in transaction:
        c_lat, c_lon, c_name = resolve_location(transaction["current_txn_location"])
    elif "current_txn_lat" in transaction and "current_txn_lon" in transaction:
        c_lat  = transaction["current_txn_lat"]
        c_lon  = transaction["current_txn_lon"]
        c_name = f"{c_lat:.4f}, {c_lon:.4f}"
    else:
        return u_lat, u_lon, u_lat, u_lon, u_name, u_name   # same = 0 km

    return u_lat, u_lon, c_lat, c_lon, u_name, c_name


def _location_flag(km: float) -> str | None:
    if km <= 50:    return None
    if km <= 200:   return f"{km:.0f} km from usual — mild deviation"
    if km <= 500:   return f"{km:.0f} km from usual — moderate (different city/state)"
    if km <= 2000:  return f"{km:.0f} km from usual — HIGH (far region of India)"
    return f"{km:.0f} km from usual — VERY HIGH (likely outside India)"


def _amount_tier(ratio: float) -> str | None:
    if ratio < 5:   return None
    if ratio < 10:  return f"{ratio:.1f}x avg — mild spike (5–10x)"
    if ratio < 15:  return f"{ratio:.1f}x avg — moderate spike (10–15x)"
    if ratio < 20:  return f"{ratio:.1f}x avg — HIGH spike (15–20x)"
    return f"{ratio:.1f}x avg — VERY HIGH spike (20x+)"


def _velocity_flag(v15: int) -> str | None:
    if v15 <= 1:  return None
    if v15 <= 3:  return f"{v15} transactions in last 15 min — slightly elevated"
    if v15 <= 6:  return f"{v15} transactions in last 15 min — suspicious velocity"
    return f"{v15} transactions in last 15 min — ACCOUNT DRAIN pattern"


def _build_risk_factors(txn: dict, computed: dict) -> list:
    flags = []

    f = _amount_tier(computed.get("amount_deviation_ratio", 0))
    if f: flags.append(f"Amount spike: {f}")

    if txn.get("device_id_match", 1) == 0:
        flags.append("Unknown / new device — not sender's registered device")

    f = _location_flag(computed.get("location_deviation_km", 0))
    if f: flags.append(f"Location: {f}")

    f = _velocity_flag(txn.get("transactions_last_15min", 0))
    if f: flags.append(f"Velocity: {f}")

    h = txn.get("transaction_hour", 12)
    if 0 <= h <= 5:
        flags.append(f"Unusual hour: {h:02d}:00 (late night / early morning)")

    if not flags:
        flags.append("No significant risk factors detected")
    return flags


def predict_transaction(
    transaction: dict,
    model_name: str = "xgboost",
    threshold: float = 0.5,
) -> dict:
   
    from preprocessing import preprocess_single

    computed = dict(transaction)

    # ── Resolve locations ──────────────────────────────────────────────────
    u_lat, u_lon, c_lat, c_lon, u_name, c_name = _resolve_coords(transaction)

    if u_lat is not None and c_lat is not None:
        computed["location_deviation_km"] = haversine_km(u_lat, u_lon, c_lat, c_lon)
        # Store resolved names back for display
        computed["_usual_location_name"]   = u_name
        computed["_current_location_name"] = c_name
    else:
        computed["location_deviation_km"]  = 0.0
        computed["_usual_location_name"]   = "unknown"
        computed["_current_location_name"] = "unknown"

    # ── Derived ratios ─────────────────────────────────────────────────────
    sender_avg = max(transaction.get("sender_avg_txn_amount", 1), 1)
    computed["amount_deviation_ratio"] = transaction["transaction_amount"] / sender_avg

    # ── Model inference ────────────────────────────────────────────────────
    X          = preprocess_single(computed)
    model      = _get_model(model_name)
    fraud_prob = float(model.predict_proba(X)[0][1])
    label      = int(fraud_prob >= threshold)

    if fraud_prob >= 0.80 or fraud_prob <= 0.20:
        confidence = "HIGH"
    elif fraud_prob >= 0.60 or fraud_prob <= 0.40:
        confidence = "MEDIUM"
    else:
        confidence = "LOW — borderline, recommend manual review"

    return {
        "prediction":               "Fraud" if label == 1 else "Not Fraud",
        "label":                    label,
        "fraud_probability":        round(fraud_prob, 4),
        "confidence":               confidence,
        "threshold_used":           threshold,
        "risk_factors":             _build_risk_factors(transaction, computed),
        "amount_deviation_ratio":   round(computed["amount_deviation_ratio"], 2),
        "location_deviation_km":    round(computed["location_deviation_km"], 1),
        "usual_location":           computed["_usual_location_name"],
        "current_location":         computed["_current_location_name"],
    }