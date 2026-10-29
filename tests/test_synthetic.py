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


def test_answer_numbers_over_100_not_doubled(tmp_path):
    """실사용(10개 통합본 221문제): 100번부터 미주가 "196)  196) [정답] ①"처럼 번호가 두 번 찍혔다(정답 줄의 번호 글자를
    두 자리까지만 지움). 98~102번 문제집으로 확인하고, 해설이 있는 정답 줄은 '다음 문단과 함께'(해설이 다음 단으로
    넘어가면 정답 번호도 같이)."""
    import zipfile

    pdf = tmp_path / "s98.pdf"
    build(str(pdf), start=98)
    res = convert(str(pdf), out_dir=str(tmp_path), overwrite=True, style=DocStyle(answers_as_endnotes=True))
    v = res["validation"]
    assert v["status"] == "PASS", v["root_causes"]
    assert v["checks"]["question_count"] == v["checks"]["answer_count"] == v["checks"]["endnotes"] == 5
    notes = [p["text"] for p in read_hwpx(res["hwpx"])["paragraphs"] if p.get("note") and re.match(r"\d+\)", p["text"])]
    assert [n.split(")")[0] for n in notes] == ["98", "99", "100", "101", "102"]
    assert not any(re.match(r"^\d+\)\s*\d{1,3}\s*\)", n) for n in notes), notes
    with zipfile.ZipFile(res["hwpx"]) as z:
        header = z.read("Contents/header.xml").decode("utf-8")
        sec0 = z.read("Contents/section0.xml").decode("utf-8")
    head_pp = re.search(r'<hp:endNote [^>]*>.*?<hp:p [^>]*paraPrIDRef="(\d+)"', sec0, re.S).group(1)
    assert re.search(rf'<hh:paraPr id="{head_pp}"[^>]*>.*?keepWithNext="1"', header, re.S)


@pytest.mark.parametrize("endnotes", [False, True])
def test_bare_big_question_numbers(tmp_path, endnotes):
    """실사용([시대별 문학]): 문제 번호가 마침표 없이 큰 회색 숫자 "1"뿐(옆에 흰색 1pt 숨은 글자 "zb1)")이라 문제를 하나도
    못 찾고 정답 10개를 문서 끝에 모았다(통합본에서는 미주가 빠지고 번호가 건너뜀). 번호 글자가 본문·뒤 글자보다 확실히 크면
    문제 머리로 보고, 발문은 다른 양식처럼 "1. …"로 맞춘다."""
    pdf = tmp_path / "bare.pdf"
    build(str(pdf), bare_numbers=True)
    res = convert(str(pdf), out_dir=str(tmp_path), overwrite=True, style=DocStyle(answers_as_endnotes=endnotes))
    v = res["validation"]
    assert v["status"] == "PASS", (v["root_causes"], v["warnings"])
    qs = _items(res, "question")
    assert [q["number"] for q in qs] == [1, 2, 3, 4, 5]
    assert all(re.match(rf"^{q['number']}\. \S", q["stem"]) for q in qs), [q["stem"] for q in qs]
    assert v["checks"]["answer_count"] == 5 and (v["checks"]["endnotes"] == 5 if endnotes else True)
    text = " ".join(p["text"] for p in read_hwpx(res["hwpx"])["paragraphs"])
    assert "zb1)" not in text and "1. 1" not in text


def test_written_sub_questions_and_credit_without_space(tmp_path):
    """실사용(제망매가 10번): ① ②가 고르는 선택지가 아니라 '…쓰시오.' 하위 물음이고 그 아래 "(a) :" 답 칸 줄이 있다.
    답 칸 줄을 선택지 글에 잇지 않고 따로 두며, 서술형으로 보고(선택지 수 경고 없음) 그 뒤 <조건> 박스는 원래대로 뒤에 둔다.
    출전이 대시 뒤 띄어쓰기 없이("-한호, 「…」") 오른쪽에 붙어도 출전 줄로 본다."""
    pdf = tmp_path / "written.pdf"
    build(str(pdf), written_parts=True, credit_nospace=True)
    res = convert(str(pdf), out_dir=str(tmp_path), overwrite=True)
    v = res["validation"]
    assert v["status"] == "PASS", (v["root_causes"], v["warnings"])
    qs = {q["number"]: q for q in _items(res, "question")}
    q4 = qs[4]
    assert q4["qtype"] == "subjective" and len(q4["choices"]) == 2
    assert q4["choices"][0].rstrip().endswith("쓰시오.")
    assert q4["choice_sublines"] == {"①": ["(a) :"], "②": ["(b) :"]}
    assert q4["blocks"] == [] and [b.get("title") for b in q4["after"]] == ["<조건>"]
    assert not any("선택지" in w for w in res["document"]["warnings"] + v["warnings"])
    assert qs[3]["choices"][0] == "① 현저동" and qs[3]["choice_credits"]["①"] == ["-작가1, 「작품1」"]
    assert qs[3]["choice_credits"]["⑤"] == ["-작가5, 「작품5」"] and qs[3]["after"] == []
    paras = [p["text"].strip() for p in read_hwpx(res["hwpx"])["paragraphs"]]
    i = paras.index("(a) :")
    assert paras[i - 1].endswith("쓰시오.") and "(b) :" in paras[i + 1:i + 3]


def test_two_choices_per_line_with_wide_label_gap(tmp_path):
    """실사용(최척전(04) 20번): 원문자 아이콘과 글 사이(4.6pt)가 두 선택지 사이(글자 0.7개)보다 크게 벌어진 문제집.
    번호 뒤 간격은 '보통 띄어쓰기' 폭에서 빼고 재야 ①③⑤로 붙지 않는다."""
    pdf = tmp_path / "wide.pdf"
    build(str(pdf), narrow_pairs="wide_label")
    res = convert(str(pdf), out_dir=str(tmp_path), overwrite=True)
    v = res["validation"]
    assert v["status"] == "PASS", (v["root_causes"], v["warnings"])
    q1 = _items(res, "question")[0]
    assert [c[:1] for c in q1["choices"]] == list("①②③④⑤"), q1["choices"]


