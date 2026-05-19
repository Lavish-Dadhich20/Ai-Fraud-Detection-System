"""
api_v2.py  — VoidGuard FastAPI Backend (v3 — ML Model Integrated)
------------------------------------------------------------------
Run:  uvicorn api_v2:app --host 0.0.0.0 --port 8000 --reload

SETUP BEFORE RUNNING:
  1. Place xgboost.joblib and preprocessor.joblib in a folder called 'models/'
     (same directory as this file)
     e.g.  mkdir models && cp xgboost.joblib models/ && cp preprocessor.joblib models/
  2. Install deps:
     pip install fastapi uvicorn pymongo pydantic joblib scikit-learn numpy pandas

Endpoints:
  GET  /health                       → health check
  GET  /users                        → all users from MongoDB
  GET  /users/{user_id}              → single user profile
  POST /users                        → add new user to MongoDB
  GET  /recipients                   → all recipients
  POST /recipients                   → add new recipient
  GET  /transactions                 → all fraud log transactions
  POST /predict                      → run ML model + save result to MongoDB
  POST /transactions/{id}/respond    → save user response (yes/no) + police flag
  GET  /stats                        → dashboard stats from MongoDB
  POST /seed                         → seed initial data (run once)
  POST /send-email                   → send email via Gmail SMTP
"""

import time
import uuid
import math
import random
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pymongo import MongoClient, DESCENDING
from bson import ObjectId
from predict import predict_transaction
import os
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
client    = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db        = client["fraud_db"]

users_col        = db["users"]
recipients_col   = db["recipients"]
transactions_col = db["transactions"]



# Load Gmail credentials from .env
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_PASS")

