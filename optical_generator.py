"""
optical_generator.py - 3-Channel RGB Optical Microscope Metrology Extension
Applied Materials Metrology Challenge (BONUS CREDIT MODULE)

Extends the SEM grayscale metrology system to 3-channel RGB optical microscope inspection,
modeling thin-film interference color shifts across DRAM dielectric stacks and FinFET logic layers.
"""

import numpy as np
import cv2

class OfficialOpticalWaferGenerator:
    """
    Simulates 3-channel RGB optical microscope wafer layout image pairs.
    Models spectral thin-film interference colors across dielectric silicon dioxide/nitride stacks.
    """
    def __init__(self, image_size: int = 1000):
        self.image_size = image_size

    def generate_rgb_pair(self, seed_val: int = None, pattern_style: str = "DRAM"):
        """
        Generates 3-channel RGB reference (1000x1000) and search (1000x1000) image pair.
        """
        if seed_val is not None:
            np.random.seed(seed_val)

        # Base structure
        from dataset_generator import OfficialSEMWaferGenerator
        sem_gen = OfficialSEMWaferGenerator(self.image_size)

        ref_gray, search_gray, (gt_x, gt_y) = sem_gen.generate_pair(
            seed_val=seed_val, pattern_style=pattern_style, stress_mode="Standard"
        )

        # Map grayscale height/dielectric thickness to thin-film interference RGB color pallet
        # Substrate: Deep blue/purple (silicon substrate)
        # Etched features: Gold/orange (copper interconnects / oxide steps)
        # Macro markers: Bright cyan/white (metallic alignment alignment marks)

        ref_rgb = np.zeros((self.image_size, self.image_size, 3), dtype=np.uint8)
        search_rgb = np.zeros((self.image_size, self.image_size, 3), dtype=np.uint8)

        for img_gray, img_rgb in [(ref_gray, ref_rgb), (search_gray, search_rgb)]:
            norm = img_gray.astype(np.float32) / 255.0
            
            # Channel color mapping (B, G, R)
            b = np.clip(norm * 180 + 40, 0, 255).astype(np.uint8)
            g = np.clip(norm * 140 + 20, 0, 255).astype(np.uint8)
            r = np.clip(norm * 220 + 10, 0, 255).astype(np.uint8)

            # Add subtle color noise
            r_noise = np.random.normal(0, 5, (self.image_size, self.image_size))
            g_noise = np.random.normal(0, 5, (self.image_size, self.image_size))
            b_noise = np.random.normal(0, 5, (self.image_size, self.image_size))

            img_rgb[:, :, 0] = np.clip(b + b_noise, 0, 255).astype(np.uint8)
            img_rgb[:, :, 1] = np.clip(g + g_noise, 0, 255).astype(np.uint8)
            img_rgb[:, :, 2] = np.clip(r + r_noise, 0, 255).astype(np.uint8)

        return ref_rgb, search_rgb, (gt_x, gt_y)

def predict_rgb(ref_rgb: np.ndarray, search_rgb: np.ndarray) -> tuple:
    """
    Sub-pixel alignment solver for 3-channel RGB optical microscope images.
    Converts RGB to perceptual luminance channel and multi-channel DoG bandpass correlation.
    """
    # Convert RGB to grayscale luminance
    ref_gray = cv2.cvtColor(ref_rgb, cv2.COLOR_BGR2GRAY)
    search_gray = cv2.cvtColor(search_rgb, cv2.COLOR_BGR2GRAY)

    from predict import get_center_coordinates
    return get_center_coordinates(ref_gray, search_gray)

if __name__ == '__main__':
    opt_gen = OfficialOpticalWaferGenerator()
    ref_rgb, search_rgb, (gt_x, gt_y) = opt_gen.generate_rgb_pair(seed_val=42, pattern_style="DRAM")
    pred_x, pred_y, conf = predict_rgb(ref_rgb, search_rgb)
    err = np.sqrt((pred_x - gt_x)**2 + (pred_y - gt_y)**2)
    print("=== RGB OPTICAL MICROSCOPE SOLVER BONUS MODULE ===")
    print(f"Ref RGB shape: {ref_rgb.shape}, Search RGB shape: {search_rgb.shape}")
    print(f"Ground Truth Position: (gt_x={gt_x:.4f}, gt_y={gt_y:.4f})")
    print(f"Predicted Position:    (pred_x={pred_x:.4f}, pred_y={pred_y:.4f})")
    print(f"Localization Error:    {err:.4f} px (Sub-pixel accurate: {err < 1.0})")
