"""합성 PDF(2-x 계열 특징)로 전체 파이프라인을 검증한다. 한글/Windows 없이 실행된다."""
import re

import pytest

from pdf2hwpx.convert import convert
from pdf2hwpx.style import DocStyle
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


def test_academy_name_two_sizes(tmp_path):
    """학원 이름을 앞(김한춘)·뒤(국어전문학원) 글자 크기를 따로: 수작업 시험지처럼 한 칸 안에서 뒷부분만 작게."""
    import zipfile
    from pdf2hwpx.style import DocStyle

    pdf = tmp_path / "s.pdf"
    build(str(pdf))
    st = DocStyle(academy_name="김한춘", academy_sub="국어전문학원", academy_size=15, academy_sub_size=12,
                  title="[중간 대비] 합성", title_size=16, frame=True)
    res = convert(str(pdf), out_dir=str(tmp_path), overwrite=True, style=st)
    assert res["validation"]["status"] == "PASS", res["validation"]
    with zipfile.ZipFile(res["hwpx"]) as z:
        header = z.read("Contents/header.xml").decode("utf-8")
        mp = z.read("Contents/masterpage0.xml").decode("utf-8")
    runs = re.findall(r'<hp:run charPrIDRef="(\d+)"><hp:t>([^<]*)</hp:t></hp:run>', mp)
    by_text = {t: cid for cid, t in runs}
    assert "김한춘 " in by_text and "국어전문학원" in by_text

    def height(cid):
        return int(re.search(rf'<hh:charPr id="{cid}" height="(\d+)" textColor="(#[0-9A-F]+)"', header).group(1))
    assert height(by_text["김한춘 "]) == 1500 and height(by_text["국어전문학원"]) == 1200
    assert height(by_text["[중간 대비] 합성"]) == 1600
    # 뒷부분만 써도 된다
    st2 = DocStyle(academy_sub="국어전문학원", academy_sub_size=12).validate()
    assert st2.header_enabled
    assert DocStyle.from_dict({"academy_name": "김한춘", "academy_sub": "국어전문학원", "academy_size": 99}).academy_size == 24


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
    assert sec.count("<hp:tbl ") == 4 and v["checks"]["tables"] == 4  # 괄호, 표, 선택지 격자, 빈칸 네모
    # 빈칸 네모: 공백이 아니라 글자처럼 취급하는 빈 네모(표)로
    from pdf2hwpx.model import BLANK_BOX
    blank = [p for p in box["paras"] if p.get("text", "").startswith("주제")][0]["text"]
    assert blank.startswith("주제 :") and blank.endswith(BLANK_BOX) and blank.count(BLANK_BOX) >= 8
    assert re.search(r'주제 :</hp:t></hp:run><hp:run charPrIDRef="0"><hp:tbl [^>]*rowCnt="1" colCnt="1"', sec.replace("주제 : <", "주제 :<"))
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


def test_short_intro_kept_with_figure():
    """짧은 머리글 다음에 큰 그림/표가 오면 머리글 문단을 '다음 문단과 함께'로 둔다(그림이 다음 쪽으로 밀릴 때 같이 넘어가게)."""
    import re
    from pdf2hwpx.hwpx_writer import HwpxWriter
    from pdf2hwpx.model import Document, ImageEl, Para, Passage, Run
    img = ImageEl(1, 0, 0, 0, 100, 300, "x", 0)
    img.png = b"\x89PNG"
    ps = Passage(1, Para(runs=[Run("※ 다음 글을 읽고 물음에 답하시오.")]),
                 [Para(runs=[Run("짧은 소개 글입니다.")]), Para(kind="image", image=img)])
    w = HwpxWriter(Document(source="t", items=[ps]))
    out = w._passage(ps)
    pps = [re.search(r'paraPrIDRef="(\d+)"', o).group(1) for o in out]
    header = w.styles.render_header(1)
    keep = lambda pid: re.search(rf'<hh:paraPr id="{pid}"[^>]*>.*?keepWithNext="(\d)"', header, re.S).group(1)
    assert keep(pps[0]) == "1" and keep(pps[1]) == "1"


