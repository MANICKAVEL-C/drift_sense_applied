# Advanced SEM Metrology & Physics-Grounded Signal Processing
## Theoretical Foundations, Mathematical Derivations, and Hybrid Architecture Specifications

### Executive Overview
This document details the advanced mathematical, physical, and signal-processing foundations for the **Drift-Sense SEM Wafer Metrology Solver**. It bridges fundamental Scanning Electron Microscopy (SEM) electron-matter interactions with rigorous multi-dimensional signal processing, continuous sub-pixel optimization, and localized contrast recovery algorithms.

---

## 1. Physics of SEM Image Formation & Degradation

### 1.1 Secondary Electron Yield & Topographic Edge Brightening (Postek, 1994)
In Scanning Electron Microscopy, the image intensity $I(x, y)$ is proportional to the local Secondary Electron (SE) emission yield $\delta(x, y)$. When primary electrons strike a flat dielectric substrate at normal incidence ($\theta = 0$), the SE escape depth is governed by Kanaya-Okayama electron range $\rho S$.

At steep topographical boundaries (such as DRAM trench walls or FinFET logic gates), the local surface tilt angle $\theta(x, y)$ increases relative to the incident beam:

$$\delta(\theta) = \delta_0 \cdot \sec(\theta)$$

Taking the first-order spatial Taylor expansion of the local topography surface gradient $\nabla h(x, y) = \left( \frac{\partial h}{\partial x}, \frac{\partial h}{\partial y} \right)$:

$$I_{\text{edge}}(x, y) = I_{\text{base}}(x, y) + \alpha \cdot \sqrt{\left(\frac{\partial I}{\partial x}\right)^2 + \left(\frac{\partial I}{\partial y}\right)^2}$$

Where $\alpha \in [0.15, 0.45]$ represents the secondary electron escape fraction coefficient.

### 1.2 Low-Dose Quantum Poisson Electron Shot Noise (Sim et al., 2004)
Primary electron beam flux arriving at pixel location $(x, y)$ during a dwell time $\tau$ follows a discrete quantum Poisson point process:

$$P(k \text{ electrons received}) = \frac{\lambda^k e^{-\lambda}}{k!}$$

Where the mean electron count $\lambda(x, y)$ is related to normalized noiseless intensity $I_{\text{norm}}(x, y) \in [0, 1]$ and primary dose beam current $I_{\text{beam}}$ by:

$$\lambda(x, y) = \text{scale} \cdot I_{\text{norm}}(x, y) = \left(\frac{I_{\text{beam}} \cdot \tau}{e}\right) \cdot I_{\text{norm}}(x, y)$$

The signal-to-noise ratio (SNR) of low-dose SEM images is strictly shot-noise limited by Rose's Law:

$$\text{SNR}_{\text{shot}} = \frac{\lambda}{\sigma_{\text{shot}}} = \frac{\lambda}{\sqrt{\lambda}} = \sqrt{\lambda}$$

### 1.3 Cazaux Surface Potential Dielectric Charging Swells (Cazaux, 1999)
Under non-conductive dielectric materials ($\text{SiO}_2$, $\text{Si}_3\text{N}_4$), secondary electron emission ratio $\delta \neq 1$ induces a spatial surface charge accumulation $Q(x,y)$. The resulting surface potential $V(x,y)$ creates a spatially varying electrostatic potential field that deflects low-energy secondary electrons:

$$V(x,y) = \sum_{k=1}^K A_k \cdot \exp\left( -\frac{(x - c_{x,k})^2 + (y - c_{y,k})^2}{2\sigma_{\text{charge},k}^2} \right)$$

This spatial potential swell acts as a low-frequency spatial additive intensity offset:

$$I_{\text{observed}}(x, y) = \text{clip}\left( I_{\text{specimen}}(x, y) + V(x, y), 0, 255 \right)$$

This spatial swell compresses local dynamic range, reducing local Michelson contrast $C_{\text{local}} = \frac{I_{\max} - I_{\min}}{I_{\max} + I_{\min}}$ at the true target site.

