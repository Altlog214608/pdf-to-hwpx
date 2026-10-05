"""합성 PDF(2-x 계열 특징)로 전체 파이프라인을 검증한다. 한글/Windows 없이 실행된다."""
import re

import pytest

from pdf2hwpx.convert import convert
from pdf2hwpx.validate import read_hwpx
from tests.synth_pdf import build


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    d = tmp_path_factory.mktemp("synth")
    pdf = d / "synth.pdf"
    build(str(pdf))
    return convert(str(pdf), out_dir=str(d), overwrite=True)


def _items(result, kind):
    return [x for x in result["document"]["items"] if x["type"] == kind]


def test_validation_passes(result):
    v = result["validation"]
    assert v["status"] == "PASS", v
    assert v["checks"]["text_coverage"] >= 0.995


def test_questions_and_choices(result):
    qs = _items(result, "question")
    assert [q["number"] for q in qs] == [1, 2, 3, 4, 5]
    assert [q["qtype"] for q in qs] == ["objective"] * 3 + ["subjective", "objective"]
    # 한 줄에 선택지 두 개(① ㄱ, ㄴ   ② ㄱ, ㄷ)도 다섯 개로 분리
    assert qs[0]["choices"][1].startswith("②") and len(qs[0]["choices"]) == 5
    assert [q["answer"] for q in qs][:3] == ["③", "⑤", "①"]


def test_passage_continuation_is_one_box(result):
    p1 = _items(result, "passage")[0]
    texts = [p.get("text", "") for p in p1["paras"]]
    assert texts[0] == "(가)"
    prose = [t for t in texts if t.startswith("어느 날")]
    assert len(prose) == 9  # 단을 넘어가도 문단이 쪼개지지 않음
    # 글자 단위 줄나눔(단어 중간)은 공백 없이, 공백에서 끊긴 줄은 공백으로 잇는다
    assert all("우물가에서" in t and "있던 노인이" in t for t in prose)
    kinds = [p["kind"] for p in p1["paras"]]
    assert "blank" in kinds  # 연 구분 보존
    assert p1["paras"][-1].get("align") == "RIGHT" and p1["paras"][-1].get("role") == "credit"


def test_aux_blocks_images_and_diagram(result):
    qs = {q["number"]: q for q in _items(result, "question")}
    b2 = qs[2]["blocks"][0]
    assert b2["title"] == "<보기>" and b2["paras"][0]["kind"] == "image"  # 박스 안 그림은 박스 안에
    assert qs[3]["blocks"][0]["diagram"] is True  # 도형 박스는 그림으로 보존
    cond = qs[4]["blocks"][0]
    assert cond["kind"] == "조건" and [p["text"] for p in cond["paras"]] == [
        "- 작품의 주제를 먼저 언급할 것.", "- 인물의 행동을 근거로 들 것."]
    titles = [b["title"] for b in qs[5]["blocks"]]
    assert titles == ["<보기 1>", "<보기 2>"]  # 그림만 있는 <보기 2>도 누락되지 않음
    assert qs[5]["blocks"][1]["paras"][0]["kind"] == "image"
    b51 = qs[5]["blocks"][0]["paras"]
    assert len(b51) == 2 and b51[1]["role"] == "credit"  # 산문 발췌는 한 문단 + 출전


def test_hwpx_package(result):
    hx = read_hwpx(result["hwpx"])
    assert hx["errors"] == []
    assert hx["pictures"] == hx["bindata"] == 5
    sec0 = [p for p in hx["paragraphs"] if p["section"].endswith("section0.xml")]
    # 보조박스 뒤에는 테두리 없는 빈 문단
    for i, p in enumerate(sec0[:-1]):
        if p["boxed"] and not sec0[i + 1]["boxed"]:
            assert sec0[i + 1]["text"] == "" or re.match(r"^\d+\.", sec0[i + 1]["text"]), sec0[i + 1]


def test_v051_review_fixes(result):
    qs = {q["number"]: q for q in _items(result, "question")}
    # 문제 옆 장식 배지는 그림으로 들어가지 않는다
    assert all(b.get("kind") != "image" for b in qs[1]["blocks"])
    # 서술형 하위 문항은 줄마다 쪼개지지 않고 한 문단
    subs = [b for b in qs[4]["blocks"] if b.get("kind") == "text"]
    assert len(subs) == 1 and subs[0]["text"].startswith("(2)") and subs[0]["text"].endswith("서술하시오.")
    # 선택지 뒤에 나온 단원 제목 박스는 선택지 뒤에 그대로 (선택지 앞으로 끌려오지 않음)
    assert qs[5]["blocks"][-1]["title"] == "<보기 2>"
    assert qs[5]["after"] and qs[5]["after"][0]["type"] == "aux"
    assert qs[5]["after"][0]["paras"][0]["text"] == "2. 서사 갈래의 이해"
    # [A] 표시는 시 행에 붙지 않는다
    p1 = _items(result, "passage")[0]
    texts = [p.get("text", "") for p in p1["paras"]]
    assert "[A]" in texts and "나는 오래 너를 기다렸다" in texts
