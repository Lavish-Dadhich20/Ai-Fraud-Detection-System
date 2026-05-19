from data_generator import generate_transaction_dataset
from preprocessing  import preprocess, NUMERICAL_FEATURES
from train_model    import apply_smote, train_logistic_regression, train_xgboost, save_model
from evaluate_model import evaluate_model, plot_feature_importance
from predict        import predict_transaction


def main():
    print("\n" + "="*60)
    print("   FRAUD DETECTION v6 â€” SENDER-ONLY FEATURES")
    print("="*60 + "\n")

    print("STEP 1 â€” Generating dataâ€¦\n")
    df = generate_transaction_dataset(n_samples=30000, fraud_ratio=0.05)

    print("STEP 2 â€” Preprocessingâ€¦\n")
    X_train, X_test, y_train, y_test, preprocessor = preprocess(df)

    print("STEP 3 â€” Oversamplingâ€¦\n")
    X_sm, y_sm = apply_smote(X_train, y_train)

    print("STEP 4A â€” Logistic Regressionâ€¦\n")
    lr = train_logistic_regression(X_sm, y_sm)
    save_model(lr, "logistic_regression")

    print("STEP 4B â€” Gradient Boostingâ€¦\n")
    gb = train_xgboost(X_sm, y_sm)
    save_model(gb, "xgboost")

    print("STEP 5 â€” Evaluationâ€¦\n")
    lr_m = evaluate_model(lr, X_test, y_test, model_name="Logistic Regression")
    gb_m = evaluate_model(gb, X_test, y_test, model_name="Gradient Boosting")

    print("\nðŸ“Š COMPARISON")
    print(f"{'Metric':<25} {'LR':>10} {'GBM':>10}")
    print("-" * 48)
    for k in ["roc_auc", "pr_auc", "recall", "f1"]:
        print(f"  {k:<23} {lr_m[k]:>10.4f} {gb_m[k]:>10.4f}")

    print("\nSTEP 6 â€” Feature importanceâ€¦\n")
    plot_feature_importance(gb, NUMERICAL_FEATURES, model_name="Gradient_Boosting")
    plot_feature_importance(lr, NUMERICAL_FEATURES, model_name="Logistic_Regression")

    print("\nSTEP 7 â€” Sample predictionsâ€¦\n")
    samples = [
        ("CREDENTIAL THEFT â€” new device, 12000 km away, 3am, 40x spike", {
            "transaction_amount":      80000,
            "transaction_hour":        3,
            "device_id_match":         0,
            "sender_avg_txn_amount":   2000,
            "sender_usual_lat":        24.57, "sender_usual_lon": 73.68,
            "current_txn_lat":         40.71, "current_txn_lon": -74.00,
            "transactions_last_15min": 1,
        }),
        ("NORMAL PAYMENT â€” â‚¹1800 UPI, same city, known device", {
            "transaction_amount":      1800,
            "transaction_hour":        14,
            "device_id_match":         1,
            "sender_avg_txn_amount":   1500,
            "sender_usual_location":   "delhi",
            "current_txn_location":    "delhi",
            "transactions_last_15min": 0,
        }),
        ("VELOCITY DRAIN â€” 12 txns in 15 min, new device", {
            "transaction_amount":      4000,
            "transaction_hour":        11,
            "device_id_match":         0,
            "sender_avg_txn_amount":   3000,
            "sender_usual_location":   "mumbai",
            "current_txn_location":    "mumbai",
            "transactions_last_15min": 12,
        }),
        ("STEALTH FRAUD â€” 4 moderate signals combined", {
            "transaction_amount":      8000,
            "transaction_hour":        3,
            "device_id_match":         0,
            "sender_avg_txn_amount":   2000,
            "sender_usual_location":   "jaipur",
            "current_txn_location":    "bhopal",
            "transactions_last_15min": 3,
        }),
        ("TRAVEL EDGE CASE â€” 800km but legit (known device, normal amount)", {
            "transaction_amount":      2000,
            "transaction_hour":        15,
            "device_id_match":         1,
            "sender_avg_txn_amount":   1800,
            "sender_usual_location":   "delhi",
            "current_txn_location":    "bengaluru",
            "transactions_last_15min": 0,
        }),
    ]

    for name, txn in samples:
        r    = predict_transaction(txn, model_name="xgboost")
        icon = "FRAUD" if r["label"] == 1 else "LEGIT"
        print(f"  [{icon}] {name}")
        print(f"         prob={r['fraud_probability']:.4f}  "
              f"amt_dev={r['amount_deviation_ratio']}x  "
              f"loc={r['location_deviation_km']} km")
        for f in r["risk_factors"]:
            print(f"         â€¢ {f}")
        print()

    print("âœ… Done. Run 'python test_prediction.py' to test interactively.\n")


if __name__ == "__main__":
    main()
