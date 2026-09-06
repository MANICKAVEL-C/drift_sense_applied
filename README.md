# DriftSense Applied - Applied Materials Metrology Challenge

High-precision sub-pixel alignment and metrology system for semiconductor SEM (Scanning Electron Microscope) and RGB Optical Microscope wafer imaging.

## Project Directory Structure

```plaintext
drift_sense_applied/
├── dataset_generator.py   # Physics-backed SEM wafer layout & noise generator
├── predict.py             # High-precision sub-pixel alignment solver
├── test_pipeline.py       # Verification benchmark suite & metric reporter
├── optical_generator.py   # BONUS: 3-Channel RGB Optical Microscope extension
├── visual_evaluator.py    # Visual inspection figure & report generator
├── requirements.txt       # Frozen dependencies list
├── submission.csv         # Generated metrology predictions CSV
└── README.md              # Complete execution & architecture guide
```

---

## 1. Physics-Based SEM Image Generation (`dataset_generator.py`)

`OfficialSEMWaferGenerator` generates paired high-resolution reference images ($1\,\text{nm/px}$, $1000 \times 1000$) and wide-field search images ($10\,\text{nm/px}$, $1000 \times 1000$) incorporating literature-backed physical SEM noise:

1. **Postek (1994) Edge Brightening**: Models secondary electron escape peak intensity at steep topography boundaries via Sobel gradient magnitude operator.
2. **Sim (2004) Poisson Shot Noise**: Simulates low primary electron beam dose quantum statistics using Poisson distribution $k \sim \text{Poisson}(\lambda \cdot I)$.
3. **Cazaux (1999) Surface Charging Swells**: Models low-frequency dielectric potential wells via multi-center 2D spatial Gaussian background fields.

Supports **DRAM** (contact hole arrays + asymmetric crosshair macro) and **FinFET** (fin/gate logic arrays + box macro) layouts across **Standard**, **Heavy Noise**, and **Surface Charging** stress modes.

---

## 2. High-Precision Sub-Pixel Solver (`predict.py`)

Localizes the 10x downsampled reference macro pattern inside the wide-field search image using a multi-stage pipeline:

1. **10x Scale Downsampling**: Resizes $1000 \times 1000$ reference image to $100 \times 100$ pixels (`cv2.INTER_AREA`).
2. **Rolling-Ball Morphological Background Subtraction + Fine Gaussian Filtering**: Applies a fine Gaussian blur ($\sigma=2.0$) to suppress Sim shot noise, then estimates and subtracts the Cazaux charging background via grayscale morphological opening with a large elliptical kernel (search radius 50px, template radius 12px) rather than a symmetric Gaussian blur -- see §5 for why this replaced an earlier, less effective DoG approach.
3. **Normalized Cross-Correlation (NCC)**: Computes template correlation map (`cv2.TM_CCOEFF_NORMED`).
4. **Applied Materials Rule 3 Candidate Selection**: Extracts candidate local maxima within 3% of maximum correlation and selects the peak candidate closest to the image center $(500, 500)$ to resolve periodic array phase aliasing.
5. **2D Quadratic Least-Squares Surface Fitting**: Fits a 2D surface $f(x, y) = ax^2 + by^2 + cx + dy + exy + f$ over all nine points of the $3 \times 3$ correlation peak neighborhood via least squares to achieve sub-pixel spatial precision ($(\Delta x, \Delta y)$ offset).

---

## 3. BONUS CREDIT: 3-Channel RGB Optical Microscope Extension (`optical_generator.py`)

Extends the metrology system to **3-Channel RGB Optical Microscope tools**, modeling thin-film interference color shifts across dielectric wafer stacks:
- Implements `OfficialOpticalWaferGenerator.generate_rgb_pair()` for RGB optical wafer captures.
- Implements `predict_rgb(ref_rgb, search_rgb)` providing sub-pixel accuracy on 3-channel optical microscope tools.

---

## 4. Execution Instructions

### Prerequisites
Install dependencies:
```bash
pip install -r requirements.txt
```

### Run Batch Dataset Generator (200 Image Pairs)
Generate 200 SEM wafer image pairs into `./sem_dataset/` with `ground_truth.csv`:
```bash
python dataset_generator.py --num_pairs 200 --output_dir ./sem_dataset
```

### Run High-Precision Inference Solver
Process test images and export predictions to `submission.csv`:
```bash
python predict.py --input_dir ./sem_dataset --output_csv submission.csv
```

### Run Verification & Benchmark Suite
Run 240 randomized benchmark cases across all stress modes:
```bash
python test_pipeline.py
```

### Run RGB Optical Microscope Bonus Solver
Demonstrate 3-channel RGB optical tool generalization:
```bash
python optical_generator.py
```

### Generate Visual Inspection Figures
Create visual side-by-side inspection figures:
```bash
python visual_evaluator.py
```

---

## 5. Benchmark Results & Failure Case Resolution

**240-pair benchmark (current):**

| Stress Mode | Sub-Pixel Rate (<1.0px) | Median Error (px) | Avg Latency (ms) |
|---|---|---|---|
| Standard | 100.0% | 0.168 | 38.6 |
| Heavy Noise | 100.0% | 0.238 | 38.9 |
| Surface Charging | 100.0% | 0.232 | 38.8 |
| **Overall** | **100.0%** | **0.214** | **38.8** |

Surface Charging was previously the hardest stress mode (41.2% sub-pixel accuracy) due to a
fixed-location contrast-washout artifact. Root cause was traced empirically (not assumed) to
correlation values measured directly on a real failure case: 0.35 at the true site vs. 0.44 at
an unrelated region. Four mitigations were tried and failed (wider Gaussian blur, CLAHE, sliding-
window normalization, two-stage rescoring) before finding one that worked: replacing the
symmetric Gaussian coarse-blur with a rolling-ball morphological background estimate, sized to
selectively remove the charging swell without smearing away legitimate template-scale structure.
Re-verified on the exact seed that originally failed (~460px error) -- now accurate to 0.5px.

**Honest caveat**: this was validated against the synthetic generator's specific charging model
(two fixed Gaussian swells + a linear gradient) and has not been validated against real fab SEM
charging artifacts, which may have different spatial statistics.
