"""
dataset_generator.py - Semiconductor SEM Wafer Image Generator
Applied Materials Metrology Challenge

Generates realistic high-resolution reference images (1 nm/px) and wide-field search images (10 nm/px)
embedding sub-pixel alignment macros with literature-backed SEM noise physics:
  - Postek (1994): Sobel edge brightening (secondary electron escape)
  - Sim (2004): Independent Poisson shot noise (beam electron dose statistics)
  - Cazaux (1999): Localized Gaussian surface charging swells (dielectric charging)
"""

import numpy as np
import cv2

class OfficialSEMWaferGenerator:
    """
    Simulates high-precision SEM wafer layout image pairs for metrology benchmarks.
    """
    def __init__(self, image_size: int = 1000):
        self.image_size = image_size

    def _generate_dram_pattern(self, size: int, scale_factor: float = 1.0, with_macro: bool = True) -> np.ndarray:
        """
        Generates a DRAM memory layout with periodic contact arrays and an optional central macro.
        """
        img = np.full((size, size), 40.0, dtype=np.float32)
        
        # Grid parameters scaled
        pitch = int(40 * scale_factor) if scale_factor >= 0.5 else 4
        pitch = max(pitch, 3)
        radius = max(int(12 * scale_factor), 1)

        # Periodic contact array (dielectric substrate with etched contacts)
        y_coords, x_coords = np.mgrid[:size, :size]
        grid_mask = ((x_coords % pitch - pitch // 2) ** 2 + (y_coords % pitch - pitch // 2) ** 2) <= (radius ** 2)
        img[grid_mask] = 180.0

        if with_macro:
            # Central alignment macro (unique asymmetric structure: crosshair + outer ring + L-bracket)
            center = size // 2
            macro_mask = np.zeros((size, size), dtype=bool)

            # Crosshairs
            arm_len = int(180 * scale_factor)
            arm_thick = max(int(16 * scale_factor), 2)
            macro_mask[center - arm_thick:center + arm_thick, center - arm_len:center + arm_len] = True
            macro_mask[center - arm_len:center + arm_len, center - arm_thick:center + arm_thick] = True

            # Concentric ring
            r_outer = int(120 * scale_factor)
            r_inner = int(90 * scale_factor)
            dist_sq = (x_coords - center)**2 + (y_coords - center)**2
            ring_mask = (dist_sq <= r_outer**2) & (dist_sq >= r_inner**2)
            macro_mask |= ring_mask

            # Asymmetric corner marker (top-right L-bracket)
            offset = int(140 * scale_factor)
            l_size = int(50 * scale_factor)
            l_thick = max(int(12 * scale_factor), 2)
            macro_mask[center - offset:center - offset + l_thick, center + offset - l_size:center + offset] = True
            macro_mask[center - offset:center - offset + l_size, center + offset - l_thick:center + offset] = True

            img[macro_mask] = 230.0

        return img

    def _generate_finfet_pattern(self, size: int, scale_factor: float = 1.0, with_macro: bool = True) -> np.ndarray:
        """
        Generates a FinFET logic layout with parallel fin/gate arrays and an optional central macro.
        """
        img = np.full((size, size), 50.0, dtype=np.float32)

        fin_pitch = max(int(24 * scale_factor), 3)
        fin_width = max(int(8 * scale_factor), 1)
        gate_pitch = max(int(60 * scale_factor), 6)
        gate_width = max(int(14 * scale_factor), 2)

        y_coords, x_coords = np.mgrid[:size, :size]
        fin_mask = (x_coords % fin_pitch) < fin_width
        gate_mask = (y_coords % gate_pitch) < gate_width

        img[fin_mask] = 130.0
        img[gate_mask] = 160.0
        img[fin_mask & gate_mask] = 210.0

        if with_macro:
            # Central alignment macro
            center = size // 2
            macro_mask = np.zeros((size, size), dtype=bool)

            box_size = int(150 * scale_factor)
            border_thick = max(int(16 * scale_factor), 2)
            
            outer_box = (np.abs(x_coords - center) <= box_size) & (np.abs(y_coords - center) <= box_size)
            inner_box = (np.abs(x_coords - center) <= (box_size - border_thick)) & (np.abs(y_coords - center) <= (box_size - border_thick))
            macro_mask |= (outer_box & ~inner_box)

            # Center dot marker
            dot_r = max(int(20 * scale_factor), 2)
            macro_mask |= ((x_coords - center)**2 + (y_coords - center)**2 <= dot_r**2)

            img[macro_mask] = 240.0

        return img

    def _apply_sem_physics_noise(self, img: np.ndarray, stress_mode: str = "Standard") -> np.ndarray:
        """
        Applies literature-backed SEM physical noise models:
          1. Postek (1994): Edge brightening via Sobel operators.
          2. Cazaux (1999): Localized Gaussian surface charging swells.
          3. Sim (2004): Independent Poisson shot noise.
        """
        img_float = img.copy().astype(np.float64)

        # Set stress parameters
        if stress_mode == "Heavy Noise":
            edge_gain = 0.35
            dose_factor = 25.0  # Low electron dose -> high shot noise
            charging_amplitude = 25.0
        elif stress_mode == "Surface Charging":
            edge_gain = 0.25
            dose_factor = 60.0
            charging_amplitude = 75.0  # Large surface potential swell
        else:  # Standard
            edge_gain = 0.25
            dose_factor = 80.0
            charging_amplitude = 20.0

        # 1. Postek (1994) Edge Brightening
        sobel_x = cv2.Sobel(img_float, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(img_float, cv2.CV_64F, 0, 1, ksize=3)
        edge_mag = cv2.magnitude(sobel_x, sobel_y)
        img_brightened = img_float + edge_gain * edge_mag

        # 2. Cazaux (1999) Surface Charging Swells (Low-frequency spatial Gaussian swell)
        h, w = img.shape
        y_grid, x_grid = np.mgrid[:h, :w]
        
        # Primary central swell
        cx1, cy1 = w * 0.45, h * 0.55
        sigma1 = 250.0
        charging_map = charging_amplitude * np.exp(-((x_grid - cx1)**2 + (y_grid - cy1)**2) / (2 * sigma1**2))

        # Secondary off-axis swell
        cx2, cy2 = w * 0.7, h * 0.3
        sigma2 = 180.0
        charging_map += (charging_amplitude * 0.6) * np.exp(-((x_grid - cx2)**2 + (y_grid - cy2)**2) / (2 * sigma2**2))

        # Linear background potential gradient
        charging_map += (x_grid / w) * (charging_amplitude * 0.3)

        img_charged = img_brightened + charging_map

        # 3. Sim (2004) Poisson Shot Noise
        normalized = np.clip(img_charged, 1.0, 255.0) / 255.0
        electron_counts = normalized * dose_factor
        poisson_counts = np.random.poisson(electron_counts)
        noisy_img = (poisson_counts / dose_factor) * 255.0

        return np.clip(noisy_img, 0, 255).astype(np.uint8)

    def generate_pair(self, seed_val: int = None, pattern_style: str = "DRAM", stress_mode: str = "Standard"):
        """
        Generates reference and wide search image pair with target ground truth sub-pixel coordinates.

        Returns:
            ref_img (np.ndarray): 1000x1000 uint8 reference image at 1 nm/px.
            search_img (np.ndarray): 1000x1000 uint8 wide search image at 10 nm/px.
            gt_coords (tuple): (gt_x, gt_y) sub-pixel ground truth center location of macro in search_img.
        """
        if seed_val is not None:
            np.random.seed(seed_val)

        # 1. Generate high-res 1000x1000 reference pattern (1 nm/px scale)
        if pattern_style == "FinFET":
            ref_clean = self._generate_finfet_pattern(self.image_size, scale_factor=1.0, with_macro=True)
            search_clean_bg = self._generate_finfet_pattern(self.image_size, scale_factor=0.1, with_macro=False)
        else: # DRAM
            ref_clean = self._generate_dram_pattern(self.image_size, scale_factor=1.0, with_macro=True)
            search_clean_bg = self._generate_dram_pattern(self.image_size, scale_factor=0.1, with_macro=False)

        # Generate exact 10x downsampled macro tile (100x100) from the 1000x1000 reference pattern
        ref_tile_clean = cv2.resize(ref_clean, (100, 100), interpolation=cv2.INTER_AREA)

        # 2. Select sub-pixel target coordinates for embedding (within 250..750 range)
        gt_x = float(np.random.uniform(250.0, 750.0))
        gt_y = float(np.random.uniform(250.0, 750.0))

        # 3. Embed 10x downsampled macro tile into search image background at sub-pixel location
        # Tile center is at (50, 50). Translation vector maps (50, 50) -> (gt_x, gt_y)
        tx = gt_x - 50.0
        ty = gt_y - 50.0
        affine_mat = np.array([[1.0, 0.0, tx], [0.0, 1.0, ty]], dtype=np.float32)

        warped_tile = cv2.warpAffine(
            ref_tile_clean, affine_mat, (self.image_size, self.image_size),
            flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=0
        )
        
        # Mask for blending tile (non-background pixels)
        tile_mask = (ref_tile_clean > 55.0).astype(np.float32)
        warped_mask = cv2.warpAffine(
            tile_mask, affine_mat, (self.image_size, self.image_size),
            flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=0
        )
        warped_mask = np.clip(warped_mask, 0.0, 1.0)

        # Composite tile over periodic background
        search_composite = search_clean_bg * (1.0 - warped_mask) + warped_tile * warped_mask

        # 4. Apply physical SEM noise to reference and search images
        ref_img = self._apply_sem_physics_noise(ref_clean, stress_mode=stress_mode)
        search_img = self._apply_sem_physics_noise(search_composite, stress_mode=stress_mode)

        return ref_img, search_img, (gt_x, gt_y)

if __name__ == '__main__':
    generator = OfficialSEMWaferGenerator()
    ref, search, (gt_x, gt_y) = generator.generate_pair(seed_val=42, pattern_style="DRAM", stress_mode="Standard")
    print(f"Generated SEM Wafer Pair successfully!")
    print(f"Ref image shape: {ref.shape}, Search image shape: {search.shape}")
    print(f"Ground Truth macro position: (gt_x={gt_x:.4f}, gt_y={gt_y:.4f})")
