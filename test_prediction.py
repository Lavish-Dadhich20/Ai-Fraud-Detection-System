

import sys, os, time, random
import numpy as np

RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BLUE   = "\033[94m"
MAGENTA= "\033[95m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"



def banner():
    print(f"\n{BOLD}{'='*62}")
    print(f"   FRAUD DETECTION — BANK TRANSACTION SIMULATOR")
    print(f"{'='*62}{RESET}")
    print(f"{DIM}  Simulates the AI sitting at the bank server verifying payments.{RESET}\n")


def ask_float(prompt, default=None, min_val=None, max_val=None):
    while True:
        hint = f" [{default}]" if default is not None else ""
        raw  = input(f"    {CYAN}{prompt}{hint}: {RESET}").strip()
        if raw == "" and default is not None:
            return float(default)
        try:
            v = float(raw)
            if min_val is not None and v < min_val:
                print(f"      {YELLOW}Must be >= {min_val}{RESET}")
                continue
            if max_val is not None and v > max_val:
                print(f"      {YELLOW}Must be <= {max_val}{RESET}")
                continue
            return v
        except ValueError:
            print(f"      {YELLOW}Enter a number.{RESET}")


def ask_int(prompt, default=None, min_val=None, max_val=None):
    return int(ask_float(prompt, default, min_val, max_val))


def ask_yn(prompt, default=0):
    hint = "Y/n" if default == 1 else "y/N"
    while True:
        raw = input(f"    {CYAN}{prompt} ({hint}): {RESET}").strip().lower()
        if raw == "":               return default
        if raw in ("y","yes","1"):  return 1
        if raw in ("n","no","0"):   return 0
        print(f"      {YELLOW}Enter y or n.{RESET}")


def ask_location(prompt, default=None):
    from geo_lookup import resolve_location
    while True:
        hint = f" [{default}]" if default else ""
        raw  = input(f"    {CYAN}{prompt}{hint}: {RESET}").strip()
        if raw == "" and default:
            raw = default
        try:
            lat, lon, display = resolve_location(raw)
            print(f"      {DIM}→ Resolved: {display} ({lat:.4f}, {lon:.4f}){RESET}")
            return raw, lat, lon, display
        except ValueError as e:
            print(f"      {YELLOW}{e}{RESET}")


def section(title, color=BLUE):
    pad = 48 - len(title)
    print(f"\n  {color}{BOLD}── {title} {'─'*max(pad,2)}{RESET}")


# ══════════════════════════════════════════════════════════════════════════════
#  SINGLE MODE  (identical to v4 — not one character changed)
# ══════════════════════════════════════════════════════════════════════════════

def collect_transaction():
    txn = {}

    section("LIVE REQUEST  (arrives with the payment)", BLUE)
    print(f"  {DIM}What the payment app sends to the bank server.{RESET}\n")

    txn["transaction_amount"] = ask_float(
        "Transaction amount (INR)", default=1500, min_val=1)

    txn["transaction_hour"] = ask_int(
        "Hour of transaction  (0=midnight  14=2pm  23=11pm)", default=14, min_val=0, max_val=23)

    txn["device_id_match"] = ask_yn(
        "Is this the sender's known/registered device?  (y=yes  n=new device)", default=1)

    section("SENDER PROFILE  (bank looks this up)", CYAN)
    print(f"  {DIM}Historical data for the sender account.{RESET}\n")

    txn["sender_avg_txn_amount"] = ask_float(
        "Sender's average transaction amount (INR)", default=2000, min_val=1)

    print(f"\n    {DIM}Location — type any Indian city or state name.{RESET}")
    print(f"    {DIM}Examples: udaipur, kerala, mumbai, new delhi, bengaluru, rajasthan{RESET}\n")

    name, lat, lon, display = ask_location(
        "Sender's USUAL location (city/state)", default="jaipur")
    txn["sender_usual_location"] = name

    print()
    name, lat, lon, display = ask_location(
        "THIS transaction's location (city/state)", default="jaipur")
    txn["current_txn_location"] = name

    print(f"\n    {DIM}Velocity — how many transactions in the last 15 minutes:{RESET}")
    print(f"    {DIM}0–1=normal  2–3=elevated  4–6=suspicious  7+=drain alert{RESET}")
    txn["transactions_last_15min"] = ask_int(
        "Transactions in last 15 minutes", default=0, min_val=0)

    return txn


