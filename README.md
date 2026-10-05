# pdf-to-hwpx

한국어 문학 문제집 PDF(2단, 문제/지문/<보기>/정답·해설)를 편집 가능한 HWPX로 변환합니다.

## v0.5 (현재) — 한글(Hancom) 설치 없이 동작

```powershell
pip install -r requirements_v0_5.txt; python .\v0_5_pdf_to_hwpx.py ".\[꼭 나오는 문제] 2026 1-1.문학의 본질과 미적 기능_비상(강호영) 문학 [25문제] [Q].pdf"
```

- 결과: PDF 옆에 `같은이름.hwpx` + `같은이름_result.json` (이미 있으면 `_run02`…)
- 폴더 일괄 변환: `python .\v0_5_pdf_to_hwpx.py .\pdfs --out-dir .\out`
- 테스트: `python -m pytest tests -q` (실제 PDF 회귀: `$env:PDF2HWPX_SAMPLES=".\pdfs"; python -m pytest tests -q`)

자세한 구조·변경 사항·한계는 [docs/V0_5.md](docs/V0_5.md)를 보세요.
`v0_4_9_5_*.py`는 이전(ChatGPT 시기) 버전으로 참고용으로만 남겨 두었습니다.
