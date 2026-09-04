"""
metrics.py
----------
Scores match_results.csv + exceptions.csv against data/ground_truth.csv.

This is the file that turns "we built a matcher" into "we measured a matcher" -
every number here is checked against a known answer key, not eyeballed.
"""

import csv
import json
from collections import Counter


def load_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def parse_ids(field):
    if field in ("NONE", "", None):
        return []
    return field.split("+")


def main():
    gt = load_csv("../data/ground_truth.csv")
    results = load_csv("../outputs/match_results.csv")
    exceptions = load_csv("../outputs/exceptions.csv")

    # index pipeline outputs by invoice_id
    result_by_invoice = {}
    for r in results:
        for inv_id in r["invoice_id"].split("+"):
            result_by_invoice[inv_id] = r

    exception_ids = {e["id"] for e in exceptions}

    total_invoice_records = 0
    should_match = 0
    should_except = 0
    correct_matches = 0
    false_matches = 0
    matches_made = 0
    exceptions_correctly_flagged = 0
    exceptions_missed = 0

    per_category = Counter()
    per_category_correct = Counter()

    for row in gt:
        category = row["category"]
        invoice_ids = parse_ids(row["invoice_id"])

        if category == "orphan_bank_txn":
            # exception lives on the bank side, not the invoice side
            should_except += 1
            per_category[category] += 1
            btx_id = row["bank_txn_id"]
            if btx_id in exception_ids:
                exceptions_correctly_flagged += 1
                per_category_correct[category] += 1
            else:
                exceptions_missed += 1
            continue

        for inv_id in invoice_ids:
            total_invoice_records += 1
            per_category[category] += 1

            if category == "orphan_invoice":
                should_except += 1
                if inv_id in exception_ids:
                    exceptions_correctly_flagged += 1
                    per_category_correct[category] += 1
                else:
                    exceptions_missed += 1
                continue

            should_match += 1
            pred = result_by_invoice.get(inv_id)

            if category == "duplicate_payment":
                legit_id = row["bank_txn_id"].split("(legit)")[0].split("/")[0].strip()
                dupe_id = row["bank_txn_id"].split("/")[1].split("(duplicate)")[0].strip()
                if pred and pred["bank_txn_id"] == legit_id:
                    correct_matches += 1
                    per_category_correct[category] += 1
                elif pred:
                    false_matches += 1
                if dupe_id in exception_ids:
                    exceptions_correctly_flagged += 1
                else:
                    exceptions_missed += 1
                should_except += 1  # the duplicate half must ALSO be caught
                if pred:
                    matches_made += 1
                continue

            expected_bank_ids = set(parse_ids(row["bank_txn_id"]))
            if pred:
                matches_made += 1
                predicted_bank_ids = set(pred["bank_txn_id"].split("+"))
                if predicted_bank_ids == expected_bank_ids:
                    correct_matches += 1
                    per_category_correct[category] += 1
                else:
                    false_matches += 1

    match_rate = matches_made / should_match if should_match else 0
    precision = correct_matches / matches_made if matches_made else 0
    exception_recall = exceptions_correctly_flagged / should_except if should_except else 0
    false_match_rate = false_matches / matches_made if matches_made else 0

    tier_breakdown = Counter(r["tier"] for r in results)

    summary = {
        "total_ground_truth_invoice_records": total_invoice_records,
        "should_auto_match": should_match,
        "should_be_exception": should_except,
        "matches_made": matches_made,
        "correct_matches": correct_matches,
        "false_matches": false_matches,
        "exceptions_correctly_flagged": exceptions_correctly_flagged,
        "exceptions_missed": exceptions_missed,
        "match_rate_pct": round(match_rate * 100, 1),
        "precision_on_matches_pct": round(precision * 100, 1),
        "exception_recall_pct": round(exception_recall * 100, 1),
        "false_match_rate_pct": round(false_match_rate * 100, 1),
        "tier_breakdown": dict(tier_breakdown),
        "category_totals": dict(per_category),
        "category_correct": dict(per_category_correct),
    }

    with open("../outputs/metrics.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