def test_auto_number_paragraphs(result, tmp_path):
    """문제 번호는 한글 문단 번호(heading NUMBER)로: 발문 글자에는 `1.`이 없고, 번호 모양은 첫 문제 번호부터."""
    import zipfile
    from pdf2hwpx.extract import extract
    from pdf2hwpx.hwpx_writer import HwpxWriter
    from pdf2hwpx.ir import build_document
    from pdf2hwpx.model import Question
    from pdf2hwpx.style import DocStyle

    with zipfile.ZipFile(result["hwpx"]) as z:
        header = z.read("Contents/header.xml").decode("utf-8")
        sec0 = z.read("Contents/section0.xml").decode("utf-8")
    nid = re.search(r'<hh:numbering id="(\d+)" start="0"><hh:paraHead start="1" level="1"[^>]*charPrIDRef="9"', header).group(1)
    assert re.search(r'<hh:numberings itemCnt="2"', header)
    pps = re.findall(rf'<hh:paraPr id="(\d+)"[^>]*>(?:(?!</hh:paraPr>).)*?<hh:heading type="NUMBER" idRef="{nid}" level="0"/>', header, re.S)
    stems = [m for m in re.finditer(r'<hp:p [^>]*paraPrIDRef="(\d+)"[^>]*>(.*?)</hp:p>', sec0, re.S) if m.group(1) in pps]
    assert len(stems) == 5
    for m in stems:
        text = "".join(re.findall(r"<hp:t>([^<]*)</hp:t>", m.group(2)))
        assert not re.match(r"\s*\d+\s*\.", text), text
    assert result["validation"]["checks"]["question_order_status"] == "PASS"
    assert result["writer"]["auto_numbers"] == 5

    # 끄면 예전처럼 글자
    pdf = tmp_path / "s.pdf"
    build(str(pdf))
    res = convert(str(pdf), out_dir=str(tmp_path), overwrite=True, style=DocStyle(auto_number=False))
    assert res["validation"]["status"] == "PASS" and "auto_numbers" not in res["writer"]


def _gap_doc(tmp_path):
    from pdf2hwpx.extract import extract
    from pdf2hwpx.ir import build_document
    from pdf2hwpx.model import Question

    pdf = tmp_path / "s.pdf"
    build(str(pdf))
    doc = build_document(extract(str(pdf)))
    qs = [it for it in doc.items if isinstance(it, Question)]
    qs[-1].number = 9                                   # 1 2 3 4 9 (5번을 못 찾은 것처럼)
    doc.answers = [a for a in doc.answers if a.number != 2]  # 2번 정답 없음, 5번 정답은 짝 없음
    return doc


