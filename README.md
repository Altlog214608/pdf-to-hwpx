# pdf-to-hwpx

한국어 문학 문제집 PDF(2단, 문제/지문/<보기>/정답·해설)를 편집 가능한 HWPX로 변환합니다.

## 사용법 — 한글(Hancom) 설치 없이 동작

```powershell
pip install -r requirements.txt; python .\v0_5_pdf_to_hwpx.py ".\[꼭 나오는 문제] 2026 1-1.문학의 본질과 미적 기능_비상(강호영) 문학 [25문제] [Q].pdf"
```

- 결과: PDF 옆에 `같은이름.hwpx` + `같은이름_result.json` (이미 있으면 `_run02`…)
- 폴더 일괄 변환: `python .\v0_5_pdf_to_hwpx.py .\pdfs --out-dir .\out`
- 테스트: `python -m pytest tests -q` (실제 PDF 회귀: `$env:PDF2HWPX_SAMPLES=".\pdfs"; python -m pytest tests -q`)

## 웹사이트 (v0.8)

**Windows에서 더블클릭**: 압축을 푼 폴더의 `실행하기.bat` → (Python이 없으면 자동 설치) → 브라우저가 열립니다.
검은 창을 닫으면 꺼집니다. 처음에 "Windows의 PC 보호" 창이 뜨면 **추가 정보 → 실행**.

명령어로 실행:
```powershell
pip install -r requirements.txt -r webapp\requirements.txt; python .\webapp\server.py
```

http://127.0.0.1:8000 에서 PDF를 끌어다 놓고, 학원 이름·로고·시험 제목·바깥 테두리·본문 글꼴과 크기를 미리 보며 정한 뒤
내려받습니다. 여러 PDF를 한 번에 올려 따로(ZIP) 받거나 번호를 이어 통합본으로 만들 수 있습니다.
파일은 페이지를 떠나거나 일정 시간이 지나면 서버에서 삭제됩니다. 실행 설정과 AWS 배포는 [docs/WEB.md](docs/WEB.md).

**AWS에 올리기**(초대 링크로 둘만 접속): `powershell -ExecutionPolicy Bypass -File .\tools\deploy_lightsail.ps1`

```
pdf2hwpx/            변환기 패키지 (extract → ir → hwpx_writer → validate)
v0_5_pdf_to_hwpx.py  실행 파일
webapp/              웹 서버(FastAPI)와 화면(static/)
tests/               합성 PDF 테스트 + 실제 PDF 회귀 테스트
docs/                변경 기록(V0_5.md)과 분석 문서
```

자세한 구조·변경 사항·한계는 [docs/V0_5.md](docs/V0_5.md)를 보세요.
이전 버전(v0.1 ~ v0.4.9.5.24, 단일 파일 + 한글 COM 방식)은 저장소에서 정리했습니다. 필요하면 git 기록의 커밋 `f5d2755`에서 꺼낼 수 있습니다.
