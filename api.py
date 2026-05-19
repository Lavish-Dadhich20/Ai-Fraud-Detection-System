"""
api.py  (v4)
------------
Now accepts location as EITHER city/state name strings OR lat/lon floats.

Start:  uvicorn api:app --host 0.0.0.0 --port 8000 --reload
Docs:   http://localhost:8000/docs
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import time, logging, sys, os

sys.path.insert(0, os.path.dirname(__file__))
from predict import predict_transaction

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Fraud Detection API v4",
    description="Real-time Indian banking fraud scoring. Accepts city names or lat/lon for location.",
    version="4.0.0",
)


class TransactionRequest(BaseModel):
    # LIVE — from payment request
    transaction_amount:       float = Field(..., gt=0)
    transaction_hour:         int   = Field(..., ge=0, le=23)
    device_id_match:          int   = Field(..., ge=0, le=1)

    # SENDER PROFILE — from bank DB
    sender_avg_txn_amount:    float = Field(..., gt=0)
    transactions_last_15min:  int   = Field(..., ge=0)

    # Location — provide EITHER city names OR lat/lon (not both required)
    sender_usual_location:    Optional[str]   = Field(None, description="City/state name e.g. 'Udaipur'")
    current_txn_location:     Optional[str]   = Field(None, description="City/state name e.g. 'Kerala'")
    sender_usual_lat:         Optional[float] = Field(None, description="Latitude (alternative to city name)")
    sender_usual_lon:         Optional[float] = Field(None, description="Longitude (alternative to city name)")
    current_txn_lat:          Optional[float] = Field(None)
    current_txn_lon:          Optional[float] = Field(None)

    model_name: str   = Field("xgboost")
    threshold:  float = Field(0.5, ge=0.0, le=1.0)

    model_config = {
        "json_schema_extra": {
            "example": {
                "transaction_amount": 80000,
                "transaction_hour": 3,
                "device_id_match": 0,
                "sender_avg_txn_amount": 2000,
                "transactions_last_15min": 1,
                "sender_usual_location": "Udaipur",
                "current_txn_location": "New York",

                "model_name": "xgboost",
                "threshold": 0.5,
            }
        }
    }


class PredictionResponse(BaseModel):
    prediction:             str
    label:                  int
    fraud_probability:      float
    confidence:             str
    threshold_used:         float
    risk_factors:           list[str]
    amount_deviation_ratio: float
    location_deviation_km:  float
    usual_location:         str
    current_location:       str
    latency_ms:             float


@app.get("/health")
def health():
    return {"status": "ok", "version": "4.0.0"}


@app.get("/locations")
def list_locations():
    """Return all supported city/state names for location lookup."""
    from geo_lookup import list_all_locations
    locs = list_all_locations()
    return {"count": len(locs), "locations": locs}


@app.post("/predict", response_model=PredictionResponse)
def predict(request: TransactionRequest):
    """
    Score a single transaction for fraud.
    Provide location as city name strings OR lat/lon — both work.
    """
    t0 = time.perf_counter()
    try:
        result = predict_transaction(
            transaction=request.model_dump(exclude={"model_name", "threshold"}, exclude_none=True),
            model_name=request.model_name,
            threshold=request.threshold,
        )
    except FileNotFoundError:
        raise HTTPException(503, detail="Model not trained. Run 'python main.py' first.")
    except ValueError as e:
        raise HTTPException(422, detail=str(e))
    except Exception as e:
        logger.exception("Prediction error")
        raise HTTPException(500, detail=str(e))

    ms = round((time.perf_counter() - t0) * 1000, 2)
    logger.info(f"₹{request.transaction_amount} → {result['prediction']} "
                f"(p={result['fraud_probability']:.3f}, {ms}ms)")
    return {**result, "latency_ms": ms}


@app.post("/predict/batch")
def predict_batch(requests: list[TransactionRequest]):
    """Score up to 100 transactions in one call."""
    if len(requests) > 100:
        raise HTTPException(400, detail="Max 100 per batch.")
    results = []
    for req in requests:
        t0 = time.perf_counter()
        r  = predict_transaction(
            transaction=req.model_dump(exclude={"model_name","threshold"}, exclude_none=True),
            model_name=req.model_name,
            threshold=req.threshold,
        )
        results.append({**r, "latency_ms": round((time.perf_counter()-t0)*1000, 2)})
    return results


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)


# ── Burst simulation endpoint ──────────────────────────────────────────────────

class BurstRequest(BaseModel):
    count:      int   = Field(20, ge=5, le=200, description="Number of transactions to simulate")
    seed:       int   = Field(42,  ge=0,        description="Random seed for reproducibility")
    model_name: str   = Field("xgboost")
    threshold:  float = Field(0.5, ge=0.0, le=1.0)


class BurstTransaction(BaseModel):
    index:       int
    type:        str
    description: str
    true_label:  int
    pred_label:  int
    probability: float
    correct:     bool
    amount:      float
    usual_location:   str
    current_location: str
    risk_factors:     list[str]


class BurstSummary(BaseModel):
    total:          int
    actual_fraud:   int
    actual_legit:   int
    detected:       int
    false_positives: int
    false_negatives: int
    accuracy:       float
    recall:         float


class BurstResponse(BaseModel):
    transactions: list[BurstTransaction]
    summary:      BurstSummary
    seed_used:    int
    latency_ms:   float


@app.post("/simulate/burst", response_model=BurstResponse, tags=["Simulation"])
def simulate_burst(request: BurstRequest):
    
    import numpy as np
    import random as _random
    from test_prediction import (
        FRAUD_TEMPLATES, LEGIT_TEMPLATES, _generate_burst_transaction
    )

    t0  = time.perf_counter()
    rng = np.random.RandomState(request.seed)

    n              = request.count
    n_fraud_target = max(1, int(n * 0.35))
    n_legit_target = n - n_fraud_target

    raw_txns = []
    for _ in range(n_fraud_target):
        tmpl       = FRAUD_TEMPLATES[rng.randint(0, len(FRAUD_TEMPLATES))]
        sender_avg = float(rng.uniform(500, 8000))
        txn, label, ttype, desc = _generate_burst_transaction(rng, sender_avg, tmpl, True)
        raw_txns.append((txn, label, ttype, desc))

    for _ in range(n_legit_target):
        tmpl       = LEGIT_TEMPLATES[rng.randint(0, len(LEGIT_TEMPLATES))]
        sender_avg = float(rng.uniform(500, 8000))
        txn, label, ttype, desc = _generate_burst_transaction(rng, sender_avg, tmpl, False)
        raw_txns.append((txn, label, ttype, desc))

    idx = list(range(len(raw_txns)))
    rng.shuffle(idx)
    raw_txns = [raw_txns[i] for i in idx]

    results = []
    for i, (txn, true_label, ttype, desc) in enumerate(raw_txns, 1):
        try:
            r = predict_transaction(txn, model_name=request.model_name,
                                    threshold=request.threshold)
        except Exception as e:
            r = {"label": 0, "fraud_probability": 0.0, "confidence": "ERROR",
                 "threshold_used": request.threshold, "risk_factors": [str(e)],
                 "amount_deviation_ratio": 0, "location_deviation_km": 0,
                 "usual_location": "", "current_location": ""}

        results.append(BurstTransaction(
            index        = i,
            type         = ttype,
            description  = desc,
            true_label   = true_label,
            pred_label   = r["label"],
            probability  = r["fraud_probability"],
            correct      = (r["label"] == true_label),
            amount       = txn.get("transaction_amount", 0),
            usual_location   = r.get("usual_location", ""),
            current_location = r.get("current_location", ""),
            risk_factors     = r.get("risk_factors", []),
        ))

    total      = len(results)
    act_fraud  = sum(1 for r in results if r.true_label  == 1)
    act_legit  = total - act_fraud
    detected   = sum(1 for r in results if r.true_label  == 1 and r.pred_label == 1)
    false_pos  = sum(1 for r in results if r.true_label  == 0 and r.pred_label == 1)
    false_neg  = sum(1 for r in results if r.true_label  == 1 and r.pred_label == 0)
    correct_n  = sum(1 for r in results if r.correct)
    accuracy   = correct_n / total * 100 if total else 0
    recall     = detected  / act_fraud * 100 if act_fraud else 0

    ms = round((time.perf_counter() - t0) * 1000, 2)
    logger.info(f"Burst: {n} txns | fraud={act_fraud} detected={detected} acc={accuracy:.1f}% {ms}ms")

    return BurstResponse(
        transactions = results,
        summary      = BurstSummary(
            total=total, actual_fraud=act_fraud, actual_legit=act_legit,
            detected=detected, false_positives=false_pos, false_negatives=false_neg,
            accuracy=round(accuracy,1), recall=round(recall,1)
        ),
        seed_used  = request.seed,
        latency_ms = ms,
    )