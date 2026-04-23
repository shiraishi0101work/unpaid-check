# -*- coding: utf-8 -*-
import shutil, os

src_dir = 'C:\\Users\\shira_k13727w\\OneDrive\\DF\\アライアンス関連\\AIブログ'
dst = 'C:\\Users\\shira_k13727w\\OneDrive\\Desktop\\クロード保管用\\temp_guide.pdf'

files = [f for f in os.listdir(src_dir) if f.endswith('.pdf')]
print("Found PDFs:", files)

# Copy the guide file (should contain 'ガイド')
for f in files:
    if 'ガイド' in f or 'guide' in f.lower():
        shutil.copy(os.path.join(src_dir, f), dst)
        print("Copied:", f)
        break
else:
    # If not found, copy first PDF
    shutil.copy(os.path.join(src_dir, files[0]), dst)
    print("Copied first:", files[0])