def show_result(txn, result):
    print(f"\n  {BOLD}{'─'*62}")
    print(f"  PREDICTION RESULT")
    print(f"  {'─'*60}{RESET}\n")

    if result["label"] == 1:
        print(f"  {RED}{BOLD}  ⚠   FRAUD DETECTED  ⚠{RESET}")
    else:
        print(f"  {GREEN}{BOLD}  ✓   LEGITIMATE TRANSACTION{RESET}")

    prob      = result["fraud_probability"]
    filled    = int(prob * 40)
    bar_color = RED if prob > 0.7 else (YELLOW if prob > 0.4 else GREEN)
    bar       = bar_color + "█" * filled + DIM + "░" * (40 - filled) + RESET

    print(f"\n  Fraud probability  : {bar} {prob*100:.1f}%")
    print(f"  Confidence         : {result['confidence']}")
    print(f"  Threshold used     : {result['threshold_used']}")

    print(f"\n  {BOLD}Key computed signals:{RESET}")

    dev = result["amount_deviation_ratio"]
    dc  = RED if dev >= 15 else (YELLOW if dev >= 5 else GREEN)
    print(f"    Amount deviation   : {dc}{dev:.2f}x sender's average{RESET}")

    loc = result["location_deviation_km"]
    lc  = RED if loc > 500 else (YELLOW if loc > 50 else GREEN)
    u   = result.get("usual_location", "")
    c   = result.get("current_location", "")
    print(f"    Location distance  : {lc}{loc:.1f} km  ({u} → {c}){RESET}")

    v15 = txn.get("transactions_last_15min", 0)
    vc  = RED if v15 >= 7 else (YELLOW if v15 >= 4 else GREEN)
    print(f"    Velocity (15 min)  : {vc}{v15} transactions{RESET}")

    print(f"\n  {BOLD}Risk factors:{RESET}")
    for f in result["risk_factors"]:
        arrow = f"  {RED}▶{RESET}" if result["label"] == 1 else f"  {DIM}•{RESET}"
        print(f"    {arrow} {f}")

    print(f"\n  {DIM}Transaction recap:")
    print(f"    Amount          : ₹{txn['transaction_amount']:,.0f}")
    print(f"    Hour            : {txn['transaction_hour']:02d}:00")
    print(f"    Known device    : {'Yes' if txn['device_id_match'] else 'No (new device)'}")
    print(f"    Sender avg      : ₹{txn['sender_avg_txn_amount']:,.0f}")
    print(f"    Usual location  : {result.get('usual_location', 'N/A')}")
    print(f"    Current location: {result.get('current_location', 'N/A')}")
    print(f"    Txns / 15 min   : {txn['transactions_last_15min']}{RESET}")
    print()


def run_single_mode(model, threshold):
    while True:
        print(f"\n{'─'*62}")
        txn = collect_transaction()
        try:
            from predict import predict_transaction
            result = predict_transaction(txn, model_name=model, threshold=threshold)
            show_result(txn, result)
        except Exception as e:
            print(f"\n  {RED}Error: {e}{RESET}\n")

        again = ask_yn("\n  Test another transaction?", default=1)
        if not again:
            print(f"\n{DIM}  Goodbye.{RESET}\n")
            break


# ══════════════════════════════════════════════════════════════════════════════
#  BURST MODE  — simulate N transactions automatically
# ══════════════════════════════════════════════════════════════════════════════