def test_example_sheet_without_question_numbers(tmp_path):
    """실사용([풀이완성]): 문제 번호가 '예제' 그림뿐이고 정답부가 없어 문제를 찾지 못하는 자료. 내용은 옮기되, 선택지
    원문자 아이콘은 같은 단에서 이어지는 줄머리 아이콘 묶음 순서로 판별하고(○ 로 바꾸지 않음), 원인을 알기 쉽게 알린다."""
    from tests.synth_pdf import build_examples

    pdf = tmp_path / "examples.pdf"
    build_examples(str(pdf))
    res = convert(str(pdf), out_dir=str(tmp_path), overwrite=True)
    v = res["validation"]
    # 문제도 정답부도 없는 자료는 '문제 있음'이 아니라 '확인 필요'(내용은 다 옮김)
    assert v["status"] == "WARN" and v["root_causes"] == [], v["root_causes"]
    assert any("문제·정답을 찾지 못한 자료" in w for w in v["warnings"]), v["warnings"]
    assert not any("원문자 아이콘" in w for w in res["document"]["warnings"])
    text = " ".join(p["text"] for p in read_hwpx(res["hwpx"])["paragraphs"])
    assert "① 선택지 1-1" in text and "⑤ 선택지 4-5" in text and "○" not in text


def _column_defs(hwpx: str) -> list[tuple[int, bool, str]]:
    """section0 의 단 정의 차례: (단 수, 그 문단에서 쪽을 나누는지, 뒤따르는 글 앞부분)."""
    import zipfile

    with zipfile.ZipFile(hwpx) as z:
        x = z.read("Contents/section0.xml").decode("utf-8")
    out = []
    for m in re.finditer(r'<hp:colPr [^>]*colCount="(\d)"', x):
        head = re.match(r"<hp:p [^>]*>", x[x.rfind("<hp:p ", 0, m.start()):]).group(0)
        rest = x[x.index(">", m.end()) + 1:][:4000]
        out.append((int(m.group(1)), 'pageBreak="1"' in head, re.sub(r"<[^>]+>", "", rest)[:20]))
    return out


def test_full_width_intro_page_is_single_column(tmp_path):
    """실사용([시대별 문학]): 앞쪽 '작품 개관' 쪽은 가운데 선 없이 쪽 전체 폭을 쓰는데, 두 단으로 나눠 읽어 줄 순서가 섞이고
    전폭 표(행 선이 쪽 폭의 60%를 넘음)도 표로 못 읽었다. 가운데 선이 없고 내용이 가운데를 가로지르는 쪽은 한 단으로 읽고,
    한글 파일에서도 한 단(가운데 선 없음)으로 넣은 뒤 지문·문제가 시작되면 새 쪽에서 원래 두 단으로. 미주는 그대로."""
    pdf = tmp_path / "intro.pdf"
    build(str(pdf), intro_page=True)
    res = convert(str(pdf), out_dir=str(tmp_path), overwrite=True, style=DocStyle(answers_as_endnotes=True))
    v = res["validation"]
    assert v["status"] == "PASS", (v["root_causes"], v["warnings"])
    assert v["checks"]["question_count"] == v["checks"]["endnotes"] == 5
    items = res["document"]["items"]
    first_q = next(k for k, x in enumerate(items) if x["type"] in ("passage", "question"))
    intro = items[:first_q]
    assert intro and all(x.get("wide") for x in intro)
    box = next(x for x in intro if x["type"] == "aux")  # 문제 밖 박스(_block 이 type 을 aux 로 씀)
    prose = " ".join(p["text"] for p in box["paras"])
    assert "자작층" not in prose and "변화가 일어났다 사설시조는 현실을" in prose  # 줄 순서 그대로 한 문단
    table = next(x for x in intro if x.get("kind") == "table")["table"]
    assert (table["rows"], table["cols"]) == (3, 2)
    assert [c["paras"][0]["text"] for c in table["cells"] if c["c"] == 0] == ["갈래", "성격", "주제"]
    cols = _column_defs(res["hwpx"])
    assert [(n, pb) for n, pb, _ in cols] == [(1, False), (2, True)], cols
    assert cols[1][2].startswith("※ 다음 글을")


def test_merge_with_full_width_pages_in_the_middle(tmp_path):
    """통합본 중간에 전폭 쪽이 든 파일이 끼어도: 그 앞에서 쪽을 나눠 한 단, 다음 파일 지문부터 다시 쪽을 나눠 두 단.
    한 구역 안에서 단 정의만 바꾸므로 문제 번호·미주 번호는 끊기지 않는다."""
    from pdf2hwpx.convert import convert_many

    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"
    build(str(a))
    build(str(b), intro_page=True)
    out = tmp_path / "merged.hwpx"
    res = convert_many([str(a), str(b), str(a)], str(out), style=DocStyle(answers_as_endnotes=True))
    v = res["validation"]
    assert v["status"] == "PASS", (v["root_causes"], v["warnings"])
    assert v["checks"]["question_count"] == v["checks"]["endnotes"] == 15
    cols = _column_defs(str(out))
    assert [(n, pb) for n, pb, _ in cols] == [(2, False), (1, True), (2, True)], cols
    assert cols[1][2].startswith("• 작자 미상") and cols[2][2].startswith("※ 다음 글을")


def test_wide_passage_on_top_of_two_column_page(tmp_path):
    """실사용([풀이완성]): 쪽 맨 위 회색 지문은 가로로 길고(단 구분선 위), 그 아래부터 두 단. 그 구간은 한 단으로 먼저
    읽고, 한글에서는 쪽을 나누지 않은 채 그 아래에서 두 단(가운데 선)으로 바꾼다."""
    pdf = tmp_path / "widetop.pdf"
    build(str(pdf), wide_top=True)
    res = convert(str(pdf), out_dir=str(tmp_path), overwrite=True, style=DocStyle(answers_as_endnotes=True))
    v = res["validation"]
    assert v["status"] == "PASS", (v["root_causes"], v["warnings"])
    items = res["document"]["items"]
    assert items[0]["type"] in ("loose", "aux") and items[0]["wide"] and "(가)" in str(items[0])
    cols = _column_defs(res["hwpx"])
    assert [(n, pb) for n, pb, _ in cols] == [(1, False), (2, False)], cols