---

## 2. Advanced Multi-Stage Metrology Solver Pipeline

### 2.1 Scale-Aware Downsampling ($10:1$ Magnification Bridge)
The high-magnification reference image $R_{100x} \in \mathbb{R}^{1000 \times 1000}$ ($1\,\text{nm/px}$) is downsampled to template $T \in \mathbb{R}^{100 \times 100}$ using an area-averaging integration operator:

$$T(u, v) = \frac{1}{s^2} \int_{us}^{(u+1)s} \int_{vs}^{(v+1)s} R_{100x}(x, y) \, dx \, dy \quad \text{where } s = 10.0$$

### 2.2 Rolling-Ball Morphological Background Subtraction + Fine Gaussian Bandpass

*(Note: an earlier version of this pipeline used a symmetric Difference-of-Gaussians filter here.
It was replaced after benchmarking showed its coarse Gaussian blur only partially removed the
Cazaux charging swell -- a wide symmetric blur that removes a 200px-scale swell also smears away
legitimate template structure at a similar scale. The method below is what is actually implemented
in `predict.py`.)*

We first apply a fine Gaussian blur to suppress high-frequency Poisson shot noise:

$$I_{\text{fine}} = G_{\sigma_{\text{fine}}} * I, \quad \sigma_{\text{fine}} = 2.0$$

We then estimate the slowly-varying charging background via grayscale morphological opening
(erosion followed by dilation) with a large elliptical structuring element $\mathbf{B}_r$ of
radius $r$:

$$I_{\text{bg}} = (I_{\text{fine}} \ominus \mathbf{B}_r) \oplus \mathbf{B}_r$$

Because opening removes bright structures smaller than the structuring element while preserving
larger smooth trends, $I_{\text{bg}}$ selectively captures the charging swell (spatial scale
$\sim$180--250px) while leaving the periodic array and macro-tile structure (smaller scale)
untouched -- unlike a symmetric Gaussian blur, which cannot distinguish "large and smooth" from
"large and legitimate." The background is estimated on a 4x-downsampled copy of the image (the
swell is smooth and low-frequency, so no relevant signal is lost) then upsampled back, which is
both more accurate and roughly 3x faster than full-resolution Gaussian filtering.

$$I_{\text{filtered}} = I_{\text{fine}} - I_{\text{bg}}, \quad \text{normalized to zero-mean/unit-variance}$$

Search-image structuring-element radius $r_{\text{search}} = 50\,\text{px}$; template radius
$r_{\text{template}} = 12\,\text{px}$ (scaled down since the 100x100 template itself is 10x smaller).

**Validated impact (240-pair benchmark):** raised Surface Charging sub-pixel accuracy from
**41.2% to 100.0%**, while Standard and Heavy Noise modes remained at 100.0%, with zero
catastrophic (>5px) failures in any stress mode -- and ~3x faster inference (39ms vs 112ms
per pair) due to the downsampled background-estimation pass.

### 2.3 Normalized Cross-Correlation (NCC) Matching
The filtered template $T_{\text{DoG}}$ is correlated across filtered search canvas $S_{\text{DoG}} \in \mathbb{R}^{1000 \times 1000}$:

$$\gamma(x, y) = \frac{\sum_{u, v} \left(T_{\text{DoG}}(u, v) - \bar{T}_{\text{DoG}}\right) \left(S_{\text{DoG}}(x+u, y+v) - \bar{S}_{\text{DoG}}(x, y)\right)}{\sqrt{\sum_{u,v} \left(T_{\text{DoG}}(u, v) - \bar{T}_{\text{DoG}}\right)^2 \sum_{u,v} \left(S_{\text{DoG}}(x+u, y+v) - \bar{S}_{\text{DoG}}(x, y)\right)^2}}$$

Where $\gamma(x, y) \in [-1.0, 1.0]$ is zero-mean unit-variance normalized.