# Indian city pairs used for realistic location generation in burst mode
# (usual city, possible current city, distance_approx_km)
CITY_PAIRS = [
    # Same city — clearly legit location
    ("delhi",      "delhi",        0),
    ("mumbai",     "mumbai",       0),
    ("bengaluru",  "bengaluru",    0),
    ("jaipur",     "jaipur",       0),
    ("chennai",    "chennai",      0),
    ("hyderabad",  "hyderabad",    0),
    ("pune",       "pune",         0),
    ("kolkata",    "kolkata",      0),
    # Short domestic trip — mild flag
    ("delhi",      "jaipur",       280),
    ("mumbai",     "pune",         150),
    ("bengaluru",  "mysuru",       145),
    ("delhi",      "agra",         200),
    # Long domestic — moderate flag
    ("delhi",      "mumbai",       1400),
    ("jaipur",     "chennai",      1607),
    ("mumbai",     "kolkata",      1900),
    ("delhi",      "bengaluru",    1740),
    ("udaipur",    "hyderabad",    1100),
    # Cross-country — high flag
    ("delhi",      "kochi",        2700),
    ("jaipur",     "guwahati",     2300),
    ("mumbai",     "dibrugarh",    2800),
]

# Fraud scenario templates — each has a descriptive type name
FRAUD_TEMPLATES = [
    {
        "type": "Credential Theft",
        "desc": "Stolen credentials used from abroad, massive amount spike",
        "amt_mult": (15, 35),   # multiplier range over sender_avg
        "hour": (0, 5),
        "device": 0,
        "usual": "delhi",   "current_lat": 40.71, "current_lon": -74.00,
        "velocity": (1, 3),
    },
    {
        "type": "Account Takeover",
        "desc": "New device, rapid transactions draining account",
        "amt_mult": (8, 20),
        "hour": (0, 6),
        "device": 0,
        "usual": "mumbai",  "current": "mumbai",
        "velocity": (6, 15),
    },
    {
        "type": "Location Anomaly",
        "desc": "Transaction initiated from far-away location, new device",
        "amt_mult": (5, 12),
        "hour": (0, 23),
        "device": 0,
        "usual": "jaipur",  "current": "kolkata",
        "velocity": (0, 3),
    },
    {
        "type": "Velocity Attack",
        "desc": "Burst of transactions in 15 minutes from new device",
        "amt_mult": (2, 6),
        "hour": (0, 23),
        "device": 0,
        "usual": "bengaluru", "current": "bengaluru",
        "velocity": (8, 20),
    },
    {
        "type": "Stealth Fraud",
        "desc": "Multiple moderate signals combined — new device, night, distant",
        "amt_mult": (4, 9),
        "hour": (0, 5),
        "device": 0,
        "usual": "chennai",  "current": "delhi",
        "velocity": (2, 5),
    },
]

LEGIT_TEMPLATES = [
    {
        "type": "Normal UPI",
        "desc": "Everyday small payment, same city, known device",
        "amt_mult": (0.3, 1.5),
        "hour": (8, 22),
        "device": 1,
        "pair_idx": 0,   # same city pair
        "velocity": (0, 1),
    },
    {
        "type": "Bill Payment",
        "desc": "Utility or subscription, known device, daytime",
        "amt_mult": (0.5, 2.0),
        "hour": (9, 20),
        "device": 1,
        "pair_idx": 1,
        "velocity": (0, 1),
    },
    {
        "type": "Weekend Shopping",
        "desc": "Slightly elevated amount, known device, afternoon",
        "amt_mult": (1.5, 3.0),
        "hour": (11, 20),
        "device": 1,
        "pair_idx": 2,
        "velocity": (0, 2),
    },
    {
        "type": "Business Travel",
        "desc": "User travelling, known device, normal amount",
        "amt_mult": (0.8, 2.0),
        "hour": (8, 22),
        "device": 1,
        "pair_idx": 8,   # delhi → jaipur ~280km
        "velocity": (0, 1),
    },
    {
        "type": "Late Night Transfer",
        "desc": "Odd hour but known device, normal amount, same city",
        "amt_mult": (0.5, 1.5),
        "hour": (0, 5),
        "device": 1,
        "pair_idx": 3,
        "velocity": (0, 1),
    },
]


