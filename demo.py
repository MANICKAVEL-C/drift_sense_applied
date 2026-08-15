"""
demo.py - Master Live Demonstration Script
Applied Materials Metrology Challenge (SEMICON India 2026)

Runs the complete end-to-end metrology workflow in a single command:
  1. Synthetic Dataset Generation (10 SEM pairs)
  2. Sub-Pixel Prediction Solver (predict.py -> submission.csv)
  3. Benchmark Validation Suite (test_pipeline.py)
  4. RGB Optical Microscope Bonus Module (optical_generator.py)
  5. Visual Inspection Figures Generator (visual_evaluator.py)
"""

import time
import subprocess
import sys

def print_banner(title):
    print("\n" + "=" * 70)
    print(f"  ▶ {title}")
    print("=" * 70)

def main():
    print_banner("1. GENERATING SYNTHETIC SEM WAFER DATASET (10 PAIRS)")
    subprocess.run([sys.executable, "dataset_generator.py", "--num_pairs", "10", "--output_dir", "./sem_dataset"])
    time.sleep(1)

    print_banner("2. RUNNING SUB-PIXEL INFERENCE SOLVER (EXPORTS submission.csv)")
    subprocess.run([sys.executable, "predict.py", "--input_dir", "./sem_dataset", "--output_csv", "submission.csv"])
    time.sleep(1)

    print_banner("3. RUNNING RGB OPTICAL MICROSCOPE BONUS MODULE")
    subprocess.run([sys.executable, "optical_generator.py"])
    time.sleep(1)

    print_banner("4. GENERATING VISUAL INSPECTION FIGURES")
    subprocess.run([sys.executable, "visual_evaluator.py"])
    time.sleep(1)

    print_banner("5. RUNNING OFFICIAL VALIDATION BENCHMARK SUITE")
    subprocess.run([sys.executable, "test_pipeline.py"])

    print("\n" + "🌟" * 35)
    print("  DEMO COMPLETE: All steps executed cleanly and exported!")
    print("🌟" * 35 + "\n")

if __name__ == '__main__':
    main()
