# Ledger Sentinel

**A tiered AI reconciliation agent that closes a 3-way finance-ops loop (invoices ↔ GL ledger ↔ bank statement) and reports its match rate, precision, and honest exception list against a known answer key.**

Built for: AI Finance Controller track.

## Why this approach

Most reconciliation demos show a handful of cherry-picked clean matches. That proves nothing about accuracy. Ledger Sentinel instead:

1. Generates a **synthetic dataset with known ground truth**, deliberately seeded with the mess a real close process hits — settlement lags, split/combined payments, FX/fee rounding, duplicate payments, unreferenced bank memos, and true orphan records.
2. Runs a **tiered matching pipeline** that escalates from cheap/deterministic to expensive/agentic, only calling on agentic reasoning for the records that actually need it.
3. **Scores every output against the answer key** — match rate, precision on matches made, exception recall, and false-match rate. Nothing is asserted; everything is measured.

## Architecture

```
Tier 1 — Exact match        deterministic, same amount + same date, ~50% of volume
Tier 2 — Fuzzy match         settlement-lag tolerance, FX/fee tolerance,
                              AND vendor-name fuzzy matching for bank lines with
                              no invoice reference at all (real fuzzy logic, not
                              a substring lookup)
Tier 3 — Agentic reasoning   investigates what's left: split payments, combined
                              payments, duplicate-payment detection — emits a
                              confidence score + one-sentence justification per
                              resolution, like a controller's workpaper note
Tier 4 — Exception queue     anything unresolved is categorized, never dropped
```

Tier 3 ships as a deterministic reasoning engine (`pipeline/match_pipeline.py`) so the
pipeline is fully reproducible offline. `pipeline/tier3_llm_agent.py` documents the exact
drop-in replacement using the real Claude API with tool use
(`lookup_invoice` / `lookup_bank_txn` / `compute_delta` / `flag_exception`) — same
input/output contract, just backed by a model call instead of hand-written rules.

## Results on the 60-record synthetic batch

| Metric | Result |
|---|---|
| Match rate | **96.7%** (59 / 61 records that should auto-resolve did) |
| Precision on matches made | **98.3%** (58 / 59 matches were correct against ground truth) |
| Exception recall | **100%** (all 4 records that should be flagged, were flagged) |
| False-match rate | **1.7%** (1 record) — reported, not hidden |

Tier breakdown: 31 exact, 16 fuzzy vendor-name, 5 fuzzy timing, 3 fuzzy amount, 4 agentic.

The one false match and the full exception list (with categorized reasons) are in
`outputs/exceptions.csv` and `outputs/match_results.csv` — nothing is swept under the rug.

## Run it yourself

```bash
pip install -r requirements.txt
python3 run_pipeline.py
```

This regenerates the synthetic dataset (or reuses it if already present — delete
`data/*.csv` to force a fresh batch), runs all four tiers, and prints the scorecard.
Outputs land in `outputs/`.

## Project structure

Project structure
README.md                  project overview and results
generate_data.py           synthetic 3-way dataset generator
invoices.csv               synthetic invoice dataset
gl_ledger.csv              synthetic GL ledger dataset
bank_transactions.csv      synthetic bank transaction dataset
ground_truth.csv           known answer key for evaluation
match_pipeline.py          Tier 1-4 matching engine
metrics.py                 scores outputs against ground truth
tier3_llm_agent.py         Claude API + tool-use version of Tier 3
run_pipeline.py            one-command pipeline entry point
dashboard.html             reconciliation results dashboard
match_results.csv          resolved records with tier, confidence, justification
exceptions.csv             unresolved records with category and justification
metrics.json               machine-readable scorecard
requirements.txt           Python dependencies


## What would change in production

- Tier 3 backed by the live Claude API (`tier3_llm_agent.py`) instead of the rule engine.
- Multi-currency FX-rate lookups instead of a flat tolerance band.
- A confidence threshold below which even a Tier 1-3 "match" gets routed to human review.
- Persisted exception queue with assignment/resolution workflow instead of a CSV.