def _generate_burst_transaction(rng, sender_avg, template, is_fraud):
    """
    Build one transaction dict from a template.
    Returns (txn_dict, ground_truth_label, type_name, description)
    """
    lo, hi = template["amt_mult"]
    amt    = round(sender_avg * rng.uniform(lo, hi), 2)
    amt    = max(10, min(amt, 500000))

    h_lo, h_hi = template["hour"]
    hour   = int(rng.randint(h_lo, h_hi + 1)) if h_lo < h_hi else h_lo

    v_lo, v_hi = template["velocity"]
    vel    = int(rng.randint(v_lo, v_hi + 1))

    # Location
    if "current_lat" in template:
        # Fraud going abroad — use raw coords
        txn = {
            "transaction_amount":      amt,
            "transaction_hour":        hour,
            "device_id_match":         template["device"],
            "sender_avg_txn_amount":   sender_avg,
            "sender_usual_location":   template["usual"],
            "current_txn_lat":         template["current_lat"],
            "current_txn_lon":         template["current_lon"],
            "transactions_last_15min": vel,
        }
    else:
        usual   = template.get("usual",   None)
        current = template.get("current", None)
        if usual and current:
            txn = {
                "transaction_amount":      amt,
                "transaction_hour":        hour,
                "device_id_match":         template["device"],
                "sender_avg_txn_amount":   sender_avg,
                "sender_usual_location":   usual,
                "current_txn_location":    current,
                "transactions_last_15min": vel,
            }
        else:
            pair = CITY_PAIRS[template.get("pair_idx", 0)]
            txn  = {
                "transaction_amount":      amt,
                "transaction_hour":        hour,
                "device_id_match":         template["device"],
                "sender_avg_txn_amount":   sender_avg,
                "sender_usual_location":   pair[0],
                "current_txn_location":    pair[1],
                "transactions_last_15min": vel,
            }

    return txn, int(is_fraud), template["type"], template["desc"]