def test_annotated_poem_bracket_rows(tmp_path):
    """실사용([시대별 문학] 시 풀이 쪽): 장마다 구절 위아래 작은 파란 풀이, 오른쪽 "]" 괄호 뒤 요약. 한글에서 줄이 뒤섞이고
    괄호가 가운데 세로선 하나로 나왔다. 장마다 한 행인 세 칸 표 [구절·풀이 | 괄호(위·오른쪽·아래 변) | 요약], 장 사이 빈 행,
    괄호를 가로지르는 줄(풀이와 요약이 같은 높이)은 괄호에서 나누고, 풀이 글자는 원문 비율대로 작게, 원문 자간대로 좁게."""
    import zipfile

    from pdf2hwpx.extract import extract
    from pdf2hwpx.ir import build_document
    from pdf2hwpx.model import AuxBlock
    from tests.synth_pdf import build_poem

    pdf = tmp_path / "poem.pdf"
    build_poem(str(pdf))
    doc = build_document(extract(str(pdf)))
    t = next(p.table for it in doc.items if isinstance(it, AuxBlock) for p in it.paras if p.kind == "table")
    assert len(t.xs) == 4 and len(t.ys) - 1 == 5  # 장 3개 + 사이 빈 행 2개
    assert [c.row for c in t.cells if c.sides == ("top", "right", "bottom")] == [0, 2, 4]
    text = lambda c: " ".join(p.text for p in c.paras)  # noqa: E731
    left = [text(c) for c in t.cells if c.col == 0 and c.colspan == 1]
    right = [text(c) for c in t.cells if c.col == 2]
    assert all("▶" not in s for s in left) and [s[:4] for s in right] == ["▶ 초장", "▶ 중장", "▶ 종장"]
    assert "청풍 한 간 맡겨 두고" in left[1]
    first = t.cells[0].paras
    assert first[1].left_pt < 10 < first[0].left_pt  # 풀이는 원문 위치만큼 들여(구절보다 오른쪽)
    assert all(p.spacing < 0 for p in first)  # 원문이 좁게 찍힌 만큼 자간을 좁힌다

    res = convert(str(pdf), out_dir=str(tmp_path), overwrite=True)
    with zipfile.ZipFile(res["hwpx"]) as z:
        head = z.read("Contents/header.xml").decode("utf-8")
        sec = z.read("Contents/section0.xml").decode("utf-8")
    blue = [int(h) for h in re.findall(r'<hh:charPr id="\d+" height="(\d+)" textColor="#29458F"', head)]
    assert blue and max(blue) < 1000  # 파란 풀이는 본문(10pt)보다 작게
    assert re.search(r'<hh:spacing hangul="-\d+"', head)
    # 한글 기본 빈칸(글꼴 빈칸보다 넓음)이면 원문 위치에 맞춘 줄이 넘어가므로 글꼴 빈칸으로
    assert re.search(r'<hh:charPr id="\d+" height="\d+" textColor="#29458F"[^>]*useFontSpace="1"', head)
    assert all(len(c.paras) == 1 for c in t.cells if c.col == 2)  # 요약은 줄마다 끊지 않고 한 문단
    assert sec.count('<hp:cellMargin left="0" right="0"') >= 6  # 구절·괄호 칸은 좌우 여백 없이(줄이 넘어가지 않게)


def test_example_labels_tip_boxes_and_explanations(tmp_path):
    """실사용([풀이완성]): ① 발문 앞 '예제1/예제2' 꼬리표 그림을 글자 번호로(그림 종류가 나온 차례, 이름은 본문의 [예제1] 표기),
    ② 진한 테두리 안에 몇 pt 들여 칠한 Tip 상자가 상자 두 개(하나는 빈 띠)나 세 칸 표로 갈리지 않고 상자 하나(테두리 색은
    바깥 틀), ③ 줄 오른쪽 끝 "( ✕ )"는 그 선택지 끝에, 작은 파란 해설은 둘째 줄을 들여 써도 한 문단."""
    from pdf2hwpx.extract import extract
    from pdf2hwpx.ir import build_document
    from pdf2hwpx.model import AuxBlock, Box, Para, TableEl
    from tests.synth_pdf import build_examples

    pdf = tmp_path / "examples.pdf"
    build_examples(str(pdf))
    ex = extract(str(pdf))
    boxes = [it for it in ex.flow if isinstance(it, Box)]
    assert len(boxes) == 4 and not any(isinstance(it, TableEl) for it in ex.flow)
    assert all(b.fill and b.border_color and b.border_color != b.fill and b.all_items() for b in boxes)
    doc = build_document(ex)
    texts = [it.text for it in doc.items if isinstance(it, Para) and it.kind == "text"]
    labels = [t.split(" ")[0] for t in texts if t.startswith("예제")]
    assert labels == ["예제1", "예제2", "예제1", "예제2", "예제1"], labels
    assert sum(isinstance(it, AuxBlock) for it in doc.items) == 4
    assert sum(t.startswith("둘째 줄에서 끝나는 선택지.") and t.endswith("( X )") for t in texts) == 3
    expl = [t for t in texts if t.startswith("- 해설 첫 줄")]
    assert len(expl) == 3 and all(t.endswith("둘째 줄은 들여 써서 이어진다.") for t in expl)


@pytest.mark.parametrize("endnotes", [True, False])
def test_answer_explanations_have_no_hanging_indent(tmp_path, endnotes):
    """실사용 피드백: 해설(미주·문서 끝 정답)이 원문처럼 '[해설]' 다음 줄부터 오른쪽으로 들어가 읽기 불편하다.
    원문에 내어쓰기가 있어도 해설 문단은 들여쓰기 없이 왼쪽에서 그대로 잇는다."""
    import zipfile

    pdf = tmp_path / "hang.pdf"
    build(str(pdf), hanging_expl=True)
    from pdf2hwpx.extract import extract
    from pdf2hwpx.ir import build_document
    doc = build_document(extract(str(pdf)))
    expl = [p for a in doc.answers for p in a.paras if p.kind == "text" and p.text.startswith("[해설]")]
    assert expl and all(p.indent_pt < -5 for p in expl)  # 원문은 내어쓰기
    assert all("둘째 줄은 안쪽에서" in p.text for p in expl)  # 한 문단으로 이어짐
    res = convert(str(pdf), out_dir=str(tmp_path), overwrite=True, style=DocStyle(answers_as_endnotes=endnotes))
    assert res["validation"]["status"] == "PASS", res["validation"]["root_causes"]
    with zipfile.ZipFile(res["hwpx"]) as z:
        head = z.read("Contents/header.xml").decode("utf-8")
        sec = "".join(z.read(n).decode("utf-8") for n in z.namelist() if n.startswith("Contents/section"))
    intent = {m.group(1): int(m.group(2)) for m in re.finditer(
        r'<hh:paraPr id="(\d+)".*?<hc:intent value="(-?\d+)"', head, re.S)}
    ids = re.findall(r'paraPrIDRef="(\d+)"[^>]*>(?:(?!</hp:p>).)*?\[해설\]', sec, re.S)
    assert ids and all(intent[i] == 0 for i in ids), [(i, intent[i]) for i in ids]
    # 문단 보호 없음: 긴 해설이 통째로 다음 단으로 넘어가 앞에 큰 빈칸이 생기지 않게(실사용: 미주 1번·7번이 떨어져 보임)
    keep = {m.group(1): m.group(2) for m in re.finditer(r'<hh:paraPr id="(\d+)".*?keepLines="(\d)"', head, re.S)}
    assert all(keep[i] == "0" for i in ids), [(i, keep[i]) for i in ids]


