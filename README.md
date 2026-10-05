# pdf-to-hwpx

한국어 문학 문제집 PDF(2단, 문제/지문/<보기>/정답·해설)를 편집 가능한 HWPX로 변환합니다.

## 사용법 — 한글(Hancom) 설치 없이 동작

```powershell
pip install -r requirements.txt; python .\v0_5_pdf_to_hwpx.py ".\[꼭 나오는 문제] 2026 1-1.문학의 본질과 미적 기능_비상(강호영) 문학 [25문제] [Q].pdf"
```

- 결과: PDF 옆에 `같은이름.hwpx` + `같은이름_result.json` (이미 있으면 `_run02`…)
- 폴더 일괄 변환: `python .\v0_5_pdf_to_hwpx.py .\pdfs --out-dir .\out`
- 테스트: `python -m pytest tests -q` (실제 PDF 회귀: `$env:PDF2HWPX_SAMPLES=".\pdfs"; python -m pytest tests -q`)

```
pdf2hwpx/            변환기 패키지 (extract → ir → hwpx_writer → validate)
v0_5_pdf_to_hwpx.py  실행 파일
tests/               합성 PDF 테스트 + 실제 PDF 회귀 테스트
docs/                변경 기록(V0_5.md)과 분석 문서
```

자세한 구조·변경 사항·한계는 [docs/V0_5.md](docs/V0_5.md)를 보세요.
이전 버전(v0.1 ~ v0.4.9.5.24, 단일 파일 + 한글 COM 방식)은 저장소에서 정리했습니다. 필요하면 git 기록의 커밋 `f5d2755`에서 꺼낼 수 있습니다.
