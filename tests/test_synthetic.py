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


def test_choice_credit_lines(result):
    q3 = {q["number"]: q for q in _items(result, "question")}[3]
    assert q3["choices"][0] == "① 현저동"  # 출전이 선택지 본문에 붙지 않음
    assert q3["choice_credits"]["①"] == ["- 작가1, <작품1>"]
    assert q3["choice_credits"]["⑤"] == ["- 작가5, <작품5>"] and q3["after"] == []


def test_plain_answer_format(tmp_path):
    """'1) 정답 ③' + '오답 point' 소제목 형식(최다오답·최상위 공략)도 정답부로 인식한다."""
    pdf = tmp_path / "plain.pdf"
    build(str(pdf), answer_style="plain")
    res = convert(str(pdf), out_dir=str(tmp_path), overwrite=True)
    assert res["validation"]["root_causes"] == []
    qs = {q["number"]: q for q in _items(res, "question")}
    assert [qs[n]["answer"] for n in (1, 2, 3, 5)] == ["③", "⑤", "①", "①"]
    assert qs[5]["after"] == [] or all(a.get("text", "") != "1) 정답" for a in qs[5]["after"])
    assert qs[1]["explanation"][0] == "오답 point"


def test_doc_style_masterpage(tmp_path):
    """글꼴/크기와 바탕쪽(학원 이름·로고, 제목, 바깥 테두리) 옵션."""
    import zipfile
    import pymupdf as fitz
    from pdf2hwpx.style import DocStyle

    pdf = tmp_path / "s.pdf"
    build(str(pdf))
    d = fitz.open()
    pg = d.new_page(width=120, height=24)
    pg.draw_rect(pg.rect, color=(0, 0, 0), fill=(0, 0, 0))
    logo = pg.get_pixmap().tobytes("png")
    for logo_bytes, name in ((None, "김한춘국어전문학원"), (logo, "")):
        st = DocStyle(body_font="나눔명조", body_size=11, title="[중간 대비] 합성 시험", academy_name=name,
                      logo=logo_bytes, frame=True)
        res = convert(str(pdf), out_dir=str(tmp_path), overwrite=True, style=st)
        assert res["validation"]["status"] == "PASS", res["validation"]
        with zipfile.ZipFile(res["hwpx"]) as z:
            names = z.namelist()
            header = z.read("Contents/header.xml").decode("utf-8")
            sec0 = z.read("Contents/section0.xml").decode("utf-8")
            mp = z.read("Contents/masterpage0.xml").decode("utf-8")
        assert "Contents/masterpage0.xml" in names and "Contents/masterpage1.xml" in names
        assert 'face="나눔명조"' in header and '<hh:charPr id="0" height="1100"' in header
        assert '<hp:masterPage idRef="masterpage0"/>' in sec0 and 'masterPageCnt="1"' in sec0
        assert "[중간 대비] 합성 시험" in mp and 'textWrap="BEHIND_TEXT"' in mp
        assert (name in mp) if name else ("<hp:pic" in mp)


def test_answers_as_endnotes_and_title_color(tmp_path):
    """정답·해설을 각 문제 첫 줄에 연결된 미주로(수작업 시험지 방식), 제목 글자 색."""
    import re
    import zipfile
    from pdf2hwpx.style import DocStyle

    pdf = tmp_path / "s.pdf"
    build(str(pdf))
    st = DocStyle(title="[중간 대비] 합성", title_color="#666666", answers_as_endnotes=True)
    res = convert(str(pdf), out_dir=str(tmp_path), overwrite=True, style=st)
    v = res["validation"]
    assert v["status"] == "PASS", v
    assert v["checks"]["endnotes"] == v["checks"]["answer_count"] == 5
    with zipfile.ZipFile(res["hwpx"]) as z:
        names = z.namelist()
        header = z.read("Contents/header.xml").decode("utf-8")
        sec0 = z.read("Contents/section0.xml").decode("utf-8")
    assert "Contents/section1.xml" not in names and "Contents/masterpage1.xml" not in names
    assert re.search(r'<hh:charPr id="\d+" height="1400" textColor="#666666"', header)
    # 미주 표시는 문제 첫 문단 맨 앞, 1pt 흰 글자로 숨김
    hidden = re.search(r'<hh:charPr id="(\d+)" height="100" textColor="#FFFFFF"', header).group(1)
    notes = re.findall(rf'<hp:run charPrIDRef="{hidden}"><hp:ctrl><hp:endNote number="(\d+)"', sec0)
    assert notes == ["1", "2", "3", "4", "5"]
    # 미주 본문: 자동 번호 `1)`이 원래 정답 줄의 번호를 대신하고, 나머지 정답 글자는 그대로
    first = re.search(r"<hp:endNote .*?</hp:endNote>", sec0, re.S).group(0)
    text = "".join(re.findall(r"<hp:t>([^<]*)</hp:t>", first))
    assert '<hp:autoNum num="1" numType="ENDNOTE">' in first and "③" in text and not text.lstrip().startswith("1)")
    assert "[정답 및 해설]" not in sec0

    # 문제 번호가 연속이 아니면(미주 자동 번호와 어긋남) 문서 끝 정답으로 되돌리고 알린다
    from pdf2hwpx.hwpx_writer import HwpxWriter
    from pdf2hwpx.model import Question
    from pdf2hwpx.extract import extract
    from pdf2hwpx.ir import build_document
    doc = build_document(extract(str(pdf)))
    qs = [it for it in doc.items if isinstance(it, Question)]
    qs[-1].number = 9
    w = HwpxWriter(doc, style=DocStyle(answers_as_endnotes=True))
    assert w.endnotes is None and any("미주" in x for x in doc.warnings)