def test_page_frame_is_not_a_box(tmp_path):
    """실사용(학원 자체 교재): 쪽마다 내용 전체를 두르는 테두리가 상자로 잡혀 다음 쪽 테두리와 이어 붙고, 단원 전체가
    상자 하나(도형이 많아 통째로 그림)가 됐다. 내용 영역 위·아래 끝까지 닿는 쪽 크기의 사각형과 머리 띠 안의 칸은
    상자가 아니다: 테두리 없는 원본과 같은 결과."""
    from pdf2hwpx.extract import extract

    plain, framed = tmp_path / "plain.pdf", tmp_path / "framed.pdf"
    build(str(plain))
    build(str(framed), page_frame=True)
    a, b = extract(str(plain)), extract(str(framed))
    assert b.stats["page_frames"] == b.stats["pages"]
    box = lambda ex: [(round(x.x0), round(x.y0), round(x.x1), round(x.y1), len(x.parts)) for x in ex.flow if type(x).__name__ == "Box"]
    assert box(a) == box(b)
    res = convert(str(framed), out_dir=str(tmp_path), overwrite=True)
    v = res["validation"]
    assert v["status"] == "PASS", (v["root_causes"], v["warnings"])
    assert v["checks"]["question_count"] == 5


def test_mismapped_space_symbols():
    """실사용: 제목 글꼴이 띄어쓰기 자리에 좁은 '$'·'%'·'#'·'&'를 찍거나(전략적$ 공약) 글자 정보 없는 글자
    (전략적�공약)로 읽혔다. 진짜 기호보다 훨씬 좁은 것만 공백으로."""
    from pdf2hwpx.extract import _mismapped_space

    assert _mismapped_space("$", 2.2, 9.8) and _mismapped_space("�", 2.1, 9.8) and _mismapped_space("&", 3.9, 12.0)
    assert not _mismapped_space("%", 7.5, 10.0)  # 30%
    assert not _mismapped_space("#", 5.5, 10.0) and not _mismapped_space(".", 2.0, 10.0)


def test_punctuation_fragment_inside_long_fragment():
    """실사용: 문장부호만 다른 조각으로 찍혀(긴 조각 안쪽에 겹친 ". ") 그 뒤 조각("? 이는")과의 거리를 바로 앞 조각 끝에서
    재 줄이 갈라지고 순서가 섞였다("…것일까 / ? 이는 ‘전략적 공약 이라 / ’"). 앞 조각들 중 가장 오른쪽 끝에서 잰다."""
    from pdf2hwpx.extract import _Frag, _build_line, _split_far_fragments
    from pdf2hwpx.model import Glyph

    def frag(text: str, x: float, adv: float = 9.8) -> _Frag:
        gs = [Glyph(c, x + k * adv, 170.7, x + (k + 1) * adv, 182.4, 9.8) for k, c in enumerate(text)]
        return _Frag(gs, gs[0].x0, 170.7, gs[-1].x1, 182.4, 9.8)

    long = frag("는 경우가 많다", 225.5)
    long.glyphs += [Glyph(c, 320 + k * 9.8, 170.7, 320 + (k + 1) * 9.8, 182.4, 9.8) for k, c in enumerate("왜 이런 것일까")]
    long.x1 = long.glyphs[-1].x1
    dot = frag(".", long.glyphs[7].x1, 4.7)
    q = frag("?", long.x1, 6.6)
    rest = frag("이는", q.x1 + 3)
    groups = _split_far_fragments([long, dot, q, rest])
    assert len(groups) == 1
    assert _build_line(1, 0, groups[0]).text == "는 경우가 많다. 왜 이런 것일까? 이는"


def test_linked_box_chart_and_outline_text_rows(tmp_path, monkeypatch):
    """실사용(학원 자체 교재): ① 지문 구조도(상자를 화살표로 이음)는 쪽 테두리에 묻혀 쪽째 그림이 됐는데, 테두리를 빼면 상자가
    흩어지고 나란한 상자 속 글이 한 줄로 섞인다 → 선으로 이어진 상자 묶음은 테두리 없는 상자 하나(도형으로 세어 그림).
    ② 발문을 글꼴 없이 윤곽선으로 그려 글자가 없어 통째로 빠졌다 → 윤곽선 글자 줄은 그 영역을 그림으로 넣고,
    사이에 낀 진짜 글자("㉠∼㉤")는 그림에 포함(글로 또 넣지 않음), 바로 아래 두 글자 줄도 이어진 줄로."""
    from pdf2hwpx.extract import OUTLINE_TEXT, extract
    from pdf2hwpx.ir import build_document
    from pdf2hwpx.model import AuxBlock
    from pdf2hwpx import ocr
    from tests.synth_pdf import build_flow_outline

    monkeypatch.setattr(ocr, "_langs", lambda: frozenset())  # OCR이 없는 환경(그림으로 남는 경우)
    pdf = tmp_path / "flow.pdf"
    info = build_flow_outline(str(pdf))
    ex = extract(str(pdf))
    pm = ex.pages[0]
    assert ex.stats["linked_box_charts"] == 1
    chart = [b for b in pm.boxes if not b.border]
    assert len(chart) == 1 and len(pm.boxes) == 1
    c = chart[0]
    assert all(c.x0 <= r.x0 and r.x1 <= c.x1 and c.y0 <= r.y0 and r.y1 <= c.y1 for r in info["boxes"])
    outl = [im for im in pm.images if im.digest == OUTLINE_TEXT]
    assert len(outl) == 2
    sx0, sy0, sx1, _ = info["stem"]
    assert outl[0].x0 <= sx0 and outl[0].x1 >= sx1 - 2
    assert not any("㉠" in ln.text for ln in pm.lines)
    doc = build_document(ex)
    aux = [it for it in doc.items if isinstance(it, AuxBlock)]
    assert len(aux) == 1 and aux[0].diagram is not None and not aux[0].border
    res = convert(str(pdf), out_dir=str(tmp_path), overwrite=True)
    v = res["validation"]
    assert not v["root_causes"], v["root_causes"]


