r"""PDF -> HWPX 변환기 v0.5 실행 파일.

사용 예 (PowerShell 한 줄):
  python .\v0_5_pdf_to_hwpx.py ".\[꼭 나오는 문제] 2026 1-1.문학의 본질과 미적 기능_비상(강호영) 문학 [25문제] [Q].pdf"
폴더 전체 일괄 변환:
  python .\v0_5_pdf_to_hwpx.py .\pdfs --out-dir .\out
"""
from pdf2hwpx.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
