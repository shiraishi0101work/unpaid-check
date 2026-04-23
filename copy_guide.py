# -*- coding: utf-8 -*-
import shutil, os, sys

src_dir = u'C:\\Users\\shira_k13727w\\OneDrive\\DF\\\u30a2\u30e9\u30a4\u30a2\u30f3\u30b9\u95a2\u9023\\AI\u30d6\u30ed\u30b0'
dst_dir = u'C:\\Users\\shira_k13727w\\OneDrive\\Desktop\\\u30af\u30ed\u30fc\u30c9\u4fdd\u7ba1\u7528\\06\u3010AI\u30d6\u30ed\u30b0\u30de\u30b9\u30bf\u30fc\u4ed5\u69d8\u8aac\u660e\u66f8\u3011'
dst = os.path.join(dst_dir, 'guide.pdf')

files = [f for f in os.listdir(src_dir) if f.endswith('.pdf')]
shutil.copy(os.path.join(src_dir, files[0]), dst)
sys.stdout.buffer.write(('Copied: ' + files[0] + '\n').encode('utf-8', errors='replace'))