def test_memo_column_pages_follow_source_pages(tmp_path):
    """실사용(학원 자체 교재의 지문 분석 쪽): 쪽 테두리 안을 점선으로 나눠 한쪽은 빈 메모 칸, 다른 쪽에 글.
    점선은 짧은 획 수백 개라 선으로 잡히지 않아 메모 칸이 사라졌다 → 점선을 하나의 선으로 이어 쪽 크기 두 칸 표(메모 칸 | 글)로,
    표 높이는 쪽 본문 높이, 글은 칸 위에서부터. 쪽 테두리가 있는 교재는 원문 쪽마다 새 쪽(PDF 한 쪽 = 한글 한 쪽),
    글 없는 메모 쪽은 다른 빈 쪽처럼 넣지 않는다."""
    import zipfile

    from pdf2hwpx.extract import extract
    from pdf2hwpx.model import TableEl
    from tests.synth_pdf import build_memo_pages

    pdf = tmp_path / "memo.pdf"
    info = build_memo_pages(str(pdf))
    ex = extract(str(pdf))
    assert ex.faithful
    memo = [t for t in ex.flow if isinstance(t, TableEl)]
    assert [t.page for t in memo] == [1, 3] and all(t.memo for t in memo)
    assert [round(t.xs[1]) for t in memo] == [206, 392]
    filled = [[bool(cl.items) for cl in t.cells] for t in memo]
    assert filled == [[False, True], [True, False]]
    assert all(cl.valign == "TOP" for t in memo for cl in t.cells)
    res = convert(str(pdf), out_dir=str(tmp_path), overwrite=True)
    with zipfile.ZipFile(res["hwpx"]) as z:
        sec = z.read("Contents/section0.xml").decode("utf-8")
    assert len(re.findall(r'<hp:tbl ', sec)) == 2
    assert len(re.findall(r'<hp:p [^>]*pageBreak="1"', sec)) == 1  # 글 있는 두 쪽 사이에만
    text = "".join(re.findall(r"<hp:t>([^<]*)</hp:t>", sec))
    assert all(t in text for t in info["texts"])


def test_ocr_fix_chars():
    """OCR 글자 교정: 맨 앞 '윗글'(받침이 작아 '워글'로), 번호 뒤 군더더기 점, 따옴표는 여닫음을 번갈아 홑따옴표로,
    '<보기>'의 '<'를 따옴표로 읽은 것, 닫는 따옴표를 ':'로 읽은 것."""
    from pdf2hwpx.ocr import OcrChar, fix_chars

    def chars(text: str) -> list:
        return [OcrChar(c, 10.0 * k, 0.0, 10.0 * k + 9.0, 10.0, 90.0) for k, c in enumerate(text)]

    fix = lambda t: "".join(ch.c for ch in fix_chars(chars(t)))
    assert fix("1.워글에서") == "1.윗글에서"
    assert fix("3.。윗글을") == "3.윗글을"
    assert fix("“음악해석'에") == "‘음악해석’에"
    assert fix("'보기>를") == "<보기>를"
    assert fix("(나)의'아리스토텔레스:의") == "(나)의‘아리스토텔레스’의"


def test_ocr_reads_korean_stem(tmp_path):
    """Tesseract(한국어 모델)가 있으면: 글꼴 없이 그림으로 된 발문 줄을 글자로 읽는다(없는 환경에서는 건너뜀)."""
    import pymupdf as fitz

    from pdf2hwpx import ocr

    if not ocr.available():
        pytest.skip("Tesseract 한국어 모델 없음")
    src = fitz.open()
    sp = src.new_page(width=400, height=40)
    sp.insert_text((10, 26), "1. 윗글에서 언급한 내용이 아닌 것은?", fontname="korea", fontsize=16)
    png = sp.get_pixmap(dpi=300, alpha=False).tobytes("png")
    doc = fitz.open()
    page = doc.new_page(width=400, height=40)
    page.insert_image(page.rect, stream=png)
    rows = ocr.read_rows(page, [(0, 0, 400, 40)], [[]])
    text = "".join(ch.c for ch in ocr.fix_chars(rows[0]))
    assert "윗글에서언급한내용이아닌것은?" in text, text



def test_semibold_body_font_is_not_bold():
    """SemiBold·DemiBold(글꼴 굵게 표시가 켜져 있어도)는 본문 굵기: 교재 본문 전체가 굵게 되면 글자가 넓어져 쪽이 넘친다."""
    from pdf2hwpx.extract import _is_bold

    assert not _is_bold("AAAAAI+Eulyoo1945-SemiBold", 20, 16)
    assert not _is_bold("NotoSans-DemiBold", 20)
    assert _is_bold("HCRDotum-Bold", 20, 16)
    assert _is_bold("NanumSquareEB", 4)


def test_blank_image_mask_is_not_an_icon(tmp_path):
    """아무것도 칠하지 않는 그림(투명도가 모두 0인 이미지 마스크, 흰 그림)은 원문자 아이콘(○)으로 만들지 않는다."""
    import pymupdf as fitz

    from pdf2hwpx.extract import _blank_image

    doc = fitz.open()
    page = doc.new_page(width=100, height=100)
    white = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 8, 8), False)
    white.set_rect(white.irect, (255, 255, 255))
    dark = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 8, 8), False)
    dark.set_rect(dark.irect, (0, 0, 0))
    clear = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 8, 8), True)
    clear.set_rect(clear.irect, (0, 0, 0, 0))
    xw = page.insert_image(fitz.Rect(10, 10, 20, 20), pixmap=white)
    xd = page.insert_image(fitz.Rect(30, 10, 40, 20), pixmap=dark)
    xc = page.insert_image(fitz.Rect(50, 10, 60, 20), pixmap=clear)
    assert _blank_image(doc, xw) and _blank_image(doc, xc)
    assert not _blank_image(doc, xd)


def test_linked_chart_absorbs_overlapping_boxes():
    """잇는 선이 우연히 닫힌 네모를 이루면 그 네모가 상자로 잡힌다: 거기에 걸친 상자(2·3문단)도 구조도 묶음에 넣어
    그림이 잘리지 않게 한다."""
    from pdf2hwpx.extract import _Seg, _linked_boxes

    one, two, three, four = (69, 459, 201, 539), (244, 382, 376, 461), (244, 542, 376, 622), (422, 459, 554, 539)
    loop = (222, 422, 399, 582)  # 1문단 오른쪽에서 갈라져 2·3문단으로 가는 선과 4문단으로 모이는 선이 이룬 네모
    segs = [_Seg(201, 499, 222, 499, 0.5, None), _Seg(399, 499, 417, 499, 0.5, None)]
    out = _linked_boxes([one, two, three, four, loop], segs, None)
    assert len(out) == 1
    x0, y0, x1, y1 = out[0]
    assert y0 <= 382 and y1 >= 622 and x0 <= 69 and x1 >= 554