def test_numbering_and_endnotes_survive_gaps(tmp_path):
    """번호가 건너뛰거나(못 찾은 문제) 정답이 빠져도 자동 번호·미주를 끄지 않고, 한글에서 편집해도 꼬이지 않게:
    번호 모양은 문서에 하나(1부터 1씩), 미주는 문제마다 하나(정답이 없으면 '찾지 못함'), '새 번호로 시작'은 없음.
    (건너뛴 곳에 '9부터 시작'을 고정하면 문제를 지우거나 다른 시험지에 붙여 넣을 때 번호·미주가 1 2 3 5 4 …로 꼬였다)"""
    import zipfile
    from pdf2hwpx.hwpx_writer import MISSING_ANSWER, HwpxWriter
    from pdf2hwpx.style import DocStyle

    doc = _gap_doc(tmp_path)
    out = tmp_path / "gap.hwpx"
    HwpxWriter(doc, style=DocStyle(answers_as_endnotes=True)).write(str(out))
    with zipfile.ZipFile(out) as z:
        header = z.read("Contents/header.xml").decode("utf-8")
        sec0 = z.read("Contents/section0.xml").decode("utf-8")
        sec1 = z.read("Contents/section1.xml").decode("utf-8")
    starts = re.findall(r'<hh:numbering id="\d+" start="0"><hh:paraHead start="(\d+)" level="1"', header)
    assert starts == ["1", "1"]  # 템플릿 기본 1개 + 문제용 1개
    paras = [p["text"] for p in read_hwpx(str(out))["paragraphs"] if not p.get("note")]
    assert [int(m.group(1)) for t in paras if (m := re.match(r"(\d+)\.(?!\s)", t))][:5] == [1, 2, 3, 4, 5]
    # 미주: 문제마다 하나, 번호도 1~5. 2번·9번(→5)은 '찾지 못함'
    assert re.findall(r'<hp:endNote number="(\d+)"', sec0) == ["1", "2", "3", "4", "5"]
    assert "numType=\"ENDNOTE\"/>" not in sec0 and "<hp:newNum" not in sec0
    assert sec0.count(MISSING_ANSWER) == 2
    # 짝 없는 5번 정답은 문서 끝 [정답 및 해설]
    assert "[정답 및 해설]" in sec1 and "5)" in sec1
    w = " ".join(doc.warnings)
    assert "4→9" in w and "2, 9번" in w and "짝이 없는 정답 1개" in w


def test_typed_numbers_keep_endnote_restart(tmp_path):
    """자동 번호를 끄면(번호가 글자) 미주 번호를 글자 번호에 맞추려고 건너뛴 곳에 '새 번호로 시작'을 넣는다."""
    import zipfile
    from pdf2hwpx.hwpx_writer import HwpxWriter
    from pdf2hwpx.style import DocStyle

    doc = _gap_doc(tmp_path)
    out = tmp_path / "typed.hwpx"
    HwpxWriter(doc, style=DocStyle(answers_as_endnotes=True, auto_number=False)).write(str(out))
    sec0 = zipfile.ZipFile(out).read("Contents/section0.xml").decode("utf-8")
    assert re.findall(r'<hp:endNote number="(\d+)"', sec0) == ["1", "3", "4"]
    assert re.findall(r'<hp:newNum num="(\d+)" numType="ENDNOTE"/>', sec0) == ["3"]
    assert sec0.index('<hp:newNum num="3"') < sec0.index('<hp:endNote number="3"')


@pytest.mark.parametrize("white_bg", [(2,), (5,), (1, 3)])
def test_invisible_white_rect_is_not_a_box(tmp_path, white_bg):
    """실사용(22문제 중 4번): 발문 뒤에 깔린 선 없는 흰 사각형(보이지 않음)의 가장자리를 박스 테두리로 읽어
    발문을 보기 박스에 넣고 그 문제 번호를 놓쳤다(문제 21개, 정답 22개)."""
    from pdf2hwpx.convert import convert

    pdf = tmp_path / "white.pdf"
    build(str(pdf), white_bg=white_bg)
    res = convert(str(pdf), out_dir=str(tmp_path), overwrite=True, style=DocStyle(answers_as_endnotes=True))
    v = res["validation"]
    assert v["status"] == "PASS", v["root_causes"]
    assert v["checks"]["question_count"] == v["checks"]["answer_count"] == v["checks"]["endnotes"] == 5
    stems = [x["stem"] for x in res["document"]["items"] if x["type"] == "question"]
    assert stems[1].startswith("2.<보기>는 영상 시의") and stems[4].startswith("5.<보기 1>을")


