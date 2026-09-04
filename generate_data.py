"""
generate_data.py
-----------------
Generates a synthetic 3-way reconciliation dataset:
  - invoices.csv        : source invoices (AP side)
  - gl_ledger.csv        : ERP / general ledger postings
  - bank_transactions.csv: bank statement lines
  - ground_truth.csv     : the ANSWER KEY (category + correct links)

The dataset is deliberately messy on purpose, matching the category mix
used to report precision / exception recall honestly:

  65% clean 1:1 match           (invoice == ledger == bank, exact)
  15% timing difference          (bank settles T+1 / T+2 after invoice/GL)
   8% split / combined payments  (1 invoice -> 2 bank lines, or 2 invoices -> 1 bank line)
   5% amount discrepancy         (FX rounding / bank fee shaved off)
   5% duplicate payment          (invoice paid twice -> 2 bank lines, only 1 legit)
   2% orphan                     (bank txn or invoice with NO counterpart at all)

Run: python3 generate_data.py
Output: writes 4 CSVs into this folder.
"""

import csv
import random
from datetime import date, timedelta

random.seed(42)

VENDORS = [
    ("Acme Corporation", "ACME CORP", "ACME CORPORATION LLC"),
    ("Northwind Traders", "NORTHWIND TRDG", "NORTHWIND TRADERS INC"),
    ("Globex Industries", "GLOBEX IND", "GLOBEX INDUSTRIES CO"),
    ("Initech Solutions", "INITECH SOL", "INITECH SOLUTIONS LLC"),
    ("Umbrella Supplies", "UMBRELLA SUP", "UMBRELLA SUPPLIES CORP"),
    ("Wayne Logistics", "WAYNE LOG", "WAYNE LOGISTICS INC"),
    ("Stark Materials", "STARK MAT", "STARK MATERIALS LLC"),
    ("Hooli Consulting", "HOOLI CONS", "HOOLI CONSULTING GROUP"),
    ("Soylent Freight", "SOYLENT FRT", "SOYLENT FREIGHT CO"),
    ("Aperture Devices", "APERTURE DEV", "APERTURE DEVICES INC"),
]

START_DATE = date(2026, 6, 1)
N_INVOICES = 60  # yields 60+ ground-truth records, comfortably above the 50-record bar

invoices = []
ledger = []
bank = []
ground_truth = []

inv_counter = 1000
gl_counter = 5000
bank_counter = 9000


def next_invoice_id():
    global inv_counter
    inv_counter += 1
    return f"INV-{inv_counter}"


def next_gl_id():
    global gl_counter
    gl_counter += 1
    return f"GL-{gl_counter}"


def next_bank_id():
    global bank_counter
    bank_counter += 1
    return f"BTX-{bank_counter}"


def rand_date(base, spread=45):
    return base + timedelta(days=random.randint(0, spread))


# --- category plan for N_INVOICES records ---
plan = (
    ["clean"] * int(N_INVOICES * 0.65)
    + ["timing"] * int(N_INVOICES * 0.15)
    + ["split_combined"] * int(N_INVOICES * 0.08)
    + ["fx_discrepancy"] * int(N_INVOICES * 0.05)
    + ["duplicate"] * int(N_INVOICES * 0.05)
    + ["orphan"] * int(N_INVOICES * 0.02)
)
while len(plan) < N_INVOICES:
    plan.append("clean")
random.shuffle(plan)

