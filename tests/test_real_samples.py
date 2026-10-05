"""실제 문제집 PDF 회귀 테스트.

PDF는 저작권 때문에 저장소에 넣지 않는다. 로컬에서 PDF들이 있는 폴더를 지정해 실행:
  PowerShell:  $env:PDF2HWPX_SAMPLES=".\\samples"; python -m pytest tests -q
"""
import os
from pathlib import Path

import pytest

from pdf2hwpx.convert import convert

SAMPLES = os.environ.get("PDF2HWPX_SAMPLES")
PDFS = sorted(Path(SAMPLES).glob("*.pdf")) if SAMPLES and Path(SAMPLES).is_dir() else []


@pytest.mark.skipif(not PDFS, reason="PDF2HWPX_SAMPLES 폴더가 지정되지 않음")
@pytest.mark.parametrize("pdf", PDFS, ids=[p.name[:40] for p in PDFS])
def test_sample(pdf, tmp_path):
    res = convert(str(pdf), out_dir=str(tmp_path), overwrite=True)
    v = res["validation"]
    assert v["root_causes"] == [], v["root_causes"]
    assert v["checks"]["text_coverage"] >= 0.99
    m = __import__("re").search(r"\[(\d+)문제\]", pdf.name)
    if m:
        assert v["checks"]["question_count"] == int(m.group(1))


@pytest.mark.skipif(not any("1-1." in p.name for p in PDFS), reason="1-1 샘플 없음")
def test_1_1_known_fixes(tmp_path):
    pdf = next(p for p in PDFS if "1-1." in p.name)
    res = convert(str(pdf), out_dir=str(tmp_path), overwrite=True)
    doc = res["document"]
    qs = {x["number"]: x for x in doc["items"] if x["type"] == "question"}
    assert "적절하지 않은 것을" in qs[1]["stem"]  # 글자 간격 기반 공백 복원
    assert "않은 학생을" in qs[17]["stem"]
    assert "(나)의 화자는" in qs[11]["choices"][2]  # 줄 끝 공백 보존
    assert qs[10]["choices"][3].startswith("④ (B) 이 시를")  # 조사 붙이기 휴리스틱 제거
    assert qs[16]["blocks"][0]["paras"][1]["text"].startswith("①")  # 보기 안 원문자
    p1 = next(x for x in doc["items"] if x["type"] == "passage")
    assert p1["guide"] == "※ 다음 글을 읽고, 물음에 답하시오."  # 안내문 원문
    assert sum(1 for p in p1["paras"] if p["kind"] == "blank") == 3  # 연 구분
    assert res["validation"]["checks"]["box_groups"] == 26
