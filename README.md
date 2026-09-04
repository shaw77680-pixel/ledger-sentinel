Ledger Sentinel

A tiered AI reconciliation agent that closes a 3-way finance-ops loop (invoices ↔ GL ledger ↔ bank statement) and reports its match rate, precision, and honest exception list against a known answer key.

Built for: AI Finance Controller track.

Why this approach

Most reconciliation demos show a handful of cherry-picked clean matches. That proves nothing about accuracy. Ledger Sentinel instead:

Generates a synthetic dataset with known ground truth, deliberately seeded with the mess a real close process hits — settlement lags, split/combined payments, FX/fee rounding, duplicate payments, unreferenced bank memos, and true orphan records.
Runs a tiered matching pipeline that escalates from cheap/deterministic to expensive/agentic, only calling on agentic reasoning for the records that actually need it.
Scores every output against the answer key — match rate, precision on matches made, exception recall, and false-match rate. Nothing is asserted; everything is measured.
Architecture
Tier 1 — Exact match
Deterministic matching using the same amount + same date.

Tier 2 — Fuzzy match
Settlement-lag tolerance, FX/fee tolerance, and vendor-name
fuzzy matching for bank lines with no invoice reference.

Tier 3 — Agentic reasoning
Investigates what remains: split payments, combined payments,
and duplicate-payment detection. Emits a confidence score
and one-sentence justification for each resolution.

Tier 4 — Exception queue
Anything unresolved is categorized and surfaced for review.
Nothing is silently dropped.


Tier 3 ships as a deterministic reasoning engine in match_pipeline.py, so the pipeline is fully reproducible offline. tier3_llm_agent.py documents the exact drop-in replacement using the real Claude API with tool use:

lookup_invoice
lookup_bank_txn
compute_delta
flag_exception

The real model-backed version uses the same input/output contract, replacing the deterministic reasoning rules with a model call.

Results on the 60-record synthetic batch
Metric	Result
Match rate	96.7% (59 / 61 records that should auto-resolve did)
Precision on matches made	98.3% (58 / 59 matches were correct against ground truth)
Exception recall	100% (all 4 records that should be flagged, were flagged)
False-match rate	1.7% (1 record) — reported, not hidden

Tier breakdown: 31 exact, 16 fuzzy vendor-name, 5 fuzzy timing, 3 fuzzy amount, 4 agentic.

The one false match and the full exception list, including categorized reasons, are available in exceptions.csv and match_results.csv. Nothing is swept under the rug.

Run it yourself

Install the dependencies:

pip install -r requirements.txt


Then run:

python3 run_pipeline.py


This regenerates the synthetic dataset, or reuses it if the existing CSV files are present. To force a fresh batch, remove the existing CSV data files before running the pipeline.

The generated results are written to the repository root, including:

match_results.csv
exceptions.csv
metrics.json

The pipeline then prints the scorecard to the console.

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

What would change in production
Live AI reasoning: Tier 3 would be backed by the live Claude API instead of the deterministic reasoning engine.
Real FX data: Multi-currency FX-rate lookups would replace the flat tolerance band.
Human-in-the-loop review: Matches below a configurable confidence threshold would be routed to human review.
Persistent exception workflow: The CSV exception list would become a persistent queue with assignment, review, and resolution tracking.
Production data integrations: The system would connect directly to ERP/GL, banking, and invoice systems instead of synthetic CSV inputs.
Why Ledger Sentinel matters

Ledger Sentinel is designed around a simple principle:

A reconciliation system should prove what it got right, expose what it got wrong, and never hide the exceptions.

Instead of optimizing for a perfect-looking demo, the system measures its own performance against known ground truth and explicitly reports false matches and unresolved records.
- Tier 3 backed by the live Claude API (`tier3_llm_agent.py`) instead of the rule engine.
- Multi-currency FX-rate lookups instead of a flat tolerance band.
- A confidence threshold below which even a Tier 1-3 "match" gets routed to human review.
- Persisted exception queue with assignment/resolution workflow instead of a CSV.