def test_tables_and_brackets(tmp_path):
    """족보닷컴 형식: [A] 묶음 괄호 지문, <보기> 안 선으로 그린 표(병합 칸·칸 색·칸 안 그림), 표 모양 선택지."""
    import re
    import zipfile
    from tests.synth_pdf import build_tables

    pdf = tmp_path / "t.pdf"
    build_tables(str(pdf))
    res = convert(str(pdf), out_dir=str(tmp_path), overwrite=True)
    v = res["validation"]
    assert v["status"] in ("PASS", "WARN") and not v["root_causes"], v
    items = res["document"]["items"]
    ps = [x for x in items if x["type"] == "passage"][0]
    br = [p for p in ps["paras"] if p["kind"] == "bracket"]
    assert len(br) == 1 and br[0]["label"] == "[A]"
    assert [p["text"] for p in br[0]["paras"]][0].startswith("해마다") and len(br[0]["paras"]) == 4
    assert not any(p.get("text") == "[A]" for p in ps["paras"])  # 표시는 괄호 이름으로만

    q = [x for x in items if x["type"] == "question"][0]
    box = q["blocks"][0]
    assert box["title"] == "<보기>" and not box["diagram"]  # 표가 있다고 박스 전체를 그림으로 바꾸지 않는다
    t = [p for p in box["paras"] if p["kind"] == "table"][0]["table"]
    assert (t["rows"], t["cols"]) == (3, 3)
    cells = {(c["r"], c["c"]): c for c in t["cells"]}
    assert cells[(0, 0)]["rs"] == 2 and cells[(0, 0)]["paras"][0]["text"] == "구분"
    assert cells[(0, 1)]["fill"] and not cells[(1, 1)]["fill"]
    assert cells[(2, 1)]["paras"][0]["kind"] == "image"
    assert all(p.get("align") == "CENTER" for c in t["cells"] for p in c["paras"] if p["kind"] == "text")
    # 표 모양 선택지: 칸 사이 간격을 전각 공백으로 살리고 한 선택지로 유지
    assert len(q["choices"]) == 5 and "\u2003" in q["choices"][0] and q["choices"][0].endswith("남풍")
    # 머리(㉠ ㉡)와 선택지 열을 맞춘 보이지 않는 표로 출력, 머리 줄은 따로 남지 않는다
    assert q["grid"]["header"] == ["㉠", "㉡"] and q["grid"]["rows"][0] == ["①", "보리", "남풍"]
    assert not any(b.get("text", "").startswith("㉠") for b in q["blocks"])

    with zipfile.ZipFile(res["hwpx"]) as z:
        sec = z.read("Contents/section0.xml").decode("utf-8")
        header = z.read("Contents/header.xml").decode("utf-8")
    assert sec.count("<hp:tbl ") == 3 and v["checks"]["tables"] == 3  # 괄호, 표, 선택지 격자
    assert 'rowSpan="2"' in sec and 'treatAsChar="1"' in sec
    # 괄호 칸: 왼쪽/위/아래 선만 있는 테두리( [ 모양 )
    assert re.search(r'<hh:leftBorder type="SOLID"[^>]*/><hh:rightBorder type="NONE"[^>]*/><hh:topBorder type="SOLID"'
                     r'[^>]*/><hh:bottomBorder type="SOLID"', header)


def test_subjective_space_and_subitems(result):
    """서술형 문제 뒤에 답 쓸 빈 줄."""
    from pdf2hwpx.hwpx_writer import SUBJECTIVE_BLANK_LINES
    hx = read_hwpx(result["hwpx"])
    texts = [p["text"] for p in hx["paragraphs"] if p["section"].endswith("section0.xml")]
    i = next(k for k, t in enumerate(texts) if t.startswith("(2) 위에서 답한"))  # 4번(서술형)의 마지막 문단
    assert texts[i + 1:i + 1 + SUBJECTIVE_BLANK_LINES] == [""] * SUBJECTIVE_BLANK_LINES
