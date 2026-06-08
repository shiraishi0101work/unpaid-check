from PIL import Image
import numpy as np

orig = r"C:\Users\shira_k13727w\OneDrive\Desktop\クロード保管用\17【岩田さん用株式会社Della Force会社概要資料】\page6_original.png"
img = Image.open(orig).convert("RGB")
arr = np.array(img, dtype=np.float32)
W, H = img.size

BG_Y0, BG_Y1 = 1035, 1820
left_bg  = arr[BG_Y0:BG_Y1,  20:100, :].mean(axis=1)
right_bg = arr[BG_Y0:BG_Y1, 3740:3820, :].mean(axis=1)
zone_h = BG_Y1 - BG_Y0
xs = np.linspace(0, 1, W)
bg_zone = np.zeros((zone_h, W, 3), dtype=np.float32)
for c in range(3):
    bg_zone[:, :, c] = left_bg[:, c:c+1] * (1-xs) + right_bg[:, c:c+1] * xs

# Check within group 1 (x=1675-2936) with smaller gap detection
y0, y1 = 1100, 1600  # Middle of logo zone, icon area only (not text)
logo_strip = arr[y0:y1, 1675:2937, :]
bg_strip   = bg_zone[y0-BG_Y0:y1-BG_Y0, 1675:2937, :]
diff = np.abs(logo_strip - bg_strip).max(axis=(0, 2))

threshold = 25
content_cols = np.where(diff > threshold)[0]

# Find gap within group 1
print("Diff values around middle of group 1 (offset from x=1675):")
mid = 1675 + 630  # middle of group 1 range
offset = mid - 1675
print(f"Checking around offset {offset} (absolute x={mid}):")
for d in range(-80, 80, 5):
    col = offset + d
    if 0 <= col < len(diff):
        print(f"  col+{d} (x={1675+col}): diff={diff[col]:.1f}")

# Find sub-groups within group 1
groups2 = []
if len(content_cols) > 0:
    start = int(content_cols[0])
    prev  = int(content_cols[0])
    for c in content_cols[1:]:
        c = int(c)
        if c - prev > 30:
            groups2.append((1675+start, 1675+prev))
            start = c
        prev = c
    groups2.append((1675+start, 1675+prev))

print(f"\nSub-groups in group1 (gap>30): {len(groups2)}")
for i, (x0, x1) in enumerate(groups2):
    print(f"  {i}: x={x0}-{x1}, width={x1-x0}")

# Also try gap threshold 20
groups3 = []
if len(content_cols) > 0:
    start = int(content_cols[0])
    prev  = int(content_cols[0])
    for c in content_cols[1:]:
        c = int(c)
        if c - prev > 10:
            groups3.append((1675+start, 1675+prev))
            start = c
        prev = c
    groups3.append((1675+start, 1675+prev))

print(f"\nSub-groups in group1 (gap>10): {len(groups3)}")
for i, (x0, x1) in enumerate(groups3):
    print(f"  {i}: x={x0}-{x1}, width={x1-x0}")
