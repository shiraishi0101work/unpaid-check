# -*- coding: utf-8 -*-
import shutil, os, sys

src_dir = 'C:\\Users\\shira_k13727w\\OneDrive\\DF\\\u30a2\u30e9\u30a4\u30a2\u30f3\u30b9\u95a2\u9023\\AI\u30d6\u30ed\u30b0'
dst = 'C:\\Users\\shira_k13727w\\OneDrive\\Desktop\\\u30af\u30ed\u30fc\u30c9\u4fdd\u7ba1\u7528\\temp_guide.pdf'

files = [f for f in os.listdir(src_dir) if f.endswith('.pdf')]
sys.stdout.buffer.write(('Found PDFs: ' + str(len(files)) + '\n').encode('utf-8'))

# Copy the guide file (should contain guide-related text)
for f in files:
    sys.stdout.buffer.write((f + '\n').encode('utf-8', errors='replace'))
    if True:
        shutil.copy(os.path.join(src_dir, f), dst)
        sys.stdout.buffer.write(('Copied: ' + f + '\n').encode('utf-8', errors='replace'))
        break
