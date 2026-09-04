"""
run_pipeline.py
----------------
One-command entry point: generates data (if missing), runs the tiered matcher,
scores it against ground truth, and prints the scorecard.

Usage: python3 run_pipeline.py
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
PIPELINE_DIR = os.path.join(ROOT, "pipeline")
OUT_DIR = os.path.join(ROOT, "outputs")


def run(cmd, cwd):
    print(f"\n$ {' '.join(cmd)}  (in {os.path.relpath(cwd, ROOT)}/)")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        sys.exit(result.returncode)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)

    if not os.path.exists(os.path.join(DATA_DIR, "ground_truth.csv")):
        run([sys.executable, "generate_data.py"], cwd=DATA_DIR)
    else:
        print("Synthetic dataset already exists (delete data/*.csv to regenerate).")

    run([sys.executable, "match_pipeline.py"], cwd=PIPELINE_DIR)
    run([sys.executable, "metrics.py"], cwd=PIPELINE_DIR)

    print(f"\nDone. Outputs written to {os.path.relpath(OUT_DIR, ROOT)}/:")
    for f in sorted(os.listdir(OUT_DIR)):
        print(f"  - {f}")