def test_ocr_align_wide_first_char_box():
    """OCR이 단어 첫 글자에 단어 전체 상자를 붙여도('설' 438.8~474) 원문 글자 도형과 짝지어 '설 명'처럼 띄지 않는다."""
    import pymupdf as fitz

    from pdf2hwpx.extract import _align
    from pdf2hwpx.ocr import OcrChar

    chars = [OcrChar("설", 438.8, 0, 474.1, 9, 93), OcrChar("명", 447.8, 0, 456.6, 9, 91)]
    shapes = [fitz.Rect(438.8, 0, 447.0, 9), fitz.Rect(448.3, 0, 455.9, 9)]
    pairs = _align(chars, shapes, 9.94)
    assert [(c.c, q.x0) for c, q in pairs] == [("설", 438.8), ("명", 448.3)]


def test_source_gaps_column_break_and_cap():
    """원문 쪽을 따르는 교재: 두 단 쪽에서 한참 위로 돌아가는 문단은 오른쪽 단의 첫 문단(단 나눔), 문제 사이 큰 빈칸은
    3줄까지만(한글에서 지문이 길어지면 단이 넘친다). 전폭 쪽(표지)은 원문 간격 그대로."""
    from pdf2hwpx.ir import _source_gaps
    from pdf2hwpx.model import Para

    a = Para(src=(1, 100, 290, 1))
    b = Para(src=(1, 370, 390, 1))  # 80pt 아래: 8줄 -> 3줄
    c = Para(src=(1, 105, 150, 1))  # 오른쪽 단 맨 위
    w1, w2 = Para(src=(2, 100, 200, 2), wide=True), Para(src=(2, 300, 320, 2), wide=True)
    _source_gaps([a, b, c, w1, w2], 10.0)
    assert b.gap == 3.0 and not b.col_break
    assert c.col_break and c.gap == 0.0
    assert w2.gap == 10.0


def test_chart_labels_join_the_picture():
    """그래프 그림 위에 글자로 찍은 라벨(A, 눈금, 세로 축 이름)은 그림과 한 덩어리로, 그림 옆 본문 줄과 그림 위에
    글자가 없는 그림(선택지 그림)은 그대로."""
    from collections import Counter

    from pdf2hwpx.extract import _absorb_chart_labels, _Frag
    from pdf2hwpx.model import Glyph, ImageEl

    def frag(text, x0, y0, size=9.0):
        gs = [Glyph(c, x0 + k * size, y0, x0 + (k + 1) * size, y0 + size, size) for k, c in enumerate(text)]
        return _Frag(gs, x0, y0, gs[-1].x1, y0 + size, size)

    chart = ImageEl(1, 1, 367, 178, 526, 320, "g", 1)
    plain = ImageEl(1, 0, 60, 400, 200, 500, "p", 2)
    a, hundred, axis = frag("A", 408, 214), frag("100", 340, 187), frag("원", 353, 209)
    ticks, unit = frag("12345", 400, 309), frag("시간(억년)", 420, 322)
    body = frag("암석", 324, 339) , frag("가 생성될 때 방사성 동위원소를 함유하고", 352, 339)
    choice = frag("①", 45, 440)
    kept = [a, hundred, axis, ticks, unit, *body, choice]
    left = _absorb_chart_labels([chart, plain], kept, Counter())
    assert left == [*body, choice]
    assert (chart.x0, chart.y0, chart.x1, chart.y1) == (340, 178, 526, 331)
    assert (plain.x0, plain.y1) == (60, 500)


def test_negative_words_underlined_like_other_stems():
    """어느 발문이라도 부정어에 밑줄을 그은 문서는 밑줄이 빠진 발문의 부정어(않은·아닌·먼)에도 긋고, OCR이 붙인
    "하지않은"·띄운 "않 은"은 바로잡는다. 그런 관례가 없는 문서는 그대로."""
    from pdf2hwpx.ir import _underline_negatives
    from pdf2hwpx.model import Para, Run

    def ul(p):
        return "".join(f"[{r.text}]" if r.underline else r.text for r in p.runs)

    marked = Para(runs=[Run("2. 적절하지 "), Run("않은", underline=True), Run(" 것은?")])
    plain = Para(runs=[Run("1. 윗글에서 언급한 내용이 아닌 것은?")])
    glued = Para(runs=[Run("3. 적절하지않은 것은?")])
    split = Para(runs=[Run("4. 적절하지 "), Run("않", underline=True), Run(" 은 것은?")])
    far = Para(runs=[Run("5. 의미가 가장 먼 것은?")])
    _underline_negatives([marked, plain, glued, split, far])
    assert ul(plain) == "1. 윗글에서 언급한 내용이 [아닌] 것은?"
    assert ul(glued) == "3. 적절하지 [않은] 것은?"
    assert ul(split) == "4. 적절하지 [않은] 것은?"
    assert ul(far) == "5. 의미가 가장 [먼] 것은?"

    alone = Para(runs=[Run("1. 적절하지 않은 것은?")])
    _underline_negatives([alone])
    assert ul(alone) == "1. 적절하지 않은 것은?"


def test_stroke_on_every_char_is_not_bold():
    """칠하고 테두리까지 그린 글자(가짜 굵게)라도 한 글꼴의 거의 모든 글자가 그렇다면 그 글꼴의 보통 모양이다."""
    from pdf2hwpx.extract import _plain_strokes
    from pdf2hwpx.model import Glyph

    every = [Glyph("가", 0, 0, 10, 10, 10, True) for _ in range(300)]
    some = [Glyph("주", 0, 0, 10, 10, 10, True) for _ in range(50)]
    _plain_strokes({"Batang": [302, 300, every], "Eulyoo1945-Regular": [1200, 50, some]})
    assert not any(g.bold for g in every)
    assert all(g.bold for g in some)


def test_linked_chart_diagonal_lines():
    """실사용(교재 '플라톤' 지문 구조): 상자를 비스듬한 선으로 이은 구조도((가) 1문단 아래 변 -> 2문단 위 변 -> 3문단 아래 변)가
    가로·세로 선만 보던 탓에 묶이지 않아, 상자 넷이 글 상자로 흩어지고 선이 사라졌다 → 양 끝이 서로 다른 상자 변에 닿는
    비스듬한 선도 잇는 선. 한쪽 끝만 상자에 닿은 비스듬한 선(그래프 선 등)은 아니다."""
    from pdf2hwpx.extract import _Seg, _linked_boxes

    one, two, three, four = (46, 399, 178, 478), (142, 502, 273, 582), (273, 399, 405, 478), (403, 502, 535, 582)
    segs = [_Seg(112, 477, 202, 502, 0.36, None), _Seg(208, 478, 333, 503, 0.36, None),
            _Seg(339, 477, 464, 502, 0.36, None)]
    out = _linked_boxes([one, two, three, four], segs, None)
    assert len(out) == 1
    x0, y0, x1, y1 = out[0]
    assert x0 <= 46 and y0 <= 399 and x1 >= 535 and y1 >= 582
    assert _linked_boxes([one, two], [_Seg(100, 477, 112, 520, 0.36, None)], None) == []


