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

# Analyze columns in the middle of the logo zone
y0, y1 = 1100, 1700
logo_strip = arr[y0:y1, :, :]
bg_strip   = bg_zone[y0-BG_Y0:y1-BG_Y0, :, :]
diff = np.abs(logo_strip - bg_strip).max(axis=(0, 2))

threshold = 25
content_cols = np.where(diff > threshold)[0]
print(f"Content columns count: {len(content_cols)}")
print(f"First/last content col: {content_cols[0] if len(content_cols)>0 else 'none'} / {content_cols[-1] if len(content_cols)>0 else 'none'}")

# Find gaps (groups of logo content)
groups = []
if len(content_cols) > 0:
    start = int(content_cols[0])
    prev  = int(content_cols[0])
    for c in content_cols[1:]:
        c = int(c)
        if c - prev > 60:
            groups.append((start, prev))
            start = c
        prev = c
    groups.append((start, prev))

print(f"\nLogo groups ({len(groups)} found):")
for i, (x0, x1) in enumerate(groups):
    print(f"  Group {i}: x={x0} to x={x1}, width={x1-x0}")

# Also check vertically for each group
print("\nVertical extent per group (checking full height):")
for i, (gx0, gx1) in enumerate(groups):
    strip_v = arr[BG_Y0:BG_Y1, gx0:gx1+1, :]
    bg_v    = bg_zone[:, gx0:gx1+1, :]
    diff_v  = np.abs(strip_v - bg_v).max(axis=(1, 2))
    content_rows = np.where(diff_v > threshold)[0]
    if len(content_rows) > 0:
        print(f"  Group {i}: y={BG_Y0+content_rows[0]} to y={BG_Y0+content_rows[-1]}")
    else:
        print(f"  Group {i}: no content found vertically")