@pytest.mark.parametrize("word_box", [(3,), (1, 5)])
def test_word_box_in_stem_keeps_question(tmp_path, word_box):
    """실사용(1-4 노찬성과 에반 3번): 발문 속 낱말에 친 작은 네모를 박스로 읽고, 줄 가운데 점이 그 안에 든다고
    발문 줄 전체를 그 박스에 넣어 3번을 놓쳤다(문제 23, 정답 24). 줄이 가로로 다 들어가는 박스에만 넣는다."""
    from pdf2hwpx.convert import convert

    base = tmp_path / "base.pdf"
    build(str(base))
    pdf = tmp_path / "word.pdf"
    build(str(pdf), word_box=word_box)
    want = convert(str(base), out_dir=str(tmp_path), overwrite=True)["validation"]["checks"]
    v = convert(str(pdf), out_dir=str(tmp_path), overwrite=True, style=DocStyle(answers_as_endnotes=True))["validation"]
    assert v["status"] == "PASS", v["root_causes"]
    c = v["checks"]
    assert (c["question_count"], c["answer_count"], c["box_groups"]) == (5, 5, want["box_groups"])


def test_two_choices_per_line_with_narrow_gap(tmp_path):
    """실사용(1-2 최척전 5번): 한 줄에 선택지 두 개, 사이가 띄어쓰기 두어 칸뿐이라 ①③⑤ 세 개로 읽혔다.
    다음 번호이면서 그 줄의 다른 띄어쓰기보다 확연히 넓으면 나눈다."""
    from pdf2hwpx.convert import convert

    pdf = tmp_path / "narrow.pdf"
    build(str(pdf), narrow_pairs=True)
    res = convert(str(pdf), out_dir=str(tmp_path), overwrite=True)
    v = res["validation"]
    assert v["status"] == "PASS", (v["root_causes"], v["warnings"])
    q1 = next(x for x in res["document"]["items"] if x["type"] == "question" and x["number"] == 1)
    assert [c[:1] for c in q1["choices"]] == list("①②③④⑤")
    assert q1["choices"][0].rstrip() == "① ㄱ,ㄴ"


def test_publisher_notice_is_dropped(tmp_path):
    """첫 쪽 맨 위 출판사 고지문(「콘텐츠산업 진흥법」 표시, 제작연월일, © 마크, 저작권 경고 박스)은 빼고,
    오른쪽 경고 박스가 왼쪽 지문 박스의 '다음 단으로 이어지는 부분'으로 붙어 지문 중간에 끼던 문제도 막는다."""
    from pdf2hwpx.convert import convert

    plain, noted = tmp_path / "plain.pdf", tmp_path / "notice.pdf"
    build(str(plain))
    build(str(noted), notice=True)
    base = convert(str(plain), out_dir=str(tmp_path), overwrite=True)["validation"]["checks"]
    res = convert(str(noted), out_dir=str(tmp_path), overwrite=True)
    v = res["validation"]
    assert v["status"] == "PASS", v["root_causes"]
    c = v["checks"]
    assert (c["question_count"], c["box_groups"], c["pictures"]) == (base["question_count"], base["box_groups"], base["pictures"])
    text = " ".join(p["text"] for p in read_hwpx(res["hwpx"])["paragraphs"])
    assert "콘텐츠산업" not in text and "저작권법" not in text and "제작연월일" not in text
    assert not c["loose_items"]
    # 지문 속에 법 이름이 나오면 그대로 둔다: 덩어리가 본문 박스의 일부에만 걸치면 빼지 않는다
    from pdf2hwpx.extract import _notice_items
    from pdf2hwpx.model import Box, Glyph, Line

    def line(text, y):
        return Line(1, 0, [Glyph(ch, 60 + 9 * i, y, 69 + 9 * i, y + 10, 9) for i, ch in enumerate(text)],
                    60, y, 60 + 9 * len(text), y + 10, 9, 9)
    law, rest = line("저작권법에 의하여 보호되는 권리를", 100), line("정하고 있다.", 112)
    body = line("본문 문장입니다.", 200)
    assert _notice_items([law, rest], [], [Box(1, 1, 0, 57, 98, 283, 125, items=[law, rest])], [])
    assert _notice_items([law, rest, body], [], [Box(1, 1, 0, 57, 98, 283, 300, items=[law, rest, body])], []) == set()


