import os
import cv2
import pandas as pd
from dataset_generator import OfficialSEMWaferGenerator

print("=========================================================")
print("   GENERATING 200 HIGH-ACCURACY SEM DATASET PAIRS       ")
print("=========================================================")

os.makedirs("./sem_dataset_200/reference", exist_ok=True)
os.makedirs("./sem_dataset_200/search", exist_ok=True)

gen = OfficialSEMWaferGenerator()
modes = ["standard", "heavy_noise", "charging"]
gt_records = []

for idx in range(200):
    mode = modes[idx % 3]  # Evenly distributes across Standard, Heavy Noise, and Charging
    ref_img, search_img, (gt_x, gt_y) = gen.generate_pair(seed_val=2000 + idx, stress_mode=mode)
    
    sample_id = f"sample_{idx+1:03d}"
    cv2.imwrite(f"./sem_dataset_200/reference/ref_{idx+1:03d}.png", ref_img)
    cv2.imwrite(f"./sem_dataset_200/search/search_{idx+1:03d}.png", search_img)
    
    gt_records.append({
        "sample_id": sample_id,
        "gt_x": gt_x,
        "gt_y": gt_y,
        "stress_mode": mode
    })

    if (idx + 1) % 50 == 0:
        print(f"Progress: {idx + 1}/200 image pairs created...")

# Save ground truth manifest
df = pd.DataFrame(gt_records)
df.to_csv("./sem_dataset_200/ground_truth_200.csv", index=False)

print("\n[SUCCESS] Generated 200 dataset pairs in './sem_dataset_200/'!")
print("=========================================================")