app = FastAPI(title="VoidGuard API", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def fix_id(doc):
    """Convert ObjectId/_id to string so JSON serializes cleanly."""
    if doc is None:
        return None
    doc = dict(doc)
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc



class UserCreate(BaseModel):
    _id: Optional[str] = None
    name: str
    bank: str
    branch: str
    ifsc: str
    account: str
    pan: str
    aadhaar: str
    phone: str
    email: str
    address: str
    avg_txn_amount: float
    usual_location: str
    known_devices: List[str] = []


class RecipientCreate(BaseModel):
    account_number: str
    name: str
    bank: str
    branch: str
    ifsc: str
    pan: str
    address: str
    avg_inflow: float
    total_transactions: int = 0


class UserResponse(BaseModel):
    transaction_id: str
    user_response: str  
    status: str        


class EmailRequest(BaseModel):
    to: List[str]
    subject: str
    html: str



@app.get("/health")
def health():
    return {"status": "ok", "version": "3.0", "model": "xgboost"}


@app.get("/users")
def get_all_users():
    users = [fix_id(u) for u in users_col.find()]
    return {"users": users, "count": len(users)}


@app.get("/users/{user_id}")
def get_user(user_id: str):
    u = users_col.find_one({"_id": user_id})
    if not u:
        raise HTTPException(404, f"User '{user_id}' not found")
    return fix_id(u)


@app.post("/users")
def create_user(user: UserCreate):
    doc = user.dict()
    uid = doc.pop("_id", None) or f"user_{int(time.time())}"
    doc["_id"] = uid
    doc["created_at"] = datetime.datetime.utcnow().isoformat()
    users_col.replace_one({"_id": uid}, doc, upsert=True)
    return {"message": "User saved", "user_id": uid}

 
@app.get("/recipients")
def get_all_recipients():
    recs = [fix_id(r) for r in recipients_col.find()]
    return {"recipients": recs, "count": len(recs)}


@app.post("/recipients")
def create_recipient(rec: RecipientCreate):
    doc = rec.dict()
    acc = doc["account_number"]
    doc["created_at"] = datetime.datetime.utcnow().isoformat()
    recipients_col.replace_one({"account_number": acc}, doc, upsert=True)
    return {"message": "Recipient saved", "account_number": acc}

@app.get("/transactions")
def get_transactions(limit: int = 200, status: str = None):
    query = {}
    if status and status != "all":
        query["status"] = status.upper()
    txns = [fix_id(t) for t in
            transactions_col.find(query).sort("timestamp", DESCENDING).limit(limit)]
    return {"transactions": txns, "count": len(txns)}


@app.post("/transactions/{txn_id}/respond")
def user_respond(txn_id: str, body: UserResponse):
    update = {
        "user_response": body.user_response,
        "final_status":  body.status,
        "responded_at":  datetime.datetime.utcnow().isoformat(),
    }
    if body.user_response == "yes_its_me":
        update["status"] = "SAFE"
        update["label"]  = 0
    elif body.user_response == "not_me":
        update["status"]       = "FRAUD"
        update["police_filed"] = True
        update["case_number"]  = (
            f"CYB-{datetime.datetime.utcnow().year}-{int(time.time()) % 90000 + 10000}"
        )
    transactions_col.update_one({"transaction_id": txn_id}, {"$set": update})
    return {"message": "Response recorded", "transaction_id": txn_id, **update}



@app.post("/predict")
def predict(
    user_id: str,
    transaction_amount: float,
    transaction_hour: int,
    current_txn_location: str,
    device_id: str,
    transactions_last_15min: int,
    recipient_avg_inflow: float = 2000.0,
    recipient_txn_history_count: int = 100,
):
    """
    Main fraud prediction endpoint.

    1. Fetches sender profile from MongoDB
    2. Checks device match
    3. Builds feature dict for predict_transaction() — uses the 7-feature XGBoost model
    4. Runs ML model via predict.py
    5. Saves full result to MongoDB transactions collection
    6. Returns prediction + metadata to the frontend

    Note: recipient_avg_inflow and recipient_txn_history_count are stored in MongoDB
    for audit/display purposes but are NOT used by the ML model (which uses only
    the 7 sender-side features trained in train_model.py).
    """

    sender = users_col.find_one({"_id": user_id})
    if not sender:
        raise HTTPException(404, f"User '{user_id}' not found in MongoDB")

    device_match = 1 if device_id in sender.get("known_devices", []) else 0

    txn_for_model = {
        "transaction_amount":      transaction_amount,
        "transaction_hour":        transaction_hour,
        "device_id_match":         device_match,
        "sender_avg_txn_amount":   sender["avg_txn_amount"],
        "transactions_last_15min": transactions_last_15min,
    }

    if "usual_lat" in sender and "usual_lon" in sender:
        txn_for_model["sender_usual_lat"] = sender["usual_lat"]
        txn_for_model["sender_usual_lon"] = sender["usual_lon"]
    else:
        txn_for_model["sender_usual_location"] = sender["usual_location"]

    txn_for_model["current_txn_location"] = current_txn_location

    t0 = time.time()
    try:
        result = predict_transaction(txn_for_model, model_name="xgboost", threshold=0.5)
    except FileNotFoundError:
        raise HTTPException(
            503,
            detail=(
                "Model files not found. "
                "Ensure models/xgboost.joblib and models/preprocessor.joblib exist. "
                "Run: python main.py  to train and save the model."
            ),
        )
    except ValueError as e:
        raise HTTPException(422, detail=str(e))
    latency = round((time.time() - t0) * 1000, 2)

    prob   = result.get("fraud_probability", 0)
    label  = result.get("label", 0)
    status = "FRAUD" if label == 1 else ("REVIEW" if prob > 0.4 else "SAFE")

    txn_id = "TXN_" + uuid.uuid4().hex[:8].upper()
    log_doc = {
        "transaction_id":               txn_id,
        "user_id":                      user_id,
        "user_name":                    sender.get("name", user_id),
        "transaction_amount":           transaction_amount,
        "transaction_hour":             transaction_hour,
        "current_txn_location":         current_txn_location,
        "usual_location":               sender.get("usual_location", ""),
        "device_id":                    device_id,
        "device_match":                 device_match,
        "transactions_last_15min":      transactions_last_15min,
        "recipient_avg_inflow":         recipient_avg_inflow,
        "recipient_txn_history_count":  recipient_txn_history_count,
        "fraud_probability":            prob,
        "status":                       status,
        "label":                        label,
        "risk_factors":                 result.get("risk_factors", []),
        "location_deviation_km":        result.get("location_deviation_km", 0),
        "amount_deviation_ratio":       result.get("amount_deviation_ratio", 0),
        "confidence":                   result.get("confidence", ""),
        "usual_location_resolved":      result.get("usual_location", ""),
        "current_location_resolved":    result.get("current_location", ""),
        "latency_ms":                   latency,
        "timestamp":                    datetime.datetime.utcnow().isoformat(),
        "user_response":                None,
        "police_filed":                 False,
    }
    transactions_col.insert_one(log_doc)
    log_doc.pop("_id", None)


    return {
        **result,
        "transaction_id": txn_id,
        "status":         status,
        "latency_ms":     latency,
    }



@app.get("/stats")
def get_stats():
    total  = transactions_col.count_documents({})
    fraud  = transactions_col.count_documents({"status": "FRAUD"})
    review = transactions_col.count_documents({"status": "REVIEW"})
    safe   = transactions_col.count_documents({"status": "SAFE"})
    pipeline = [{"$group": {"_id": None, "avg_lat": {"$avg": "$latency_ms"}}}]
    avg_lat_res = list(transactions_col.aggregate(pipeline))
    avg_lat = round(avg_lat_res[0]["avg_lat"], 1) if avg_lat_res else 0
    return {
        "total": total, "fraud": fraud,
        "review": review, "safe": safe,
        "avg_latency_ms": avg_lat,
    }



@app.post("/seed")
def seed_database():
    """Seed MongoDB with 3 users, 3 recipients, and 500 realistic test transactions."""

    users_col.delete_many({})
    users_col.insert_many([
        {
            "_id": "user_001", "name": "Rahul Sharma", "bank": "HDFC Bank",
            "branch": "Udaipur Main", "ifsc": "HDFC0001234", "account": "XXXX XXXX 4321",
            "pan": "ABCPS1234R", "aadhaar": "XXXX-XXXX-1234", "phone": "98XX-XXXX-12",
            "email": "rahul.s@email.com",
            "address": "12 Lake View Colony, Udaipur, Rajasthan 313001",
            "avg_txn_amount": 2000, "usual_location": "Udaipur",
            "usual_lat": 24.5854, "usual_lon": 73.7125,
            "known_devices": ["device_abc123", "device_xyz789"],
            "total_transactions": 342, "created_at": "2022-03-15T10:30:00Z",
        },
        {
            "_id": "user_002", "name": "Priya Mehta", "bank": "ICICI Bank",
            "branch": "Bandra West", "ifsc": "ICICI0005678", "account": "XXXX XXXX 8765",
            "pan": "CDEFS5678K", "aadhaar": "XXXX-XXXX-5678", "phone": "91XX-XXXX-56",
            "email": "priya.m@email.com",
            "address": "45 Sea View Apartments, Bandra, Mumbai, Maharashtra 400050",
            "avg_txn_amount": 8000, "usual_location": "Mumbai",
            "usual_lat": 19.0760, "usual_lon": 72.8777,
            "known_devices": ["device_def456"],
            "total_transactions": 521, "created_at": "2021-07-22T09:15:00Z",
        },
        {
            "_id": "user_003", "name": "Arjun Patel", "bank": "State Bank of India",
            "branch": "Navrangpura", "ifsc": "SBIN0009012", "account": "XXXX XXXX 2109",
            "pan": "GHIJK9012P", "aadhaar": "XXXX-XXXX-9012", "phone": "79XX-XXXX-90",
            "email": "arjun.p@email.com",
            "address": "7 Commerce House, Navrangpura, Ahmedabad, Gujarat 380009",
            "avg_txn_amount": 1200, "usual_location": "Ahmedabad",
            "usual_lat": 23.0225, "usual_lon": 72.5714,
            "known_devices": ["device_ghi789"],
            "total_transactions": 198, "created_at": "2023-01-10T14:45:00Z",
        },
    ])

    
    recipients_col.delete_many({})
    recipients_col.insert_many([
        {
            "account_number": "SBI0001", "name": "Vikram Singh",
            "bank": "State Bank of India", "branch": "Jaipur Central",
            "ifsc": "SBIN0001001", "account": "XXXX XXXX 1001", "pan": "LMNOP1001Q",
            "address": "22 MI Road, Jaipur, Rajasthan 302001",
            "avg_inflow": 2000, "total_transactions": 450,
        },
        {
            "account_number": "SBI0002", "name": "Unknown / Mule Account",
            "bank": "State Bank of India", "branch": "Unknown Branch",
            "ifsc": "SBIN0002002", "account": "XXXX XXXX 2002", "pan": "NOT REGISTERED",
            "address": "Address not verified",
            "avg_inflow": 300, "total_transactions": 4,
        },
        {
            "account_number": "HDFC001", "name": "Meera Nair",
            "bank": "HDFC Bank", "branch": "Koregaon Park",
            "ifsc": "HDFC0003003", "account": "XXXX XXXX 3003", "pan": "QRSTU3003V",
            "address": "99 Koregaon Park, Pune, Maharashtra 411001",
            "avg_inflow": 15000, "total_transactions": 1200,
        },
    ])

    transactions_col.delete_many({})
    random.seed(42)

    INDIA_CITIES = [
        ("Udaipur",   24.5854, 73.7125), ("Mumbai",    19.0760, 72.8777),
        ("Delhi",     28.6139, 77.2090), ("Jaipur",    26.9124, 75.7873),
        ("Bangalore", 12.9716, 77.5946), ("Hyderabad", 17.3850, 78.4867),
        ("Chennai",   13.0827, 80.2707), ("Kolkata",   22.5726, 88.3639),
        ("Pune",      18.5204, 73.8567), ("Ahmedabad", 23.0225, 72.5714),
        ("Indore",    22.7196, 75.8577), ("Bhopal",    23.2599, 77.4126),
        ("Lucknow",   26.8467, 80.9462), ("Noida",     28.5355, 77.3910),
        ("Jodhpur",   26.2389, 73.0243), ("Surat",     21.1702, 72.8311),
        ("Kota",      25.2138, 75.8648), ("Ajmer",     26.4499, 74.6399),
        ("Chandigarh",30.7333, 76.7794), ("Nagpur",    21.1458, 79.0882),
        ("Pali",      25.7717, 73.3236), ("Bhilwara",  25.4709, 74.6961),
    ]
    FRAUD_TYPES = ["credential_theft", "money_mule", "velocity_attack", "location_anomaly"]

    def haversine(lat1, lon1, lat2, lon2):
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2
             + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
             * math.sin(dlon / 2) ** 2)
        return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 1)

    usual_lat, usual_lon = 24.5854, 73.7125   
    usual_avg = 2000
    batch = []
    fraud_count = 0

    for i in range(500):
        is_fraud = (i % 10 == 0)
        city_name, city_lat, city_lon = random.choice(INDIA_CITIES)
        dist = haversine(usual_lat, usual_lon, city_lat, city_lon)

        if is_fraud:
            fraud_count += 1
            ftype  = FRAUD_TYPES[fraud_count % 4]
            amount = round(random.uniform(usual_avg * 10, usual_avg * 40), 2)
            hour   = random.randint(0, 5)
            v15    = random.randint(6, 18) if ftype == "velocity_attack" else random.randint(0, 2)
            device = "device_unknown_" + str(random.randint(1000, 9999))
            prob   = round(random.uniform(0.72, 0.99), 4)
            status = "FRAUD"
            risk_factors = []
            if dist > 500:
                risk_factors.append(f"Location: {dist} km from usual — HIGH")
            risk_factors.append(f"Amount spike: {round(amount / usual_avg, 1)}x avg — VERY HIGH")
            if v15 > 5:
                risk_factors.append(f"Velocity: {v15} txns in 15 min — ACCOUNT DRAIN")
            if "unknown" in device:
                risk_factors.append("Unknown device — not registered")
            if hour <= 5:
                risk_factors.append(f"Unusual hour: {str(hour).zfill(2)}:00 — late night")
        else:
            amount     = round(random.uniform(usual_avg * 0.2, usual_avg * 2.5), 2)
            hour       = random.randint(7, 22)
            v15        = random.randint(0, 1)
            device     = random.choice(["device_abc123", "device_xyz789"])
            city_name  = random.choice(["Udaipur", "Jaipur", "Ajmer", "Kota", "Jodhpur"])
            city_info2 = next((c for c in INDIA_CITIES if c[0] == city_name), INDIA_CITIES[0])
            city_lat, city_lon = city_info2[1], city_info2[2]
            dist         = haversine(usual_lat, usual_lon, city_lat, city_lon)
            prob         = round(random.uniform(0.02, 0.25), 4)
            status       = "SAFE"
            risk_factors = ["No major risk factors"]

        ts = datetime.datetime.utcnow() - datetime.timedelta(
            days=random.randint(0, 30),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )
        batch.append({
            "transaction_id":               f"TXN_{i + 1:04d}",
            "user_id":                      "user_001",
            "user_name":                    "Rahul Sharma",
            "transaction_amount":           amount,
            "transaction_hour":             hour,
            "current_txn_location":         city_name,
            "usual_location":               "Udaipur",
            "device_id":                    device,
            "device_match":                 1 if device in ["device_abc123", "device_xyz789"] else 0,
            "transactions_last_15min":      v15,
            "recipient_avg_inflow":         random.choice([2000, 300, 15000]),
            "recipient_txn_history_count":  random.randint(4, 1200),
            "fraud_probability":            prob,
            "status":                       status,
            "label":                        1 if status == "FRAUD" else 0,
            "risk_factors":                 risk_factors,
            "location_deviation_km":        dist,
            "amount_deviation_ratio":       round(amount / usual_avg, 2),
            "confidence":                   "HIGH" if prob >= 0.8 or prob <= 0.2 else "MEDIUM",
            "latency_ms":                   round(random.uniform(18, 48), 1),
            "timestamp":                    ts.isoformat(),
            "user_response":                None,
            "police_filed":                 False,
        })

    transactions_col.insert_many(batch)

    return {
        "message":            "Database seeded successfully",
        "users":              3,
        "recipients":         3,
        "transactions":       len(batch),
        "fraud_transactions": fraud_count,
    }



@app.post("/send-email")
def send_email(body: EmailRequest):
    """Send email via Gmail SMTP."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = body.subject
        msg["From"]    = f"VoidGuard AI <{GMAIL_USER}>"
        msg["To"]      = ", ".join(body.to)
        msg.attach(MIMEText(body.html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, body.to, msg.as_string())

        print(f"[Email] ✓ Sent to {body.to}")
        return {"success": True, "to": body.to}

    except smtplib.SMTPAuthenticationError:
        raise HTTPException(
            401,
            detail="Gmail auth failed — check GMAIL_USER and GMAIL_PASS (use App Password)",
        )
    except smtplib.SMTPException as e:
        raise HTTPException(500, detail=f"SMTP error: {e}")
    except Exception as e:
        raise HTTPException(500, detail=f"Email error: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_v2:app", host="0.0.0.0", port=8000, reload=True)
    