@pytest.mark.parametrize("endnotes", [False, True])
def test_merge_documents_renumbers(tmp_path, endnotes):
    """통합본: 파일 3개(문제 5개씩)를 이으면 1~15번, 정답도 1)~15), 미주도 15개."""
    from pdf2hwpx.convert import convert_many
    from pdf2hwpx.style import DocStyle

    pdfs = []
    for k in range(3):
        p = tmp_path / f"s{k}.pdf"
        build(str(p))
        pdfs.append(str(p))
    out = tmp_path / "merged.hwpx"
    res = convert_many(pdfs, str(out), style=DocStyle(answers_as_endnotes=endnotes))
    v = res["validation"]
    assert v["status"] == "PASS", v
    c = v["checks"]
    assert c["question_count"] == c["answer_count"] == 15
    assert c["endnotes"] == (15 if endnotes else 0)
    paras = [p["text"] for p in read_hwpx(str(out))["paragraphs"]]
    stems = [int(m.group(1)) for t in paras if (m := re.match(r"(\d+)\.(?!\s)", t))]
    assert stems == list(range(1, 16))
    if not endnotes:
        heads = [int(m.group(1)) for t in paras if (m := re.match(r"\s*(\d+)\)\s*\[정답\]", t))]
        assert heads == list(range(1, 16))


def test_merge_rewrites_literal_numbers():
    """번호가 글자로 든 곳(지문 안내 [1~3], 정답 1), 발문 1.)을 조각난 글자 모양을 지키며 고친다."""
    from pdf2hwpx.merge import merge_documents
    from pdf2hwpx.model import AnswerEntry, Document, Para, Passage, Question, Run

    def doc(n):
        d = Document(source="x.pdf")
        d.items.append(Passage(1, Para(runs=[Run("[", bold=True), Run("1~"), Run(f"{n}] 다음 글을 읽고")]), [],
                               question_numbers=list(range(1, n + 1))))
        for i in range(1, n + 1):
            d.items.append(Question(i, Para(runs=[Run(f"{i}. 물음", bold=True)]), 1))
            d.answers.append(AnswerEntry(i, Para(runs=[Run(f"{i}) [정답] ③")])))
        return d
    m = merge_documents([doc(3), doc(2)], ["a.pdf", "b.pdf"])
    qs = [it for it in m.items if isinstance(it, Question)]
    ps = [it for it in m.items if isinstance(it, Passage)]
    assert [q.number for q in qs] == [1, 2, 3, 4, 5]
    assert qs[3].stem.text == "4. 물음" and qs[3].passage_id == 2
    assert ps[1].guide.text == "[4~5] 다음 글을 읽고" and ps[1].guide.runs[0].bold
    assert ps[1].question_numbers == [4, 5] and ps[1].id == 2
    assert [a.head.text for a in m.answers][3:] == ["4) [정답] ③", "5) [정답] ③"]


def test_partial_workbook_starting_at_13(tmp_path):
    """문제집 일부(13번부터, 정답도 '13) [정답]'부터)도 문제·정답을 찾는다. 전에는 1번을 기다리다 0개였다."""
    import zipfile
    from pdf2hwpx.convert import convert_many
    from pdf2hwpx.style import DocStyle

    pdf = tmp_path / "s13.pdf"
    build(str(pdf), start=13)
    res = convert(str(pdf), out_dir=str(tmp_path), overwrite=True, style=DocStyle(answers_as_endnotes=True))
    v = res["validation"]
    assert v["status"] == "PASS", v
    assert [q["number"] for q in _items(res, "question")] == [13, 14, 15, 16, 17]
    assert v["checks"]["answer_count"] == v["checks"]["endnotes"] == 5
    with zipfile.ZipFile(res["hwpx"]) as z:
        header = z.read("Contents/header.xml").decode("utf-8")
        sec0 = z.read("Contents/section0.xml").decode("utf-8")
    assert re.findall(r'<hh:numbering id="\d+" start="0"><hh:paraHead start="(\d+)"', header)[-1] == "13"
    assert re.findall(r'<hp:endNote number="(\d+)"', sec0) == ["13", "14", "15", "16", "17"]

    # 통합본: 13번부터인 파일도 앞 파일 바로 다음 번호로 이어진다(1~5 + 6~10)
    a = tmp_path / "a.pdf"
    build(str(a))
    out = tmp_path / "m.hwpx"
    r = convert_many([str(a), str(pdf)], str(out), style=DocStyle(answers_as_endnotes=True))
    assert r["validation"]["status"] == "PASS", r["validation"]
    stems = [int(m.group(1)) for p in read_hwpx(str(out))["paragraphs"] if (m := re.match(r"(\d+)\.(?!\s)", p["text"]))]
    assert stems == list(range(1, 11))


