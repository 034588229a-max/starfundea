"""PDF 轉圖：有 pdftoppm 就用，沒有（例如 Windows）就用 PyMuPDF（pip install pymupdf）。
輸出檔名跟 pdftoppm 一樣：<prefix>-1.png、<prefix>-2.png…
"""
import shutil, subprocess


def pdf_to_pngs(pdf, prefix, dpi=150):
    if shutil.which('pdftoppm'):
        subprocess.run(['pdftoppm', '-r', str(dpi), '-png', pdf, prefix], check=True)
        return
    import pymupdf
    doc = pymupdf.open(pdf)
    for i, page in enumerate(doc, 1):
        page.get_pixmap(dpi=dpi).save('%s-%d.png' % (prefix, i))
    doc.close()
