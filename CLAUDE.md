# pdf-to-hwpx — 작업 규칙

- 현재 버전은 `pdf2hwpx/` 패키지(v0.8.x)와 실행 파일 `v0_5_pdf_to_hwpx.py`, 웹 서버 `webapp/`(docs/WEB.md). 이전 단일 파일 버전들은 정리됨(git 커밋 f5d2755에 보존).
- 단계: extract(PDF→페이지 모델) → ir(논리 구조) → hwpx_writer(순수 XML) → validate. 단계 경계를 지킬 것.
- HWPX는 후처리 패치 없이 IR에서 한 번에 생성한다. 스타일은 `pdf2hwpx/template/header.xml`의 검증된 id를
  재사용하고 변형은 `Styles.derive()`로만 추가한다. 머리 부분(학원/제목/테두리)은 `masterpage.py`의 바탕쪽, 사용자 옵션은 `style.DocStyle`.
  학원 시험지의 바탕쪽은 프리셋(`pdf2hwpx/presets/*.json`, `tools/make_preset.py`로 한 번 뽑음)으로 고르고 `master_template.py`가
  id를 바꿔 끼운다. 웹에서 사용자가 올린 파일에서 바탕쪽을 뽑는 기능은 두지 않는다(프리셋에는 바탕쪽만, 시험지 본문·제목은 넣지 않음).
- 웹: 업로드 파일은 작업 폴더에만 두고 TTL·페이지 이탈 시 삭제한다(저작권). 영구 저장 기능을 추가하지 말 것.
  유일한 예외는 `webapp/samples.py`: 변환 결과가 '문제 있음'(FAIL)이거나 오류가 난 파일만 고치기 위해 기한(기본 14일)·개수 제한을
  두고 보관하며, 관리자만 내려받고, 화면에 이 사실을 알린다. 대상을 넓히거나(정상 파일 등) 기한을 없애지 말 것. 저장소에 넣지 말 것.
  이용 기록(`webapp/usage.py`)은 누가·언제·동작·쪽수·문제 수 같은 숫자만 남긴다(파일 내용·파일 이름·제목·학원 이름 금지).
- 특정 PDF 한 개만 맞추는 하드코딩 금지. 기하(좌표) 기반 규칙으로 일반화하고, 합성 PDF 테스트(`tests/synth_pdf.py`)에
  해당 특징을 추가해 회귀를 막는다.
- 변경 후: `python -m pytest tests -q` (실제 PDF가 있으면 `PDF2HWPX_SAMPLES=폴더`).
- 사용자는 Windows PowerShell 한 줄 명령을 선호한다. 한글(Hancom)에서 실제로 열어 보는 확인은 사용자가 한다.