def _template_hwpx(tmp_path, logo: bool = False) -> bytes:
    """테스트용 '내 시험지' 파일: 이 변환기로 바탕쪽(학원 칸·제목 칸·테두리)을 만든 HWPX. 제목 글꼴은 직접 설치한 글꼴 이름."""
    import pymupdf as fitz
    from pdf2hwpx.style import DocStyle

    pdf = tmp_path / "tpl_src.pdf"
    build(str(pdf))
    png = None
    if logo:
        d = fitz.open()
        pg = d.new_page(width=120, height=24)
        pg.draw_rect(pg.rect, color=(0.2, 0.2, 0.6), fill=(0.2, 0.2, 0.6))
        png = pg.get_pixmap().tobytes("png")
    st = DocStyle(academy_name="김한춘", academy_sub="국어전문학원", academy_size=15, academy_sub_size=12,
                  title="[충여_추가] 옛 제목", title_font="잘풀리는오늘 Medium", frame=True, logo=png)
    out = tmp_path / ("tpl_logo.hwpx" if logo else "tpl.hwpx")
    convert(str(pdf), hwpx_path=str(out), write_json=False, style=st)
    return out.read_bytes()


@pytest.mark.parametrize("logo", [False, True])
def test_masterpage_template_from_my_hwpx(tmp_path, logo):
    """내 한글 파일의 바탕쪽을 그대로: 학원 칸·테두리·글꼴(목록에 없는 글꼴 이름 포함)·로고는 그대로, 제목 칸 글자만 새 제목."""
    import zipfile
    from pdf2hwpx.master_template import extract_template

    pkg = extract_template(_template_hwpx(tmp_path, logo))
    assert pkg["title_text"] == "[충여_추가] 옛 제목"
    assert pkg["title_runs"][0]["font"] == "잘풀리는오늘 Medium" and pkg["title_runs"][0]["size"] == 14
    if not logo:
        assert [r["t"] for r in pkg["academy_runs"]] == ["김한춘 ", "국어전문학원"]
    assert len(pkg["images"]) == (1 if logo else 0)

    pdf = tmp_path / "new.pdf"
    build(str(pdf))
    out = tmp_path / "new.hwpx"
    res = convert(str(pdf), hwpx_path=str(out), write_json=False,
                  style=DocStyle(title="[충여_추가] 새 제목", template=pkg, answers_as_endnotes=True))
    assert res["validation"]["status"] == "PASS", res["validation"]["root_causes"]
    assert read_hwpx(str(out))["errors"] == []  # 가져온 글자·문단 모양·테두리 id가 모두 header.xml에 있다
    with zipfile.ZipFile(out) as z:
        mp = z.read("Contents/masterpage0.xml").decode("utf-8")
        header = z.read("Contents/header.xml").decode("utf-8")
        hpf = z.read("Contents/content.hpf").decode("utf-8")
        names = z.namelist()
    assert "[충여_추가] 새 제목" in mp and "옛 제목" not in mp
    assert ("김한춘" in mp) != logo and 'textWrap="BEHIND_TEXT"' in mp
    hangul = re.search(r'<hh:fontface lang="HANGUL" fontCnt="(\d+)">(.*?)</hh:fontface>', header, re.S)
    faces = dict(re.findall(r'<hh:font id="(\d+)" face="([^"]+)"', hangul.group(2)))
    assert int(hangul.group(1)) == len(faces) and "잘풀리는오늘 Medium" in faces.values()
    fid = next(k for k, v in faces.items() if v == "잘풀리는오늘 Medium")
    title_cp = re.search(r'<hp:run charPrIDRef="(\d+)"><hp:t>\[충여_추가\] 새 제목', mp).group(1)
    assert re.search(rf'<hh:charPr id="{title_cp}" height="1400"[^>]*>.*?<hh:fontRef hangul="{fid}"', header, re.S)
    if logo:
        item = re.search(r'binaryItemIDRef="([^"]+)"', mp).group(1)
        assert f'id="{item}" href="BinData/{item}.png"' in hpf and f"BinData/{item}.png" in names