def test_ocr_rereads_row_alone_when_glyphs_missed(monkeypatch):
    """실사용: 발문 줄 여러 개를 한 장에 이어 읽으면 큰 번호 "1." 때문에 한 줄을 여러 글줄로 쪼개 읽어 앞부분을 잃었다
    ("1. 윗글에서 언급된 …" -> "급된 내용이 아닌 것것은?") → 원문 글자 도형을 여럿 덮지 못한 줄은 그 줄만 한 글줄로 다시 읽는다."""
    from collections import Counter

    import pymupdf as fitz

    from pdf2hwpx import ocr
    from pdf2hwpx.extract import _ocr_rows
    from tests.synth_pdf import _outline_glyph

    doc = fitz.open()
    page = doc.new_page(width=300, height=60)
    text = "윗글에서언급된것"
    xs = [20 + 12 * k for k in range(len(text))]
    for x in xs:
        _outline_glyph(page, x, 20, 10, 10)

    def chars(part):
        return [ocr.OcrChar(c, xs[k], 20, xs[k] + 10, 30, 95.0, 0) for k, c in enumerate(text) if k in part]
    calls = []

    def read_rows(page, rects, masks, allow="", line=False):
        calls.append(line)
        if allow:
            return [[] for _ in rects]
        return [chars(range(len(text)) if line else range(5, len(text)))]
    monkeypatch.setattr(ocr, "read_rows", read_rows)
    stats = Counter()
    frag = _ocr_rows(page, [(15, 15, 120, 35)], [], stats)[0]
    assert stats["ocr_line_retry"] == 1 and True in calls
    assert "".join(g.c for g in frag.glyphs if not g.is_space) == text


def test_heading_above_wide_chart_leaves_columns(tmp_path):
    """실사용(교재 '플라톤' 정리 쪽): 짧은 두 단(핵심 정리) 아래 왼쪽에 '지문 구조' 칸, 그 바로 아래 쪽 너비 구조도.
    소제목 칸을 두 단의 왼쪽 단 끝에 두니 한글이 단 높이를 맞추며 오른쪽 단 맨 위로 옮겼다 → 다른 단 내용보다 아래에서
    가로지르는 상자에 붙은 한쪽 단 항목은 아래 전폭 구간으로."""
    import pymupdf as fitz

    from pdf2hwpx.extract import extract
    from tests.synth_pdf import Writer

    w = Writer()
    w.doc.delete_page(-1)
    w.new_page(divider=False)
    page = w.page
    page.draw_line(fitz.Point(297.6, 140), fitz.Point(297.6, 240), width=0.3)  # 정리 부분에만 짧은 구분선
    for k in range(4):
        w.text(70, 150 + 25 * k, f"왼쪽 단 정리 내용 {k + 1}번째 줄입니다 가나다라마")
        w.text(320, 150 + 25 * k, f"오른쪽 단 정리 내용 {k + 1}번째 줄입니다 가나다")
    page.draw_rect(fitz.Rect(69, 300, 146, 322), color=(0, 0, 0), width=0.8)
    w.text(80, 316, "지문 구조", 11)
    a, b = fitz.Rect(70, 340, 230, 400), fitz.Rect(370, 340, 530, 400)
    for r in (a, b):
        page.draw_rect(r, color=(0, 0, 0), width=0.9)
        w.text(r.x0 + 40, r.y0 + 30, "문단 요약", 10)
    page.draw_line(fitz.Point(230, 370), fitz.Point(370, 370), width=0.4)
    pdf = tmp_path / "wide_head.pdf"
    w.doc.save(str(pdf))
    ex = extract(str(pdf))
    head = next(it for it in ex.flow if it.page == 1 and abs(it.y0 - 300) < 3)
    assert id(head) in ex.wide_ids
    right = [it for it in ex.flow if getattr(it, "col", None) == 1 and it.y0 < 260]
    assert right and ex.flow.index(head) > max(ex.flow.index(it) for it in right)


def test_ocr_big_question_number_kept_with_stem():
    """실사용(교재 발문): 윤곽선으로 그린 큰 문제 번호가 문제로 잡히지 않았다 → 번호를 발문 줄에 넣는다.
    ① "4.  <보기>는 …": 번호 뒤를 넓게 띄어 번호만 따로 떨어진 줄이 됐다(글자 하나 줄은 버림)
    ② "4. <보기>의 …"처럼 번호만 윤곽선이고 발문은 진짜 글자: 번호가 통째로 빠졌다
    ③ "3.  ⓐ~ⓒ에 …": 번호와 진짜 글자 ⓐ 사이가 넓어 번호 줄과 발문 줄이 합쳐지지 않았다"""
    import pymupdf as fitz

    from pdf2hwpx.extract import _Frag, _merge_outline_rows, _outline_rows
    from pdf2hwpx.model import Glyph
    from tests.synth_pdf import _outline_glyph

    doc = fitz.open()
    page = doc.new_page(width=600, height=200)
    _outline_glyph(page, 312.6, 20, 7, 11)  # ① 큰 번호, 19pt 띄고 발문
    for k in range(6):
        _outline_glyph(page, 338.6 + 9 * k, 22, 8, 9)
    rows = _outline_rows(page.get_drawings())
    assert [round(r[0], 1) for r in rows] == [312.6] and rows[0][4] == 7

    def frag(cs, x, y, w=9.6):
        gs = [Glyph(c, x + w * k, y, x + w * (k + 1), y + 10, 10.0, False) for k, c in enumerate(cs)]
        return _Frag(gs, gs[0].x0, y, gs[-1].x1, y + 10, 10.0)
    left = frag("왼쪽단글", 240, 110)  # 왼쪽 단 글(번호 왼쪽으로 1.5배 넘게 떨어짐)
    out = _merge_outline_rows([[312.6, 109.6, 319.7, 120.4, 1]], [left, frag("보기의문장", 336, 110)])
    assert len(out) == 1 and out[0][0] < 312.6  # ② 번호만 윤곽선
    assert _merge_outline_rows([[312.6, 109.6, 319.7, 120.4, 1]], [left]) == []  # 뒤에 글이 없는 외톨이 도형은 아니다
    reals = [frag("ⓐ", 338.9, 488), frag("ⓒ", 352.1, 488)]  # ③
    out = _merge_outline_rows([[312.6, 485.3, 319.6, 496.6, 1], [361.6, 488.3, 521.7, 497.2, 16]], reals)
    assert len(out) == 1 and out[0][0] < 312.6 and out[0][2] > 521