def run_burst_mode(model, threshold, n=20, seed=None):
    """
    Generate n simulated transactions, run each through the model,
    print live results, then show an accuracy summary.

    Distribution: ~35% fraud, ~65% legit (slightly higher fraud than real world
    so the demo shows enough fraud detections to be interesting).
    """
    from predict import predict_transaction

    rng = np.random.RandomState(seed if seed is not None else random.randint(0, 9999))

    n_fraud_target = max(1, int(n * 0.35))
    n_legit_target = n - n_fraud_target

    # Build transaction list
    transactions = []
    for _ in range(n_fraud_target):
        tmpl       = FRAUD_TEMPLATES[rng.randint(0, len(FRAUD_TEMPLATES))]
        sender_avg = float(rng.uniform(500, 8000))
        txn, label, ttype, desc = _generate_burst_transaction(rng, sender_avg, tmpl, True)
        transactions.append((txn, label, ttype, desc))

    for _ in range(n_legit_target):
        tmpl       = LEGIT_TEMPLATES[rng.randint(0, len(LEGIT_TEMPLATES))]
        sender_avg = float(rng.uniform(500, 8000))
        txn, label, ttype, desc = _generate_burst_transaction(rng, sender_avg, tmpl, False)
        transactions.append((txn, label, ttype, desc))

    # Shuffle so fraud and legit are interleaved
    indices = list(range(len(transactions)))
    rng.shuffle(indices)
    transactions = [transactions[i] for i in indices]

    # ── Header ─────────────────────────────────────────────────────────────
    print(f"\n  {BOLD}{MAGENTA}{'═'*62}")
    print(f"  BURST SIMULATION — {n} TRANSACTIONS")
    print(f"  {'═'*60}{RESET}")
    print(f"  {DIM}Simulating live bank server processing each transaction…{RESET}\n")
    time.sleep(0.4)

    # ── Run each transaction ────────────────────────────────────────────────
    results     = []
    col_w       = 22

    # Table header
    print(f"  {BOLD}{'#':>3}  {'Type':<20}  {'Actual':<8}  {'Model':<8}  {'Prob':>7}  {'Match'}{RESET}")
    print(f"  {'─'*60}")

    for i, (txn, true_label, ttype, desc) in enumerate(transactions, 1):
        time.sleep(0.08)   # small delay — makes it look like real-time processing

        try:
            result = predict_transaction(txn, model_name=model, threshold=threshold)
        except Exception as e:
            result = {"label": 0, "fraud_probability": 0.0,
                      "confidence": "ERROR", "threshold_used": threshold,
                      "risk_factors": [str(e)],
                      "amount_deviation_ratio": 0, "location_deviation_km": 0,
                      "usual_location": "", "current_location": ""}

        pred_label = result["label"]
        prob       = result["fraud_probability"]
        correct    = (pred_label == true_label)

        actual_str = f"{RED}FRAUD{RESET}"  if true_label  == 1 else f"{GREEN}LEGIT{RESET}"
        pred_str   = f"{RED}FRAUD{RESET}"  if pred_label  == 1 else f"{GREEN}LEGIT{RESET}"
        match_str  = f"{GREEN}✓{RESET}"   if correct else f"{RED}✗{RESET}"
        prob_color = RED if prob > 0.7 else (YELLOW if prob > 0.4 else GREEN)

        print(f"  {i:>3}  {ttype:<20}  {actual_str:<17}  {pred_str:<17}  "
              f"{prob_color}{prob*100:5.1f}%{RESET}  {match_str}")

        results.append({
            "index":         i,
            "type":          ttype,
            "description":   desc,
            "true_label":    true_label,
            "pred_label":    pred_label,
            "probability":   prob,
            "correct":       correct,
            "txn":           txn,
            "result":        result,
        })

    # ── Summary ─────────────────────────────────────────────────────────────
    total         = len(results)
    actual_fraud  = sum(1 for r in results if r["true_label"] == 1)
    actual_legit  = total - actual_fraud
    detected      = sum(1 for r in results if r["true_label"]==1 and r["pred_label"]==1)
    false_pos     = sum(1 for r in results if r["true_label"]==0 and r["pred_label"]==1)
    false_neg     = sum(1 for r in results if r["true_label"]==1 and r["pred_label"]==0)
    correct_total = sum(1 for r in results if r["correct"])
    accuracy      = correct_total / total * 100

    print(f"\n  {BOLD}{MAGENTA}{'─'*62}")
    print(f"  SIMULATION SUMMARY")
    print(f"  {'─'*60}{RESET}\n")

    print(f"  Total transactions simulated : {BOLD}{total}{RESET}")
    print(f"  Actual fraud transactions    : {RED}{BOLD}{actual_fraud}{RESET}  "
          f"{DIM}({actual_fraud/total*100:.0f}% of total){RESET}")
    print(f"  Actual legit transactions    : {GREEN}{BOLD}{actual_legit}{RESET}")

    print(f"\n  {BOLD}Model performance:{RESET}")

    det_color = GREEN if detected == actual_fraud else (YELLOW if detected >= actual_fraud*0.7 else RED)
    print(f"    Fraud correctly detected   : {det_color}{BOLD}{detected} / {actual_fraud}{RESET}  "
          f"{'✓ All caught!' if detected==actual_fraud else f'({detected/actual_fraud*100:.0f}% recall)'}")

    fp_color = GREEN if false_pos == 0 else (YELLOW if false_pos <= 2 else RED)
    print(f"    Legitimate wrongly blocked : {fp_color}{false_pos}{RESET}  "
          f"{DIM}(false positives){RESET}")

    fn_color = GREEN if false_neg == 0 else RED
    print(f"    Fraud missed               : {fn_color}{false_neg}{RESET}  "
          f"{DIM}(false negatives — most costly){RESET}")

    acc_color = GREEN if accuracy >= 80 else YELLOW
    print(f"    Overall accuracy           : {acc_color}{BOLD}{accuracy:.1f}%{RESET}")

    # Highlight any misses
    misses = [r for r in results if not r["correct"]]
    if misses:
        print(f"\n  {YELLOW}Transactions where model differed from ground truth:{RESET}")
        for r in misses:
            a = "FRAUD" if r["true_label"] == 1 else "LEGIT"
            p = "FRAUD" if r["pred_label"] == 1 else "LEGIT"
            print(f"    #{r['index']:>2}  {r['type']:<20}  actual={a}  model={p}  "
                  f"prob={r['probability']*100:.1f}%")
            print(f"        {DIM}{r['description']}{RESET}")

    print(f"\n  {DIM}Tip: Run burst mode again with a different seed for varied results.{RESET}")
    print()

    return results


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN — mode selector
# ══════════════════════════════════════════════════════════════════════════════

