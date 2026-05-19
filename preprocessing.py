"""
preprocessing.py  (v6 — 7 clean features, no recipient columns)
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
import joblib, os

NUMERICAL_FEATURES = [
    "transaction_amount",        # raw INR — gives model absolute scale
    "transaction_hour",          # 0-23
    "device_id_match",           # 0 or 1
    "sender_avg_txn_amount",     # historical average
    "location_deviation_km",     # computed from lat/lon
    "amount_deviation_ratio",    # txn / sender_avg
    "transactions_last_15min",   # velocity
]

DROP_FEATURES = [
    "sender_usual_lat", "sender_usual_lon",
    "current_txn_lat",  "current_txn_lon",
]

TARGET = "label"


def load_data(filepath="transactions.csv"):
    df = pd.read_csv(filepath)
    print(f"[Load] {len(df)} rows from '{filepath}'")
    return df


def build_preprocessor():
    pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler",  StandardScaler()),
    ])
    return ColumnTransformer([("num", pipeline, NUMERICAL_FEATURES)])


def preprocess(df, test_size=0.2, random_state=42):
    df = df.drop(columns=DROP_FEATURES, errors="ignore")
    X  = df.drop(columns=[TARGET])
    y  = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, stratify=y, random_state=random_state
    )

    preprocessor = build_preprocessor()
    X_train_proc = preprocessor.fit_transform(X_train)
    X_test_proc  = preprocessor.transform(X_test)

    os.makedirs("models", exist_ok=True)
    joblib.dump(preprocessor, "models/preprocessor.joblib")
    print(f"[Preprocess] Saved → models/preprocessor.joblib")
    print(f"[Preprocess] Train: {X_train_proc.shape} | Test: {X_test_proc.shape}")
    print(f"[Preprocess] Fraud ratio — Train: {y_train.mean():.3f} | Test: {y_test.mean():.3f}\n")
    return X_train_proc, X_test_proc, y_train, y_test, preprocessor


def preprocess_single(transaction: dict, preprocessor_path="models/preprocessor.joblib"):
    preprocessor = joblib.load(preprocessor_path)
    row = {f: transaction.get(f, 0) for f in NUMERICAL_FEATURES}
    return preprocessor.transform(pd.DataFrame([row]))