for i, category in enumerate(plan):
    vendor_full, vendor_bank_short, vendor_gl_variant = random.choice(VENDORS)
    inv_date = rand_date(START_DATE)
    amount = round(random.uniform(250, 18500), 2)
    invoice_id = next_invoice_id()

    if category == "clean":
        invoices.append([invoice_id, vendor_full, inv_date.isoformat(), amount, "USD"])
        gl_id = next_gl_id()
        ledger.append([gl_id, invoice_id, vendor_gl_variant, inv_date.isoformat(), amount])
        btx_id = next_bank_id()
        # ~35% of the time the bank memo has NO invoice reference at all -
        # forces real name+amount+date fuzzy matching instead of a string lookup
        if random.random() < 0.35:
            desc = f"ACH CREDIT {vendor_bank_short}"
        else:
            desc = f"PMT REF {invoice_id} {vendor_bank_short}"
        bank.append([btx_id, inv_date.isoformat(), amount, "USD", desc])
        ground_truth.append([invoice_id, gl_id, btx_id, "clean_match",
                              "Exact 3-way match, same date/amount"])

    elif category == "timing":
        invoices.append([invoice_id, vendor_full, inv_date.isoformat(), amount, "USD"])
        gl_id = next_gl_id()
        ledger.append([gl_id, invoice_id, vendor_gl_variant, inv_date.isoformat(), amount])
        lag = random.choice([1, 2, 3])
        settle_date = inv_date + timedelta(days=lag)
        btx_id = next_bank_id()
        if random.random() < 0.35:
            desc = f"ACH CREDIT {vendor_bank_short}"
        else:
            desc = f"PMT REF {invoice_id} {vendor_bank_short}"
        bank.append([btx_id, settle_date.isoformat(), amount, "USD", desc])
        ground_truth.append([invoice_id, gl_id, btx_id, "timing_difference",
                              f"Bank settled T+{lag}, same amount"])

    elif category == "split_combined":
        invoices.append([invoice_id, vendor_full, inv_date.isoformat(), amount, "USD"])
        gl_id = next_gl_id()
        ledger.append([gl_id, invoice_id, vendor_gl_variant, inv_date.isoformat(), amount])
        if random.random() < 0.5:
            # split: one invoice paid across two bank lines
            part1 = round(amount * random.uniform(0.3, 0.6), 2)
            part2 = round(amount - part1, 2)
            btx1, btx2 = next_bank_id(), next_bank_id()
            bank.append([btx1, inv_date.isoformat(), part1, "USD",
                         f"PARTIAL PMT {invoice_id} {vendor_bank_short}"])
            bank.append([btx2, (inv_date + timedelta(days=1)).isoformat(), part2, "USD",
                         f"PARTIAL PMT {invoice_id} {vendor_bank_short}"])
            ground_truth.append([invoice_id, gl_id, f"{btx1}+{btx2}", "split_payment",
                                  "One invoice paid via two bank lines that sum to invoice amount"])
        else:
            # combined: this invoice + a second invoice paid in one bank line
            vendor_full2, vendor_bank_short2, vendor_gl_variant2 = vendor_full, vendor_bank_short, vendor_gl_variant
            amount2 = round(random.uniform(250, 5000), 2)
            invoice_id2 = next_invoice_id()
            invoices.append([invoice_id2, vendor_full2, inv_date.isoformat(), amount2, "USD"])
            gl_id2 = next_gl_id()
            ledger.append([gl_id2, invoice_id2, vendor_gl_variant2, inv_date.isoformat(), amount2])
            combined_amount = round(amount + amount2, 2)
            btx_id = next_bank_id()
            bank.append([btx_id, inv_date.isoformat(), combined_amount, "USD",
                         f"COMBINED PMT {invoice_id}/{invoice_id2} {vendor_bank_short}"])
            ground_truth.append([f"{invoice_id}+{invoice_id2}", f"{gl_id}+{gl_id2}", btx_id,
                                  "combined_payment",
                                  "Two invoices paid via a single bank line that sums to both"])

    elif category == "fx_discrepancy":
        invoices.append([invoice_id, vendor_full, inv_date.isoformat(), amount, "USD"])
        gl_id = next_gl_id()
        ledger.append([gl_id, invoice_id, vendor_gl_variant, inv_date.isoformat(), amount])
        # bank shaves off a small fee / fx rounding, within ~1.5%
        delta = round(amount * random.uniform(0.003, 0.015), 2)
        bank_amount = round(amount - delta, 2)
        btx_id = next_bank_id()
        bank.append([btx_id, inv_date.isoformat(), bank_amount, "USD",
                     f"PMT REF {invoice_id} {vendor_bank_short} (FEE/FX ADJ)"])
        ground_truth.append([invoice_id, gl_id, btx_id, "amount_discrepancy",
                              f"Bank amount differs from invoice by {delta} (fee/FX rounding)"])

    elif category == "duplicate":
        invoices.append([invoice_id, vendor_full, inv_date.isoformat(), amount, "USD"])
        gl_id = next_gl_id()
        ledger.append([gl_id, invoice_id, vendor_gl_variant, inv_date.isoformat(), amount])
        btx_legit = next_bank_id()
        btx_dupe = next_bank_id()
        bank.append([btx_legit, inv_date.isoformat(), amount, "USD",
                     f"PMT REF {invoice_id} {vendor_bank_short}"])
        bank.append([btx_dupe, (inv_date + timedelta(days=2)).isoformat(), amount, "USD",
                     f"PMT REF {invoice_id} {vendor_bank_short}"])
        ground_truth.append([invoice_id, gl_id, f"{btx_legit} (legit) / {btx_dupe} (duplicate)",
                              "duplicate_payment",
                              "Invoice paid twice; only the first bank line is the legitimate match"])

    elif category == "orphan":
        if random.random() < 0.5:
            # orphan invoice: no ledger posting, no bank payment at all
            invoices.append([invoice_id, vendor_full, inv_date.isoformat(), amount, "USD"])
            ground_truth.append([invoice_id, "NONE", "NONE", "orphan_invoice",
                                  "Invoice has no ledger posting and no bank payment"])
        else:
            # orphan bank line: e.g. a bank fee / charge with no invoice or GL entry
            btx_id = next_bank_id()
            fee_amount = round(random.uniform(15, 300), 2)
            bank.append([btx_id, inv_date.isoformat(), fee_amount, "USD",
                         "BANK SERVICE CHARGE"])
            ground_truth.append(["NONE", "NONE", btx_id, "orphan_bank_txn",
                                  "Bank charge with no corresponding invoice or GL entry"])


def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


write_csv("invoices.csv", ["invoice_id", "vendor", "invoice_date", "amount", "currency"], invoices)
write_csv("gl_ledger.csv", ["gl_id", "ref_invoice_id", "vendor", "gl_date", "amount"], ledger)
write_csv("bank_transactions.csv", ["bank_txn_id", "txn_date", "amount", "currency", "description"], bank)
write_csv("ground_truth.csv",
          ["invoice_id", "gl_id", "bank_txn_id", "category", "note"], ground_truth)

print(f"Generated {len(invoices)} invoices, {len(ledger)} GL postings, "
      f"{len(bank)} bank txns, {len(ground_truth)} ground-truth records.")
print("Category mix:")
from collections import Counter
print(Counter(row[3] for row in ground_truth))