def test_ocr_tilde_between_real_glyphs(monkeypatch):
    """실사용: "ⓐ~ⓔ의", "㉠~㉤의"의 '~'가 글자 도형보다 작게 칠한 도형이라 읽히지 않아 "ⓐ ⓔ의"가 됐다 →
    OCR 줄 안 진짜 글자 둘 사이 가운데 높이의 작은 가로 도형은 '~'."""
    from collections import Counter

    import pymupdf as fitz

    from pdf2hwpx import ocr
    from pdf2hwpx.extract import _Frag, _ocr_rows
    from pdf2hwpx.model import Glyph
    from tests.synth_pdf import _outline_glyph

    doc = fitz.open()
    page = doc.new_page(width=300, height=60)
    xs = [95 + 9 * k for k in range(4)]
    for x in xs:
        _outline_glyph(page, x, 21, 8, 9)
    page.draw_rect(fitz.Rect(75.7, 23.7, 80.2, 25.7), color=None, fill=(0, 0, 0))
    a = Glyph("ⓐ", 65, 22.4, 74.6, 32.3, 10.0, True)
    e = Glyph("ⓔ", 82.4, 22.4, 92.0, 32.3, 10.0, True)
    kept = [_Frag([a], a.x0, a.y0, a.x1, a.y1, 10.0), _Frag([e], e.x0, e.y0, e.x1, e.y1, 10.0)]

    def read_rows(page, rects, masks, allow="", line=False):
        if allow:
            return [[] for _ in rects]
        return [[ocr.OcrChar(c, x, 21, x + 8, 30, 95.0, 0) for c, x in zip("의사전적", xs)]]
    monkeypatch.setattr(ocr, "read_rows", read_rows)
    stats = Counter()
    frag = _ocr_rows(page, [(60, 18, 135, 35)], kept, stats)[0]
    assert stats["ocr_tilde"] == 1
    assert "".join(g.c for g in frag.glyphs if not g.is_space) == "~의사전적"
    t = next(g for g in frag.glyphs if g.c == "~")
    assert a.x1 <= t.x0 and t.x1 <= e.x0


def test_ocr_fix_gajang():
    """발문의 '가장 적절한'을 OCR이 '기장'으로 읽는 것을 고친다(다른 '기장'은 그대로)."""
    from pdf2hwpx import ocr

    def chars(s):
        return [ocr.OcrChar(c, k, 0, k + 1, 1, 90.0, 0) for k, c in enumerate(s)]
    assert "".join(c.c for c in ocr.fix_chars(chars("1.윗글에대한설명으로기장적절한것은?"))).endswith("가장적절한것은?")
    assert "".join(c.c for c in ocr.fix_chars(chars("기장이말했다"))) == "기장이말했다"


def test_hancom_equation_font_chars():
    """실사용(교재 '크기의 과학'): 한글 수식 글꼴(HancomEQN)은 글자를 사용자 영역에 매겨 "L², 1/12³"이 한글에서 "'"처럼
    깨졌다 → 영문 대문자·숫자·'/'로 바꾸고, 작게 올려 쓴 숫자는 위첨자로."""
    from pdf2hwpx.extract import HANCOM_EQN, SUPERSCRIPT

    assert "".join(HANCOM_EQN[c] for c in "") == "L1/123"
    assert "23".translate(SUPERSCRIPT) == "²³"


def test_ocr_short_row_takes_page_stem_size(monkeypatch):
    """실사용: 발문 둘째 줄 "은?"처럼 도형이 두셋뿐인 짧은 줄은 OCR 상자로 크기를 재 6pt가 됐다 → 쪽의 발문 크기로.
    받침을 놓친 "으?"는 "은?"으로."""
    from collections import Counter

    import pymupdf as fitz

    from pdf2hwpx import ocr
    from pdf2hwpx.extract import _ocr_rows
    from tests.synth_pdf import _outline_glyph

    doc = fitz.open()
    page = doc.new_page(width=300, height=100)
    long_xs = [20 + 10 * k for k in range(8)]
    for x in long_xs:
        _outline_glyph(page, x, 20, 8.8, 8.8)
    for x in (20, 30):
        _outline_glyph(page, x, 50, 8.8, 8.8)

    def read_rows(page, rects, masks, allow="", line=False):
        if allow:
            return [[] for _ in rects]
        return [[ocr.OcrChar(c, x, 20, x + 8.8, 28.8, 95.0, 0) for c, x in zip("윗글에서알수있는", long_xs)],
                [ocr.OcrChar("으", 20, 51, 28, 56, 95.0, 0), ocr.OcrChar("?", 30, 51, 34, 56, 95.0, 0)]]
    monkeypatch.setattr(ocr, "read_rows", read_rows)
    a, b = _ocr_rows(page, [(15, 17, 105, 32), (15, 47, 45, 62)], [], Counter())
    assert abs(b.size - a.size) < 0.01 and a.size > 9
    assert "".join(g.c for g in b.glyphs if not g.is_space) == "은?"


def test_big_number_tight_pitch_lines_do_not_overlap(tmp_path):
    """실사용: 큰 문제 번호(15pt)가 든 발문을 원문 줄 간격(13pt)으로 재면 번호 기준 95%가 되어 한글에서 둘째 줄이 첫 줄에
    겹쳤다 → 번호보다 좁은 간격은 본문 크기 기준(130%)."""
    from pdf2hwpx.extract import extract
    from pdf2hwpx.ir import build_document
    from pdf2hwpx.model import Para
    from tests.synth_pdf import Writer

    w = Writer()
    page = w.page
    page.insert_text((60, 120), "4.", fontname="korea", fontsize=15)
    w.text(78, 120, "<보기>의 문장들을 표준 형식의 명제로 고친 것으로", 10)
    w.text(78, 128, "적절하지 않은 것은?", 10)
    for k in range(5):
        w.text(78, 155 + 16 * k, f"{'①②③④⑤'[k]} 선택지 내용 {k + 1}", 10)
    pdf = tmp_path / "tight.pdf"
    w.doc.save(str(pdf))
    doc = build_document(extract(str(pdf)))
    stems = [q.stem for q in doc.questions] + [it for it in doc.items if isinstance(it, Para) and it.text.startswith("4.")]
    assert stems and all(p.line_pct >= 120 for p in stems), [p.line_pct for p in stems]