def main():
    banner()

    if not os.path.exists("models/xgboost.joblib"):
        print(f"  {RED}ERROR: No trained model found.{RESET}")
        print(f"  Run  {BOLD}python main.py{RESET}  first.\n")
        sys.exit(1)

    # ── Mode selection ────────────────────────────────────────────────────
    print(f"  {BOLD}Select mode:{RESET}\n")
    print(f"    {CYAN}[1]{RESET}  Single mode   — enter one transaction manually")
    print(f"    {CYAN}[2]{RESET}  Burst mode    — auto-simulate N transactions (demo / presentation)\n")

    while True:
        raw = input(f"    {CYAN}Choice (1 or 2) [1]: {RESET}").strip()
        if raw in ("", "1"):
            mode = "single"
            break
        if raw == "2":
            mode = "burst"
            break
        print(f"      {YELLOW}Enter 1 or 2.{RESET}")

    # ── Model + threshold (shared by both modes) ──────────────────────────
    print(f"\n  {BOLD}Model settings:{RESET}\n")
    raw   = input(f"    {CYAN}Model (xgboost / logistic_regression) [xgboost]: {RESET}").strip()
    model = "logistic_regression" if raw.lower() == "logistic_regression" else "xgboost"

    print(f"\n    {DIM}Lower threshold = catch more fraud (more false alarms){RESET}")
    threshold = ask_float("    Decision threshold (0.0–1.0)", default=0.5, min_val=0.0, max_val=1.0)

    # ── Run selected mode ─────────────────────────────────────────────────
    if mode == "single":
        run_single_mode(model, threshold)

    else:
        print(f"\n  {BOLD}Burst settings:{RESET}\n")
        n = ask_int(
            "Number of transactions to simulate",
            default=20, min_val=5, max_val=200)

        print(f"\n    {DIM}Seed controls which transactions are generated.")
        print(f"    Same seed = same transactions every run (good for reproducible demos).")
        print(f"    Leave blank for a random seed.{RESET}")
        raw_seed = input(f"    {CYAN}Random seed (or Enter for random) [42]: {RESET}").strip()
        seed = int(raw_seed) if raw_seed.isdigit() else (42 if raw_seed == "" else None)

        run_burst_mode(model, threshold, n=n, seed=seed)

        # Option to run again with different seed
        while True:
            again = ask_yn("\n  Run burst again with a new random seed?", default=0)
            if not again:
                break
            run_burst_mode(model, threshold, n=n, seed=None)

        print(f"\n{DIM}  Goodbye.{RESET}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{DIM}  Interrupted. Goodbye.{RESET}\n")