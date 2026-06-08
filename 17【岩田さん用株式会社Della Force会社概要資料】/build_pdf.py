import fitz

orig_pdf = r"C:\Users\shira_k13727w\OneDrive\DF\アライアンス関連\資料\デザイン調整後資料\DellaForce(メイン)会社概要システム開発長い.pdf"
new_p6   = r"C:\Users\shira_k13727w\OneDrive\Desktop\クロード保管用\17【岩田さん用株式会社Della Force会社概要資料】\page6_with_pos.png"
out_pdf  = r"C:\Users\shira_k13727w\OneDrive\Desktop\クロード保管用\17【岩田さん用株式会社Della Force会社概要資料】\DellaForce_会社概要_POS追加版.pdf"

doc = fitz.open(orig_pdf)
page = doc[5]  # 0-indexed → page 6

# Clear existing content and insert new image
page.clean_contents()
for xref in page.get_images(full=True):
    page.delete_image(xref[0])

page.insert_image(page.rect, filename=new_p6, keep_proportion=False)
doc.save(out_pdf, garbage=4, deflate=True)
doc.close()
print("Done:", out_pdf)
print(f"Total pages: {fitz.open(out_pdf).page_count}")
