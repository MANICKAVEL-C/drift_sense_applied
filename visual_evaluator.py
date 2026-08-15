"""
visual_evaluator.py - Visual Metrology Inspection & Plotting Suite
Applied Materials Metrology Challenge

Generates side-by-side visual demonstration figures showing reference images, wide search images with
ground truth vs predicted bounding boxes/crosshairs, DoG filter response maps, and sub-pixel error vectors.
"""

import os
import numpy as np
import cv2
import matplotlib.pyplot as plt
from dataset_generator import OfficialSEMWaferGenerator
from predict import get_center_coordinates, apply_dog_filter

def create_visual_inspection_report(output_dir: str = "visual_reports"):
    os.makedirs(output_dir, exist_ok=True)
    generator = OfficialSEMWaferGenerator()

    styles = ["DRAM", "FinFET"]
    for idx, style in enumerate(styles):
        ref_img, search_img, (gt_x, gt_y) = generator.generate_pair(
            seed_val=42 + idx, pattern_style=style, stress_mode="Standard"
        )

        pred_x, pred_y, confidence = get_center_coordinates(ref_img, search_img)
        err = np.sqrt((pred_x - gt_x)**2 + (pred_y - gt_y)**2)

        # Process DoG filter maps
        tpl_10x = cv2.resize(ref_img, (100, 100), interpolation=cv2.INTER_AREA)
        dog_search = apply_dog_filter(search_img, sigma_fine=1.0, sigma_coarse=20.0)

        # Plotting figure
        fig, axes = plt.subplots(1, 3, figsize=(18, 6))
        fig.suptitle(f"DriftSense SEM Wafer Metrology Inspection [{style} Stack] - Error: {err:.4f} px ({err*10:.2f} nm)", fontsize=14, fontweight='bold')

        # 1. Reference Image
        axes[0].imshow(ref_img, cmap='gray')
        axes[0].set_title(f"Reference Image (1000x1000, 1 nm/px)\n[{style} Central Alignment Macro]")
        axes[0].axis('off')

        # 2. Search Image with Overlay
        search_rgb = cv2.cvtColor(search_img, cv2.COLOR_GRAY2RGB)
        
        # Draw Ground Truth Box (Green)
        gt_x_int, gt_y_int = int(round(gt_x)), int(round(gt_y))
        cv2.rectangle(search_rgb, (gt_x_int - 50, gt_y_int - 50), (gt_x_int + 50, gt_y_int + 50), (0, 255, 0), 2)
        cv2.drawMarker(search_rgb, (gt_x_int, gt_y_int), (0, 255, 0), cv2.MARKER_CROSS, 20, 2)

        # Draw Predicted Box (Red)
        pred_x_int, pred_y_int = int(round(pred_x)), int(round(pred_y))
        cv2.rectangle(search_rgb, (pred_x_int - 50, pred_y_int - 50), (pred_x_int + 50, pred_y_int + 50), (255, 0, 0), 2)
        cv2.drawMarker(search_rgb, (pred_x_int, pred_y_int), (255, 0, 0), cv2.MARKER_TILTED_CROSS, 20, 2)

        axes[1].imshow(search_rgb)
        axes[1].set_title(f"Wide Search Image (1000x1000, 10 nm/px)\nGreen: Ground Truth ({gt_x:.1f}, {gt_y:.1f}) | Red: Pred ({pred_x:.1f}, {pred_y:.1f})")
        axes[1].axis('off')

        # 3. DoG Filter Response Map
        axes[2].imshow(dog_search, cmap='inferno')
        axes[2].set_title(f"Difference-of-Gaussians (DoG) Filter Map\n[Surface Charging & Noise Suppressed]")
        axes[2].axis('off')

        plt.tight_layout()
        save_path = os.path.join(output_dir, f"metrology_demo_{style.lower()}.png")
        plt.savefig(save_path, dpi=200, bbox_inches='tight')
        plt.close()
        print(f"Generated visual metrology inspection figure: '{save_path}'")

if __name__ == '__main__':
    create_visual_inspection_report()
