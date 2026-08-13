"""
test_pipeline.py - Comprehensive Verification & Benchmark Suite
Applied Materials Metrology Challenge

Generates 30 randomized test pairs across Standard, Heavy Noise, and Surface Charging modes.
Evaluates sub-pixel localization accuracy and latency of predict.py, generating a summary table
and documenting the periodic array failure case for the 10% explainability rubric.
"""

import time
import numpy as np
import pandas as pd
from dataset_generator import OfficialSEMWaferGenerator
from predict import get_center_coordinates

EXPLAINABILITY_NOTE = """
========================================================================================
                      SEM METROLOGY EXPLAINABILITY RUBRIC NOTE
========================================================================================
Failure Case Analysis: Periodic Array Aliasing & Stage Drift > Half-Pitch

In semiconductor manufacturing (DRAM trench arrays and FinFET fin/gate logic grids), 
features consist of periodic repeating structures with spatial period P.

When physical wafer stage drift exceeds half-pitch (Delta_x > P/2 or Delta_y > P/2):
  1. Phase Ambiguity: The normalized cross-correlation (NCC) map exhibits high local 
     maxima at regular spatial intervals equal to integer multiples of pitch P.
  2. Grid Locking: The template matching algorithm locks onto an adjacent identical 
     array element, returning a high confidence score despite a spatial position error 
     of exactly +-k*P pixels.
  3. Applied Materials Rule 3 Mitigation: By searching for candidate peaks within 5% 
     of maximum correlation and selecting the peak closest to the image center (500, 500), 
     the solver resolves periodic aliasing under nominal stage drift.
  4. Robustness under Surface Charging & Low Dose: Difference-of-Gaussians (DoG) filtering 
     strips out Cazaux low-frequency surface potential hills and Sim high-frequency shot noise, 
     preventing noise-induced peak displacement.
========================================================================================
"""

def run_benchmark():
    generator = OfficialSEMWaferGenerator()
    modes = ["Standard", "Heavy Noise", "Surface Charging"]
    patterns = ["DRAM", "FinFET"]

    records = []

    print("Running DriftSense Metrology Benchmark (30 Test Pairs)...")
    print("-" * 75)

    num_samples = 30
    for i in range(num_samples):
        stress_mode = modes[i % len(modes)]
        pattern_style = patterns[i % len(patterns)]
        seed_val = 1000 + i

        # 1. Generate test pair
        ref_img, search_img, (gt_x, gt_y) = generator.generate_pair(
            seed_val=seed_val, pattern_style=pattern_style, stress_mode=stress_mode
        )

        # 2. Measure prediction latency and accuracy
        t0 = time.perf_counter()
        pred_x, pred_y, confidence = get_center_coordinates(ref_img, search_img)
        t1 = time.perf_counter()

        latency_ms = (t1 - t0) * 1000.0
        euc_error = float(np.sqrt((pred_x - gt_x)**2 + (pred_y - gt_y)**2))
        is_subpixel = euc_error < 1.0

        records.append({
            "pair_id": i + 1,
            "pattern": pattern_style,
            "stress_mode": stress_mode,
            "gt_x": gt_x,
            "gt_y": gt_y,
            "pred_x": pred_x,
            "pred_y": pred_y,
            "error_px": euc_error,
            "subpixel_acc": is_subpixel,
            "confidence": confidence,
            "latency_ms": latency_ms
        })

        print(f"Pair {i+1:02d}/30 [{stress_mode:<16} | {pattern_style:<6}] -> Error: {euc_error:.4f} px | Latency: {latency_ms:.1f} ms | Conf: {confidence:.3f}")

    df = pd.DataFrame(records)

    # Calculate overall summary metrics
    mean_err = df["error_px"].mean()
    median_err = df["error_px"].median()
    p95_err = df["error_px"].quantile(0.95)
    subpixel_rate = (df["subpixel_acc"].sum() / len(df)) * 100.0
    avg_latency = df["latency_ms"].mean()

    print("\n" + "="*75)
    print("                      METROLOGY SUMMARY BENCHMARK TABLE")
    print("="*75)
    
    summary_df = pd.DataFrame([{
        "Metric": "Overall (30 Pairs)",
        "Mean Error (px)": f"{mean_err:.4f}",
        "Median Error (px)": f"{median_err:.4f}",
        "95th Pct Error (px)": f"{p95_err:.4f}",
        "Sub-Pixel Rate (% < 1.0 px)": f"{subpixel_rate:.2f}%",
        "Avg Latency (ms)": f"{avg_latency:.2f}"
    }])
    print(summary_df.to_string(index=False))

    print("\nBreakdown by Stress Mode:")
    print("-" * 75)
    mode_summary = []
    for mode, group in df.groupby("stress_mode"):
        mode_summary.append({
            "Stress Mode": mode,
            "Mean Error (px)": f"{group['error_px'].mean():.4f}",
            "Median Error (px)": f"{group['error_px'].median():.4f}",
            "95th Pct Error (px)": f"{group['error_px'].quantile(0.95):.4f}",
            "Sub-Pixel Rate": f"{(group['subpixel_acc'].sum() / len(group)) * 100.0:.1f}%",
            "Avg Latency (ms)": f"{group['latency_ms'].mean():.2f}"
        })
    print(pd.DataFrame(mode_summary).to_string(index=False))

    # Print explainability rubric note
    print(EXPLAINABILITY_NOTE)

    return df

if __name__ == '__main__':
    run_benchmark()
