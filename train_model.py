

import numpy as np
import joblib
import os
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.utils import resample


def apply_smote(X_train, y_train, random_state=42):
    """Oversample minority class (fraud) to 1:1 ratio."""
    y_train = np.array(y_train)
    X_f = X_train[y_train == 1]
    X_l = X_train[y_train == 0]

    X_f_up = resample(X_f, replace=True, n_samples=len(X_l), random_state=random_state)
    X_res  = np.vstack([X_l, X_f_up])
    y_res  = np.concatenate([np.zeros(len(X_l), int), np.ones(len(X_l), int)])

    idx    = np.random.RandomState(random_state).permutation(len(y_res))
    print(f"[Oversample] Fraud: {y_train.sum()} → {y_res.sum()} | "
          f"Legit: {(y_train==0).sum()} → {(y_res==0).sum()}\n")
    return X_res[idx], y_res[idx]


def train_logistic_regression(X_train, y_train):
    print("[Train] Logistic Regression...")
    model = LogisticRegression(
        class_weight="balanced",
        solver="lbfgs",
        max_iter=1000,
        C=0.5,
        random_state=42,
    )
    model.fit(X_train, y_train)
    print("[Train] Done ✓\n")
    return model


def train_xgboost(X_train, y_train):
    
    print("[Train] Gradient Boosting...")
    model = GradientBoostingClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.04,
        subsample=0.7,
        max_features="sqrt",     # key: forces feature diversity per split
        min_samples_leaf=40,     # key: prevents single-feature memorisation
        random_state=42,
    )
    model.fit(X_train, y_train)
    print("[Train] Done ✓\n")
    return model


def save_model(model, name, folder="models"):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{name}.joblib")
    joblib.dump(model, path)
    print(f"[Save] → {path}")


def load_model(name, folder="models"):
    path = os.path.join(folder, f"{name}.joblib")
    model = joblib.load(path)
    print(f"[Load] ← {path}")
    return model