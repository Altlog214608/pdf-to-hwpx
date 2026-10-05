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


def _doc(name, tmp_path):
    pdf = next((p for p in PDFS if name in p.name), None)
    if pdf is None:
        pytest.skip(f"{name} 샘플 없음")
    return convert(str(pdf), out_dir=str(tmp_path), overwrite=True)["document"]


def test_2_3_box_across_columns(tmp_path):
    doc = _doc("2-3.", tmp_path)
    text = __import__("json").dumps(doc, ensure_ascii=False)
    assert "농구부를 떠난다." in text  # 단 구분선을 박스 테두리로 오인하지 않음
    q2 = next(x for x in doc["items"] if x.get("number") == 2)
    assert "않은 것은" in q2["stem"]  # 줄 끝 굵은 밑줄 강조어 뒤 공백


def test_2_5_media(tmp_path):
    doc = _doc("2-5.", tmp_path)
    qs = {x["number"]: x for x in doc["items"] if x["type"] == "question"}
    assert qs[3]["choice_credits"]["①"] == ["- 정호승, <내가 사랑하는 사람>"]
    assert qs[7]["blocks"][0]["paras"][0]["kind"] == "image"
    assert qs[17]["blocks"][0]["diagram"] is True
    assert [b["title"] for b in qs[19]["blocks"]] == ["<보기 1>", "<보기 2>"]
    p2 = [x for x in doc["items"] if x["type"] == "passage"][1]
    t = [p.get("text", p["kind"]) for p in p2["paras"]]
    assert t[t.index("사람이 될 수 있대.") + 1] == "blank"  # 단을 넘는 연 구분


def test_choesangwi_bold_and_answers(tmp_path):
    doc = _doc("[최상위 공략] 2.다양한 빛깔로 만나는, 문학(01)", tmp_path)
    qs = [x for x in doc["items"] if x["type"] == "question"]
    assert all(q["answer"] for q in qs)  # '1) 정답 ③' 형식
    p2 = [x for x in doc["items"] if x["type"] == "passage"][1]
    bold = [b for p in p2["paras"] for b in p.get("bold", [])]
    assert "흰 바람벽" in bold  # 지문 속 굵은 강조 시어 보존


@pytest.mark.skipif(not any("족보닷컴" in p.name for p in PDFS), reason="족보닷컴 샘플 없음")
def test_jokbo_tables_and_brackets(tmp_path):
    """족보닷컴 미리보는 중간고사: 선으로 그린 표 6개(칸 색, 칸 안 사진), [A]/[B] 묶음 괄호 3개."""
    pdf = next(p for p in PDFS if "족보닷컴" in p.name)
    res = convert(str(pdf), out_dir=str(tmp_path), overwrite=True)
    doc = res["document"]
    qs = {x["number"]: x for x in doc["items"] if x["type"] == "question"}

    def tables(paras):
        return [p["table"] for p in paras if p.get("kind") == "table"]
    q9 = qs[9]["blocks"][0]
    assert not q9["diagram"] and tables(q9["paras"])[0]["rows"] == 7  # 표 때문에 <보기> 전체가 그림이 되지 않음
    t13 = tables(qs[13]["blocks"])[0]
    assert (t13["rows"], t13["cols"]) == (3, 3)
    t20 = tables(qs[20]["blocks"][0]["paras"])[0]
    assert [c["fill"] is not None for c in t20["cells"] if c["c"] == 0] == [True] * 5
    assert " " in qs[17]["choices"][4] and qs[17]["choices"][4].endswith("정책을 결정한 후에")
    brackets = [p for x in doc["items"] if x["type"] == "passage" for p in x["paras"] if p["kind"] == "bracket"]
    assert [b["label"] for b in brackets] == ["[A]", "[B]", "[A]"]
    assert res["validation"]["checks"]["tables"] >= 9  # 표 6 + 괄호 3
