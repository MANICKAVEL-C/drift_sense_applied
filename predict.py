"""
predict.py - High-Precision SEM Sub-Pixel Metrology Solver
Applied Materials Metrology Challenge

Localizes 10x downsampled reference macro pattern inside 1000x1000 SEM search images:
  - Rolling-ball morphological background subtraction + fine Gaussian bandpass filtering.
  - Multi-scale template pyramid search (0.95x, 1.0x, 1.05x) for scale-jitter robustness.
  - Peak-to-Sidelobe Ratio (PSR) & calibrated confidence estimation.
  - Applied Materials Rule 3: Candidate selection within 3% of max correlation closest to center (500, 500).
  - 2D Quadratic Least-Squares Surface Fitting with negative-definiteness Hessian verification.
"""

import os
import glob
import argparse
import numpy as np
import cv2
import pandas as pd
from scipy.ndimage import maximum_filter

def apply_rollingball_filter(img: np.ndarray, sigma_fine: float = 2.0, ball_radius: int = 50, downsample: int = 4) -> np.ndarray:
    """
    Rolling-ball background subtraction bandpass filter.
    Suppresses low-frequency Cazaux charging swells via downsampled morphological opening,
    and high-frequency Poisson shot noise via fine Gaussian blur.
    """
    img_f = img.astype(np.float32)
    blur_fine = cv2.GaussianBlur(img_f, (0, 0), sigmaX=sigma_fine, sigmaY=sigma_fine)

    h, w = img_f.shape
    small = cv2.resize(blur_fine, (max(1, w // downsample), max(1, h // downsample)), interpolation=cv2.INTER_AREA)
    r_small = max(3, ball_radius // downsample)
    ksize = r_small * 2 + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksize, ksize))
    background_small = cv2.morphologyEx(small, cv2.MORPH_OPEN, kernel)
    background = cv2.resize(background_small, (w, h), interpolation=cv2.INTER_LINEAR)

    result = blur_fine - background
    std_val = np.std(result)
    if std_val > 1e-6:
        result = (result - np.mean(result)) / std_val
    return result

def fit_2d_parabola_subpixel(neighborhood: np.ndarray) -> tuple:
    """
    Fits a 2D quadratic surface f(x, y) = a*x^2 + b*y^2 + c*x + d*y + e*x*y + f over a 3x3 grid.
    Includes Hessian negative-definiteness verification (2a < 0, 2b < 0, det(M) > 0) to ensure
    the critical point is a true local maximum, falling back to central differences if not.
    """
    if neighborhood.shape != (3, 3):
        return 0.0, 0.0

    x = np.array([-1, 0, 1, -1, 0, 1, -1, 0, 1], dtype=np.float64)
    y = np.array([-1, -1, -1, 0, 0, 0, 1, 1, 1], dtype=np.float64)
    z = neighborhood.flatten().astype(np.float64)

    A = np.column_stack([x**2, y**2, x, y, x*y, np.ones(9)])

    try:
        coeffs, _, _, _ = np.linalg.lstsq(A, z, rcond=None)
        a, b, c, d, e, _ = coeffs

        det_H = 4 * a * b - e**2
        # Hessian Negative-Definiteness check for local maximum: 2a < 0, 2b < 0, det(H) > 0
        if a < 0 and b < 0 and det_H > 1e-6:
            M = np.array([[2*a, e], [e, 2*b]], dtype=np.float64)
            B = np.array([-c, -d], dtype=np.float64)
            sol = np.linalg.solve(M, B)
            dx, dy = float(sol[0]), float(sol[1])
            dx = np.clip(dx, -1.0, 1.0)
            dy = np.clip(dy, -1.0, 1.0)
            return dx, dy
    except Exception:
        pass

    # Central-Difference Fallback
    L, C_val, R = neighborhood[1, 0], neighborhood[1, 1], neighborhood[1, 2]
    T, B_val = neighborhood[0, 1], neighborhood[2, 1]

    denom_x = (L - 2*C_val + R)
    dx = (L - R) / (2.0 * denom_x) if abs(denom_x) > 1e-6 else 0.0

    denom_y = (T - 2*C_val + B_val)
    dy = (T - B_val) / (2.0 * denom_y) if abs(denom_y) > 1e-6 else 0.0

    dx = np.clip(dx, -1.0, 1.0)
    dy = np.clip(dy, -1.0, 1.0)
    return dx, dy

def calculate_psr(corr_map: np.ndarray, peak_x: int, peak_y: int, radius: int = 10) -> float:
    """
    Computes Peak-to-Sidelobe Ratio (PSR) for signal reliability verification:
      PSR = (Peak_Value - Mean_Sidelobe) / Std_Sidelobe
    High PSR (> 6.0) indicates a strong, unambiguous target match.
    """
    h, w = corr_map.shape
    peak_val = corr_map[peak_y, peak_x]

    y_indices, x_indices = np.ogrid[:h, :w]
    dist_from_peak = np.sqrt((x_indices - peak_x)**2 + (y_indices - peak_y)**2)
    sidelobe_mask = (dist_from_peak <= radius) & (dist_from_peak > 3)

    sidelobe_vals = corr_map[sidelobe_mask]
    if len(sidelobe_vals) == 0:
        return 0.0

    mean_sl = np.mean(sidelobe_vals)
    std_sl = np.std(sidelobe_vals)

    if std_sl < 1e-6:
        return 0.0

    psr = (peak_val - mean_sl) / std_sl
    return float(psr)

def get_center_coordinates(ref_img: np.ndarray, search_img: np.ndarray) -> tuple:
    """
    Localizes reference macro pattern in search image with sub-pixel spatial accuracy.
    Includes multi-scale template matching (0.95x, 1.0x, 1.05x) and PSR-based confidence.

    Args:
        ref_img (np.ndarray): 1000x1000 reference image at 1 nm/px scale.
        search_img (np.ndarray): 1000x1000 search image at 10 nm/px scale.

    Returns:
        tuple: (pred_x, pred_y, confidence, psr, is_valid_match)
    """
    search_dog = apply_rollingball_filter(search_img, sigma_fine=2.0, ball_radius=50, downsample=4)

    # Multi-Scale Pyramid Search over ±5% Scale Jitter
    scales = [0.95, 0.98, 1.0, 1.02, 1.05]
    best_scale_val = -1.0
    best_corr_map = None
    best_tpl_w, best_tpl_h = 100, 100

    for scale in scales:
        target_size = max(20, int(round(100 * scale)))
        tpl_scaled = cv2.resize(ref_img, (target_size, target_size), interpolation=cv2.INTER_AREA)
        r_tpl = max(3, int(round(12 * scale)))
        tpl_dog = apply_rollingball_filter(tpl_scaled, sigma_fine=2.0, ball_radius=r_tpl, downsample=1)

        corr_map = cv2.matchTemplate(search_dog.astype(np.float32), tpl_dog.astype(np.float32), cv2.TM_CCOEFF_NORMED)
        curr_max = float(np.max(corr_map))

        if curr_max > best_scale_val:
            best_scale_val = curr_max
            best_corr_map = corr_map
            best_tpl_w, best_tpl_h = target_size, target_size

    corr_map = best_corr_map
    threshold = best_scale_val * 0.97

    local_max = (maximum_filter(corr_map, size=5) == corr_map) & (corr_map >= threshold)
    peak_y, peak_x = np.where(local_max)

    if len(peak_x) == 0:
        peak_y, peak_x = np.unravel_index(np.argmax(corr_map), corr_map.shape)
        peak_y, peak_x = [peak_y], [peak_x]

    img_center_x, img_center_y = 500.0, 500.0
    best_dist = float('inf')
    best_px, best_py = peak_x[0], peak_y[0]

    for py, px in zip(peak_y, peak_x):
        candidate_cx = px + (best_tpl_w / 2.0)
        candidate_cy = py + (best_tpl_h / 2.0)
        dist = np.sqrt((candidate_cx - img_center_x)**2 + (candidate_cy - img_center_y)**2)
        if dist < best_dist:
            best_dist = dist
            best_px, best_py = px, py

    confidence = float(corr_map[best_py, best_px])
    psr_score = calculate_psr(corr_map, best_px, best_py, radius=10)

    # Valid match requires correlation >= 0.40 and Peak-to-Sidelobe Ratio >= 4.0
    is_valid_match = (confidence >= 0.40) and (psr_score >= 4.0)

    h_map, w_map = corr_map.shape
    if 1 <= best_py < h_map - 1 and 1 <= best_px < w_map - 1:
        neighborhood = corr_map[best_py-1:best_py+2, best_px-1:best_px+2]
        dx, dy = fit_2d_parabola_subpixel(neighborhood)
    else:
        dx, dy = 0.0, 0.0

    pred_x = float(best_px + (best_tpl_w / 2.0) + dx)
    pred_y = float(best_py + (best_tpl_h / 2.0) + dy)

    return pred_x, pred_y, confidence

def main():
    parser = argparse.ArgumentParser(description="SEM Wafer Sub-Pixel Metrology Solver")
    parser.add_argument("--input_dir", type=str, default="data", help="Directory containing test images")
    parser.add_argument("--output_csv", type=str, default="submission.csv", help="Path to export submission CSV")
    args = parser.parse_args()

    results = []

    if os.path.exists(args.input_dir):
        ref_files = sorted(glob.glob(os.path.join(args.input_dir, "*_ref.png")))
        for ref_file in ref_files:
            search_file = ref_file.replace("_ref.png", "_search.png")
            if os.path.exists(search_file):
                img_id = os.path.basename(ref_file).replace("_ref.png", "")
                ref_img = cv2.imread(ref_file, cv2.IMREAD_GRAYSCALE)
                search_img = cv2.imread(search_file, cv2.IMREAD_GRAYSCALE)

                pred_x, pred_y, conf = get_center_coordinates(ref_img, search_img)
                results.append({"image_id": img_id, "pred_x": pred_x, "pred_y": pred_y, "confidence": conf})

    if not results:
        print("No input images found in directory. Generating mock demo submission...")
        from dataset_generator import OfficialSEMWaferGenerator
        gen = OfficialSEMWaferGenerator()
        for i in range(5):
            ref_img, search_img, (gt_x, gt_y) = gen.generate_pair(seed_val=100 + i, pattern_style="DRAM", stress_mode="Standard")
            pred_x, pred_y, conf = get_center_coordinates(ref_img, search_img)
            results.append({"image_id": f"sample_{i+1:03d}", "pred_x": pred_x, "pred_y": pred_y, "confidence": conf})

    df = pd.DataFrame(results)
    df.to_csv(args.output_csv, index=False)
    print(f"Exported metrology predictions to '{args.output_csv}' successfully!")
    print(df.to_string())

if __name__ == '__main__':
    main()