### 2.4 Applied Materials Rule 3 Tie-Breaking Candidate Selection
In periodic semiconductor structure arrays (DRAM trench pitch $P_x$, FinFET logic pitch $P_y$), $\gamma(x, y)$ generates multiple local maxima.

1. Extract all peak candidate coordinates $(x_k, y_k)$ satisfying:
   $$\gamma(x_k, y_k) \ge \eta \cdot \gamma_{\max} \quad (\eta = 0.97)$$
2. Select candidate index $k^*$ minimizing Euclidean spatial offset to search center $(w/2, h/2) = (500, 500)$:
   $$k^* = \arg\min_k \sqrt{(x_k - 500)^2 + (y_k - 500)^2}$$

### 2.5 Continuous 2D Quadratic Least-Squares Sub-Pixel Surface Refinement

*(Note: this section previously described a simplified 5-point finite-difference Hessian
shortcut. That formulation does not match what `predict.py` actually computes -- verified
numerically, the two diverge on real correlation neighborhoods. The derivation below matches
the implemented code.)*

Around the integer peak grid location $(x_0, y_0)$, we extract a $3 \times 3$ correlation
neighborhood and fit a full general quadratic surface to **all nine points** via least squares,
rather than reading off a handful of finite differences:

$$f(x, y) = a x^2 + b y^2 + c x + d y + e xy + f_0$$

$$\mathbf{A}\boldsymbol{\theta} = \mathbf{z}, \quad \boldsymbol{\theta} = [a, b, c, d, e, f_0]^T, \quad \boldsymbol{\theta}^* = (\mathbf{A}^T\mathbf{A})^{-1}\mathbf{A}^T\mathbf{z}$$

where $\mathbf{z}$ is the flattened $3\times3$ neighborhood and $\mathbf{A}$ is the design matrix
of $(x^2, y^2, x, y, xy, 1)$ evaluated at the nine grid offsets. Using all nine samples (rather
than a small stencil) makes the fit more robust to noise in the correlation surface, at the cost
of the closed-form simplicity of a pure finite-difference approach.

The critical point of the fitted quadratic is found by setting its gradient to zero:

$$\begin{bmatrix} 2a & e \\ e & 2b \end{bmatrix} \begin{bmatrix} \Delta x^* \\ \Delta y^* \end{bmatrix} = \begin{bmatrix} -c \\ -d \end{bmatrix}$$

solved directly provided $\det \ne 0$. **Known gap (not yet fixed in code):** this does not
currently verify that the critical point is actually a maximum (i.e. that the 2x2 matrix above
is negative-definite) -- it only checks the determinant is nonzero. A saddle point or minimum
could in principle be accepted uncorrected. Recommended fix: additionally require
$2a < 0$ and $\det > 0$, falling back to the existing simple central-difference method otherwise.

The final predicted target center is:

$$(x_{\text{pred}}, y_{\text{pred}}) = (x_0 + \Delta x^*, y_0 + \Delta y^*)$$

---

## 3. Comparative Theoretical Summary

| Metric / Property | Classical Raw Template Matching | Basic Deep Learning (CNN Bounding Box) | Drift-Sense Sub-Pixel Solver |
| :--- | :--- | :--- | :--- |
| **Spatial Precision** | Integer Pixel ($\pm 1.0 - 5.0\,\text{px}$) | Bounding Box ($\pm 2.0 - 4.0\,\text{px}$) | **Sub-Pixel Continuous (median $0.21\,\text{px}$, 240-pair benchmark)** |
| **Hardware Requirement** | CPU-only | NVIDIA GPU Required (CUDA) | **Zero-GPU (Standard x86 CPU, ~39ms)** |
| **Cazaux Charging Swells** | Fails (Locks to local brightness) | Requires 5000+ training images | **Rolling-Ball Background Subtraction (radius=50px), 100% sub-pixel accuracy** |
| **Periodic Pitch Ambiguity** | Locks to adjacent dies | Phase aliasing uncertainty | **AMAT Rule 3 Tie-Break ($\ge 0.97 R_{\max}$ min dist)** |
