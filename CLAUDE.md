# pdf-to-hwpx — 작업 규칙

- 현재 버전은 `pdf2hwpx/` 패키지(v0.8.x)와 실행 파일 `v0_5_pdf_to_hwpx.py`, 웹 서버 `webapp/`(docs/WEB.md). 이전 단일 파일 버전들은 정리됨(git 커밋 f5d2755에 보존).
- 단계: extract(PDF→페이지 모델) → ir(논리 구조) → hwpx_writer(순수 XML) → validate. 단계 경계를 지킬 것.
- HWPX는 후처리 패치 없이 IR에서 한 번에 생성한다. 스타일은 `pdf2hwpx/template/header.xml`의 검증된 id를
  재사용하고 변형은 `Styles.derive()`로만 추가한다. 머리 부분(학원/제목/테두리)은 `masterpage.py`의 바탕쪽, 사용자 옵션은 `style.DocStyle`.
- 웹: 업로드 파일은 작업 폴더에만 두고 TTL·페이지 이탈 시 삭제한다(저작권). 영구 저장 기능을 추가하지 말 것.
- 특정 PDF 한 개만 맞추는 하드코딩 금지. 기하(좌표) 기반 규칙으로 일반화하고, 합성 PDF 테스트(`tests/synth_pdf.py`)에
  해당 특징을 추가해 회귀를 막는다.
- 변경 후: `python -m pytest tests -q` (실제 PDF가 있으면 `PDF2HWPX_SAMPLES=폴더`).
- 사용자는 Windows PowerShell 한 줄 명령을 선호한다. 한글(Hancom)에서 실제로 열어 보는 확인은 사용자가 한다.