def test_masterpage_template_errors(tmp_path):
    """바탕쪽이 없는 파일·한글 파일이 아닌 것·깨진 묶음은 알기 쉬운 오류로."""
    from pdf2hwpx.master_template import TemplateError, extract_template

    pdf = tmp_path / "plain.pdf"
    build(str(pdf))
    plain = tmp_path / "plain.hwpx"
    convert(str(pdf), hwpx_path=str(plain), write_json=False)  # 머리 부분 없음 = 바탕쪽 없음
    with pytest.raises(TemplateError, match="바탕쪽이 없습니다"):
        extract_template(plain.read_bytes())
    with pytest.raises(TemplateError, match="HWPX"):
        extract_template(b"not a zip")
    pkg = extract_template(_template_hwpx(tmp_path))
    with pytest.raises(ValueError):
        DocStyle(template=dict(pkg, inner=pkg["inner"] + "<hp:p>")).validate()
    with pytest.raises(ValueError):
        DocStyle(template=dict(pkg, charPr={"1": '<hh:charPr id="2"/>'})).validate()
    with pytest.raises(ValueError, match="프리셋"):
        DocStyle.from_dict({"preset": "없는프리셋"})
    # 화면에서 바탕쪽 XML을 보내도 받지 않는다(서버에 있는 프리셋 이름만)
    assert DocStyle.from_dict({"template": pkg}).template is None


def test_builtin_preset_hakwon1(tmp_path):
    """학원 1 프리셋(선생님 시험지 바탕쪽을 한 번 뽑아 둔 것): 학원 칸·글꼴 그대로, 제목 칸만 새 제목. 원래 시험지 글은 없음."""
    import json
    import zipfile
    from importlib import resources
    from pdf2hwpx.presets import list_presets, load

    assert [p["id"] for p in list_presets()] == ["hakwon1"]
    raw = resources.files("pdf2hwpx.presets").joinpath("hakwon1.json").read_text(encoding="utf-8")
    assert "운수" not in raw and "충여" not in raw  # 원래 시험지의 제목·본문은 담지 않는다
    pkg = load("hakwon1")
    assert pkg["name"] == "학원 1" and json.loads(raw)["title_text"] == "시험 제목"
    pdf = tmp_path / "s.pdf"
    build(str(pdf))
    out = tmp_path / "preset.hwpx"
    res = convert(str(pdf), hwpx_path=str(out), write_json=False,
                  style=DocStyle.from_dict({"preset": "hakwon1", "title": "[중간 대비] 새 시험", "answers_as_endnotes": True}))
    assert res["validation"]["status"] == "PASS", res["validation"]["root_causes"]
    assert read_hwpx(str(out))["errors"] == []
    with zipfile.ZipFile(out) as z:
        mp = z.read("Contents/masterpage0.xml").decode("utf-8")
        header = z.read("Contents/header.xml").decode("utf-8")
    assert "김한춘" in mp and "국어전문학원" in mp and "[중간 대비] 새 시험" in mp and "시험 제목" not in mp
    assert 'face="엘리스 디지털배움체 OTF"' in header and 'face="잘풀리는오늘 Medium"' in header
